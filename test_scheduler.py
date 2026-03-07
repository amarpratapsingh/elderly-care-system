"""
ReminderScheduler Test Script - Elderly Care Monitoring System

Tests:
1. Mock TTS engine integration
2. One-time and daily reminder scheduling
3. Background scheduler start/stop
4. Reminder trigger execution
5. Database logging verification
"""

import time
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

from modules.database import Database
from modules.scheduler import ReminderScheduler


class MockTTSEngine:
    """Mock TTS engine for testing reminder callbacks."""

    def __init__(self) -> None:
        self.spoken_messages = []

    def speak(self, message: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] TTS: {message}")
        self.spoken_messages.append(message)


def _future_hhmm(minutes_from_now: int) -> str:
    """Generate HH:MM time string minutes from now."""
    target = datetime.now() + timedelta(minutes=minutes_from_now)
    return target.strftime("%H:%M")


def main() -> None:
    """Run scheduler integration test."""
    print("=" * 70)
    print("  Elderly Care - ReminderScheduler Test")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_scheduler.db"
        database = Database(str(db_path))
        assert database.connect() is True, "Failed to connect to test database"

        tts = MockTTSEngine()
        scheduler = ReminderScheduler(tts_engine=tts, database=database)

        print("\nDisabling default reminders for deterministic test run...")
        scheduler.scheduler.clear()

        now = datetime.now()
        print(f"Current time: {now.strftime('%H:%M:%S')}")

        one_time_1 = _future_hhmm(1)
        one_time_2 = _future_hhmm(2)
        daily_1 = _future_hhmm(3)

        print("\nScheduling reminders:")
        print(f"- one-time #1 at {one_time_1}")
        print(f"- one-time #2 at {one_time_2}")
        print(f"- daily #1 at {daily_1}")

        assert scheduler.add_reminder(
            time_str=one_time_1,
            message="One-time reminder #1",
            reminder_type="test_once_1",
            repeat="once",
        ), "Failed to add one-time reminder #1"

        assert scheduler.add_reminder(
            time_str=one_time_2,
            message="One-time reminder #2",
            reminder_type="test_once_2",
            repeat="once",
        ), "Failed to add one-time reminder #2"

        assert scheduler.add_reminder(
            time_str=daily_1,
            message="Daily reminder #1",
            reminder_type="test_daily_1",
            repeat="daily",
        ), "Failed to add daily reminder"

        jobs = scheduler.list_reminders()
        print(f"\nJobs scheduled: {len(jobs)}")
        assert len(jobs) == 3, f"Expected 3 jobs, got {len(jobs)}"

        scheduler.start()
        print("Scheduler started. Waiting up to 4 minutes for all reminders to trigger...")

        deadline = time.time() + (4 * 60)
        while time.time() < deadline:
            if len(tts.spoken_messages) >= 3:
                break
            time.sleep(1)

        scheduler.stop()
        print("Scheduler stopped gracefully")

        print("\nVerifying triggers...")
        assert len(tts.spoken_messages) >= 3, (
            f"Expected at least 3 trigger events, got {len(tts.spoken_messages)}"
        )
        print(f"✓ Triggered messages: {len(tts.spoken_messages)}")

        print("\nVerifying database logging...")
        alert_logs = database.get_recent_logs("alerts", limit=20)
        reminder_logs = database.get_recent_logs("reminders", limit=20)

        reminder_alerts = [a for a in alert_logs if a.get("alert_type") == "reminder"]
        assert len(reminder_alerts) >= 3, (
            f"Expected at least 3 reminder alert logs, got {len(reminder_alerts)}"
        )

        scheduled_entries = [r for r in reminder_logs if str(r.get("status", "")).startswith("scheduled_")]
        triggered_entries = [r for r in reminder_logs if r.get("status") == "triggered"]

        assert len(scheduled_entries) >= 3, (
            f"Expected at least 3 scheduled reminder entries, got {len(scheduled_entries)}"
        )
        assert len(triggered_entries) >= 3, (
            f"Expected at least 3 triggered reminder entries, got {len(triggered_entries)}"
        )

        print(f"✓ Reminder alert logs: {len(reminder_alerts)}")
        print(f"✓ Scheduled reminder entries: {len(scheduled_entries)}")
        print(f"✓ Triggered reminder entries: {len(triggered_entries)}")

        remaining_jobs = scheduler.list_reminders()
        once_remaining = [j for j in remaining_jobs if "test_once_1" in j["tags"] or "test_once_2" in j["tags"]]
        assert len(once_remaining) == 0, "One-time reminders were not removed after triggering"
        print("✓ One-time reminders removed after trigger")

        database.close()

    print("\n" + "=" * 70)
    print("✓ ReminderScheduler test completed successfully")
    print("=" * 70)


if __name__ == "__main__":
    main()
