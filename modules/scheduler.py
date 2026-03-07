"""
Scheduler Module - Reminder Scheduling and Time-based Tasks
Handles medication reminders and other scheduled tasks.
"""

import schedule
import threading
import logging
import time
import sqlite3
from typing import Dict, Optional, List, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class ReminderScheduler:
    """Thread-safe scheduler for voice reminders."""

    def __init__(self, tts_engine, database) -> None:
        """
        Initialize scheduler with TTS and database dependencies.

        Args:
            tts_engine: Object exposing speak(message: str)
            database: Database-like object for logging reminder events
        """
        self.tts_engine = tts_engine
        self.database = database
        self.scheduler = schedule.Scheduler()
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._is_running = False

        self.default_reminders = [
            ("08:00", "Good morning. Time for your medicine.", "morning_medicine", "daily"),
            ("12:30", "It is lunch time.", "lunch", "daily"),
            ("20:00", "Good evening. Time for your medicine.", "evening_medicine", "daily"),
        ]

        for time_str, message, reminder_type, repeat in self.default_reminders:
            self.add_reminder(
                time_str=time_str,
                message=message,
                reminder_type=reminder_type,
                repeat=repeat,
            )

    def add_reminder(
        self,
        time_str: str,
        message: str,
        reminder_type: str,
        repeat: str = "daily",
    ) -> bool:
        """
        Add a reminder at specified time using HH:MM format.

        Args:
            time_str: Time in HH:MM format
            message: Reminder message spoken by TTS
            reminder_type: Reminder category/type
            repeat: 'daily' or 'once'

        Returns:
            bool: True if reminder added successfully
        """
        try:
            datetime.strptime(time_str, "%H:%M")

            repeat_mode = repeat.lower().strip()
            if repeat_mode not in {"daily", "once"}:
                logger.error("Invalid repeat value '%s'. Use 'daily' or 'once'", repeat)
                return False

            with self._lock:
                if repeat_mode == "daily":
                    self.scheduler.every().day.at(time_str).do(
                        self._trigger_reminder,
                        message=message,
                        reminder_type=reminder_type,
                    ).tag(reminder_type)
                else:
                    self.scheduler.every().day.at(time_str).do(
                        self._trigger_once,
                        message=message,
                        reminder_type=reminder_type,
                    ).tag(reminder_type)

                self._log_reminder_scheduled(
                    reminder_type=reminder_type,
                    scheduled_time=time_str,
                    repeat=repeat_mode,
                )

            logger.info(
                "Reminder added: type=%s, time=%s, repeat=%s",
                reminder_type,
                time_str,
                repeat_mode,
            )
            return True

        except ValueError:
            logger.error(f"Invalid time format: {time_str}. Use HH:MM")
            return False
        except Exception as e:
            logger.error(f"Error adding reminder: {e}")
            return False

    def _trigger_once(self, message: str, reminder_type: str):
        """Trigger one-time reminder and unschedule it after execution."""
        self._trigger_reminder(message=message, reminder_type=reminder_type)
        return schedule.CancelJob

    def _get_database_path(self) -> Optional[str]:
        """Extract sqlite database path from database dependency."""
        if self.database is None:
            return None
        if hasattr(self.database, "db_path"):
            return str(self.database.db_path)
        return None

    def _execute_db_write(self, query: str, params: tuple) -> None:
        """Execute sqlite write using a short-lived connection (thread-safe)."""
        db_path = self._get_database_path()
        if not db_path:
            return

        connection = sqlite3.connect(db_path)
        try:
            cursor = connection.cursor()
            cursor.execute(query, params)
            connection.commit()
        finally:
            connection.close()

    def _trigger_reminder(self, message: str, reminder_type: str = "general") -> None:
        """
        Trigger reminder callback: speak message and log event.

        Args:
            message: Reminder text to speak
            reminder_type: Reminder category
        """
        try:
            with self._lock:
                if self.tts_engine is not None:
                    self.tts_engine.speak(message)

            self._execute_db_write(
                """
                INSERT INTO alerts (alert_type, severity, message, resolved)
                VALUES (?, ?, ?, 0)
                """,
                ("reminder", "low", f"{reminder_type}: {message}"),
            )
            self._execute_db_write(
                """
                INSERT INTO reminders (reminder_type, scheduled_time, status)
                VALUES (?, ?, ?)
                """,
                (reminder_type, datetime.now().strftime("%H:%M"), "triggered"),
            )

            logger.info("Reminder triggered: %s", reminder_type)
        except Exception as e:
            logger.error("Error triggering reminder: %s", e)

    def _log_reminder_scheduled(self, reminder_type: str, scheduled_time: str, repeat: str) -> None:
        """Log reminder scheduling event in database reminders table."""
        try:
            self._execute_db_write(
                """
                INSERT INTO reminders (reminder_type, scheduled_time, status)
                VALUES (?, ?, ?)
                """,
                (reminder_type, scheduled_time, f"scheduled_{repeat}"),
            )
        except Exception as e:
            logger.error("Error logging scheduled reminder: %s", e)

    def start(self) -> None:
        """Start scheduler loop in a background thread."""
        with self._lock:
            if self._is_running:
                logger.warning("Scheduler is already running")
                return

            self._stop_event.clear()
            self._is_running = True
            self._thread = threading.Thread(target=self._run_scheduler_loop, daemon=True)
            self._thread.start()
            logger.info("ReminderScheduler started")

    def _run_scheduler_loop(self) -> None:
        """Run pending jobs until stop signal is set."""
        try:
            while not self._stop_event.is_set():
                with self._lock:
                    self.scheduler.run_pending()
                time.sleep(0.5)
        except Exception as e:
            logger.error(f"Error in scheduler loop: {e}")
        finally:
            with self._lock:
                self._is_running = False

    def stop(self) -> None:
        """Stop scheduler loop and wait for background thread to exit."""
        with self._lock:
            if not self._is_running:
                return
            self._stop_event.set()

        if self._thread:
            self._thread.join(timeout=5)

        with self._lock:
            self._is_running = False
        logger.info("ReminderScheduler stopped")

    def list_reminders(self) -> List[Dict[str, Any]]:
        """Return currently scheduled jobs as serializable dictionaries."""
        with self._lock:
            jobs = []
            for job in self.scheduler.jobs:
                jobs.append(
                    {
                        "next_run": job.next_run.isoformat() if job.next_run else None,
                        "tags": list(job.tags),
                        "interval": job.interval,
                        "unit": job.unit,
                        "at_time": str(job.at_time) if job.at_time else None,
                    }
                )
            return jobs

    def start_scheduler(self) -> None:
        """Backward-compatible wrapper for start()."""
        self.start()

    def stop_scheduler(self) -> None:
        """Backward-compatible wrapper for stop()."""
        self.stop()
