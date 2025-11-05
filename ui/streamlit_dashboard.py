"""
OVERWATCH Streamlit Dashboard
Human-in-the-Loop control interface for process remediation.
"""

import streamlit as st
import sys
import os
import requests
import json
from datetime import datetime
import pandas as pd

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from database.db_manager import DatabaseManager

# Page configuration
st.set_page_config(
    page_title="OVERWATCH Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database
@st.cache_resource
def get_db():
    return DatabaseManager()

db = get_db()

# Configuration
EXECUTOR_URL = os.getenv('EXECUTOR_URL', 'http://localhost:8080')
EXECUTOR_TOKEN = os.getenv('EXECUTOR_TOKEN', 'executor-secret-token')

# Styling
st.markdown("""
<style>
.big-font {
    font-size:20px !important;
    font-weight: bold;
}
.metric-card {
    background-color: #f0f2f6;
    padding: 20px;
    border-radius: 10px;
    margin: 10px 0;
}
</style>
""", unsafe_allow_html=True)


def execute_action(alert_id: str, recommendation_id: int, action_type: str,
                  pid: int, command: str, dry_run: bool = False) -> dict:
    """
    Execute an action via PowerShell executor.
    
    Args:
        alert_id: Alert ID
        recommendation_id: Recommendation ID
        action_type: Type of action
        pid: Process ID
        command: Command to execute
        dry_run: If True, simulate without executing
        
    Returns:
        Result dictionary
    """
    try:
        if dry_run:
            # Simulate execution
            result = {
                'success': True,
                'message': 'Dry-run: Would have executed command',
                'command': command,
                'dry_run': True
            }
        else:
            # Real execution via PowerShell executor
            response = requests.post(
                f"{EXECUTOR_URL}/execute",
                json={
                    'command': command,
                    'alert_id': alert_id
                },
                headers={
                    'Authorization': f'Bearer {EXECUTOR_TOKEN}',
                    'Content-Type': 'application/json'
                },
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
            else:
                result = {
                    'success': False,
                    'error': f'Executor returned {response.status_code}: {response.text}'
                }
        
        # Log action to database
        db.create_action(alert_id, recommendation_id, {
            'action_type': action_type,
            'pid': pid,
            'command': command,
            'executed': not dry_run,
            'dry_run': dry_run,
            'success': result.get('success', False),
            'error_message': result.get('error'),
            'executed_by': st.session_state.get('username', 'streamlit_user')
        })
        
        return result
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def render_header():
    """Render dashboard header."""
    col1, col2, col3 = st.columns([2, 3, 1])
    
    with col1:
        st.title("🛡️ OVERWATCH")
        st.caption("Enterprise Process Monitoring & Remediation")
    
    with col2:
        # System status indicators
        try:
            pending_count = len(db.get_pending_alerts())
            st.metric("Pending Alerts", pending_count, 
                     delta=None if pending_count == 0 else f"+{pending_count}")
        except:
            st.metric("Pending Alerts", "Error", delta="⚠️")
    
    with col3:
        if st.button("🔄 Refresh"):
            st.rerun()


def render_alert_card(alert: dict, show_actions: bool = True):
    """Render an individual alert card."""
    severity_colors = {
        'critical': '🔴',
        'warning': '🟡',
        'info': '🟢'
    }
    
    category_icons = {
        'orphaned': '👻',
        'zombie': '🧟',
        'resource_leeching': '🔥'
    }
    
    severity = alert.get('severity', 'info')
    category = alert.get('category', 'unknown')
    
    with st.container():
        st.markdown(f"""
        ### {severity_colors.get(severity, '⚪')} Alert: {alert.get('alert_name', 'Unknown')}
        **Category:** {category_icons.get(category, '❓')} {category.upper()}  
        **PID:** {alert.get('pid')} | **Process:** {alert.get('process_name', 'N/A')}  
        **Time:** {alert.get('timestamp', 'N/A')}
        """)
        
        # Process details in expander
        with st.expander("📋 Process Details"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Parent PID:** {alert.get('parent_pid', 'N/A')}")
                st.write(f"**CPU:** {alert.get('cpu_percent', 'N/A')}%")
                st.write(f"**Memory:** {alert.get('memory_percent', 'N/A')}%")
            
            with col2:
                st.write(f"**Owner:** {alert.get('owner', 'N/A')}")
                st.write(f"**Start Time:** {alert.get('start_time', 'N/A')}")
            
            cmdline = alert.get('cmdline', 'N/A')
            if cmdline and cmdline != 'N/A':
                st.write(f"**Command Line:**")
                st.code(cmdline, language=None)
        
        # AI recommendation
        if alert.get('action'):
            action = alert.get('action')
            confidence = alert.get('confidence', 0.0)
            reasoning = alert.get('reasoning', 'No reasoning provided')
            
            action_icons = {
                'kill': '❌',
                'manual': '👤',
                'safe_check': '🔍'
            }
            
            st.markdown(f"""
            **🤖 AI Recommendation:** {action_icons.get(action, '❓')} **{action.upper()}**  
            **Confidence:** {confidence:.1%}  
            **Reasoning:** {reasoning}
            """)
        
        # Action buttons
        if show_actions and alert.get('status') in ['pending', 'analyzing']:
            col1, col2, col3, col4 = st.columns(4)
            
            alert_id = alert.get('id')
            pid = alert.get('pid')
            command = f"Stop-Process -Id {pid} -Force"
            
            with col1:
                if st.button(f"✅ Approve", key=f"approve_{alert_id}"):
                    result = execute_action(
                        alert_id=alert_id,
                        recommendation_id=None,
                        action_type='kill',
                        pid=pid,
                        command=command,
                        dry_run=False
                    )
                    if result['success']:
                        st.success(f"✅ Process {pid} terminated successfully")
                    else:
                        st.error(f"❌ Failed: {result.get('error', 'Unknown error')}")
                    st.rerun()
            
            with col2:
                if st.button(f"🧪 Dry Run", key=f"dryrun_{alert_id}"):
                    result = execute_action(
                        alert_id=alert_id,
                        recommendation_id=None,
                        action_type='kill',
                        pid=pid,
                        command=command,
                        dry_run=True
                    )
                    st.info(f"🧪 Dry run: Would execute: {command}")
            
            with col3:
                if st.button(f"⏭️ Skip", key=f"skip_{alert_id}"):
                    db.create_action(alert_id, None, {
                        'action_type': 'skip',
                        'pid': pid,
                        'command': None,
                        'executed': False,
                        'dry_run': False,
                        'success': True,
                        'executed_by': st.session_state.get('username', 'streamlit_user')
                    })
                    st.info("⏭️ Alert skipped")
                    st.rerun()
            
            with col4:
                if st.button(f"🚫 Reject", key=f"reject_{alert_id}"):
                    db.create_action(alert_id, None, {
                        'action_type': 'manual_review',
                        'pid': pid,
                        'command': None,
                        'executed': False,
                        'dry_run': False,
                        'success': True,
                        'executed_by': st.session_state.get('username', 'streamlit_user')
                    })
                    st.warning("🚫 Alert rejected - marked for manual review")
                    st.rerun()
        
        st.markdown("---")


def render_pending_alerts():
    """Render pending alerts tab."""
    st.header("⚠️ Pending Alerts")
    
    pending = db.get_pending_alerts()
    
    if not pending:
        st.success("✅ No pending alerts! System is healthy.")
        return
    
    st.write(f"**{len(pending)} alert(s) requiring review:**")
    st.markdown("---")
    
    for alert in pending:
        render_alert_card(alert, show_actions=True)


def render_history():
    """Render history tab."""
    st.header("📜 Alert History")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        limit = st.selectbox("Show last:", [10, 25, 50, 100, 500], index=2)
    
    history = db.get_alert_history(limit=limit)
    
    if not history:
        st.info("No historical alerts")
        return
    
    # Convert to DataFrame for better display
    df_data = []
    for alert in history:
        df_data.append({
            'Time': alert.get('timestamp', 'N/A'),
            'Alert': alert.get('alert_name', 'N/A'),
            'PID': alert.get('pid', 'N/A'),
            'Process': alert.get('process_name', 'N/A'),
            'Category': alert.get('category', 'N/A'),
            'AI Action': alert.get('action', 'N/A'),
            'Status': alert.get('status', 'N/A'),
            'Success': '✅' if alert.get('success') else '❌' if alert.get('success') is False else '⏳'
        })
    
    df = pd.DataFrame(df_data)
    st.dataframe(df, use_container_width=True)
    
    # Detailed view
    st.markdown("---")
    st.subheader("Detailed View")
    
    for alert in history[:10]:  # Show first 10 in detail
        render_alert_card(alert, show_actions=False)


def render_configuration():
    """Render configuration tab."""
    st.header("⚙️ Configuration")
    
    st.subheader("Protected Processes (Deny List)")
    
    # Get current deny rules
    deny_rules = db.get_process_rules('deny')
    
    if deny_rules:
        df_data = []
        for rule in deny_rules:
            df_data.append({
                'Pattern': rule['pattern'],
                'Type': rule['pattern_type'],
                'Notes': rule['notes'] or 'N/A',
                'Created By': rule['created_by']
            })
        
        df = pd.DataFrame(df_data)
        st.dataframe(df, use_container_width=True)
    
    # Add new rule
    st.markdown("---")
    st.subheader("Add New Protection Rule")
    
    col1, col2 = st.columns(2)
    
    with col1:
        pattern = st.text_input("Process Name Pattern")
        pattern_type = st.selectbox("Pattern Type", ['name', 'cmdline', 'pid_range'])
    
    with col2:
        notes = st.text_area("Notes")
    
    if st.button("➕ Add Rule"):
        if pattern:
            db.add_process_rule(
                rule_type='deny',
                pattern=pattern,
                pattern_type=pattern_type,
                created_by=st.session_state.get('username', 'streamlit_user'),
                notes=notes
            )
            st.success(f"✅ Added protection rule for: {pattern}")
            st.rerun()
        else:
            st.error("Pattern is required")


def main():
    """Main dashboard."""
    # Render header
    render_header()
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 🛡️ OVERWATCH")
        st.markdown("### Navigation")
        
        page = st.radio(
            "Select Page:",
            ["⚠️ Pending Alerts", "📜 History", "⚙️ Configuration", "📊 Stats"],
            label_visibility="collapsed"
        )
        
        st.markdown("---")
        st.markdown("### System Info")
        st.caption(f"Database: {db.db_path}")
        st.caption(f"Version: 2.1")
    
    # Main content
    if page == "⚠️ Pending Alerts":
        render_pending_alerts()
    elif page == "📜 History":
        render_history()
    elif page == "⚙️ Configuration":
        render_configuration()
    elif page == "📊 Stats":
        st.header("📊 Statistics")
        st.info("Statistics dashboard coming soon!")


if __name__ == '__main__':
    main()
