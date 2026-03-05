"""
Alerts Module - Email Alerts and Notification Management
Handles sending email alerts to caregivers and managing alert status.
"""

import yagmail
import logging
from typing import Optional, Dict, List, Tuple
from datetime import datetime
from pathlib import Path
import json
import time

logger = logging.getLogger(__name__)


class AlertManager:
    """
    Manages alerts and notifications to caregivers via email.
    
    Features:
    - HTML email formatting with timestamps
    - Retry logic (3 attempts) for failed sends
    - Database logging of all alert attempts
    - Connection testing and verification
    - Professional alert formatting
    
    Attributes:
        caregiver_email: Primary recipient email address
        smtp_user: SMTP sender email address
        smtp_pass: SMTP password (app password for Gmail)
        smtp_server: SMTP server hostname
        smtp_port: SMTP server port
        yag: yagmail SMTP connection
        database: Optional database connection for logging
    """

    def __init__(
        self,
        caregiver_email: str,
        smtp_user: str,
        smtp_pass: str,
        smtp_server: str = "smtp.gmail.com",
        smtp_port: int = 587,
        database: Optional[object] = None,
    ) -> None:
        """
        Initialize AlertManager with SMTP credentials.
        
        Args:
            caregiver_email: Email address of primary caregiver
            smtp_user: SMTP sender email (gmail account)
            smtp_pass: SMTP password or app password
            smtp_server: SMTP server hostname (default: Gmail)
            smtp_port: SMTP server port (default: 587 for TLS)
            database: Optional Database instance for logging
        """
        self.caregiver_email = caregiver_email
        self.smtp_user = smtp_user
        self.smtp_pass = smtp_pass
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.database = database
        self.yag: Optional[yagmail.SMTP] = None
        self.alert_history: List[Dict] = []
        self.max_retries = 3
        self.retry_delay = 2  # seconds
        
        # Try to initialize email connection
        self._initialize_email()

    def _initialize_email(self) -> bool:
        """
        Initialize SMTP connection for email sending.
        
        Returns:
            bool: True if connection successful
        """
        try:
            self.yag = yagmail.SMTP(
                user=self.smtp_user,
                password=self.smtp_pass,
                host=self.smtp_server,
                port=self.smtp_port,
            )
            logger.info(f"Email connection initialized: {self.smtp_user}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize email connection: {e}")
            self.yag = None
            return False

    def test_connection(self) -> Tuple[bool, str]:
        """
        Test SMTP connection and credentials.
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            test_yag = yagmail.SMTP(
                user=self.smtp_user,
                password=self.smtp_pass,
                host=self.smtp_server,
                port=self.smtp_port,
            )
            test_yag.close()
            message = f"✓ Connection successful: {self.smtp_user} → {self.caregiver_email}"
            logger.info(message)
            return True, message
            
        except Exception as e:
            message = f"✗ Connection failed: {str(e)}"
            logger.error(message)
            return False, message

    def send_email(
        self,
        subject: str,
        body: str,
        alert_type: str = "INFO",
        severity: str = "medium",
    ) -> bool:
        """
        Send HTML-formatted email alert with retry logic.
        
        Args:
            subject: Email subject line
            body: Email body content
            alert_type: Type/category of alert
            severity: Severity level (low, medium, high, critical)
            
        Returns:
            bool: True if email sent successfully
        """
        if not self.yag:
            logger.warning("Email not initialized - cannot send alert")
            self._log_alert_attempt(subject, body, alert_type, severity, status="failed", reason="Not initialized")
            return False
        
        html_content = self._format_html_email(subject, body, alert_type, severity)
        
        # Retry logic
        for attempt in range(1, self.max_retries + 1):
            try:
                self.yag.send(
                    to=self.caregiver_email,
                    subject=subject,
                    contents=html_content,
                )
                
                logger.info(f"Alert sent successfully (attempt {attempt}): {subject}")
                self._log_alert_attempt(subject, body, alert_type, severity, status="sent", attempt=attempt)
                return True
                
            except Exception as e:
                logger.warning(f"Failed to send (attempt {attempt}/{self.max_retries}): {e}")
                
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"Failed to send alert after {self.max_retries} attempts: {subject}")
                    self._log_alert_attempt(subject, body, alert_type, severity, status="failed", 
                                          attempt=attempt, reason=str(e))
                    return False
        
        return False

    def _format_html_email(
        self,
        subject: str,
        body: str,
        alert_type: str,
        severity: str,
    ) -> str:
        """
        Format email as professional HTML.
        
        Args:
            subject: Email subject
            body: Email body
            alert_type: Alert type
            severity: Severity level
            
        Returns:
            HTML-formatted email content
        """
        severity_colors = {
            "low": "#4CAF50",      # Green
            "medium": "#FFC107",   # Amber
            "high": "#FF9800",     # Orange
            "critical": "#F44336", # Red
        }
        
        color = severity_colors.get(severity.lower(), "#2196F3")
        
        html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; border: 1px solid #ddd; border-radius: 8px; overflow: hidden;">
                    <!-- Header -->
                    <div style="background-color: {color}; color: white; padding: 20px; text-align: center;">
                        <h2 style="margin: 0; font-size: 24px;">🚨 ELDERLY CARE SYSTEM ALERT</h2>
                    </div>
                    
                    <!-- Alert Info -->
                    <div style="padding: 20px; background-color: #f9f9f9;">
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr>
                                <td style="padding: 8px; font-weight: bold; width: 150px;">Alert Type:</td>
                                <td style="padding: 8px;">{alert_type.upper()}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px; font-weight: bold;">Severity:</td>
                                <td style="padding: 8px; color: {color}; font-weight: bold;">{severity.upper()}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px; font-weight: bold;">Timestamp:</td>
                                <td style="padding: 8px;">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td>
                            </tr>
                        </table>
                    </div>
                    
                    <!-- Message Body -->
                    <div style="padding: 20px; border-top: 2px solid #ddd;">
                        <h3 style="color: {color}; margin-top: 0;">Details:</h3>
                        <p style="white-space: pre-wrap; background-color: #f5f5f5; padding: 15px; border-radius: 4px; border-left: 4px solid {color};">
{body}
                        </p>
                    </div>
                    
                    <!-- Action Required -->
                    <div style="padding: 20px; background-color: #fff3cd; border-top: 2px solid #ddd;">
                        <p style="margin: 0; color: #856404; font-weight: bold;">
                            ⚠️ ACTION REQUIRED: Please respond to this alert immediately if you have not already done so.
                        </p>
                    </div>
                    
                    <!-- Footer -->
                    <div style="padding: 15px; background-color: #f0f0f0; text-align: center; font-size: 12px; color: #666;">
                        <p style="margin: 5px 0;">This is an automated alert from the Elderly Care Monitoring System.</p>
                        <p style="margin: 5px 0;">Do not reply to this email. Please contact the system administrator if you have questions.</p>
                    </div>
                </div>
            </body>
        </html>
        """
        return html

    def send_inactivity_alert(self, duration_seconds: int) -> bool:
        """
        Send formatted inactivity alert.
        
        Args:
            duration_seconds: Duration of inactivity detected
            
        Returns:
            bool: True if alert sent successfully
        """
        hours = duration_seconds // 3600
        minutes = (duration_seconds % 3600) // 60
        seconds = duration_seconds % 60
        
        subject = f"⚠️ ALERT: Inactivity Detected ({hours}h {minutes}m)"
        
        body = f"""No motion detected for {hours} hours, {minutes} minutes, and {seconds} seconds.

IMMEDIATE ACTION REQUIRED:
• Check on the elderly person immediately
• Ensure they are safe and responsive
• Contact emergency services if necessary
• Verify they can move/interact normally

This alert was triggered by the motion detection system.
If the person is resting or sleeping, you can dismiss this alert.
Consider adjusting the inactivity threshold if false positives occur."""
        
        return self.send_email(
            subject,
            body,
            alert_type="inactivity",
            severity="high"
        )

    def send_emergency_alert(self, source: str = "system", details: str = "") -> bool:
        """
        Send urgent emergency alert.
        
        Args:
            source: Source of emergency ('voice', 'vision', 'system', 'test')
            details: Additional details about the emergency
            
        Returns:
            bool: True if alert sent successfully
        """
        subject = "🚨 EMERGENCY ALERT: IMMEDIATE ACTION REQUIRED"
        
        source_info = {
            "voice": "Voice System - Elderly person called for help",
            "vision": "Vision System - Potential fall detected",
            "system": "System - Critical error detected",
            "test": "Test - Alert system verification",
        }
        
        source_desc = source_info.get(source, f"Unknown source: {source}")
        
        body = f"""EMERGENCY SITUATION DETECTED!

Source: {source_desc}
Details: {details if details else "No additional details provided"}

IMMEDIATE ACTIONS REQUIRED:
1. Contact the elderly person immediately
2. Call emergency services (911) if necessary
3. Go to the location if possible
4. Stay calm and provide immediate assistance
5. Report status back to the system

This is a critical alert requiring your immediate attention.
DO NOT IGNORE THIS MESSAGE."""
        
        return self.send_email(
            subject,
            body,
            alert_type="emergency",
            severity="critical"
        )

    def _log_alert_attempt(
        self,
        subject: str,
        body: str,
        alert_type: str,
        severity: str,
        status: str = "logged",
        attempt: int = 0,
        reason: str = "",
    ) -> None:
        """
        Log alert attempt locally and to database if available.
        
        Args:
            subject: Alert subject
            body: Alert body
            alert_type: Alert type
            severity: Alert severity
            status: Send status
            attempt: Attempt number
            reason: Failure reason if applicable
        """
        alert_record = {
            "timestamp": datetime.now().isoformat(),
            "subject": subject,
            "body": body,
            "alert_type": alert_type,
            "severity": severity,
            "status": status,
            "attempt": attempt,
            "recipient": self.caregiver_email,
            "reason": reason,
        }
        
        # Store locally
        self.alert_history.append(alert_record)
        
        # Log to database if available
        if self.database:
            try:
                self.database.log_alert(
                    alert_type=alert_type,
                    severity=severity,
                    message=subject,
                )
            except Exception as e:
                logger.warning(f"Failed to log alert to database: {e}")


    def get_alert_history(
        self,
        alert_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """
        Get alert history.
        
        Args:
            alert_type: Filter by alert type (optional)
            limit: Maximum number of records to return
            
        Returns:
            List of alert records
        """
        records = self.alert_history
        
        if alert_type:
            records = [r for r in records if r["alert_type"] == alert_type]
        
        return records[-limit:]

    def get_critical_alerts(self) -> List[Dict]:
        """
        Get all critical severity alerts.
        
        Returns:
            List of critical severity alert records
        """
        return [r for r in self.alert_history if r.get("severity") == "critical"]

    def export_alerts(self, filepath: str) -> bool:
        """
        Export alert history to JSON file.
        
        Args:
            filepath: Path to export file
            
        Returns:
            bool: True if export successful
        """
        try:
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            
            with open(filepath, 'w') as f:
                json.dump(self.alert_history, f, indent=2)
            
            logger.info(f"Alerts exported to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting alerts: {e}")
            return False

    def clear_history(self) -> None:
        """Clear all alert history."""
        self.alert_history.clear()
        logger.info("Alert history cleared")

    def close(self) -> None:
        """Close email connection."""
        if self.yag:
            try:
                self.yag.close()
                logger.info("Email connection closed")
            except Exception as e:
                logger.error(f"Error closing connection: {e}")

