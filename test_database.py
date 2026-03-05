"""
Database Test Script - Elderly Care Monitoring System

Comprehensive tests for Database class including:
1. Database initialization and connection
2. Logging activities (motion detection)
3. Logging alerts
4. Logging voice interactions
5. Retrieving logs from all tables
6. Data integrity verification

Uses tempfile for testing and cleans up after execution.
"""

import sys
import tempfile
import logging
import sqlite3
from pathlib import Path
from datetime import datetime

# Import database module directly, bypassing __init__.py
sys.path.insert(0, str(Path(__file__).parent))
# Import directly from the database.py file
import importlib.util
spec = importlib.util.spec_from_file_location("database", "modules/database.py")
database_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(database_module)
Database = database_module.Database

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_database_initialization() -> bool:
    """
    Test 1: Database initialization and connection.
    
    Returns:
        bool: True if initialization successful
    """
    print("\n" + "=" * 70)
    print("TEST 1: Database Initialization")
    print("=" * 70)
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test_elderly_care.db"
            db = Database(db_path=db_path)
            
            # Test connection
            result = db.connect()
            assert result is True, "Failed to connect to database"
            print("✓ Connected to database successfully")
            
            # Verify database file was created
            assert Path(db_path).exists(), "Database file was not created"
            print(f"✓ Database file created at: {db_path}")
            
            # Verify tables exist
            cursor = db.connection.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            expected_tables = ['activity_logs', 'alerts', 'voice_logs', 'reminders']
            for table in expected_tables:
                assert table in tables, f"Table '{table}' not found in database"
            print(f"✓ All required tables created: {', '.join(expected_tables)}")
            
            db.close()
            print("✓ Database connection closed successfully")
            return True
            
    except Exception as e:
        print(f"✗ Test 1 FAILED: {e}")
        return False


def test_log_activities() -> bool:
    """
    Test 2: Logging 5 sample activity entries.
    
    Returns:
        bool: True if all activities logged successfully
    """
    print("\n" + "=" * 70)
    print("TEST 2: Logging Activities (Motion Detection)")
    print("=" * 70)
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Database(db_path=f"{tmpdir}/test_elderly_care.db")
            
            # Initialize database
            assert db.connect() is True, "Failed to connect"
            
            # Log 5 sample activities
            activities = [
                (True, 0),      # Motion detected
                (True, 2),      # Motion detected
                (False, 15),    # No motion, 15 seconds inactivity
                (False, 30),    # No motion, 30 seconds inactivity
                (True, 0),      # Motion detected again
            ]
            
            logged_ids = []
            for motion_detected, inactivity in activities:
                activity_id = db.log_activity(motion_detected, inactivity)
                assert activity_id is not None and activity_id > 0, f"Failed to log activity"
                logged_ids.append(activity_id)
                status = "MOTION" if motion_detected else f"INACTIVE ({inactivity}s)"
                print(f"✓ Activity logged (ID: {activity_id}): {status}")
            
            # Verify all activities were
            logs = db.get_recent_logs('activity_logs', limit=10)
            assert len(logs) == 5, f"Expected 5 activities, found {len(logs)}"
            print(f"✓ All 5 activities verified in database")
            
            db.close()
            return True
            
    except Exception as e:
        print(f"✗ Test 2 FAILED: {e}")
        return False


def test_log_alerts() -> bool:
    """
    Test 3: Logging 2 sample alerts.
    
    Returns:
        bool: True if all alerts logged successfully
    """
    print("\n" + "=" * 70)
    print("TEST 3: Logging Alerts")
    print("=" * 70)
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Database(db_path=f"{tmpdir}/test_elderly_care.db")
            
            # Initialize database
            assert db.connect() is True, "Failed to connect"
            
            # Log 2 sample alerts
            alerts = [
                ("inactivity", "critical", "No motion detected for 2 minutes"),
                ("fall_detection", "high", "Potential fall detected in living room"),
            ]
            
            logged_ids = []
            for alert_type, severity, message in alerts:
                alert_id = db.log_alert(alert_type, severity, message)
                assert alert_id is not None and alert_id > 0, "Failed to log alert"
                logged_ids.append(alert_id)
                print(f"✓ Alert logged (ID: {alert_id}): {alert_type} [{severity.upper()}]")
                print(f"  Message: {message}")
            
            # Verify all alerts were logged
            logs = db.get_recent_logs('alerts', limit=10)
            assert len(logs) == 2, f"Expected 2 alerts, found {len(logs)}"
            print(f"✓ All 2 alerts verified in database")
            
            # Verify alert details
            for log in logs:
                assert log['resolved'] == 0, "Alert should not be resolved"
                print(f"  - {log['alert_type']}: {log['message']}")
            
            db.close()
            return True
            
    except Exception as e:
        print(f"✗ Test 3 FAILED: {e}")
        return False


def test_log_voice_interaction() -> bool:
    """
    Test 4: Logging 1 voice interaction.
    
    Returns:
        bool: True if voice interaction logged successfully
    """
    print("\n" + "=" * 70)
    print("TEST 4: Logging Voice Interaction")
    print("=" * 70)
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Database(db_path=f"{tmpdir}/test_elderly_care.db")
            
            # Initialize database
            assert db.connect() is True, "Failed to connect"
            
            # Log voice interaction
            transcript = "ନମସ୍କାର, ମୋ ଔଷଧ ସମୟ ହୋଇଛି?"
            intent = "medicine_query"
            response = "Your medicine time is scheduled. ଔଷଧ ସମୟ ହୋଇଛି."
            
            voice_id = db.log_voice_interaction(transcript, intent, response)
            assert voice_id is not None and voice_id > 0, "Failed to log voice interaction"
            print(f"✓ Voice interaction logged (ID: {voice_id})")
            print(f"  Transcript: {transcript}")
            print(f"  Intent: {intent}")
            print(f"  Response: {response}")
            
            # Verify voice interaction was logged
            logs = db.get_recent_logs('voice_logs', limit=10)
            assert len(logs) == 1, f"Expected 1 voice log, found {len(logs)}"
            print(f"✓ Voice interaction verified in database")
            
            # Verify details
            log = logs[0]
            assert log['transcript'] == transcript, "Transcript mismatch"
            assert log['intent'] == intent, "Intent mismatch"
            assert log['response'] == response, "Response mismatch"
            print(f"✓ All details match: transcript, intent, and response")
            
            db.close()
            return True
            
    except Exception as e:
        print(f"✗ Test 4 FAILED: {e}")
        return False


def test_retrieve_and_print_logs() -> bool:
    """
    Test 5: Retrieve and print recent logs from each table.
    
    Returns:
        bool: True if logs retrieved successfully
    """
    print("\n" + "=" * 70)
    print("TEST 5: Retrieving and Printing Logs")
    print("=" * 70)
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Database(db_path=f"{tmpdir}/test_elderly_care.db")
            
            # Initialize and populate database
            assert db.connect() is True, "Failed to connect"
            
            # Add multiple entries
            for i in range(3):
                db.log_activity(i % 2 == 0, i * 10)
            
            db.log_alert("test_alert_1", "low", "Test alert 1")
            db.log_alert("test_alert_2", "critical", "Test alert 2")
            
            db.log_voice_interaction("Test transcript 1", "greeting", "Hello")
            db.log_voice_interaction("Test transcript 2", "emergency", "Help incoming")
            
            # Retrieve and display logs
            tables = ['activity_logs', 'alerts', 'voice_logs']
            
            for table in tables:
                print(f"\n📋 {table.upper()} (limit=10):")
                print("-" * 70)
                
                logs = db.get_recent_logs(table, limit=10)
                assert logs is not None, f"Failed to retrieve logs from {table}"
                assert len(logs) > 0, f"No logs found in {table}"
                
                print(f"Total retrieved: {len(logs)} records\n")
                
                for i, log in enumerate(logs, 1):
                    print(f"Record {i}:")
                    for key, value in log.items():
                        print(f"  {key}: {value}")
                    print()
            
            print("✓ All logs retrieved and displayed successfully")
            db.close()
            return True
            
    except Exception as e:
        print(f"✗ Test 5 FAILED: {e}")
        return False


def test_data_integrity() -> bool:
    """
    Test 6: Verify data integrity with assertions.
    
    Returns:
        bool: True if all data integrity checks pass
    """
    print("\n" + "=" * 70)
    print("TEST 6: Data Integrity Verification")
    print("=" * 70)
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Database(db_path=f"{tmpdir}/test_elderly_care.db")
            
            # Initialize database
            assert db.connect() is True, "Failed to connect"
            
            # Test 1: Activity data types
            print("\n▸ Checking activity_logs data types...")
            activity_id = db.log_activity(True, 45)
            logs = db.get_recent_logs('activity_logs')
            log = logs[0]
            
            assert isinstance(log['id'], int), "ID should be integer"
            assert isinstance(log['motion_detected'], int), "motion_detected should be boolean/int"
            assert isinstance(log['inactivity_seconds'], (int, type(None))), "inactivity_seconds should be int or None"
            assert log['timestamp'] is not None, "timestamp should not be None"
            print("  ✓ Activity data types correct")
            
            # Test 2: Alert data integrity
            print("\n▸ Checking alerts data integrity...")
            alert_id = db.log_alert("severe_fall", "critical", "Fall detected in bedroom")
            logs = db.get_recent_logs('alerts')
            log = logs[0]
            
            assert log['alert_type'] == "severe_fall", "alert_type mismatch"
            assert log['severity'] == "critical", "severity mismatch"
            assert log['message'] == "Fall detected in bedroom", "message mismatch"
            assert log['resolved'] == 0, "resolved should be 0 (False)"
            print("  ✓ Alert data integrity verified")
            
            # Test 3: Voice interaction data integrity
            print("\n▸ Checking voice_logs data integrity...")
            voice_id = db.log_voice_interaction("Emergency help", "emergency", "Calling for help")
            logs = db.get_recent_logs('voice_logs')
            log = logs[0]
            
            assert log['transcript'] == "Emergency help", "transcript mismatch"
            assert log['intent'] == "emergency", "intent mismatch"
            assert log['response'] == "Calling for help", "response mismatch"
            print("  ✓ Voice interaction data integrity verified")
            
            # Test 4: Timestamp format
            print("\n▸ Checking timestamp format...")
            for table in ['activity_logs', 'alerts', 'voice_logs']:
                logs = db.get_recent_logs(table, limit=1)
                if logs:
                    timestamp = logs[0]['timestamp']
                    # Timestamp should be ISO format or similar
                    assert timestamp is not None, f"timestamp is None in {table}"
            print("  ✓ All timestamps present and valid")
            
            # Test 5: Insertion verification
            print("\n▸ Verifying all inserts returned valid IDs...")
            assert activity_id > 0, "Invalid activity ID returned"
            assert alert_id > 0, "Invalid alert ID returned"
            assert voice_id > 0, "Invalid voice ID returned"
            print("  ✓ All inserts returned valid IDs")
            
            print("\n✓ All data integrity checks PASSED")
            
            db.close()
            return True
            
    except Exception as e:
        print(f"✗ Test 6 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests() -> None:
    """Run all tests and print summary."""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 13 + "ELDERLY CARE SYSTEM - DATABASE TESTS" + " " * 20 + "║")
    print("╚" + "=" * 68 + "╝")
    
    tests = [
        ("Database Initialization", test_database_initialization),
        ("Log Activities", test_log_activities),
        ("Log Alerts", test_log_alerts),
        ("Log Voice Interaction", test_log_voice_interaction),
        ("Retrieve and Print Logs", test_retrieve_and_print_logs),
        ("Data Integrity", test_data_integrity),
    ]
    
    results = {}
    for test_name, test_func in tests:
        results[test_name] = test_func()
    
    # Print summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{test_name:.<50} {status}")
    
    print("=" * 70)
    print(f"\nTotal: {passed}/{total} tests passed\n")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! Database implementation is working correctly.")
    else:
        print(f"⚠️  {total - passed} test(s) failed. Please review the errors above.")


if __name__ == "__main__":
    run_all_tests()
