"""
Main application entry point for the elderly care monitoring system.
"""

import logging
import queue
import signal
import sqlite3
import sys
import threading
import time
import json
from enum import Enum
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Callable

sys.path.insert(0, str(Path(__file__).parent))

from utils import load_config as _load_config
from utils import setup_logging as _setup_logging
from utils import setup_data_directories
from modules.vision import CameraHandler, MotionDetector, ActivityTracker
from modules.voice import VoiceAssistant
from modules.database import Database
from modules.alerts import AlertManager
from modules.scheduler import ReminderScheduler


logger = logging.getLogger(__name__)


class SystemState(Enum):
    INIT = "INIT"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    SHUTDOWN = "SHUTDOWN"


def load_config(config_path: str = "config.json") -> Dict[str, Any]:
    """Read and return application configuration from JSON file."""
    return _load_config(config_path)


def setup_logging(config: Dict[str, Any]) -> logging.Logger:
    """Configure logging to console and file using config.logging settings."""
    log_cfg = config.get("logging", {})
    system_cfg = config.get("system", {})
    return _setup_logging(
        log_file=log_cfg.get("file", "logs/system.log"),
        log_level=log_cfg.get("level", system_cfg.get("log_level", "INFO")),
    )


class ElderlyCareSystem:
    """Main orchestrator class for vision, voice, alerts, DB, and reminders."""

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize all modules from loaded configuration."""
        self.config = config
        setup_data_directories()

        self.shutdown_event = threading.Event()
        self.event_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()

        self.vision_thread: Optional[threading.Thread] = None
        self.voice_thread: Optional[threading.Thread] = None
        self.event_thread: Optional[threading.Thread] = None

        self._db_lock = threading.Lock()
        self._running = False
        self._state_lock = threading.RLock()
        self._state = SystemState.INIT
        self._state_file = Path("data/system_state.json")
        self._email_retry_lock = threading.Lock()
        self._email_retry_queue: list[Dict[str, Any]] = []
        self._email_retry_interval_seconds = 300
        self._next_email_retry_ts = 0.0
        self._db_available = True
        self._db_fallback_file = Path("logs/database_fallback.log")
        self._camera_available = True
        self._voice_available = True
        self._offline_stt_mode = False
        self._stt_none_count = 0
        self._stt_none_threshold = 5

        db_cfg = self.config.get("database", {})
        self.database = Database(db_path=db_cfg.get("path", "data/elderly_care.db"))
        try:
            if not self.database.connect():
                self._db_available = False
                self._log_database_fallback("Initial database connection failed; running with file fallback.")
        except sqlite3.Error as e:
            self._db_available = False
            logger.error("Database sqlite error during init: %s", e)
            self._log_database_fallback(f"Database init sqlite error: {e}")
        except Exception as e:
            self._db_available = False
            logger.error("Database error during init: %s", e)
            self._log_database_fallback(f"Database init error: {e}")

        vision_cfg = self.config.get("vision", {})
        resolution = vision_cfg.get("resolution", {})
        width = int(vision_cfg.get("width", resolution.get("width", 640)))
        height = int(vision_cfg.get("height", resolution.get("height", 480)))
        self.camera = CameraHandler(
            camera_id=vision_cfg.get("camera_id", 0),
            width=width,
            height=height,
        )
        self.motion_detector = MotionDetector(
            threshold=vision_cfg.get("motion_threshold", vision_cfg.get("threshold", 25)),
            min_area=vision_cfg.get("min_contour_area", vision_cfg.get("min_area", 500)),
        )
        self.activity_tracker = ActivityTracker(
            inactivity_threshold=vision_cfg.get("inactivity_threshold_seconds", 3600)
        )

        voice_cfg = self.config.get("voice", {})
        self.voice_assistant: Optional[VoiceAssistant] = None
        self._offline_stt_mode = str(voice_cfg.get("stt_engine", "google")).lower() != "google"
        try:
            self.voice_assistant = VoiceAssistant(
                language=voice_cfg.get("language", "or"),
                sample_rate=voice_cfg.get("sample_rate", 16000),
                chunk_duration=voice_cfg.get("chunk_duration", 1024),
                timeout_seconds=voice_cfg.get("timeout_seconds", 10),
            )
        except OSError as e:
            self._voice_available = False
            logger.error("Microphone initialization failed (vision-only mode): %s", e)
        except RuntimeError as e:
            self._voice_available = False
            logger.error("Voice runtime initialization failed (vision-only mode): %s", e)
        except Exception as e:
            self._voice_available = False
            logger.error("Voice initialization failed (vision-only mode): %s", e)

        alerts_cfg = self.config.get("alerts", {})
        self.alert_manager = AlertManager(
            caregiver_email=alerts_cfg.get("caregiver_email", "caregiver@example.com"),
            smtp_user=alerts_cfg.get("smtp_username") or alerts_cfg.get("smtp_user", ""),
            smtp_pass=alerts_cfg.get("smtp_password", ""),
            smtp_server=alerts_cfg.get("smtp_server", "smtp.gmail.com"),
            smtp_port=int(alerts_cfg.get("smtp_port", 587)),
            database=self.database,
        )

        self.reminder_scheduler = ReminderScheduler(
            tts_engine=self.voice_assistant,
            database=self.database,
        )

        self.intent_actions: Dict[str, Callable[[str], Optional[str]]] = {
            "emergency": self._intent_emergency,
            "medicine_query": self._intent_medicine_query,
            "status": self._intent_status,
            "stop": self._intent_stop,
            "greeting": self._intent_greeting,
        }

        # Callback registration pattern requested by user.
        self.activity_tracker.on_inactive = self._handle_inactive
        self.activity_tracker.register_callback(self._on_activity_state_change)

        # Route reminder trigger handling through main callback system.
        self.reminder_scheduler._trigger_reminder = self._on_reminder_trigger  # type: ignore[attr-defined]
        self._register_configured_reminders()
        self._persist_state()

    def _set_state(self, new_state: SystemState) -> None:
        """Set system state in a thread-safe way and persist it."""
        with self._state_lock:
            if self._state == new_state:
                return
            logger.info("System state transition: %s -> %s", self._state.value, new_state.value)
            self._state = new_state
            self._persist_state()

    def get_state(self) -> SystemState:
        """Return current system state."""
        with self._state_lock:
            return self._state

    def _persist_state(self) -> None:
        """Persist runtime state so dashboard can display it."""
        try:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "state": self._state.value,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            with open(self._state_file, "w", encoding="utf-8") as state_fp:
                json.dump(payload, state_fp)
        except Exception as e:
            logger.warning("Could not persist system state: %s", e)

    def _register_configured_reminders(self) -> None:
        """Register reminders from config; defaults already exist in scheduler."""
        reminders_cfg = self.config.get("reminders", {})
        for reminder_type, reminder_cfg in reminders_cfg.items():
            if isinstance(reminder_cfg, dict):
                time_str = str(reminder_cfg.get("time", "")).strip()
                message = str(
                    reminder_cfg.get(
                        "message",
                        f"Reminder: {reminder_type.replace('_', ' ')}",
                    )
                )
            else:
                time_str = str(reminder_cfg).strip()
                message = f"Reminder: {reminder_type.replace('_', ' ')}"

            if not time_str:
                logger.warning("Skipping reminder '%s': missing time", reminder_type)
                continue

            if not self.reminder_scheduler.add_reminder(
                time_str=time_str,
                message=message,
                reminder_type=reminder_type,
                repeat="daily",
            ):
                logger.warning("Failed to register reminder '%s' at '%s'", reminder_type, time_str)

    def _speak_safe(self, text: str) -> None:
        """Speak message without crashing when voice is unavailable."""
        if not self.voice_assistant:
            return
        try:
            self.voice_assistant.speak(text)
        except (OSError, RuntimeError) as e:
            logger.error("TTS error: %s", e)
        except Exception as e:
            logger.error("Unexpected TTS error: %s", e)

    def _log_database_fallback(self, message: str) -> None:
        """Append database fallback messages to file when DB is unavailable."""
        try:
            self._db_fallback_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._db_fallback_file, "a", encoding="utf-8") as fallback_file:
                fallback_file.write(f"{datetime.now().isoformat()} | {message}\n")
        except OSError as e:
            logger.error("Failed to write database fallback log: %s", e)

    def _on_database_error(self, operation_name: str, error: Exception) -> None:
        """Handle DB operation failures and switch to fallback logging mode."""
        if self._db_available:
            logger.error("Database unavailable during '%s': %s", operation_name, error)
        self._db_available = False
        self._log_database_fallback(f"Database error in {operation_name}: {error}")

    def _on_database_recovery(self) -> None:
        """Handle database recovery and send alert when DB becomes healthy again."""
        if self._db_available:
            return
        self._db_available = True
        message = "Database connectivity recovered. Persistent logging resumed."
        logger.info(message)
        self._send_or_queue_email(
            subject="Database Recovery",
            body=message,
            alert_type="DATABASE_RECOVERY",
            severity="low",
        )

    def _queue_email_retry(self, payload: Dict[str, Any], reason: str) -> None:
        """Queue failed email payload for scheduled retries."""
        with self._email_retry_lock:
            payload["attempts"] = int(payload.get("attempts", 0))
            payload["last_reason"] = reason
            self._email_retry_queue.append(payload)
            if self._next_email_retry_ts == 0.0:
                self._next_email_retry_ts = time.time() + self._email_retry_interval_seconds
        logger.warning("Email queued for retry: kind=%s, reason=%s", payload.get("kind"), reason)

    def _send_or_queue_email(
        self,
        subject: str,
        body: str,
        alert_type: str,
        severity: str,
    ) -> None:
        """Send generic email alert or queue it for retry on failure."""
        try:
            success = self.alert_manager.send_email(
                subject=subject,
                body=body,
                alert_type=alert_type,
                severity=severity,
            )
            logger.info(
                "Email attempt (%s): %s",
                alert_type,
                "success" if success else "failed",
            )
            if not success:
                self._queue_email_retry(
                    {
                        "kind": "generic",
                        "subject": subject,
                        "body": body,
                        "alert_type": alert_type,
                        "severity": severity,
                    },
                    reason="send_email returned False",
                )
        except (ConnectionError, TimeoutError, OSError) as e:
            logger.error("Email connection failure for %s: %s", alert_type, e)
            self._queue_email_retry(
                {
                    "kind": "generic",
                    "subject": subject,
                    "body": body,
                    "alert_type": alert_type,
                    "severity": severity,
                },
                reason=str(e),
            )
        except Exception as e:
            logger.error("Unexpected email failure for %s: %s", alert_type, e)
            self._queue_email_retry(
                {
                    "kind": "generic",
                    "subject": subject,
                    "body": body,
                    "alert_type": alert_type,
                    "severity": severity,
                },
                reason=str(e),
            )

    def _send_inactivity_alert_safe(self, duration: int) -> None:
        """Send inactivity alert with retry queue fallback."""
        try:
            success = self.alert_manager.send_inactivity_alert(duration)
            logger.info("Inactivity email attempt: %s", "success" if success else "failed")
            if not success:
                self._queue_email_retry(
                    {
                        "kind": "inactivity",
                        "duration": duration,
                    },
                    reason="send_inactivity_alert returned False",
                )
        except (ConnectionError, TimeoutError, OSError) as e:
            logger.error("Inactivity email failure: %s", e)
            self._queue_email_retry({"kind": "inactivity", "duration": duration}, reason=str(e))
        except Exception as e:
            logger.error("Unexpected inactivity email failure: %s", e)
            self._queue_email_retry({"kind": "inactivity", "duration": duration}, reason=str(e))

    def _send_emergency_alert_safe(self, source: str, details: str) -> None:
        """Send emergency alert with retry queue fallback."""
        try:
            success = self.alert_manager.send_emergency_alert(source=source, details=details)
            logger.info("Emergency email attempt: %s", "success" if success else "failed")
            if not success:
                self._queue_email_retry(
                    {
                        "kind": "emergency",
                        "source": source,
                        "details": details,
                    },
                    reason="send_emergency_alert returned False",
                )
        except (ConnectionError, TimeoutError, OSError) as e:
            logger.error("Emergency email failure: %s", e)
            self._queue_email_retry(
                {"kind": "emergency", "source": source, "details": details},
                reason=str(e),
            )
        except Exception as e:
            logger.error("Unexpected emergency email failure: %s", e)
            self._queue_email_retry(
                {"kind": "emergency", "source": source, "details": details},
                reason=str(e),
            )

    def _retry_email_payload(self, payload: Dict[str, Any]) -> bool:
        """Retry one queued email payload and return success status."""
        kind = str(payload.get("kind", ""))
        try:
            if kind == "generic":
                return self.alert_manager.send_email(
                    subject=str(payload.get("subject", "Alert")),
                    body=str(payload.get("body", "")),
                    alert_type=str(payload.get("alert_type", "INFO")),
                    severity=str(payload.get("severity", "medium")),
                )
            if kind == "inactivity":
                return self.alert_manager.send_inactivity_alert(int(payload.get("duration", 0)))
            if kind == "emergency":
                return self.alert_manager.send_emergency_alert(
                    source=str(payload.get("source", "system")),
                    details=str(payload.get("details", "")),
                )
        except Exception as e:
            logger.error("Queued email retry exception (%s): %s", kind, e)
            return False
        return False

    def _process_email_retry_queue(self) -> None:
        """Retry queued email alerts every configured interval."""
        now = time.time()
        with self._email_retry_lock:
            if not self._email_retry_queue:
                self._next_email_retry_ts = 0.0
                return
            if self._next_email_retry_ts and now < self._next_email_retry_ts:
                return
            queue_snapshot = list(self._email_retry_queue)
            self._email_retry_queue = []

        logger.info("Retrying %s queued email alerts", len(queue_snapshot))
        remaining: list[Dict[str, Any]] = []
        for payload in queue_snapshot:
            payload["attempts"] = int(payload.get("attempts", 0)) + 1
            success = self._retry_email_payload(payload)
            logger.info(
                "Email retry attempt %s for %s: %s",
                payload.get("attempts"),
                payload.get("kind"),
                "success" if success else "failed",
            )
            if not success:
                remaining.append(payload)

        with self._email_retry_lock:
            self._email_retry_queue.extend(remaining)
            self._next_email_retry_ts = (
                time.time() + self._email_retry_interval_seconds if self._email_retry_queue else 0.0
            )

    def _log_activity_safe(self, motion_detected: bool, inactivity_seconds: int) -> None:
        """Log activity to DB with fallback handling."""
        with self._db_lock:
            try:
                self.database.log_activity(
                    motion_detected=motion_detected,
                    inactivity_seconds=inactivity_seconds,
                )
                self._on_database_recovery()
            except (sqlite3.Error, AttributeError, RuntimeError) as e:
                self._on_database_error("log_activity", e)
            except Exception as e:
                self._on_database_error("log_activity", e)

    def _log_alert_safe(self, alert_type: str, severity: str, message: str) -> None:
        """Log alert to DB with fallback handling."""
        with self._db_lock:
            try:
                self.database.log_alert(
                    alert_type=alert_type,
                    severity=severity,
                    message=message,
                )
                self._on_database_recovery()
            except (sqlite3.Error, AttributeError, RuntimeError) as e:
                self._on_database_error("log_alert", e)
            except Exception as e:
                self._on_database_error("log_alert", e)

    def _log_voice_safe(self, transcript: str, intent: str, response: Optional[str]) -> None:
        """Log voice interaction to DB with fallback handling."""
        with self._db_lock:
            try:
                self.database.log_voice_interaction(
                    transcript=transcript,
                    intent=intent,
                    response=response,
                )
                self._on_database_recovery()
            except (sqlite3.Error, AttributeError, RuntimeError) as e:
                self._on_database_error("log_voice_interaction", e)
            except Exception as e:
                self._on_database_error("log_voice_interaction", e)

    def _activate_offline_stt_mode(self, reason: str) -> None:
        """Switch to offline STT response mode."""
        if self._offline_stt_mode:
            return
        self._offline_stt_mode = True
        logger.warning("STT API failure detected. Switching to offline mode: %s", reason)

    def _offline_template_response(self, transcript: str) -> tuple[str, str]:
        """Generate template response in offline mode."""
        intent = self._determine_intent(transcript, {"intent": "unknown"})
        response_map = {
            "emergency": "Help notified",
            "medicine_query": self._get_next_reminder_response(),
            "status": f"Current inactivity duration is {int(self.activity_tracker.get_inactivity_duration())} seconds",
            "stop": "Reminder marked as complete",
            "greeting": "Hello. I am here to help you.",
            "unknown": "Offline mode active. Please repeat your command.",
        }
        return intent, response_map.get(intent, response_map["unknown"])

    def start(self) -> None:
        """Start vision thread, voice thread, and scheduler."""
        if self._running:
            logger.warning("System already running")
            return

        self._running = True
        self.shutdown_event.clear()
        self._set_state(SystemState.RUNNING)

        self.event_thread = threading.Thread(target=self._event_loop, daemon=True)
        self.event_thread.start()

        self.vision_thread = threading.Thread(target=self._vision_loop, daemon=True)
        self.vision_thread.start()

        if self._voice_available and self.voice_assistant is not None:
            self.voice_thread = threading.Thread(target=self._voice_loop, daemon=True)
            self.voice_thread.start()
        else:
            logger.warning("Voice loop not started; microphone unavailable (vision-only mode).")

        try:
            self.reminder_scheduler.start()
        except Exception as e:
            logger.error("Reminder scheduler failed to start: %s", e)
        logger.info("ElderlyCareSystem started")

    def pause(self) -> None:
        """Pause vision processing while keeping voice loop active."""
        if not self._running:
            logger.warning("Cannot pause: system is not running")
            return
        self._set_state(SystemState.PAUSED)
        logger.info("System paused (voice remains active)")

    def resume(self) -> None:
        """Resume vision processing after pause."""
        if not self._running:
            logger.warning("Cannot resume: system is not running")
            return
        self._set_state(SystemState.RUNNING)
        logger.info("System resumed")

    def shutdown(self) -> None:
        """Graceful shutdown for all components and background threads."""
        self._set_state(SystemState.SHUTDOWN)
        self.stop()

    def stop(self) -> None:
        """Graceful shutdown for all components and background threads."""
        if not self._running:
            self._set_state(SystemState.SHUTDOWN)
            return

        self.shutdown_event.set()

        try:
            self.reminder_scheduler.stop()
        except Exception as e:
            logger.error("Error stopping scheduler: %s", e)

        try:
            self.voice_assistant.stop_listening()
            self.voice_assistant.cleanup()
        except AttributeError:
            pass
        except Exception as e:
            logger.error("Error stopping voice assistant: %s", e)

        try:
            self.camera.release()
        except Exception as e:
            logger.error("Error releasing camera: %s", e)

        for thread in [self.vision_thread, self.voice_thread, self.event_thread]:
            if thread and thread.is_alive():
                thread.join(timeout=3)

        try:
            self.alert_manager.close()
        except Exception as e:
            logger.error("Error closing alert manager: %s", e)

        try:
            self.database.close()
        except Exception as e:
            logger.error("Error closing database: %s", e)

        self._running = False
        self._set_state(SystemState.SHUTDOWN)
        logger.info("ElderlyCareSystem stopped")

    def _vision_loop(self) -> None:
        """Capture frames, detect motion, track activity, and raise inactivity events."""
        opened = False
        for attempt in range(1, 4):
            try:
                if self.camera.start():
                    opened = True
                    break
                logger.warning("Camera start attempt %s/3 failed", attempt)
            except RuntimeError as e:
                logger.error("Camera runtime error on attempt %s/3: %s", attempt, e)
            except OSError as e:
                logger.error("Camera OS error on attempt %s/3: %s", attempt, e)
            except Exception as e:
                logger.error("Unexpected camera error on attempt %s/3: %s", attempt, e)
            time.sleep(1)

        if not opened:
            self._camera_available = False
            message = "Camera failed after 3 retries. System continuing in voice-only mode."
            logger.error(message)
            self._send_or_queue_email(
                subject="Camera Failure - Voice Only Mode",
                body=message,
                alert_type="CAMERA_FAILURE",
                severity="high",
            )
            return

        previous_frame = self.camera.read_frame()
        if previous_frame is None:
            logger.error("Vision loop stopped: could not capture initial frame")
            self.camera.release()
            return

        last_activity_log_time = 0.0

        while not self.shutdown_event.is_set():
            if self.get_state() == SystemState.PAUSED:
                time.sleep(0.2)
                continue

            current_frame = self.camera.read_frame()
            if current_frame is None:
                time.sleep(0.1)
                continue

            motion_detected, _confidence = self.motion_detector.detect(previous_frame, current_frame)
            self.activity_tracker.update(motion_detected)
            inactivity_duration = int(self.activity_tracker.get_inactivity_duration())

            now = time.time()
            if now - last_activity_log_time >= 2.0:
                self._log_activity_safe(
                    motion_detected=motion_detected,
                    inactivity_seconds=inactivity_duration,
                )
                last_activity_log_time = now

            previous_frame = current_frame

    def _voice_loop(self) -> None:
        """Listen, transcribe, classify, and respond to voice intents."""
        if not self.voice_assistant:
            return

        while not self.shutdown_event.is_set():
            try:
                text = self.voice_assistant.listen()
            except (OSError, RuntimeError) as e:
                self._voice_available = False
                logger.error("Microphone failure detected; continuing with vision only: %s", e)
                return
            except Exception as e:
                if "request" in str(e).lower() or "speech" in str(e).lower():
                    self._activate_offline_stt_mode(str(e))
                else:
                    logger.error("Unexpected voice listen error: %s", e)
                time.sleep(0.2)
                continue

            if not text:
                self._stt_none_count += 1
                if self._stt_none_count >= self._stt_none_threshold:
                    self._activate_offline_stt_mode("consecutive empty STT results")
                continue
            self._stt_none_count = 0

            if self._offline_stt_mode:
                intent, response = self._offline_template_response(text)
                self._speak_safe(response)
                self._log_voice_safe(transcript=text, intent=intent, response=response)
                if intent == "emergency":
                    self._handle_emergency(text)
                continue

            try:
                intent_result = self.voice_assistant.process_intent(text)
            except Exception as e:
                self._activate_offline_stt_mode(str(e))
                intent, response = self._offline_template_response(text)
                self._speak_safe(response)
                self._log_voice_safe(transcript=text, intent=intent, response=response)
                continue

            intent = self._determine_intent(text=text, intent_result=intent_result)
            response: Optional[str] = None

            self._log_voice_safe(
                transcript=text,
                intent=intent,
                response=None,
            )

            action = self.intent_actions.get(intent)
            if action:
                response = action(text)
            elif intent == "help":
                response = "You can ask for help, reminders, or emergency support."
                self._speak_safe(response)
            elif intent == "reminder":
                response = self._intent_medicine_query(text)

            if response is not None:
                self._log_voice_safe(
                    transcript=text,
                    intent=intent,
                    response=response,
                )

    def _determine_intent(self, text: str, intent_result: Dict[str, Any]) -> str:
        """Determine command intent using bilingual keyword checks plus model intent."""
        transcript = text.lower().strip()

        if any(token in transcript for token in ["emergency", "ସାହାଯ୍ୟ"]):
            return "emergency"
        if any(token in transcript for token in ["medicine time", "medicine", "ଔଷଧ"]):
            return "medicine_query"
        if any(token in transcript for token in ["status", "ଅବସ୍ଥା"]):
            return "status"
        if any(token in transcript for token in ["stop", "ବନ୍ଦ"]):
            return "stop"
        if any(token in transcript for token in ["hello", "hi", "ନମସ୍କାର"]):
            return "greeting"

        inferred_intent = str(intent_result.get("intent", "unknown"))
        if inferred_intent == "reminder":
            return "medicine_query"
        if inferred_intent in {"emergency", "status", "greeting"}:
            return inferred_intent
        return "unknown"

    def _intent_emergency(self, transcript: str) -> str:
        """Handle explicit emergency command and confirm notification."""
        self._handle_emergency(transcript)
        confirmation = "Help notified"
        self._speak_safe(confirmation)
        return confirmation

    def _intent_medicine_query(self, _transcript: str) -> str:
        """Handle medicine command by speaking next scheduled reminder time."""
        response = self._get_next_reminder_response()
        self._speak_safe(response)
        return response

    def _intent_status(self, _transcript: str) -> str:
        """Speak current inactivity duration."""
        inactivity_seconds = int(self.activity_tracker.get_inactivity_duration())
        response = f"Current inactivity duration is {inactivity_seconds} seconds"
        self._speak_safe(response)
        return response

    def _intent_stop(self, _transcript: str) -> str:
        """Acknowledge the most recent triggered reminder as complete."""
        acknowledged = False
        with self._db_lock:
            try:
                if self.database.connection is not None:
                    cursor = self.database.connection.cursor()
                    cursor.execute(
                        """
                        UPDATE reminders
                        SET status = 'acknowledged'
                        WHERE id = (
                            SELECT id FROM reminders
                            WHERE status = 'triggered'
                            ORDER BY created_at DESC, id DESC
                            LIMIT 1
                        )
                        """
                    )
                    self.database.connection.commit()
                    acknowledged = cursor.rowcount > 0
                    self._on_database_recovery()
            except Exception as e:
                self._on_database_error("acknowledge_reminder", e)

        if acknowledged:
            response = "Reminder marked as complete"
        else:
            response = "No active reminder to acknowledge"
        self._speak_safe(response)
        return response

    def _intent_greeting(self, _transcript: str) -> str:
        """Handle greeting command."""
        response = "Hello. I am here to help you."
        self._speak_safe(response)
        return response

    def _get_next_reminder_response(self) -> str:
        """Return response string for nearest upcoming reminder."""
        try:
            reminders = self.reminder_scheduler.list_reminders()
            upcoming = []
            now = datetime.now()
            for reminder in reminders:
                next_run = reminder.get("next_run")
                if not next_run:
                    continue
                try:
                    parsed = datetime.fromisoformat(str(next_run))
                except ValueError:
                    continue
                if parsed >= now:
                    upcoming.append(parsed)

            if upcoming:
                next_time = min(upcoming)
                return f"Your next reminder is scheduled at {next_time.strftime('%H:%M')}"

            return "No upcoming reminders are scheduled"
        except Exception as e:
            logger.error("Error fetching next reminder: %s", e)
            return "I could not fetch reminder schedule right now"

    def _on_activity_state_change(self, event_name: str) -> None:
        """Translate tracker events into system callbacks."""
        if event_name == "inactivity_detected" and hasattr(self.activity_tracker, "on_inactive"):
            duration = int(self.activity_tracker.get_inactivity_duration())
            self.activity_tracker.on_inactive(duration)

    def _handle_inactive(self, duration: int) -> None:
        """Dispatch inactivity event to the central event queue."""
        self.event_queue.put({
            "type": "inactivity",
            "duration": duration,
        })

    def _inactivity_callback(self, duration: int) -> None:
        """Handle inactivity: log DB, send email, and speak local warning."""
        logger.warning("Inactivity callback triggered at %ss", duration)

        alerts_cfg = self.config.get("alerts", {})
        warning_threshold = int(alerts_cfg.get("inactivity_warning_seconds", 1800))
        critical_threshold = int(alerts_cfg.get("inactivity_critical_seconds", 3600))
        severity = "critical" if duration >= critical_threshold else "high"
        if duration < warning_threshold:
            severity = "medium"

        self._log_alert_safe(
            alert_type="inactivity",
            severity=severity,
            message=f"No motion detected for {duration} seconds",
        )

        self._send_inactivity_alert_safe(duration)
        self._speak_safe("Please move or press emergency button")

    def _handle_emergency(self, transcript: str) -> None:
        """Handle emergency intent immediately."""
        logger.critical("Emergency intent detected from voice input")

        self._log_alert_safe(
            alert_type="emergency",
            severity="critical",
            message=f"Emergency intent detected: {transcript}",
        )

        self._send_emergency_alert_safe(source="voice", details=transcript)

    def _on_reminder_trigger(self, message: str, reminder_type: str = "general") -> None:
        """Reminder callback routed into queue for thread-safe event handling."""
        self.event_queue.put(
            {
                "type": "reminder",
                "message": message,
                "reminder_type": reminder_type,
            }
        )

    def _event_loop(self) -> None:
        """Central event dispatcher for inactivity/reminder callbacks."""
        while not self.shutdown_event.is_set():
            self._process_email_retry_queue()

            try:
                event = self.event_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            event_type = event.get("type")
            if event_type == "inactivity":
                self._inactivity_callback(int(event.get("duration", 0)))
            elif event_type == "reminder":
                message = str(event.get("message", "Reminder"))
                reminder_type = str(event.get("reminder_type", "general"))

                self._speak_safe(message)
                self._log_alert_safe(
                    alert_type="reminder",
                    severity="low",
                    message=f"{reminder_type}: {message}",
                )

                if self.config.get("voice", {}).get("require_ack_for_reminder", False):
                    self._speak_safe("Please say yes to acknowledge this reminder.")


def _create_signal_handler(system: ElderlyCareSystem):
    """Create process signal handler bound to system instance."""

    def _handler(_sig, _frame):
        logger.info("Shutdown signal received")
        system.shutdown()
        sys.exit(0)

    return _handler


def main() -> int:
    """Application process entry point."""
    config = load_config("config.json")
    setup_logging(config)

    system = ElderlyCareSystem(config)
    signal_handler = _create_signal_handler(system)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    system.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        system.shutdown()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
