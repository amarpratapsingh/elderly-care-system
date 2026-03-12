"""
Utility Module - Helper Functions
Common utility functions for configuration, logging, and time handling.
"""

import json
import logging
import logging.handlers
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import sys

# Constants
DEFAULT_CONFIG_PATH = "config.json"
DEFAULT_LOG_DIR = Path("logs")
DEFAULT_LOG_FILE = DEFAULT_LOG_DIR / "system.log"


logger = logging.getLogger(__name__)


def load_config(config_path: str = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    """
    Load configuration from JSON file.
    
    Args:
        config_path: Path to config.json file
        
    Returns:
        Configuration dictionary
        
    Raises:
        FileNotFoundError: If config file not found
        json.JSONDecodeError: If config file is invalid JSON
    """
    try:
        config_file = Path(config_path)
        
        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)

        logger.info("Configuration loaded from %s", config_path)
        return config
        
    except FileNotFoundError as e:
        logger.error("Config file error: %s", e)
        raise
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in %s: %s", config_path, e)
        raise
    except Exception as e:
        logger.error("Unexpected error loading config: %s", e)
        raise


def save_config(config: Dict[str, Any], config_path: str = DEFAULT_CONFIG_PATH) -> bool:
    """
    Save configuration to JSON file.
    
    Args:
        config: Configuration dictionary
        config_path: Path to save config file
        
    Returns:
        bool: True if successful
    """
    try:
        config_file = Path(config_path)
        config_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)

        logger.info("Configuration saved to %s", config_path)
        return True
        
    except Exception as e:
        logger.error("Error saving config to %s: %s", config_path, e)
        return False


def setup_logging(
    log_file: Optional[Path] = None,
    log_level: str = "INFO",
    max_bytes: int = 10485760,  # 10 MB
    backup_count: int = 5,
) -> logging.Logger:
    """
    Setup logging configuration with file and console handlers.
    
    Args:
        log_file: Path to log file (uses default if None)
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        max_bytes: Max size of log file before rotation
        backup_count: Number of backup logs to keep
        
    Returns:
        Configured logger instance
    """
    try:
        # Set log file path
        log_path = Path(log_file) if log_file else DEFAULT_LOG_FILE
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert log level string to logging constant
        numeric_level = getattr(logging, log_level.upper(), logging.INFO)
        
        # Create logger
        logger = logging.getLogger()
        logger.setLevel(numeric_level)
        
        # Remove existing handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # Format
        log_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(log_format)
        logger.addHandler(console_handler)
        
        # File handler with rotation
        file_handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(log_format)
        logger.addHandler(file_handler)
        
        logger.info(f"Logging initialized - Level: {log_level}, File: {log_path}")
        return logger
        
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error("Error setting up logging: %s", e)
        # Return basic logger if setup fails
        return logging.getLogger()


def get_timestamp(format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    Get current timestamp as formatted string.
    
    Args:
        format_str: strftime format string
        
    Returns:
        Formatted timestamp string
    """
    return datetime.now().strftime(format_str)


def get_timestamp_iso() -> str:
    """Get current timestamp in ISO format."""
    return datetime.now().isoformat()


def parse_time(time_str: str) -> Optional[datetime]:
    """
    Parse time string in HH:MM format.
    
    Args:
        time_str: Time string in HH:MM format
        
    Returns:
        datetime object with time set, or None if parsing fails
    """
    try:
        return datetime.strptime(time_str, "%H:%M")
    except ValueError:
        return None


def seconds_to_hms(seconds: int) -> str:
    """
    Convert seconds to human-readable hours:minutes:seconds format.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted string (e.g., "2h 30m 45s")
    """
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")
    
    return " ".join(parts)


def format_time(seconds: int) -> str:
    """Return human-readable duration string from seconds."""
    return seconds_to_hms(seconds)


def setup_data_directories() -> bool:
    """
    Create required data directories.
    
    Returns:
        bool: True if successful
    """
    try:
        directories = [
            Path("data"),
            Path("data/audio"),
            Path("logs"),
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

        logger.info("Data directories initialized")
        return True
        
    except Exception as e:
        logger.error("Error creating data directories: %s", e)
        return False


def validate_config(config: Dict[str, Any]) -> bool:
    """
    Validate configuration file structure.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        bool: True if valid
    """
    required_sections = ["vision", "voice", "alerts", "reminders"]
    
    for section in required_sections:
        if section not in config:
            logger.error("Missing config section: %s", section)
            return False
    
    # Validate vision section
    vision = config.get("vision", {})
    if "camera_id" not in vision:
        logger.error("Missing vision.camera_id")
        return False
    
    # Validate voice section
    voice = config.get("voice", {})
    if "language" not in voice:
        logger.error("Missing voice.language")
        return False
    
    # Validate alerts section
    alerts = config.get("alerts", {})
    if "caregiver_email" not in alerts:
        logger.error("Missing alerts.caregiver_email")
        return False
    
    # Validate reminders section
    reminders = config.get("reminders", {})
    if not reminders:
        logger.error("Empty reminders section")
        return False

    logger.info("Configuration validated successfully")
    return True


def get_system_info() -> Dict[str, Any]:
    """
    Get system information.
    
    Returns:
        Dictionary with system information
    """
    try:
        import platform
        
        info = {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "timestamp": get_timestamp_iso(),
        }
        
        return info
        
    except Exception as e:
        logger.error("Error getting system info: %s", e)
        return {}


def print_header(text: str, width: int = 50) -> None:
    """
    Print formatted header.
    
    Args:
        text: Header text
        width: Width of header line
    """
    print("\n" + "=" * width)
    print(f"  {text}")
    print("=" * width)


def print_section(text: str, width: int = 40) -> None:
    """
    Print formatted section title.
    
    Args:
        text: Section text
        width: Width of underline
    """
    print(f"\n{text}")
    print("-" * len(text))


def format_json(data: Dict[str, Any]) -> str:
    """
    Format dictionary as pretty-printed JSON.
    
    Args:
        data: Dictionary to format
        
    Returns:
        Pretty-printed JSON string
    """
    return json.dumps(data, indent=2, default=str)


def create_backup(file_path: str) -> Optional[str]:
    """
    Create backup copy of a file.
    
    Args:
        file_path: Path to file to backup
        
    Returns:
        Path to backup file or None if failed
    """
    try:
        source = Path(file_path)
        if not source.exists():
            return None
        
        timestamp = get_timestamp("%Y%m%d_%H%M%S")
        backup_path = source.parent / f"{source.stem}_backup_{timestamp}{source.suffix}"
        
        # Copy file
        backup_path.write_bytes(source.read_bytes())
        
        return str(backup_path)
        
    except Exception as e:
        logger.error("Error creating backup for %s: %s", file_path, e)
        return None


# Initialize logging on module import
logger = setup_logging()
