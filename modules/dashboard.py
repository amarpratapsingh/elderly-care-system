"""HTML/CSS/JS dashboard server for the Elderly Care Monitoring System.

Run with:
    python modules/dashboard.py

Then open:
    http://localhost:<printed-port>
"""

from __future__ import annotations

import json
import logging
import sys
import time
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict
from urllib.parse import parse_qs, urlparse

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import sqlite3

from utils import load_config
from modules.alerts import AlertManager

logger = logging.getLogger(__name__)
LATEST_CAMERA_FRAME_PATH = Path("data/latest_camera_frame.jpg")

WEB_DIR = ROOT_DIR / "web"
DATA_DIR = ROOT_DIR / "data"
SYSTEM_STATE_FILE = DATA_DIR / "system_state.json"
LATEST_CAMERA_FRAME_PATH = DATA_DIR / "latest_camera_frame.jpg"


def _read_text(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as file:
        return file.read()


class DashboardService:
    """Thin service layer for dashboard reads and actions."""

    def __init__(self) -> None:
        self.config = load_config()
        self.db_path = Path(self.config.get("database", {}).get("path", "data/elderly_care.db"))
        self.alert_manager = self._build_alert_manager()
        self._ensure_schema()

    def _build_alert_manager(self) -> AlertManager | None:
        """Build AlertManager from config when SMTP settings are available."""
        alerts_cfg = self.config.get("alerts", {})
        caregiver_email = str(alerts_cfg.get("caregiver_email", "")).strip()
        smtp_user = str(alerts_cfg.get("smtp_username") or alerts_cfg.get("smtp_user", "")).strip()
        smtp_pass = str(alerts_cfg.get("smtp_password", "")).strip()

        if not caregiver_email or not smtp_user or not smtp_pass:
            logger.warning("Dashboard emergency email disabled: SMTP credentials not configured")
            return None

        try:
            return AlertManager(
                caregiver_email=caregiver_email,
                smtp_user=smtp_user,
                smtp_pass=smtp_pass,
                smtp_server=str(alerts_cfg.get("smtp_server", "smtp.gmail.com")),
                smtp_port=int(alerts_cfg.get("smtp_port", 587)),
                database=None,
            )
        except Exception as exc:
            logger.error("Failed to initialize dashboard AlertManager: %s", exc)
            return None

    def _ensure_schema(self) -> None:
        if not self.db_path.parent.exists():
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with sqlite3.connect(str(self.db_path)) as connection:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS activity_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        motion_detected BOOLEAN NOT NULL,
                        inactivity_seconds INTEGER,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS alerts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        alert_type TEXT NOT NULL,
                        severity TEXT NOT NULL,
                        message TEXT NOT NULL,
                        resolved BOOLEAN DEFAULT 0,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS voice_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        transcript TEXT NOT NULL,
                        intent TEXT,
                        response TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                connection.commit()
        except Exception as exc:
            logger.error("Dashboard schema setup failed: %s", exc)


    def _query_logs(self, table: str, limit: int, hours: int) -> list[dict[str, Any]]:
        if not self.db_path.exists():
            return []

        try:
            with sqlite3.connect(str(self.db_path)) as connection:
                connection.row_factory = sqlite3.Row
                cursor = connection.cursor()
                cursor.execute(
                    f"""
                    SELECT * FROM {table}
                    WHERE timestamp >= datetime('now', ?)
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                    """,
                    (f"-{int(hours)} hours", int(limit)),
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as exc:
            logger.error("Dashboard DB query failed for %s: %s", table, exc)
            return []

    def _insert_alert(self, alert_type: str, severity: str, message: str) -> int | None:
        if not self.db_path.parent.exists():
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with sqlite3.connect(str(self.db_path)) as connection:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS alerts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        alert_type TEXT NOT NULL,
                        severity TEXT NOT NULL,
                        message TEXT NOT NULL,
                        resolved BOOLEAN DEFAULT 0,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                cursor.execute(
                    """
                    INSERT INTO alerts (alert_type, severity, message, resolved)
                    VALUES (?, ?, ?, 0)
                    """,
                    (alert_type, severity, message),
                )
                connection.commit()
                return cursor.lastrowid
        except Exception as exc:
            logger.error("Dashboard DB insert failed: %s", exc)
            return None

    def get_runtime_system_state(self) -> Dict[str, str]:
        if not SYSTEM_STATE_FILE.exists():
            return {"state": "UNKNOWN", "timestamp": "Not available"}

        try:
            payload = json.loads(_read_text(SYSTEM_STATE_FILE))
            return {
                "state": str(payload.get("state", "UNKNOWN")),
                "timestamp": str(payload.get("timestamp", "Not available")),
            }
        except Exception as exc:
            logger.error("Error reading runtime state: %s", exc)
            return {"state": "ERROR", "timestamp": "Not available"}

    def get_summary(self) -> Dict[str, Any]:
        activities = self._query_logs("activity_logs", limit=1, hours=24)
        alerts = self._query_logs("alerts", limit=200, hours=24)
        voice = self._query_logs("voice_logs", limit=200, hours=24)

        latest_activity = activities[0] if activities else {}

        return {
            "runtime": self.get_runtime_system_state(),
            "last_24h": {
                "activities": len(self._query_logs("activity_logs", limit=1000, hours=24)),
                "alerts": len(alerts),
                "voice_commands": len(voice),
                "high_or_critical_alerts": len(
                    [a for a in alerts if str(a.get("severity", "")).lower() in {"high", "critical"}]
                ),
            },
            "latest_activity": {
                "timestamp": latest_activity.get("timestamp", "-"),
                "motion_detected": bool(latest_activity.get("motion_detected", False)),
                "inactivity_seconds": latest_activity.get("inactivity_seconds"),
            },
        }

    def list_activity(self, hours: int, limit: int) -> Dict[str, Any]:
        rows = self._query_logs("activity_logs", limit=limit, hours=hours)
        data = []
        for row in rows:
            motion = bool(row.get("motion_detected", False))
            inactivity = row.get("inactivity_seconds")
            if motion:
                description = "Motion detected"
            elif inactivity is not None:
                description = f"No motion for {inactivity} seconds"
            else:
                description = "No motion"

            data.append(
                {
                    "id": row.get("id"),
                    "timestamp": row.get("timestamp"),
                    "activity_type": "motion" if motion else "inactivity",
                    "description": description,
                }
            )

        return {"items": data}

    def list_alerts(self, hours: int, limit: int, severity: str | None) -> Dict[str, Any]:
        rows = self._query_logs("alerts", limit=limit, hours=hours)
        if severity:
            severity = severity.lower()
            rows = [r for r in rows if str(r.get("severity", "")).lower() == severity]
        return {"items": rows}

    def list_voice(self, hours: int, limit: int) -> Dict[str, Any]:
        rows = self._query_logs("voice_logs", limit=limit, hours=hours)
        return {"items": rows}

    def get_camera_status(self) -> Dict[str, Any]:
        if not LATEST_CAMERA_FRAME_PATH.exists():
            return {
                "available": False,
                "updated_at": None,
                "url": "/camera-stream",
            }

        updated_at = datetime.fromtimestamp(LATEST_CAMERA_FRAME_PATH.stat().st_mtime).isoformat()
        return {
            "available": True,
            "updated_at": updated_at,
            "url": "/camera-stream",
        }

    def trigger_emergency_alert(self) -> Dict[str, Any]:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f"Emergency alert triggered manually from dashboard at {timestamp}."
        alert_id = self._insert_alert("emergency_manual", "critical", message)
        email_sent = False
        email_error = ""

        if self.alert_manager is None:
            email_error = "SMTP credentials not configured in config.json"
        else:
            try:
                email_sent = self.alert_manager.send_emergency_alert(
                    source="dashboard",
                    details=message,
                )
                if not email_sent:
                    email_error = "AlertManager.send_emergency_alert returned False"
            except Exception as exc:
                email_error = str(exc)
                logger.error("Dashboard emergency email send failed: %s", exc)

        ok = bool(alert_id) and email_sent
        return {
            "ok": ok,
            "alert_id": alert_id,
            "message": message,
            "db_logged": bool(alert_id),
            "email_sent": email_sent,
            "email_error": email_error,
        }


class DashboardRequestHandler(BaseHTTPRequestHandler):
    service: DashboardService

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/":
            return self._serve_html("index.html")
        if parsed.path == "/styles.css":
            return self._serve_static("styles.css", "text/css; charset=utf-8")
        if parsed.path == "/app.js":
            return self._serve_static("app.js", "application/javascript; charset=utf-8")
        if parsed.path == "/camera-stream":
            return self._serve_camera_stream()
        if parsed.path == "/camera-frame":
            return self._serve_camera_frame()

        if parsed.path.startswith("/api/"):
            return self._serve_api_get(parsed)

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/emergency":
            payload = self.service.trigger_emergency_alert()
            status = HTTPStatus.OK if payload.get("ok") else HTTPStatus.INTERNAL_SERVER_ERROR
            return self._send_json(payload, status=status)

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def log_message(self, format: str, *args: Any) -> None:
        logger.info("Dashboard HTTP - %s", format % args)

    def _serve_api_get(self, parsed: Any) -> None:
        query = parse_qs(parsed.query)
        hours = _safe_int(query.get("hours", ["24"])[0], default=24, minimum=1, maximum=720)
        limit = _safe_int(query.get("limit", ["50"])[0], default=50, minimum=1, maximum=1000)

        if parsed.path == "/api/system-state":
            return self._send_json(self.service.get_runtime_system_state())

        if parsed.path == "/api/summary":
            return self._send_json(self.service.get_summary())

        if parsed.path == "/api/camera-status":
            return self._send_json(self.service.get_camera_status())

        if parsed.path == "/api/activity":
            return self._send_json(self.service.list_activity(hours=hours, limit=limit))

        if parsed.path == "/api/alerts":
            severity = query.get("severity", [None])[0]
            return self._send_json(self.service.list_alerts(hours=hours, limit=limit, severity=severity))

        if parsed.path == "/api/voice":
            return self._send_json(self.service.list_voice(hours=hours, limit=limit))

        self.send_error(HTTPStatus.NOT_FOUND, "Unknown API endpoint")

    def _serve_html(self, file_name: str) -> None:
        self._serve_static(file_name, "text/html; charset=utf-8")

    def _serve_static(self, file_name: str, content_type: str) -> None:
        target = WEB_DIR / file_name
        if not target.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return

        body = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_camera_frame(self) -> None:
        if not LATEST_CAMERA_FRAME_PATH.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "Camera frame not available")
            return

        body = LATEST_CAMERA_FRAME_PATH.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_camera_stream(self) -> None:
        """Serve a live MJPEG stream sourced from the latest captured frame file."""
        if not LATEST_CAMERA_FRAME_PATH.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "Camera stream not available")
            return

        boundary = "frame"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"multipart/x-mixed-replace; boundary={boundary}")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

        last_good_frame: bytes | None = None
        try:
            while True:
                if not LATEST_CAMERA_FRAME_PATH.exists():
                    time.sleep(0.1)
                    continue

                frame = LATEST_CAMERA_FRAME_PATH.read_bytes()
                if not frame:
                    time.sleep(0.05)
                    continue

                # Ignore partial/corrupt reads while file is being updated.
                if not (frame.startswith(b"\xff\xd8") and frame.endswith(b"\xff\xd9")):
                    if last_good_frame is None:
                        time.sleep(0.02)
                        continue
                    frame = last_good_frame
                else:
                    last_good_frame = frame

                self.wfile.write(f"--{boundary}\r\n".encode("utf-8"))
                self.wfile.write(b"Content-Type: image/jpeg\r\n")
                self.wfile.write(f"Content-Length: {len(frame)}\r\n\r\n".encode("utf-8"))
                self.wfile.write(frame)
                self.wfile.write(b"\r\n")
                self.wfile.flush()

                # ~12 FPS is enough for dashboard preview and keeps CPU/network moderate.
                time.sleep(0.08)
        except (BrokenPipeError, ConnectionResetError):
            logger.debug("Camera stream client disconnected")
        except Exception as exc:
            logger.error("Error in camera stream: %s", exc)

    def _send_json(self, payload: Dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _safe_int(value: str, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def run_dashboard_server(host: str = "0.0.0.0", port: int = 8081) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    service = DashboardService()
    DashboardRequestHandler.service = service

    selected_port = port
    try:
        server = ThreadingHTTPServer((host, selected_port), DashboardRequestHandler)
    except OSError as exc:
        logger.warning(
            "Port %s is unavailable (%s). Falling back to a free port.",
            selected_port,
            exc,
        )
        server = ThreadingHTTPServer((host, 0), DashboardRequestHandler)

    actual_port = int(server.server_address[1])
    logger.info("Dashboard server running at http://%s:%s", host, actual_port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Dashboard server interrupted by user.")
    finally:
        server.server_close()
        logger.info("Dashboard server stopped.")


if __name__ == "__main__":
    run_dashboard_server()
