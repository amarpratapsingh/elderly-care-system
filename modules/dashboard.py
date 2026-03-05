"""
Dashboard Module - Streamlit Web Interface
Caregiver interface for monitoring system status, logs, and alerts.
"""

import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import json
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.database import Database
from modules.alerts import AlertManager
from utils import load_config

# Page configuration
st.set_page_config(
    page_title="Elderly Care Monitoring Dashboard",
    page_icon="👴",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .metric-container {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .alert-high {
        background-color: #ffcccc;
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .alert-medium {
        background-color: #fff3cd;
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .status-active {
        color: #28a745;
        font-weight: bold;
    }
    .status-inactive {
        color: #dc3545;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)


def load_config_with_cache():
    """Load configuration with caching."""
    if "config" not in st.session_state:
        st.session_state.config = load_config()
    return st.session_state.config


def get_database():
    """Get database connection with caching."""
    if "db" not in st.session_state:
        config = load_config_with_cache()
        st.session_state.db = Database(
            db_path=config.get("database", {}).get("path", "data/elderly_care.db")
        )
        st.session_state.db.connect()
    return st.session_state.db


def display_header():
    """Display dashboard header."""
    st.title("👴 Elderly Care Monitoring System")
    st.markdown("### Caregiver Dashboard & Monitoring Interface")
    st.markdown("---")


def display_status_overview():
    """Display system status overview."""
    st.header("📊 System Status")
    
    db = get_database()
    stats = db.get_dashboard_stats(hours=24)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total Activities (24h)",
            stats.get("total_activities", 0),
            delta="activities logged"
        )
    
    with col2:
        alerts = stats.get("alerts_by_severity", {})
        critical_count = alerts.get("critical", 0)
        st.metric(
            "Critical Alerts",
            critical_count,
            delta="⚠️" if critical_count > 0 else "✓"
        )
    
    with col3:
        high_count = alerts.get("high", 0)
        st.metric(
            "High Priority Alerts",
            high_count,
            delta="alerts"
        )
    
    with col4:
        voice_commands = stats.get("voice_commands_count", 0)
        st.metric(
            "Voice Commands (24h)",
            voice_commands,
            delta="commands executed"
        )
    
    # System status
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Last Activity")
        recent_activities = db.get_recent_logs("activities", limit=1)
        if recent_activities:
            activity = recent_activities[0]
            st.info(f"📍 {activity['activity_type']}\n\n{activity.get('description', 'No details')}\n\n_Last updated: {activity['timestamp']}_")
        else:
            st.warning("No recent activities")
    
    with col2:
        st.subheader("Last Motion Detection")
        recent_motions = db.get_recent_logs("motion_events", limit=1)
        if recent_motions:
            motion = recent_motions[0]
            status = "🟢 Motion Detected" if motion['motion_detected'] else "⚠️ No Motion"
            inactivity = motion.get('inactivity_seconds', 0)
            st.success(f"{status}\n\n_Inactivity: {inactivity // 3600}h {(inactivity % 3600) // 60}m_")
        else:
            st.info("No motion data available")


def display_alerts():
    """Display active alerts."""
    st.header("🚨 Active Alerts")
    
    db = get_database()
    alerts = db.get_recent_logs("alerts", limit=20, hours=72)
    
    if not alerts:
        st.success("✅ No active alerts")
        return
    
    # Filter alerts
    severity_filter = st.selectbox(
        "Filter by severity:",
        ["All", "critical", "high", "medium", "low"],
        key="alert_severity_filter"
    )
    
    if severity_filter != "All":
        alerts = [a for a in alerts if a.get("severity") == severity_filter]
    
    if not alerts:
        st.info("No alerts with selected severity")
        return
    
    # Display alerts
    for alert in alerts:
        severity = alert.get("severity", "unknown").upper()
        alert_type = alert.get("alert_type", "general")
        timestamp = alert.get("timestamp", "Unknown")
        message = alert.get("message", "No message")
        
        # Color-coded alert display
        if severity == "CRITICAL":
            color = "red"
            icon = "🔴"
        elif severity == "HIGH":
            color = "orange"
            icon = "🟠"
        elif severity == "MEDIUM":
            color = "yellow"
            icon = "🟡"
        else:
            color = "blue"
            icon = "🔵"
        
        st.markdown(f"""
        <div class="alert-{severity.lower()}">
        {icon} <b>{alert_type.upper()}</b> - {severity}<br>
        📝 {message}<br>
        🕐 {timestamp}
        </div>
        """, unsafe_allow_html=True)


def display_activities_log():
    """Display recent activities."""
    st.header("📋 Recent Activities")
    
    db = get_database()
    
    # Time range selector
    col1, col2 = st.columns(2)
    with col1:
        hours = st.slider("Time range (hours):", 1, 72, 24)
    with col2:
        activity_type = st.selectbox(
            "Filter by type:",
            ["All", "motion", "voice_command", "reminder", "other"],
            key="activity_type_filter"
        )
    
    activities = db.get_recent_logs("activities", limit=50, hours=hours)
    
    if not activities:
        st.info("No activities recorded in selected time range")
        return
    
    # Filter by type
    if activity_type != "All":
        activities = [a for a in activities if a.get("activity_type") == activity_type]
    
    if not activities:
        st.info("No activities of selected type")
        return
    
    # Create DataFrame
    activity_data = []
    for activity in activities:
        activity_data.append({
            "Time": activity.get("timestamp", ""),
            "Type": activity.get("activity_type", ""),
            "Description": activity.get("description", ""),
            "Status": "✓" if activity else "✗"
        })
    
    df = pd.DataFrame(activity_data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # Download activity log
    csv = df.to_csv(index=False)
    st.download_button(
        label="📥 Download Activity Log (CSV)",
        data=csv,
        file_name=f"activity_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )


def display_voice_commands():
    """Display voice commands log."""
    st.header("🎤 Voice Commands Log")
    
    db = get_database()
    commands = db.get_recent_logs("voice_commands", limit=30, hours=24)
    
    if not commands:
        st.info("No voice commands recorded")
        return
    
    # Create command data
    command_data = []
    for cmd in commands:
        command_data.append({
            "Time": cmd.get("timestamp", ""),
            "Command": cmd.get("command", ""),
            "Intent": cmd.get("intent", "unknown"),
            "Response": cmd.get("response", ""),
            "Status": cmd.get("status", "completed")
        })
    
    df = pd.DataFrame(command_data)
    st.dataframe(df, use_container_width=True, hide_index=True)


def display_reminders():
    """Display upcoming reminders."""
    st.header("⏰ Scheduled Reminders")
    
    db = get_database()
    reminders = db.get_recent_logs("reminders", limit=10)
    
    if not reminders:
        st.info("No reminders configured")
        return
    
    # Display reminders
    for reminder in reminders:
        col1, col2 = st.columns([1, 3])
        with col1:
            status = "🔔" if reminder.get("status") == "active" else "⏸️"
            st.write(status)
        with col2:
            st.markdown(f"""
            **{reminder.get('reminder_type', 'Unknown').title()}**
            
            Time: {reminder.get('scheduled_time', 'Not set')}
            """)


def display_settings():
    """Display system settings."""
    st.header("⚙️ System Settings")
    
    config = load_config_with_cache()
    
    tab1, tab2, tab3, tab4 = st.tabs(["Vision", "Voice", "Alerts", "Reminders"])
    
    with tab1:
        st.subheader("Vision Settings")
        vision = config.get("vision", {})
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Camera ID", vision.get("camera_id", 0))
            st.metric("Motion Threshold", vision.get("motion_threshold", 0))
        with col2:
            resolution = vision.get("resolution", {})
            st.metric("Resolution", f"{resolution.get('width', 0)}x{resolution.get('height', 0)}")
            st.metric("Inactivity Threshold (hrs)", 
                     vision.get("inactivity_threshold_seconds", 0) // 3600)
    
    with tab2:
        st.subheader("Voice Settings")
        voice = config.get("voice", {})
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Language", voice.get("language", "N/A"))
            st.metric("Sample Rate", f"{voice.get('sample_rate', 0)} Hz")
        with col2:
            st.metric("Timeout", f"{voice.get('timeout_seconds', 0)} sec")
    
    with tab3:
        st.subheader("Alert Settings")
        alerts_config = config.get("alerts", {})
        st.write(f"**Caregiver Email:** {alerts_config.get('caregiver_email', 'Not set')}")
        st.write(f"**Alerts Enabled:** {'Yes' if alerts_config.get('enabled', False) else 'No'}")
    
    with tab4:
        st.subheader("Reminders")
        reminders = config.get("reminders", {})
        
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Morning Medicine:** {reminders.get('morning_medicine', 'Not set')}")
            st.write(f"**Lunch:** {reminders.get('lunch', 'Not set')}")
        with col2:
            st.write(f"**Evening Medicine:** {reminders.get('evening_medicine', 'Not set')}")
            st.write(f"**Bedtime:** {reminders.get('bedtime', 'Not set')}")


def display_export():
    """Display data export options."""
    st.header("📤 Export & Backup")
    
    db = get_database()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📊 Export Activities (CSV)"):
            activities = db.get_recent_logs("activities", limit=1000, hours=720)
            if activities:
                df = pd.DataFrame(activities)
                csv = df.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name="activities.csv",
                    mime="text/csv"
                )
            else:
                st.warning("No data to export")
    
    with col2:
        if st.button("🚨 Export Alerts (CSV)"):
            alerts = db.get_recent_logs("alerts", limit=1000, hours=720)
            if alerts:
                df = pd.DataFrame(alerts)
                csv = df.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name="alerts.csv",
                    mime="text/csv"
                )
            else:
                st.warning("No data to export")
    
    with col3:
        if st.button("🗑️ Cleanup Old Records"):
            if db.cleanup_old_records():
                st.success("✅ Old records cleaned up successfully")
            else:
                st.error("❌ Error cleaning up records")


def main():
    """Main dashboard function."""
    display_header()
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Go to:",
        [
            "📊 Overview",
            "🚨 Alerts",
            "📋 Activities",
            "🎤 Voice Commands",
            "⏰ Reminders",
            "⚙️ Settings",
            "📤 Export"
        ]
    )
    
    # About section
    with st.sidebar:
        st.markdown("---")
        st.markdown("### About")
        st.markdown("""
        **Elderly Care Monitoring System**
        
        Real-time monitoring with motion detection, voice commands, and automated alerts.
        
        Version 1.0.0
        """)
    
    # Display selected page
    if page == "📊 Overview":
        display_status_overview()
    elif page == "🚨 Alerts":
        display_alerts()
    elif page == "📋 Activities":
        display_activities_log()
    elif page == "🎤 Voice Commands":
        display_voice_commands()
    elif page == "⏰ Reminders":
        display_reminders()
    elif page == "⚙️ Settings":
        display_settings()
    elif page == "📤 Export":
        display_export()
    
    # Auto-refresh
    st.markdown("---")
    if st.sidebar.checkbox("Auto-refresh", value=False):
        st.markdown("""
        <meta http-equiv="refresh" content="30">
        """, unsafe_allow_html=True)
        st.info("Dashboard will refresh every 30 seconds")


if __name__ == "__main__":
    main()
