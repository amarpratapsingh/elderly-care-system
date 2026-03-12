"""
Database Module - SQLite Database Management
Handles all database operations for activity and alert logging.
"""

import sqlite3
import logging
from types import TracebackType
from typing import List, Dict, Optional, Type
from pathlib import Path

logger = logging.getLogger(__name__)


class Database:
    """
    SQLite database manager for elderly care system.
    
    Attributes:
        db_path: Path to SQLite database file
        connection: Active database connection
    """

    def __init__(self, db_path: str = "data/elderly_care.db") -> None:
        """
        Initialize Database instance.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.connection: Optional[sqlite3.Connection] = None

    def __enter__(self) -> "Database":
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Context manager exit."""
        self.close()

    def connect(self) -> bool:
        """
        Connect to database and initialize schema.
        
        Returns:
            bool: True if successful
        """
        try:
            # Create data directory if it doesn't exist
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            
            self.connection = sqlite3.connect(str(self.db_path))
            # Enable dictionary-like row access
            self.connection.row_factory = sqlite3.Row
            
            self._create_tables()
            logger.info(f"Connected to database: {self.db_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to database: {e}")
            return False

    def _create_tables(self) -> None:
        """Create required database tables if they don't exist."""
        try:
            cursor = self.connection.cursor()
            
            # Activity logs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS activity_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    motion_detected BOOLEAN NOT NULL,
                    inactivity_seconds INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Alerts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    alert_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    resolved BOOLEAN DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Voice logs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS voice_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    transcript TEXT NOT NULL,
                    intent TEXT,
                    response TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Reminders table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reminder_type TEXT NOT NULL,
                    scheduled_time TIME NOT NULL,
                    status TEXT DEFAULT 'active',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indices for better query performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_activity_logs_timestamp
                ON activity_logs(timestamp)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_alerts_timestamp
                ON alerts(timestamp)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_voice_logs_timestamp
                ON voice_logs(timestamp)
            """)
            
            self.connection.commit()
            logger.info("Database schema initialized successfully")
            
        except Exception as e:
            logger.error(f"Error creating tables: {e}")
            raise

    def log_activity(self, motion_detected: bool, inactivity_seconds: Optional[int] = None) -> Optional[int]:
        """
        Log an activity (motion detection event) to the database.
        
        Args:
            motion_detected: Whether motion was detected
            inactivity_seconds: Duration of inactivity if no motion
            
        Returns:
            Activity ID or None if failed
        """
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT INTO activity_logs (motion_detected, inactivity_seconds)
                VALUES (?, ?)
            """, (motion_detected, inactivity_seconds))
            
            self.connection.commit()
            activity_id = cursor.lastrowid
            logger.debug(f"Activity logged: motion={motion_detected}, inactivity={inactivity_seconds}s (ID: {activity_id})")
            return activity_id
            
        except Exception as e:
            logger.error(f"Error logging activity: {e}")
            return None

    def log_alert(self, alert_type: str, severity: str, message: str) -> Optional[int]:
        """
        Log an alert to the database.
        
        Args:
            alert_type: Type of alert
            severity: Alert severity (e.g., 'low', 'medium', 'high', 'critical')
            message: Alert message
            
        Returns:
            Alert ID or None if failed
        """
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT INTO alerts (alert_type, severity, message, resolved)
                VALUES (?, ?, ?, 0)
            """, (alert_type, severity, message))
            
            self.connection.commit()
            alert_id = cursor.lastrowid
            logger.info(f"Alert logged: {alert_type} [{severity}] - {message} (ID: {alert_id})")
            return alert_id
            
        except Exception as e:
            logger.error(f"Error logging alert: {e}")
            return None

    def log_voice_interaction(self, transcript: str, intent: Optional[str] = None, response: Optional[str] = None) -> Optional[int]:
        """
        Log a voice interaction to the database.
        
        Args:
            transcript: Transcribed voice command text
            intent: Detected intent from the voice command
            response: System response to the command
            
        Returns:
            Voice log ID or None if failed
        """
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT INTO voice_logs (transcript, intent, response)
                VALUES (?, ?, ?)
            """, (transcript, intent, response))
            
            self.connection.commit()
            voice_log_id = cursor.lastrowid
            logger.debug(f"Voice interaction logged: intent={intent} (ID: {voice_log_id})")
            return voice_log_id
            
        except Exception as e:
            logger.error(f"Error logging voice interaction: {e}")
            return None

    # Friendly aliases: dashboard uses short names, DB uses longer canonical names.
    _TABLE_ALIASES: Dict[str, str] = {
        "activities": "activity_logs",
        "voice_commands": "voice_logs",
    }

    def get_recent_logs(
        self,
        table: str,
        limit: int = 10,
        hours: Optional[int] = None,
    ) -> List[Dict]:
        """
        Get recent logs from a specific table.

        Args:
            table: Table name or alias.
                   Canonical names: 'activity_logs', 'alerts', 'voice_logs', 'reminders'.
                   Accepted aliases: 'activities' -> 'activity_logs',
                                     'voice_commands' -> 'voice_logs'.
            limit: Maximum number of records to return (default: 10).
            hours: When provided, only return records from the last *hours* hours.

        Returns:
            List of log records as dictionaries
        """
        try:
            # Resolve alias to canonical table name
            canonical = self._TABLE_ALIASES.get(table, table)

            valid_tables = ["activity_logs", "alerts", "voice_logs", "reminders"]
            if canonical not in valid_tables:
                logger.warning(
                    f"Invalid table: '{table}'. Valid tables/aliases: "
                    f"{valid_tables + list(self._TABLE_ALIASES)}"
                )
                return []

            cursor = self.connection.cursor()

            if hours is not None:
                cursor.execute(
                    f"""
                    SELECT * FROM {canonical}
                    WHERE timestamp >= datetime('now', '-{int(hours)} hours')
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
            else:
                cursor.execute(
                    f"""
                    SELECT * FROM {canonical}
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                    """,
                    (limit,),
                )

            rows = cursor.fetchall()
            records = [dict(row) for row in rows]
            logger.debug(f"Retrieved {len(records)} records from {canonical}")
            return records

        except Exception as e:
            logger.error(f"Error retrieving logs from {table}: {e}")
            return []

    def close(self) -> None:
        """Close database connection."""
        if self.connection:
            try:
                self.connection.close()
                logger.info("Database connection closed")
            except Exception as e:
                logger.error(f"Error closing database connection: {e}")
