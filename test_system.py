"""Comprehensive unittest suite for the Elderly Care AI System.

This suite focuses on deterministic tests by mocking hardware and external APIs:
- camera access (OpenCV VideoCapture)
- speech recognition API calls
- text-to-speech network calls
- SMTP email sending

Run:
    python -m unittest test_system.py -v
"""

from __future__ import annotations

import os
import tempfile
import time
import unittest
import wave
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import speech_recognition as sr

from modules.alerts import AlertManager
from modules.database import Database
from modules.scheduler import ReminderScheduler
from modules.vision import ActivityTracker, CameraHandler, MotionDetector
from modules.voice import VoiceAssistant


class FakeVideoCapture:
    """Minimal fake OpenCV VideoCapture for camera tests."""

    def __init__(self, camera_id: int) -> None:
        self.camera_id = camera_id
        self._opened = True
        self._width = 640
        self._height = 480

    def isOpened(self) -> bool:  # noqa: N802 - mirrors OpenCV API
        return self._opened

    def read(self) -> tuple[bool, np.ndarray]:
        frame = np.zeros((self._height, self._width, 3), dtype=np.uint8)
        frame[20:120, 20:120] = 255
        return True, frame

    def set(self, prop: int, value: float) -> bool:
        if prop == 3:  # cv2.CAP_PROP_FRAME_WIDTH
            self._width = int(value)
        if prop == 4:  # cv2.CAP_PROP_FRAME_HEIGHT
            self._height = int(value)
        return True

    def get(self, prop: int) -> float:
        if prop == 3:
            return float(self._width)
        if prop == 4:
            return float(self._height)
        if prop == 5:
            return 30.0
        return 0.0

    def release(self) -> None:
        self._opened = False


class FakeSMTP:
    """Fake SMTP client that captures send calls without network access."""

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        self.sent: list[dict[str, str]] = []

    def send(self, to: str, subject: str, contents: str) -> None:
        self.sent.append({"to": to, "subject": subject, "contents": contents})

    def close(self) -> None:
        return None


class FakeTTS:
    """Fake gTTS implementation that writes a deterministic file."""

    def __init__(self, text: str, lang: str, slow: bool = False) -> None:
        self.text = text
        self.lang = lang
        self.slow = slow

    def save(self, filepath: str) -> None:
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        Path(filepath).write_bytes(b"FAKE_MP3_DATA")


class MockSpeaker:
    """Simple speaker mock for scheduler/integration tests."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    def speak(self, message: str) -> None:
        self.messages.append(message)


class TestFixtures(unittest.TestCase):
    """Reusable fixture creation for system tests."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.base_path = Path(cls.temp_dir.name)

        cls.static_frame = np.zeros((240, 320, 3), dtype=np.uint8)
        cls.moving_frame = cls.static_frame.copy()
        cls.moving_frame[80:180, 100:220] = 255

        # Known audio fixture for STT pipeline tests.
        cls.known_audio_text = "hello emergency"
        cls.known_wav_path = cls.base_path / "known_input.wav"
        with wave.open(str(cls.known_wav_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)
            wav_file.writeframes((np.zeros(16000, dtype=np.int16)).tobytes())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp_dir.cleanup()


class SystemTests(TestFixtures):
    """Comprehensive automated tests for core modules and integration."""

    @patch("modules.vision.cv2.VideoCapture", side_effect=FakeVideoCapture)
    def test_camera(self, _mock_capture: MagicMock) -> None:
        """Verify camera opens and captures a valid frame."""
        camera = CameraHandler(camera_id=0, width=320, height=240)
        self.assertTrue(camera.start())

        frame = camera.read_frame()
        self.assertIsNotNone(frame)
        assert frame is not None
        self.assertEqual(frame.shape[0], 240)
        self.assertEqual(frame.shape[1], 320)

        camera.release()
        self.assertFalse(camera.is_opened())

    def test_motion_detection(self) -> None:
        """Verify static frames do not trigger motion and moving frames do."""
        detector = MotionDetector(threshold=20, min_area=100)

        no_motion, confidence_static = detector.detect(self.static_frame, self.static_frame)
        self.assertFalse(no_motion)
        self.assertEqual(confidence_static, 0.0)

        motion, confidence_moving = detector.detect(self.static_frame, self.moving_frame)
        self.assertTrue(motion)
        self.assertGreater(confidence_moving, 0.0)

    def test_activity_tracker(self) -> None:
        """Verify inactivity timing and callback state transitions."""
        events: list[str] = []

        tracker = ActivityTracker(inactivity_threshold=0.1)
        tracker.register_callback(events.append)

        tracker.update(motion_detected=False)
        time.sleep(0.15)
        tracker.update(motion_detected=False)

        self.assertTrue(tracker.is_inactive())
        self.assertIn("inactivity_detected", events)

        duration = tracker.get_inactivity_duration()
        self.assertGreaterEqual(duration, 0.1)

        tracker.update(motion_detected=True)
        self.assertEqual(tracker.get_state(), "ACTIVE")
        self.assertIn("activity_resumed", events)

    @patch("speech_recognition.Recognizer.recognize_google")
    def test_stt(self, mock_recognize_google: MagicMock) -> None:
        """Transcribe a known audio fixture and check expected text accuracy."""
        mock_recognize_google.return_value = self.known_audio_text

        recognizer = sr.Recognizer()
        with sr.AudioFile(str(self.known_wav_path)) as source:
            audio = recognizer.record(source)

        transcription = recognizer.recognize_google(audio, language="en-US")
        self.assertIn("emergency", transcription)
        self.assertEqual(transcription, self.known_audio_text)

    @patch("modules.voice.gTTS", side_effect=FakeTTS)
    def test_tts(self, _mock_tts: MagicMock) -> None:
        """Generate speech output and verify file creation."""
        assistant = VoiceAssistant.__new__(VoiceAssistant)
        assistant.language = "en"

        audio_path = VoiceAssistant.speak(assistant, "hello world", auto_play=False)
        self.assertIsNotNone(audio_path)
        assert audio_path is not None
        self.assertTrue(Path(audio_path).exists())

    def test_intent_classifier(self) -> None:
        """Validate intent detection across supported categories."""
        assistant = VoiceAssistant.__new__(VoiceAssistant)

        samples = {
            "greeting": "hello there",
            "reminder": "what's next reminder",
            "help": "please help me",
            "status": "status check",
            "emergency": "urgent doctor needed",
            "stop": "stop now",
            "medicine_query": "medicine time now",
            "unknown": "random unrelated phrase",
        }

        for expected_intent, text in samples.items():
            result = VoiceAssistant.process_intent(assistant, text)
            self.assertEqual(result["intent"], expected_intent)
            self.assertIn("confidence", result)

    def test_database(self) -> None:
        """Verify CRUD operations and persistence behavior in SQLite backend."""
        db_path = self.base_path / "system_test.db"

        db = Database(str(db_path))
        self.assertTrue(db.connect())

        activity_id = db.log_activity(True, 0)
        alert_id = db.log_alert("inactivity", "high", "No motion detected")
        voice_id = db.log_voice_interaction("hello", "greeting", "Hi")

        self.assertIsNotNone(activity_id)
        self.assertIsNotNone(alert_id)
        self.assertIsNotNone(voice_id)

        alerts = db.get_recent_logs("alerts", limit=10)
        self.assertGreaterEqual(len(alerts), 1)

        # Update operation (U)
        cursor = db.connection.cursor()  # type: ignore[union-attr]
        cursor.execute("UPDATE alerts SET resolved=1 WHERE id=?", (alert_id,))
        db.connection.commit()  # type: ignore[union-attr]

        cursor.execute("SELECT resolved FROM alerts WHERE id=?", (alert_id,))
        resolved_row = cursor.fetchone()
        self.assertIsNotNone(resolved_row)
        self.assertEqual(int(resolved_row[0]), 1)

        # Delete operation (D)
        cursor.execute("DELETE FROM alerts WHERE id=?", (alert_id,))
        db.connection.commit()  # type: ignore[union-attr]

        cursor.execute("SELECT COUNT(*) FROM alerts WHERE id=?", (alert_id,))
        deleted_count = cursor.fetchone()[0]
        self.assertEqual(int(deleted_count), 0)

        db.close()

        # Persistence check after reconnect.
        db_reopen = Database(str(db_path))
        self.assertTrue(db_reopen.connect())
        activities = db_reopen.get_recent_logs("activity_logs", limit=10)
        self.assertGreaterEqual(len(activities), 1)
        db_reopen.close()

    @patch("modules.alerts.yagmail.SMTP", side_effect=FakeSMTP)
    def test_alerts(self, _mock_smtp: MagicMock) -> None:
        """Verify email alert sending with mocked SMTP backend."""
        manager = AlertManager(
            caregiver_email="caregiver@example.com",
            smtp_user="sender@example.com",
            smtp_pass="test-pass",
        )

        ok = manager.send_email(
            subject="Test Subject",
            body="Test Body",
            alert_type="TEST",
            severity="low",
        )
        self.assertTrue(ok)
        self.assertGreaterEqual(len(manager.get_alert_history()), 1)

    def test_scheduler(self) -> None:
        """Verify scheduler job registration and trigger side effects."""
        db_path = self.base_path / "scheduler_test.db"
        db = Database(str(db_path))
        self.assertTrue(db.connect())

        speaker = MockSpeaker()
        scheduler = ReminderScheduler(tts_engine=speaker, database=db)

        # Default reminders should be present.
        jobs = scheduler.list_reminders()
        self.assertGreaterEqual(len(jobs), 1)

        # Trigger a reminder directly to avoid waiting on wall-clock schedule.
        scheduler._trigger_reminder(message="Take medicine", reminder_type="test_reminder")

        self.assertIn("Take medicine", speaker.messages)
        alert_logs = db.get_recent_logs("alerts", limit=20)
        self.assertTrue(any(a.get("alert_type") == "reminder" for a in alert_logs))

        db.close()

    @patch("modules.alerts.yagmail.SMTP", side_effect=FakeSMTP)
    @patch("modules.voice.gTTS", side_effect=FakeTTS)
    def test_integration(self, _mock_tts: MagicMock, _mock_smtp: MagicMock) -> None:
        """Run a mocked full pipeline: vision + activity + alerts + DB + scheduler."""
        db_path = self.base_path / "integration_test.db"
        db = Database(str(db_path))
        self.assertTrue(db.connect())

        alert_manager = AlertManager(
            caregiver_email="caregiver@example.com",
            smtp_user="sender@example.com",
            smtp_pass="test-pass",
            database=db,
        )

        speaker = MockSpeaker()
        scheduler = ReminderScheduler(tts_engine=speaker, database=db)

        events: list[str] = []

        def inactivity_handler(event_name: str) -> None:
            events.append(event_name)
            if event_name == "inactivity_detected":
                alert_manager.send_inactivity_alert(duration_seconds=120)
                db.log_activity(False, 120)

        tracker = ActivityTracker(inactivity_threshold=0.1)
        tracker.register_callback(inactivity_handler)

        detector = MotionDetector(threshold=20, min_area=100)
        motion_detected, _ = detector.detect(self.static_frame, self.moving_frame)
        tracker.update(motion_detected)

        time.sleep(0.15)
        tracker.update(False)

        scheduler._trigger_reminder("Integration reminder", reminder_type="integration")

        self.assertIn("inactivity_detected", events)
        self.assertIn("Integration reminder", speaker.messages)

        alerts = db.get_recent_logs("alerts", limit=30)
        activities = db.get_recent_logs("activity_logs", limit=30)
        reminders = db.get_recent_logs("reminders", limit=30)

        self.assertTrue(any(a.get("alert_type") in {"inactivity", "reminder"} for a in alerts))
        self.assertGreaterEqual(len(activities), 1)
        self.assertGreaterEqual(len(reminders), 1)

        db.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
