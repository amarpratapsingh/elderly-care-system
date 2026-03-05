"""
Scheduler Module - Reminder Scheduling and Time-based Tasks
Handles medication reminders and other scheduled tasks.
"""

import schedule
import threading
import logging
from typing import Callable, Dict, Optional, List
from datetime import datetime, time
from pathlib import Path

logger = logging.getLogger(__name__)


class ReminderScheduler:
    """
    Scheduler for managing reminders and scheduled tasks.
    
    Attributes:
        reminders: Dictionary of configured reminders
    """

    def __init__(self) -> None:
        """Initialize the ReminderScheduler."""
        self.schedule = schedule.Scheduler()
        self.reminders: Dict[str, Dict] = {}
        self.callbacks: Dict[str, Callable] = {}
        self.is_running = False
        self.scheduler_thread: Optional[threading.Thread] = None

    def add_reminder(
        self,
        name: str,
        time_str: str,
        description: str = "",
        callback: Optional[Callable] = None,
    ) -> bool:
        """
        Add a reminder at specified time.
        
        Args:
            name: Unique reminder name
            time_str: Time in HH:MM format
            description: Reminder description
            callback: Optional callback function to execute
            
        Returns:
            bool: True if reminder added successfully
        """
        try:
            # Validate time format
            reminder_time = datetime.strptime(time_str, "%H:%M").time()
            
            # Create reminder entry
            reminder_data = {
                "name": name,
                "time": time_str,
                "description": description,
                "last_triggered": None,
                "created_at": datetime.now().isoformat(),
            }
            
            self.reminders[name] = reminder_data
            
            # Schedule the job
            job = self.schedule.at(time_str).do(self._execute_reminder, name)
            
            # Store callback if provided
            if callback:
                self.callbacks[name] = callback
            
            logger.info(f"Reminder added: {name} at {time_str}")
            return True
            
        except ValueError:
            logger.error(f"Invalid time format: {time_str}. Use HH:MM")
            return False
        except Exception as e:
            logger.error(f"Error adding reminder: {e}")
            return False

    def _execute_reminder(self, reminder_name: str) -> None:
        """
        Execute a scheduled reminder.
        
        Args:
            reminder_name: Name of the reminder to execute
        """
        try:
            logger.info(f"Executing reminder: {reminder_name}")
            
            # Update last triggered time
            if reminder_name in self.reminders:
                self.reminders[reminder_name]["last_triggered"] = datetime.now().isoformat()
            
            # Execute callback if registered
            if reminder_name in self.callbacks:
                try:
                    self.callbacks[reminder_name]()
                except Exception as e:
                    logger.error(f"Error in reminder callback: {e}")
            
            logger.info(f"Reminder executed: {reminder_name}")
            
        except Exception as e:
            logger.error(f"Error executing reminder: {e}")

    def remove_reminder(self, name: str) -> bool:
        """
        Remove a reminder.
        
        Args:
            name: Reminder name
            
        Returns:
            bool: True if removed successfully
        """
        try:
            if name in self.reminders:
                del self.reminders[name]
            
            if name in self.callbacks:
                del self.callbacks[name]
            
            # Find and remove scheduled job
            for job in self.schedule.get_jobs():
                if hasattr(job, 'job_func') and job.job_func.func.__name__ == '_execute_reminder':
                    if job.job_func.args and job.job_func.args[0] == name:
                        self.schedule.cancel_job(job)
            
            logger.info(f"Reminder removed: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Error removing reminder: {e}")
            return False

    def get_reminder(self, name: str) -> Optional[Dict]:
        """
        Get reminder details.
        
        Args:
            name: Reminder name
            
        Returns:
            Reminder data or None
        """
        return self.reminders.get(name)

    def get_all_reminders(self) -> List[Dict]:
        """
        Get all configured reminders.
        
        Returns:
            List of reminder data
        """
        return list(self.reminders.values())

    def start_scheduler(self) -> None:
        """
        Start the scheduler in a separate thread.
        Runs continuously checking for scheduled tasks.
        """
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
        
        self.is_running = True
        self.scheduler_thread = threading.Thread(
            target=self._run_scheduler_loop,
            daemon=True,
        )
        self.scheduler_thread.start()
        logger.info("Scheduler started")

    def _run_scheduler_loop(self) -> None:
        """Main scheduler loop running in separate thread."""
        try:
            while self.is_running:
                self.schedule.run_pending()
                # Check every 10 seconds
                threading.Event().wait(10)
            
        except Exception as e:
            logger.error(f"Error in scheduler loop: {e}")
        finally:
            self.is_running = False

    def stop_scheduler(self) -> None:
        """Stop the scheduler."""
        self.is_running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        logger.info("Scheduler stopped")

    def register_callback(self, reminder_name: str, callback: Callable) -> bool:
        """
        Register a callback for a reminder.
        
        Args:
            reminder_name: Name of the reminder
            callback: Callback function to execute
            
        Returns:
            bool: True if registered successfully
        """
        try:
            if reminder_name not in self.reminders:
                logger.warning(f"Reminder not found: {reminder_name}")
                return False
            
            self.callbacks[reminder_name] = callback
            logger.info(f"Callback registered for reminder: {reminder_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error registering callback: {e}")
            return False

    def get_next_reminder(self) -> Optional[Dict]:
        """
        Get the next scheduled reminder.
        
        Returns:
            Dictionary with reminder info or None
        """
        try:
            jobs = self.schedule.get_jobs()
            if not jobs:
                return None
            
            # Get the next job
            next_job = min(jobs, key=lambda x: x.next_run)
            
            # Extract reminder name from job
            if hasattr(next_job, 'job_func') and next_job.job_func.args:
                reminder_name = next_job.job_func.args[0]
                reminder = self.get_reminder(reminder_name)
                if reminder:
                    reminder["next_run"] = next_job.next_run.isoformat()
                    return reminder
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting next reminder: {e}")
            return None

    def get_upcoming_reminders(self, hours: int = 24) -> List[Dict]:
        """
        Get upcoming reminders within specified hours.
        
        Args:
            hours: Number of hours to look ahead
            
        Returns:
            List of upcoming reminders
        """
        try:
            upcoming = []
            current_time = datetime.now()
            
            for reminder_name, reminder_data in self.reminders.items():
                reminder_time = datetime.strptime(reminder_data["time"], "%H:%M").time()
                reminder_datetime = datetime.combine(current_time.date(), reminder_time)
                
                # If time has passed today, look at tomorrow
                if reminder_datetime <= current_time:
                    from datetime import timedelta
                    reminder_datetime += timedelta(days=1)
                
                # Check if within time window
                time_diff = (reminder_datetime - current_time).total_seconds() / 3600
                if 0 <= time_diff <= hours:
                    reminder_copy = reminder_data.copy()
                    reminder_copy["next_run"] = reminder_datetime.isoformat()
                    reminder_copy["hours_until"] = time_diff
                    upcoming.append(reminder_copy)
            
            # Sort by time
            upcoming.sort(key=lambda x: x["hours_until"])
            return upcoming
            
        except Exception as e:
            logger.error(f"Error getting upcoming reminders: {e}")
            return []

    def get_status(self) -> Dict:
        """
        Get scheduler status.
        
        Returns:
            Dictionary with status information
        """
        return {
            "is_running": self.is_running,
            "total_reminders": len(self.reminders),
            "scheduled_jobs": len(self.schedule.get_jobs()),
            "next_reminder": self.get_next_reminder(),
            "reminders": self.get_all_reminders(),
        }

    def clear_all_reminders(self) -> None:
        """Clear all reminders."""
        try:
            self.schedule.clear()
            self.reminders.clear()
            self.callbacks.clear()
            logger.info("All reminders cleared")
        except Exception as e:
            logger.error(f"Error clearing reminders: {e}")
