"""
Elderly Care Monitoring System Modules
Module package containing all core components for the monitoring system.
"""

from .vision import MotionDetector, CameraHandler, ActivityTracker
from .voice import VoiceAssistant
from .database import Database
from .alerts import AlertManager
from .scheduler import ReminderScheduler

__version__ = "1.0.0"
__author__ = "Development Team"

__all__ = [
    "MotionDetector",
    "CameraHandler",
    "ActivityTracker",
    "VoiceAssistant",
    "Database",
    "AlertManager",
    "ReminderScheduler",
]
