"""
Alert Manager Test Script - Elderly Care Monitoring System

Comprehensive tests for AlertManager email functionality including:
1. SMTP connection verification
2. Test email with HTML formatting
3. Inactivity alert with duration formatting
4. Emergency alert with urgent messaging
5. Success/failure handling and logging

IMPORTANT: Gmail Setup Instructions
===================================

To use this with Gmail:

1. Enable 2-Factor Authentication:
   - Visit: https://myaccount.google.com/security
   - Enable "2-Step Verification"

2. Create an App Password:
   - Visit: https://myaccount.google.com/apppasswords
   - Select "Mail" and "Windows Computer" (or your device)
   - Google will generate a 16-character password
   - Copy this password (remove spaces)

3. Set Environment Variable:
   - Export GMAIL_APP_PASSWORD="your16charpassword"
   - Or add to .env file

4. Use App Email in config.json:
   - "smtp_user": "your-email@gmail.com"
   - Do NOT use your regular Gmail password
   - Use the 16-character app password instead

For other SMTP providers:
- Update smtp_server and smtp_port in config.json
- Use your regular password (app passwords are Gmail-specific)
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime
import sys

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import database and alerts modules
sys.path.insert(0, str(Path(__file__).parent))
from modules.database import Database
from modules.alerts import AlertManager


def load_config() -> dict:
    """Load configuration from config.json."""
    config_path = Path(__file__).parent / "config.json"
    
    if not config_path.exists():
        logger.error(f"config.json not found at {config_path}")
        return {}
    
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading config.json: {e}")
        return {}


def get_smtp_credentials() -> dict:
    """
    Get SMTP credentials from config and environment variables.
    
    Returns:
        Dictionary with smtp configuration
    """
    config = load_config()
    
    # Get from config
    smtp_config = config.get("alerts", {})
    
    # Try to get password from environment variable first
    smtp_pass = os.environ.get("GMAIL_APP_PASSWORD")
    
    # Fall back to config if not in environment
    if not smtp_pass:
        smtp_pass = smtp_config.get("smtp_password")
    
    # Build credentials dictionary
    credentials = {
        "caregiver_email": smtp_config.get("caregiver_email", ""),
        "smtp_user": smtp_config.get("smtp_user", ""),
        "smtp_pass": smtp_pass or "",
        "smtp_server": smtp_config.get("smtp_server", "smtp.gmail.com"),
        "smtp_port": int(smtp_config.get("smtp_port", 587)),
    }
    
    return credentials


def test_connection(alert_manager: AlertManager) -> bool:
    """
    Test 1: Verify SMTP connection.
    
    Args:
        alert_manager: AlertManager instance
        
    Returns:
        bool: True if connection successful
    """
    print("\n" + "=" * 70)
    print("TEST 1: SMTP Connection Verification")
    print("=" * 70)
    
    success, message = alert_manager.test_connection()
    print(f"\n{message}\n")
    
    if success:
        print("✓ Connection test PASSED")
    else:
        print("✗ Connection test FAILED")
        print("\nTroubleshooting:")
        print("1. Verify SMTP credentials in config.json")
        print("2. For Gmail: Use app password, not regular password")
        print("3. Ensure 2-Factor Authentication is enabled on Gmail")
        print("4. Check firewall/proxy settings for port 587")
    
    return success


def test_email_alert(alert_manager: AlertManager) -> bool:
    """
    Test 2: Send test email alert.
    
    Args:
        alert_manager: AlertManager instance
        
    Returns:
        bool: True if email sent successfully
    """
    print("\n" + "=" * 70)
    print("TEST 2: Send Test Email Alert")
    print("=" * 70)
    
    subject = "Elderly Care System - Test Alert"
    body = """This is a test email from the Elderly Care Monitoring System.

Testing Information:
- Timestamp: """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """
- Test Type: HTML Email Formatting
- From: Automated Test Suite
- Email Service: Working correctly if you received this

If you received this email, the alert system is functioning properly.
No action is required for this test message.

Best regards,
Elderly Care Monitoring System"""
    
    print(f"\nSending test email to: {alert_manager.caregiver_email}")
    print(f"Subject: {subject}")
    
    result = alert_manager.send_email(
        subject=subject,
        body=body,
        alert_type="TEST",
        severity="low"
    )
    
    if result:
        print("\n✓ Test email sent successfully")
        print("  Check your inbox (and spam folder) for the email")
    else:
        print("\n✗ Failed to send test email")
        print("  Check logs for detailed error information")
    
    return result


def test_inactivity_alert(alert_manager: AlertManager) -> bool:
    """
    Test 3: Send inactivity alert.
    
    Args:
        alert_manager: AlertManager instance
        
    Returns:
        bool: True if alert sent successfully
    """
    print("\n" + "=" * 70)
    print("TEST 3: Send Inactivity Alert (30 minutes)")
    print("=" * 70)
    
    # Test with 30 minutes inactivity (1800 seconds)
    duration_seconds = 1800
    
    print(f"\nSimulating inactivity duration: {duration_seconds} seconds (30 minutes)")
    print(f"Recipient: {alert_manager.caregiver_email}")
    
    result = alert_manager.send_inactivity_alert(duration_seconds)
    
    if result:
        print("\n✓ Inactivity alert sent successfully")
        print(f"  Alert formatted for {duration_seconds // 3600}h {(duration_seconds % 3600) // 60}m")
    else:
        print("\n✗ Failed to send inactivity alert")
    
    return result


def test_emergency_alert(alert_manager: AlertManager) -> bool:
    """
    Test 4: Send emergency alert.
    
    Args:
        alert_manager: AlertManager instance
        
    Returns:
        bool: True if alert sent successfully
    """
    print("\n" + "=" * 70)
    print("TEST 4: Send Emergency Alert")
    print("=" * 70)
    
    print(f"\nSending emergency alert to: {alert_manager.caregiver_email}")
    print("Alert Source: Test System")
    print("Alert Type: Critical")
    
    result = alert_manager.send_emergency_alert(
        source="test",
        details="This is a test emergency alert to verify alert system functionality."
    )
    
    if result:
        print("\n✓ Emergency alert sent successfully")
        print("  This should have high priority in your inbox")
    else:
        print("\n✗ Failed to send emergency alert")
    
    return result


def verify_alert_history(alert_manager: AlertManager) -> None:
    """
    Test 5: Verify alert history and logging.
    
    Args:
        alert_manager: AlertManager instance
    """
    print("\n" + "=" * 70)
    print("TEST 5: Alert History and Logging")
    print("=" * 70)
    
    history = alert_manager.get_alert_history(limit=10)
    
    print(f"\nTotal alerts in history: {len(history)}")
    print("\nRecent alert attempts:")
    print("-" * 70)
    
    for i, alert in enumerate(history[-5:], 1):
        print(f"\n{i}. {alert['alert_type'].upper()}")
        print(f"   Subject: {alert['subject'][:60]}...")
        print(f"   Severity: {alert['severity']}")
        print(f"   Status: {alert['status']}")
        print(f"   Timestamp: {alert['timestamp']}")
        if alert.get('reason'):
            print(f"   Reason: {alert['reason']}")
    
    # Check for critical alerts
    critical = alert_manager.get_critical_alerts()
    if critical:
        print(f"\n⚠️  Found {len(critical)} critical alerts in history")
    
    print("\n✓ Alert history verification complete")


def run_all_tests() -> None:
    """Run all AlertManager tests."""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 12 + "ELDERLY CARE SYSTEM - ALERT MANAGER TESTS" + " " * 15 + "║")
    print("╚" + "=" * 68 + "╝")
    
    # Load credentials
    print("\nLoading SMTP credentials...")
    credentials = get_smtp_credentials()
    
    # Validate credentials
    if not credentials["caregiver_email"]:
        print("✗ ERROR: caregiver_email not configured in config.json")
        print("\nPlease add the following to config.json:")
        print("""
{
  "alerts": {
    "caregiver_email": "your-relative-email@gmail.com",
    "smtp_user": "your-email@gmail.com",
    "smtp_password": "your-16-char-app-password",
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587
  }
}
""")
        return
    
    if not credentials["smtp_user"]:
        print("✗ ERROR: smtp_user not configured in config.json")
        return
    
    if not credentials["smtp_pass"]:
        print("✗ ERROR: smtp_password not found in config.json or GMAIL_APP_PASSWORD environment variable")
        print("\nFor Gmail:")
        print("1. Create an App Password at https://myaccount.google.com/apppasswords")
        print("2. Set environment variable: export GMAIL_APP_PASSWORD='your-16-char-password'")
        print("3. Or add smtp_password to config.json")
        return
    
    print(f"✓ Credentials loaded")
    print(f"  Sender: {credentials['smtp_user']}")
    print(f"  Recipient: {credentials['caregiver_email']}")
    print(f"  SMTP Server: {credentials['smtp_server']}:{credentials['smtp_port']}")
    
    # Try to initialize database (optional)
    database = None
    try:
        database = Database()
        if database.connect():
            print(f"✓ Database connection successful")
        else:
            print("⚠️  Database connection failed (alerts will still work)")
            database = None
    except Exception as e:
        logger.warning(f"Could not initialize database: {e}")
    
    # Initialize AlertManager
    alert_manager = AlertManager(
        caregiver_email=credentials["caregiver_email"],
        smtp_user=credentials["smtp_user"],
        smtp_pass=credentials["smtp_pass"],
        smtp_server=credentials["smtp_server"],
        smtp_port=credentials["smtp_port"],
        database=database,
    )
    
    # Run tests
    tests = [
        ("Connection Test", lambda: test_connection(alert_manager)),
        ("Test Email", lambda: test_email_alert(alert_manager)),
        ("Inactivity Alert", lambda: test_inactivity_alert(alert_manager)),
        ("Emergency Alert", lambda: test_emergency_alert(alert_manager)),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"✗ {test_name} encountered an error: {e}")
            logger.exception(f"Error in {test_name}")
            results[test_name] = False
    
    # Verify history
    try:
        verify_alert_history(alert_manager)
    except Exception as e:
        logger.warning(f"Could not verify alert history: {e}")
    
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
    
    # Cleanup
    try:
        alert_manager.close()
        if database:
            database.close()
        logger.info("All connections closed")
    except Exception as e:
        logger.warning(f"Error during cleanup: {e}")
    
    # Final instructions
    if passed == total:
        print("🎉 ALL TESTS PASSED!")
        print("\nNext Steps:")
        print("1. Check your email inbox (and spam folder) for test messages")
        print("2. Verify you received 3 emails:")
        print("   - Test Alert (low priority)")
        print("   - Inactivity Alert (high priority)")
        print("   - Emergency Alert (critical priority)")
        print("3. If any emails are missing, check SMTP settings and firewall")
    else:
        print(f"⚠️  {total - passed} test(s) failed")
        print("\nCommon issues:")
        print("1. Gmail: Use app password, not regular password")
        print("2. Check caregiver_email is different from smtp_user")
        print("3. Verify 2-Factor Authentication is enabled (for Gmail)")
        print("4. Check firewall allows outbound traffic on port 587")


if __name__ == "__main__":
    run_all_tests()
