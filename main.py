"""
Main Module - System Orchestrator
Coordinates all system components: vision, voice, database, alerts, and reminders.
"""

import logging
import threading
import time
import signal
import sys
from pathlib import Path
from typing import Optional

# Configure path for imports
sys.path.insert(0, str(Path(__file__).parent))

from utils import (
    load_config,
    save_config,
    setup_logging,
    setup_data_directories,
    validate_config,
    print_header,
    print_section,
    get_system_info,
)

from modules.vision import MotionDetector
from modules.voice import VoiceAssistant
from modules.database import Database
from modules.alerts import AlertManager
from modules.scheduler import ReminderScheduler

logger = logging.getLogger(__name__)


class ElderlyCareSystem:
    """
    Main orchestrator for the elderly care monitoring system.
    Coordinates all components: vision, voice, database, alerts, reminders.
    """

    def __init__(self, config_path: str = "config.json") -> None:
        """
        Initialize the elderly care system.
        
        Args:
            config_path: Path to configuration file
        """
        self.config_path = config_path
        self.config = {}
        self.is_running = False
        
        # System components
        self.motion_detector: Optional[MotionDetector] = None
        self.voice_assistant: Optional[VoiceAssistant] = None
        self.database: Optional[Database] = None
        self.alert_manager: Optional[AlertManager] = None
        self.reminder_scheduler: Optional[ReminderScheduler] = None
        
        # Threads
        self.monitoring_thread: Optional[threading.Thread] = None
        self.voice_thread: Optional[threading.Thread] = None
        self.alert_thread: Optional[threading.Thread] = None

    def initialize(self) -> bool:
        """
        Initialize all system components.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            print_header("Elderly Care Monitoring System", 60)
            
            # Setup data directories
            print_section("Setting up data directories")
            if not setup_data_directories():
                logger.error("Failed to setup data directories")
                return False
            
            # Load and validate config
            print_section("Loading configuration")
            self.config = load_config(self.config_path)
            if not validate_config(self.config):
                logger.error("Configuration validation failed")
                return False
            
            # Setup logging
            print_section("Setting up logging")
            log_config = self.config.get("logging", {})
            setup_logging(
                log_file=log_config.get("file"),
                log_level=log_config.get("level", "INFO")
            )
            
            # Initialize database
            print_section("Initializing database")
            db_config = self.config.get("database", {})
            self.database = Database(
                db_path=db_config.get("path", "data/elderly_care.db"),
                retention_days=db_config.get("log_retention_days", 90)
            )
            if not self.database.connect():
                logger.error("Failed to initialize database")
                return False
            
            # Initialize motion detector
            print_section("Initializing vision system")
            vision_config = self.config.get("vision", {})
            resolution = vision_config.get("resolution", {})
            self.motion_detector = MotionDetector(
                camera_id=vision_config.get("camera_id", 0),
                resolution=(
                    resolution.get("width", 640),
                    resolution.get("height", 480)
                ),
                motion_threshold=vision_config.get("motion_threshold", 5000),
                inactivity_threshold_seconds=vision_config.get("inactivity_threshold_seconds", 3600),
                fps=vision_config.get("fps", 30)
            )
            if not self.motion_detector.initialize_camera():
                logger.warning("Camera initialization failed - continuing without vision")
            
            # Initialize voice assistant
            print_section("Initializing voice system")
            voice_config = self.config.get("voice", {})
            self.voice_assistant = VoiceAssistant(
                language=voice_config.get("language", "or"),
                sample_rate=voice_config.get("sample_rate", 16000),
                chunk_duration=voice_config.get("chunk_duration", 1024),
                timeout_seconds=voice_config.get("timeout_seconds", 10)
            )
            
            # Initialize alert manager
            print_section("Initializing alert system")
            alerts_config = self.config.get("alerts", {})
            self.alert_manager = AlertManager(
                caregiver_email=alerts_config.get("caregiver_email"),
                smtp_settings=alerts_config.get("smtp_settings")
            )
            
            # Initialize reminder scheduler
            print_section("Initializing reminder scheduler")
            self.reminder_scheduler = ReminderScheduler()
            self._setup_reminders()
            
            # Register voice intent handlers
            self._register_voice_handlers()
            
            logger.info("✓ System initialization successful")
            print_section("System ready")
            return True
            
        except Exception as e:
            logger.error(f"Error during initialization: {e}")
            return False

    def _setup_reminders(self) -> None:
        """Setup configured reminders."""
        try:
            reminders_config = self.config.get("reminders", {})
            
            for reminder_type, time_str in reminders_config.items():
                if not time_str:
                    continue
                
                # Create callback for this reminder
                def create_callback(rtype):
                    def reminder_callback():
                        logger.info(f"Reminder: {rtype}")
                        self.database.log_activity(
                            "reminder",
                            f"Reminder for {rtype}",
                            {"reminder_type": rtype}
                        )
                        
                        # Send reminder alert
                        if self.alert_manager:
                            self.alert_manager.send_reminder_alert(rtype, time_str)
                        
                        # Speak reminder
                        if self.voice_assistant:
                            self.voice_assistant.speak(
                                f"Reminder for {rtype}",
                                auto_play=True
                            )
                    
                    return reminder_callback
                
                self.reminder_scheduler.add_reminder(
                    name=reminder_type,
                    time_str=time_str,
                    description=f"Reminder for {reminder_type}",
                    callback=create_callback(reminder_type)
                )
            
            logger.info("Reminders setup complete")
            
        except Exception as e:
            logger.error(f"Error setting up reminders: {e}")

    def _register_voice_handlers(self) -> None:
        """Register handlers for voice intents."""
        try:
            if not self.voice_assistant:
                return
            
            def greeting_handler(intent_result):
                text = intent_result.get("text", "")
                self.voice_assistant.speak("Hello! How can I help you?")
                return "greeting_acknowledged"
            
            def reminder_handler(intent_result):
                upcoming = self.reminder_scheduler.get_upcoming_reminders(hours=24)
                if upcoming:
                    response = "Upcoming reminders: "
                    for r in upcoming[:3]:  # Mention next 3
                        response += f"{r['name']} at {r['time']}, "
                    self.voice_assistant.speak(response)
                else:
                    self.voice_assistant.speak("No upcoming reminders")
                return "reminders_announced"
            
            def help_handler(intent_result):
                self.voice_assistant.speak(
                    "I can help with reminders, check status, and more. Ask me anytime."
                )
                return "help_provided"
            
            def emergency_handler(intent_result):
                logger.critical("Emergency command detected!")
                if self.alert_manager:
                    self.alert_manager.send_emergency_alert("Emergency voice command detected")
                self.voice_assistant.speak("Emergency alert sent to caregiver")
                return "emergency_handled"
            
            # Register handlers
            self.voice_assistant.register_intent_handler("greeting", greeting_handler)
            self.voice_assistant.register_intent_handler("reminder", reminder_handler)
            self.voice_assistant.register_intent_handler("help", help_handler)
            self.voice_assistant.register_intent_handler("emergency", emergency_handler)
            
            logger.info("Voice handlers registered")
            
        except Exception as e:
            logger.error(f"Error registering voice handlers: {e}")

    def start(self) -> None:
        """Start all monitoring systems."""
        try:
            if self.is_running:
                logger.warning("System already running")
                return
            
            self.is_running = True
            print_section("Starting monitoring systems")
            
            # Start motion monitoring
            if self.motion_detector:
                self.motion_detector.start_monitoring(
                    callback=self._on_motion_frame
                )
            
            # Start voice listening
            if self.voice_assistant:
                self.voice_thread = threading.Thread(
                    target=self.voice_assistant.start_voice_loop,
                    daemon=True
                )
                self.voice_thread.start()
            
            # Start reminder scheduler
            if self.reminder_scheduler:
                self.reminder_scheduler.start_scheduler()
            
            # Start maintenance thread
            self.monitoring_thread = threading.Thread(
                target=self._maintenance_loop,
                daemon=True
            )
            self.monitoring_thread.start()
            
            logger.info("✓ All monitoring systems started")
            print("\n✓ System is running. Press Ctrl+C to stop.\n")
            
        except Exception as e:
            logger.error(f"Error starting system: {e}")

    def _on_motion_frame(self, motion_detected: bool, frame, inactivity_seconds: int) -> None:
        """
        Callback for motion detection frames.
        
        Args:
            motion_detected: Whether motion was detected in frame
            frame: Video frame
            inactivity_seconds: Duration of inactivity
        """
        try:
            # Log motion event periodically (not every frame)
            if motion_detected:
                logger.debug("Motion detected")
            else:
                # Check for inactivity alert
                vision_config = self.config.get("vision", {})
                threshold = vision_config.get("inactivity_threshold_seconds", 3600)
                
                if inactivity_seconds > threshold:
                    logger.warning(f"Inactivity detected: {inactivity_seconds} seconds")
                    
                    # Send alert
                    if self.alert_manager:
                        self.alert_manager.send_inactivity_alert(
                            inactivity_seconds,
                            threshold
                        )
                    
                    # Log to database
                    if self.database:
                        self.database.log_alert(
                            alert_type="inactivity",
                            severity="high",
                            message=f"No motion detected for {inactivity_seconds // 3600} hours",
                            data={"inactivity_seconds": inactivity_seconds}
                        )
            
            # Log to database periodically
            if self.database and int(time.time()) % 60 == 0:  # Every 60 seconds
                self.database.log_motion_event(motion_detected, inactivity_seconds)
        
        except Exception as e:
            logger.error(f"Error in motion callback: {e}")

    def _maintenance_loop(self) -> None:
        """Periodic maintenance tasks."""
        try:
            cleanup_interval = 3600  # 1 hour
            last_cleanup = time.time()
            
            while self.is_running:
                current_time = time.time()
                
                # Cleanup old records
                if current_time - last_cleanup > cleanup_interval:
                    if self.database:
                        db_config = self.config.get("database", {})
                        self.database.cleanup_old_records(
                            days=db_config.get("log_retention_days", 90)
                        )
                    last_cleanup = current_time
                
                time.sleep(60)  # Check every minute
        
        except Exception as e:
            logger.error(f"Error in maintenance loop: {e}")

    def stop(self) -> None:
        """Stop all monitoring systems."""
        try:
            if not self.is_running:
                return
            
            self.is_running = False
            print_section("Stopping monitoring systems")
            
            # Stop motion detection
            if self.motion_detector:
                self.motion_detector.stop_monitoring()
                self.motion_detector.release()
            
            # Stop voice assistant
            if self.voice_assistant:
                self.voice_assistant.stop_listening()
                self.voice_assistant.cleanup()
            
            # Stop scheduler
            if self.reminder_scheduler:
                self.reminder_scheduler.stop_scheduler()
            
            # Close alert manager
            if self.alert_manager:
                self.alert_manager.close()
            
            # Close database
            if self.database:
                self.database.close()
            
            logger.info("✓ All systems stopped")
            print("\n✓ System stopped.\n")
        
        except Exception as e:
            logger.error(f"Error stopping system: {e}")

    def status(self) -> None:
        """Print system status."""
        try:
            print_section("System Status")
            
            status_info = {
                "is_running": self.is_running,
                "motion_detector": self.motion_detector.get_status() if self.motion_detector else None,
                "voice_assistant": self.voice_assistant.get_status() if self.voice_assistant else None,
                "reminder_scheduler": self.reminder_scheduler.get_status() if self.reminder_scheduler else None,
                "system_info": get_system_info(),
            }
            
            for component, info in status_info.items():
                if info:
                    print(f"\n{component.upper()}: {info}")
        
        except Exception as e:
            logger.error(f"Error getting system status: {e}")


def signal_handler(sig, frame):
    """Handle interrupt signals."""
    print("\n\n" + "=" * 50)
    print("  Shutdown signal received")
    print("=" * 50)
    
    if hasattr(signal_handler, 'system') and signal_handler.system:
        signal_handler.system.stop()
    
    sys.exit(0)


def main():
    """Main entry point."""
    try:
        # Create system instance
        system = ElderlyCareSystem()
        signal_handler.system = system  # Store for signal handling
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Initialize
        if not system.initialize():
            logger.error("System initialization failed")
            return False
        
        # Start
        system.start()
        
        # Print status
        system.status()
        
        # Keep alive
        try:
            while system.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        
        return True
    
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
