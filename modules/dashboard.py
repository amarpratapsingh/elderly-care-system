"""
Dashboard Module - Streamlit Web Interface
Comprehensive caregiver interface for monitoring system status, logs, and alerts.

Features:
- Real-time system status in sidebar with last update time
- Multi-tab interface: Live Status, Activity History, Alerts, Voice Logs
- Emergency alert trigger button
- Activity timeline and alert frequency charts using Plotly
- Real-time metrics display with st.empty() containers
- CSV export functionality
- Auto-refresh every 5 seconds
- st.session_state persistence
"""
import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta
import csv
import io

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.database import Database
from modules.alerts import AlertManager
from utils import load_config

logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="Elderly Care Dashboard",
    page_icon="👴",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS with enhanced styling
st.markdown("""
<style>
    [data-testid="stMetric"] {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 8px;
        border-left: 4px solid #1f77b4;
    }
    
    .status-active {
        color: #28a745;
        font-weight: bold;
        font-size: 18px;
    }
    
    .status-inactive {
        color: #dc3545;
        font-weight: bold;
        font-size: 18px;
    }
    
    .status-paused {
        color: #ffc107;
        font-weight: bold;
        font-size: 18px;
    }
    
    .alert-high {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        padding: 12px;
        border-radius: 5px;
        margin: 10px 0;
    }
    
    .alert-medium {
        background-color: #fff3cd;
        border: 1px solid #ffeeba;
        padding: 12px;
        border-radius: 5px;
        margin: 10px 0;
    }
    
    .alert-low {
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        padding: 12px;
        border-radius: 5px;
        margin: 10px 0;
    }
    
    .emergency-button {
        background-color: #dc3545;
        color: white;
        padding: 12px 24px;
        border-radius: 5px;
        font-weight: bold;
        border: none;
        cursor: pointer;
    }
    
    .info-box {
        background-color: #e7f3ff;
        border-left: 4px solid #2196F3;
        padding: 12px;
        border-radius: 3px;
        margin: 10px 0;
    }
    
    .success-box {
        background-color: #d4edda;
        border-left: 4px solid #28a745;
        padding: 12px;
        border-radius: 3px;
        margin: 10px 0;
    }
    
    .warning-box {
        background-color: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 12px;
        border-radius: 3px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# Session State & Caching Functions
# ============================================================================

def initialize_session_state():
    """Initialize session state variables."""
    if "config" not in st.session_state:
        st.session_state.config = load_config()
    if "db" not in st.session_state:
        config = st.session_state.config
        st.session_state.db = Database(
            db_path=config.get("database", {}).get("path", "data/elderly_care.db")
        )
        try:
            st.session_state.db.connect()
        except Exception as e:
            logger.error(f"Database connection error: {e}")
    if "last_refresh" not in st.session_state:
        st.session_state.last_refresh = datetime.now()
    if "emergency_sent" not in st.session_state:
        st.session_state.emergency_sent = False


def get_config():
    """Get configuration from session state."""
    initialize_session_state()
    return st.session_state.config


def get_db():
    """Get database connection from session state."""
    initialize_session_state()
    return st.session_state.db


def get_runtime_system_state() -> dict:
    """Read runtime state emitted by main system process."""
    state_file = Path("data/system_state.json")
    if not state_file.exists():
        return {
            "state": "UNKNOWN",
            "timestamp": "Not available",
        }

    try:
        with open(state_file, "r", encoding="utf-8") as f:
            payload = json.load(f)
        return {
            "state": str(payload.get("state", "UNKNOWN")),
            "timestamp": str(payload.get("timestamp", "Not available")),
        }
    except Exception as e:
        logger.error(f"Error reading runtime state: {e}")
        return {
            "state": "ERROR",
            "timestamp": "Not available",
        }


# ============================================================================
# Sidebar Functions
# ============================================================================

def display_sidebar():
    """Display sidebar with system status and navigation."""
    st.sidebar.title("👴 System Control Panel")
    st.sidebar.markdown("---")
    
    # System Status Section
    st.sidebar.subheader("🖥️ System Status")
    
    runtime_state = get_runtime_system_state()
    state = runtime_state.get("state", "UNKNOWN")
    last_update = runtime_state.get("timestamp", "Not available")
    
    # Status indicator with color
    if state == "RUNNING":
        status_color = "🟢"
        status_class = "status-active"
    elif state == "PAUSED":
        status_color = "🟡"
        status_class = "status-paused"
    else:
        status_color = "🔴"
        status_class = "status-inactive"
    
    st.sidebar.markdown(f"""
    <div class="{status_class}">
    {status_color} {state}
    </div>
    """, unsafe_allow_html=True)
    
    st.sidebar.caption(f"Last Updated: {last_update}")
    
    st.sidebar.markdown("---")
    
    # Quick stats
    st.sidebar.subheader("📊 Quick Stats")
    db = get_db()
    
    try:
        # Get today's stats
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Count alerts today
        recent_alerts = db.get_recent_logs("alerts", limit=1000, hours=24)
        alerts_today = len([a for a in recent_alerts if a]) if recent_alerts else 0
        
        # Count activities today
        recent_activities = db.get_recent_logs("activities", limit=1000, hours=24)
        activities_today = len([a for a in recent_activities if a]) if recent_activities else 0
        
        # Count voice commands today
        recent_voice = db.get_recent_logs("voice_commands", limit=1000, hours=24)
        voice_today = len([v for v in recent_voice if v]) if recent_voice else 0
        
        with st.sidebar:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Alerts", alerts_today, label_visibility="collapsed")
            with col2:
                st.metric("Activities", activities_today, label_visibility="collapsed")
            with col3:
                st.metric("Commands", voice_today, label_visibility="collapsed")
    except Exception as e:
        st.sidebar.error(f"Error loading stats: {e}")
    
    st.sidebar.markdown("---")
    
    # About section
    st.sidebar.subheader("ℹ️ About")
    st.sidebar.markdown("""
    **Elderly Care Monitoring System**
    
    Real-time monitoring with:
    - 🎥 Motion detection
    - 🎤 Voice commands
    - 🚨 Automated alerts
    - 📊 Activity tracking
    
    **Version 1.0.0**
    """)


# ============================================================================
# Control Panel Functions
# ============================================================================

def display_control_panel():
    """Display system control panel in sidebar."""
    st.sidebar.markdown("---")
    st.sidebar.subheader("🎛️ Control Panel")
    
    # System Start/Stop Controls
    st.sidebar.markdown("**System Control**")
    col_start, col_stop = st.sidebar.columns(2)
    
    with col_start:
        if st.button("▶️ Start", use_container_width=True, key="btn_start"):
            try:
                # In a real implementation, this would call an API endpoint
                st.session_state.system_running = True
                st.sidebar.success("✅ System started!")
            except Exception as e:
                st.sidebar.error(f"❌ Error: {e}")
    
    with col_stop:
        if st.button("⏹️ Stop", use_container_width=True, key="btn_stop"):
            try:
                st.session_state.system_running = False
                st.sidebar.warning("⚠️ System stopped!")
            except Exception as e:
                st.sidebar.error(f"❌ Error: {e}")
    
    # Inactivity Threshold Control
    st.sidebar.markdown("**Thresholds**")
    config = get_config()
    current_threshold = config.get("vision", {}).get("inactivity_threshold_seconds", 1800) // 60
    
    new_threshold_mins = st.sidebar.slider(
        "Inactivity Alert (min):",
        min_value=10,
        max_value=60,
        value=current_threshold,
        step=5,
        key="inactivity_threshold"
    )
    
    if new_threshold_mins != current_threshold:
        try:
            # Update config
            config["vision"]["inactivity_threshold_seconds"] = new_threshold_mins * 60
            st.session_state.config = config
            st.sidebar.success(f"✅ Updated to {new_threshold_mins} minutes")
        except Exception as e:
            st.sidebar.error(f"❌ Update failed: {e}")
    
    # Test Alert Button
    st.sidebar.markdown("**Testing**")
    if st.sidebar.button("📧 Send Test Alert", use_container_width=True, key="btn_test_alert"):
        with st.sidebar:
            with st.spinner("📤 Sending test email..."):
                try:
                    config = get_config()
                    alerts_config = config.get("alerts", {})
                    alert_manager = AlertManager(
                        caregiver_email=alerts_config.get("caregiver_email", ""),
                        smtp_user=alerts_config.get("smtp_username", ""),
                        smtp_pass=alerts_config.get("smtp_password", ""),
                        smtp_server=alerts_config.get("smtp_server", "smtp.gmail.com"),
                        smtp_port=int(alerts_config.get("smtp_port", 587)),
                    )
                    success = alert_manager.send_email(
                        subject="Test Alert from Dashboard",
                        body="This is a test email from the Elderly Care Monitoring System.",
                        alert_type="TEST",
                        severity="medium"
                    )
                    if success:
                        st.sidebar.success("✅ Test email sent!")
                    else:
                        st.sidebar.error("❌ Failed to send test email")
                except Exception as e:
                    st.sidebar.error(f"❌ Error: {str(e)[:50]}")
    
    # Reminder Management
    st.sidebar.markdown("**Reminders**")
    
    with st.sidebar.expander("📋 View Reminders", expanded=False):
        config = get_config()
        reminders = config.get("reminders", {})
        
        if reminders:
            for reminder_key, reminder_data in reminders.items():
                if isinstance(reminder_data, dict):
                    time_val = reminder_data.get("time", "N/A")
                    message_val = reminder_data.get("message", "")
                    st.write(f"**{reminder_key.replace('_', ' ').title()}**")
                    st.caption(f"⏰ {time_val}")
                    st.caption(f"📝 {message_val[:60]}...")
                    st.divider()
        else:
            st.info("No reminders configured")
    
    with st.sidebar.expander("➕ Add Reminder", expanded=False):
        reminder_name = st.text_input("Reminder Name:", key="reminder_name_input")
        reminder_time = st.time_input("Reminder Time:", key="reminder_time_input")
        reminder_msg = st.text_area("Message (Odia or English):", key="reminder_msg_input", height=60)
        
        if st.button("✅ Add", key="btn_add_reminder", use_container_width=True):
            if reminder_name and reminder_msg:
                try:
                    config = get_config()
                    if "reminders" not in config:
                        config["reminders"] = {}
                    
                    config["reminders"][reminder_name.lower()] = {
                        "time": reminder_time.strftime("%H:%M"),
                        "message": reminder_msg
                    }
                    st.session_state.config = config
                    st.sidebar.success("✅ Reminder added!")
                    st.rerun()
                except Exception as e:
                    st.sidebar.error(f"❌ Error: {e}")
            else:
                st.sidebar.warning("⚠️ Please fill all fields")
    
    with st.sidebar.expander("🗑️ Delete Reminder", expanded=False):
        config = get_config()
        reminders = config.get("reminders", {})
        
        if reminders:
            reminder_to_delete = st.selectbox(
                "Select reminder to delete:",
                list(reminders.keys()),
                key="reminder_delete_select"
            )
            
            if st.button("🗑️ Delete", key="btn_delete_reminder", use_container_width=True):
                try:
                    del config["reminders"][reminder_to_delete]
                    st.session_state.config = config
                    st.sidebar.success("✅ Reminder deleted!")
                    st.rerun()
                except Exception as e:
                    st.sidebar.error(f"❌ Error: {e}")
        else:
            st.sidebar.info("No reminders to delete")
    
    # Configuration Editor
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Advanced**")
    
    if st.sidebar.button("⚙️ Edit Configuration", use_container_width=True, key="btn_config_editor"):
        st.session_state.show_config_editor = True
    
    if st.sidebar.button("💾 Save Configuration", use_container_width=True, key="btn_save_config"):
        try:
            # Save config to file
            from utils import save_config
            config = get_config()
            if save_config(config, "config.json"):
                st.sidebar.success("✅ Configuration saved!")
            else:
                st.sidebar.error("❌ Save failed")
        except Exception as e:
            st.sidebar.error(f"❌ Error: {e}")


def display_config_editor_modal():
    """Display configuration editor modal."""
    if not st.session_state.get("show_config_editor", False):
        return
    
    st.markdown("---")
    st.subheader("⚙️ Configuration Editor")
    
    config = get_config()
    
    with st.expander("📋 Raw JSON Editor", expanded=True):
        json_text = json.dumps(config, indent=2, ensure_ascii=False)
        edited_json = st.text_area(
            "Edit configuration (JSON):",
            value=json_text,
            height=400,
            key="json_editor"
        )
        
        col_validate, col_save = st.columns(2)
        
        with col_validate:
            if st.button("✓ Validate JSON"):
                try:
                    json.loads(edited_json)
                    st.success("✅ JSON is valid!")
                except json.JSONDecodeError as e:
                    st.error(f"❌ Invalid JSON: {e}")
        
        with col_save:
            if st.button("💾 Save Changes"):
                try:
                    new_config = json.loads(edited_json)
                    st.session_state.config = new_config
                    from utils import save_config
                    if save_config(new_config, "config.json"):
                        st.success("✅ Configuration saved successfully!")
                        st.session_state.show_config_editor = False
                    else:
                        st.error("❌ Failed to save configuration")
                except json.JSONDecodeError as e:
                    st.error(f"❌ Invalid JSON: {e}")
                except Exception as e:
                    st.error(f"❌ Error: {e}")
    
    col_close, _ = st.columns([1, 4])
    with col_close:
        if st.button("❌ Close Editor", key="btn_close_editor"):
            st.session_state.show_config_editor = False


# ============================================================================
# Alert Type Icons & Color Coding
# ============================================================================

ALERT_TYPE_ICONS = {
    "MOTION": "🔴",
    "INACTIVITY": "⏰",
    "VOICE": "🎤",
    "EMAIL": "📧",
    "CAMERA": "📹",
    "DATABASE": "🗄️",
    "SYSTEM": "⚙️",
    "EMERGENCY": "🚨",
    "WARNING": "⚠️",
    "INFO": "ℹ️",
}

SEVERITY_COLORS = {
    "critical": "#dc3545",
    "high": "#fd7e14",
    "medium": "#ffc107",
    "low": "#17a2b8",
}

SEVERITY_EMOJIS = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🔵",
}


# ============================================================================
# Live Status Tab
# ============================================================================

def display_live_status():
    """Display live status tab with real-time metrics and emergency button."""
    st.header("📊 Live Status")
    
    col_left, col_right = st.columns([3, 1])
    
    with col_right:
        st.subheader("🚨 Emergency")
        if st.button(
            "ALERT CAREGIVER",
            use_container_width=True,
            type="primary",
            key="emergency_button",
            help="Send immediate emergency alert to caregiver"
        ):
            with st.spinner("📤 Sending emergency alert..."):
                try:
                    config = get_config()
                    alerts_config = config.get("alerts", {})
                    alert_manager = AlertManager(
                        caregiver_email=alerts_config.get("caregiver_email", ""),
                        smtp_user=alerts_config.get("smtp_username", ""),
                        smtp_pass=alerts_config.get("smtp_password", ""),
                        smtp_server=alerts_config.get("smtp_server", "smtp.gmail.com"),
                        smtp_port=int(alerts_config.get("smtp_port", 587)),
                    )
                    success = alert_manager.send_emergency_alert(
                        source="dashboard_manual",
                        details="Manual emergency alert triggered from dashboard"
                    )
                    if success:
                        st.success("✅ Emergency alert sent!")
                        st.session_state.emergency_sent = True
                    else:
                        st.error("❌ Failed to send emergency alert")
                except Exception as e:
                    st.error(f"Error sending alert: {e}")
                    logger.error(f"Emergency alert error: {e}")
    
    # Real-time metrics with empty containers for updates
    with col_left:
        st.subheader("Current Status")
        
        # Dynamic metric containers with loading state
        metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
        
        db = get_db()
        
        try:
            # Get latest activity data with loading indicator
            with st.spinner("Loading metrics..."):
                recent_activities = db.get_recent_logs("activities", limit=1, hours=1)
                if recent_activities and recent_activities[0]:
                    activity = recent_activities[0]
                    inactivity_sec = activity.get("inactivity_seconds", 0)
                    
                    # Activity state with color coding
                    if inactivity_sec < 300:
                        state_color = "🟢"
                        state_text = "Active"
                        state_delta = f"{inactivity_sec}s inactive"
                    elif inactivity_sec < 1800:
                        state_color = "🟡"
                        state_text = "Caution"
                        state_delta = f"{inactivity_sec}s inactive"
                    else:
                        state_color = "🔴"
                        state_text = "CRITICAL"
                        state_delta = f"{inactivity_sec}s inactive"
                    
                    with metric_col1:
                        st.metric(
                            "Activity State",
                            f"{state_color} {state_text}",
                            delta=state_delta
                        )
                    
                    # Inactivity duration with formatted display
                    hours = inactivity_sec // 3600
                    mins = (inactivity_sec % 3600) // 60
                    secs = inactivity_sec % 60
                    
                    with metric_col2:
                        st.metric(
                            "Inactivity Duration",
                            f"{hours}h {mins}m",
                            delta=f"{secs}s"
                        )
                else:
                    with metric_col1:
                        st.metric("Activity State", "⚠️ No Data", delta="waiting")
                    with metric_col2:
                        st.metric("Inactivity Duration", "N/A", delta="—")
                
                # Recent alerts
                recent_alerts = db.get_recent_logs("alerts", limit=1, hours=24)
                if recent_alerts and recent_alerts[0]:
                    alert = recent_alerts[0]
                    severity = alert.get("severity", "unknown").upper()
                    severity_emoji = SEVERITY_EMOJIS.get(severity.lower(), "❓")
                    
                    with metric_col3:
                        st.metric(
                            "Last Alert",
                            f"{severity_emoji} {severity}",
                            delta=alert.get("timestamp", "")[:19]
                        )
                else:
                    with metric_col3:
                        st.metric("Last Alert", "✅ None", delta="healthy")
                
                # Last voice command
                recent_voice = db.get_recent_logs("voice_commands", limit=1, hours=24)
                if recent_voice and recent_voice[0]:
                    command = recent_voice[0]
                    intent = command.get("intent", "unknown").title()
                    intent_emoji = ALERT_TYPE_ICONS.get(intent.upper(), "🎤")
                    
                    with metric_col4:
                        st.metric(
                            "Last Command",
                            f"{intent_emoji} {intent}",
                            delta=command.get("timestamp", "")[:19] if command.get("timestamp") else "—"
                        )
                else:
                    with metric_col4:
                        st.metric("Last Command", "🎤 Waiting", delta="—")
        
        except Exception as e:
            with metric_col1:
                st.error(f"⚠️ Error loading metrics: {str(e)[:30]}")
            logger.error(f"Metrics error: {e}")
        
        # Activity Status Section
        st.markdown("---")
        st.subheader("📍 Current Activity")
        
        try:
            recent = db.get_recent_logs("activities", limit=1, hours=1)
            if recent and recent[0]:
                activity = recent[0]
                timestamp = activity.get("timestamp", "Unknown")
                description = activity.get("description", "No details")
                inactivity_sec = activity.get("inactivity_seconds", 0)
                
                # Color-code the info box
                if inactivity_sec < 300:
                    st.info(
                        f"🟢 **Active** | {timestamp}\n\n"
                        f"{description}"
                    )
                elif inactivity_sec < 1800:
                    st.warning(
                        f"🟡 **Caution** | {timestamp}\n\n"
                        f"Long inactivity detected: {inactivity_sec}s\n\n"
                        f"{description}"
                    )
                else:
                    st.error(
                        f"🔴 **CRITICAL** | {timestamp}\n\n"
                        f"Critical inactivity: {inactivity_sec}s\n\n"
                        f"{description}"
                    )
            else:
                st.info("⏳ No recent activity data available")
        except Exception as e:
            st.error(f"Error loading activity: {e}")
        
        # Camera Placeholder with responsive layout
        st.markdown("---")
        st.subheader("📹 Camera Feed")
        
        col_cam, col_stats = st.columns([3, 1])
        
        with col_cam:
            st.image(
                "https://via.placeholder.com/640x480/cccccc/999999?text=Camera+Feed",
                caption="Live Camera Feed - Coming Soon",
                use_column_width=True
            )
        
        with col_stats:
            st.metric("Frame Rate", "15 FPS", delta="🟢 stable")
            st.metric("Resolution", "640x480", delta="HD")
            st.metric("Status", "🟢 Active", delta="ready")


# ============================================================================
# Activity History Tab
# ============================================================================

def display_activity_history():
    """Display activity history with tables and charts."""
    st.header("📋 Activity History")
    
    db = get_db()
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        hours = st.slider("Time range (hours):", 1, 168, 24, key="activity_hours")
    
    with col2:
        activity_type = st.selectbox(
            "Activity type:",
            ["All", "motion", "voice_command", "reminder", "alert"],
            key="activity_type_filter"
        )
    
    with col3:
        limit = st.selectbox("Rows to display:", [20, 50, 100, 200], index=1, key="activity_limit")
    
    try:
        # Get activities from database with loading indicator
        with st.spinner("📊 Loading activity history..."):
            activities = db.get_recent_logs("activities", limit=limit, hours=hours)
        
        if not activities:
            st.info("📭 No activities found in selected time range")
            return
        
        # Filter by type
        if activity_type != "All":
            activities = [a for a in activities if a and a.get("activity_type") == activity_type]
        
        if not activities:
            st.info(f"📭 No activities of type '{activity_type}' found")
            return
        
        # Create DataFrame
        activity_data = []
        for activity in activities:
            if activity:
                activity_data.append({
                    "Timestamp": activity.get("timestamp", ""),
                    "Type": activity.get("activity_type", ""),
                    "Description": activity.get("description", "")[:80],
                    "Status": "✓"
                })
        
        if not activity_data:
            st.info("📭 No activities to display")
            return
        
        df = pd.DataFrame(activity_data)
        
        # Display table with responsive sizing
        st.subheader("Recent Activities")
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Activity Timeline Chart
        st.subheader("📈 Activity Timeline (Last 24 Hours)")
        
        # Count activities per hour
        now = datetime.now()
        hour_data = {}
        for i in range(24):
            hour_time = (now - timedelta(hours=i)).replace(minute=0, second=0, microsecond=0)
            hour_key = hour_time.strftime("%H:00")
            hour_data[hour_key] = 0
        
        for activity in activities:
            if activity:
                try:
                    ts = datetime.fromisoformat(activity.get("timestamp", ""))
                    hour_key = ts.strftime("%H:00")
                    if hour_key in hour_data:
                        hour_data[hour_key] += 1
                except Exception:
                    pass
        
        # Create bar chart
        hours_list = list(reversed(list(hour_data.keys())))
        counts = [hour_data[h] for h in hours_list]
        
        fig = px.bar(
            x=hours_list,
            y=counts,
            labels={"x": "Time", "y": "Activity Count"},
            title="Activity Distribution by Hour",
            color_discrete_sequence=["#1f77b4"]
        )
        fig.update_layout(
            xaxis_title="Time",
            yaxis_title="Number of Activities",
            height=400,
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # CSV Export
        st.subheader("📥 Export Data")
        csv_data = df.to_csv(index=False)
        st.download_button(
            label="⬇️ Download Activity Log (CSV)",
            data=csv_data,
            file_name=f"activity_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            key="export_activities"
        )
    
    except Exception as e:
        st.error(f"❌ Error loading activity history: {str(e)[:60]}")
        logger.error(f"Activity history error: {e}")


# ============================================================================
# Alerts Tab
# ============================================================================

def display_alerts_tab():
    """Display alerts with sorting and severity filtering."""
    st.header("🚨 Alerts")
    
    db = get_db()
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        hours = st.slider("Time range (hours):", 1, 240, 72, key="alert_hours")
    
    with col2:
        severity = st.selectbox(
            "Severity filter:",
            ["All", "critical", "high", "medium", "low"],
            key="severity_filter"
        )
    
    with col3:
        sort_by = st.selectbox(
            "Sort by:",
            ["Newest First", "Oldest First", "Severity (High→Low)"],
            key="alert_sort"
        )
    
    try:
        # Get alerts from database with loading indicator
        with st.spinner("🔍 Loading alerts..."):
            alerts = db.get_recent_logs("alerts", limit=200, hours=hours)
        
        if not alerts:
            st.success("✅ No alerts found - System is healthy!")
            return
        
        # Filter by severity
        if severity != "All":
            alerts = [a for a in alerts if a and a.get("severity") == severity]
        
        if not alerts:
            st.info(f"📭 No alerts with severity '{severity}'")
            return
        
        # Sort alerts
        if sort_by == "Oldest First":
            alerts = list(reversed(alerts))
        elif sort_by == "Severity (High→Low)":
            severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            alerts = sorted(
                alerts,
                key=lambda a: severity_order.get(a.get("severity", "low"), 4)
            )
        
        # Display stats with color coding
        col1, col2, col3 = st.columns(3)
        
        severity_counts = {}
        for alert in alerts:
            if alert:
                sev = alert.get("severity", "unknown")
                severity_counts[sev] = severity_counts.get(sev, 0) + 1
        
        with col1:
            st.metric("📊 Total Alerts", len(alerts), delta="on record")
        with col2:
            critical = severity_counts.get("critical", 0)
            st.metric(
                "🔴 Critical",
                critical,
                delta="⚠️ ACTION REQUIRED" if critical > 0 else "✓ CLEAR"
            )
        with col3:
            high = severity_counts.get("high", 0)
            st.metric("🟠 High Priority", high, delta="alerts")
        
        # Display alerts as cards with color coding and icons
        st.subheader("Alert Details")
        
        for idx, alert in enumerate(alerts):
            if not alert:
                continue
            
            severity_level = alert.get("severity", "unknown").lower()
            alert_type = alert.get("alert_type", "general").upper()
            timestamp = alert.get("timestamp", "Unknown")
            message = alert.get("message", "No message")
            
            # Determine styling and icon
            severity_emoji = SEVERITY_EMOJIS.get(severity_level, "❓")
            alert_icon = ALERT_TYPE_ICONS.get(alert_type, "📌")
            
            # Create color-coded alert card
            col_alert, col_btn = st.columns([4, 1])
            
            with col_alert:
                st.markdown(f"""
                <div class="alert-{severity_level}">
                <b>{severity_emoji} {alert_icon} {alert_type}</b><br>
                📝 {message}<br>
                🕐 {timestamp}
                </div>
                """, unsafe_allow_html=True)
            
            with col_btn:
                if st.button("✓ Mark Resolved", key=f"resolve_alert_{idx}", use_container_width=True):
                    st.success("✅ Alert marked as resolved")
        
        # Alert frequency chart
        st.markdown("---")
        st.subheader("📊 Alert Frequency Analysis")
        
        try:
            # Count alerts per hour
            alert_timeline = {}
            now = datetime.now()
            for i in range(24):
                hour_time = (now - timedelta(hours=i)).replace(minute=0, second=0, microsecond=0)
                hour_key = hour_time.strftime("%H:00")
                alert_timeline[hour_key] = 0
            
            for alert in alerts:
                if alert:
                    try:
                        ts = datetime.fromisoformat(alert.get("timestamp", ""))
                        hour_key = ts.strftime("%H:00")
                        if hour_key in alert_timeline:
                            alert_timeline[hour_key] += 1
                    except Exception:
                        pass
            
            hours_list = list(reversed(list(alert_timeline.keys())))
            counts = [alert_timeline[h] for h in hours_list]
            
            fig = px.line(
                x=hours_list,
                y=counts,
                markers=True,
                labels={"x": "Time", "y": "Alert Count"},
                title="Alert Frequency Timeline",
                color_discrete_sequence=["#dc3545"]
            )
            fig.update_layout(
                xaxis_title="Time",
                yaxis_title="Number of Alerts",
                height=400,
                hovermode="x unified"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        except Exception as e:
            st.warning(f"⚠️ Could not generate chart: {str(e)[:40]}")
        
        # CSV Export
        st.subheader("📥 Export Data")
        
        alert_data = []
        for alert in alerts:
            if alert:
                alert_data.append({
                    "Timestamp": alert.get("timestamp", ""),
                    "Type": alert.get("alert_type", ""),
                    "Severity": alert.get("severity", ""),
                    "Message": alert.get("message", "")
                })
        
        if alert_data:
            df = pd.DataFrame(alert_data)
            csv_data = df.to_csv(index=False)
            st.download_button(
                label="⬇️ Download Alerts (CSV)",
                data=csv_data,
                file_name=f"alerts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key="export_alerts"
            )
    
    except Exception as e:
        st.error(f"❌ Error loading alerts: {str(e)[:60]}")
        logger.error(f"Alerts tab error: {e}")


# ============================================================================
# Voice Logs Tab
# ============================================================================

def display_voice_logs():
    """Display voice interactions with intent filtering."""
    st.header("🎤 Voice Logs")
    
    db = get_db()
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        hours = st.slider("Time range (hours):", 1, 168, 24, key="voice_hours")
    
    with col2:
        intent_filter = st.selectbox(
            "Intent filter:",
            ["All", "emergency", "medicine_query", "status", "stop", "greeting"],
            key="intent_filter"
        )
    
    with col3:
        limit = st.selectbox("Rows to display:", [20, 50, 100], index=1, key="voice_limit")
    
    try:
        # Get voice logs with loading indicator
        with st.spinner("🔊 Loading voice logs..."):
            voice_logs = db.get_recent_logs("voice_commands", limit=limit, hours=hours)
        
        if not voice_logs:
            st.info("📭 No voice interaction logs found in this time range")
            return
        
        # Filter by intent
        if intent_filter != "All":
            voice_logs = [v for v in voice_logs if v and v.get("intent") == intent_filter]
        
        if not voice_logs:
            st.info(f"📭 No voice interactions with intent '{intent_filter}'")
            return
        
        # Create DataFrame
        voice_data = []
        for log in voice_logs:
            if log:
                voice_data.append({
                    "Timestamp": log.get("timestamp", ""),
                    "Transcript": log.get("transcript", "")[:60],  # Truncate
                    "Intent": log.get("intent", "unknown"),
                    "Response": log.get("response", "")[:60],  # Truncate
                    "Confidence": log.get("confidence", 0.0)
                })
        
        if not voice_data:
            st.info("📭 No voice interactions to display")
            return
        
        df = pd.DataFrame(voice_data)
        
        # Display table with intent tags
        st.subheader("🎙️ Recent Voice Interactions")
        
        # Custom display with tags
        for idx, row in df.iterrows():
            intent = row["Intent"]
            
            # Color-code intents
            intent_colors = {
                "emergency": "🔴",
                "medicine_query": "💊",
                "status": "📊",
                "stop": "⏹️",
                "greeting": "👋",
                "unknown": "❓"
            }
            
            icon = intent_colors.get(intent, "❓")
            
            col_main, col_conf = st.columns([4, 1])
            
            with col_main:
                st.markdown(f"""
                **{icon} {intent.upper()}**  
                📝 _Transcript:_ {row['Transcript']}  
                🤖 _Response:_ {row['Response']}  
                🕐 {row['Timestamp']}
                """)
            
            with col_conf:
                st.metric("Confidence", f"{row['Confidence']:.1%}", delta="score")
            
            st.markdown("---")
        
        # Intent Distribution Chart
        st.subheader("📊 Intent Distribution")
        
        intent_counts = {}
        for log in voice_logs:
            if log:
                intent = log.get("intent", "unknown")
                intent_counts[intent] = intent_counts.get(intent, 0) + 1
        
        if intent_counts:
            fig = px.pie(
                values=list(intent_counts.values()),
                names=list(intent_counts.keys()),
                title="Voice Command Intents Distribution",
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        # CSV Export
        st.subheader("📥 Export Data")
        csv_data = df.to_csv(index=False)
        st.download_button(
            label="⬇️ Download Voice Logs (CSV)",
            data=csv_data,
            file_name=f"voice_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            key="export_voice"
        )
    
    except Exception as e:
        st.error(f"❌ Error loading voice logs: {str(e)[:60]}")
        logger.error(f"Voice logs error: {e}")


# ============================================================================
# Auto-Refresh Logic
# ============================================================================

def setup_auto_refresh():
    """Setup auto-refresh with st.empty() and placeholder updates."""
    col1, col2 = st.columns([4, 1])
    
    with col2:
        refresh_enabled = st.checkbox("🔄 Auto-refresh", value=False, key="auto_refresh_check")
    
    if refresh_enabled:
        st.markdown("""
        <script>
            setTimeout(function() {
                window.location.reload();
            }, 5000);
        </script>
        """, unsafe_allow_html=True)


# ============================================================================
# Main Application
# ============================================================================

def main():
    """Main dashboard application."""
    # Initialize session state
    initialize_session_state()
    
    # Display sidebar
    display_sidebar()
    
    # Display control panel
    display_control_panel()
    
    # Main content with tabs
    st.title("👴 Elderly Care Monitoring Dashboard")
    st.markdown("Real-time monitoring and alert management system")
    st.markdown("---")
    
    # Create tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Live Status",
        "📋 Activity History",
        "🚨 Alerts",
        "🎤 Voice Logs"
    ])
    
    with tab1:
        display_live_status()
    
    with tab2:
        display_activity_history()
    
    with tab3:
        display_alerts_tab()
    
    with tab4:
        display_voice_logs()
    
    # Display config editor modal if requested
    display_config_editor_modal()
    
    # Auto-refresh at bottom
    st.markdown("---")
    setup_auto_refresh()
    
    # Footer
    st.markdown("""
    <div style="text-align: center; padding: 20px; color: #888;">
    <small>Elderly Care Monitoring System v1.0.0 | Last Updated: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """</small>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()

