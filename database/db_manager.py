"""Database manager for OVERWATCH."""
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages SQLite database for OVERWATCH."""
    
    def __init__(self, db_path: str = "database/overwatch.db"):
        """Initialize database manager."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database with schema."""
        schema_path = Path(__file__).parent / "schema.sql"
        
        with sqlite3.connect(self.db_path) as conn:
            if schema_path.exists():
                with open(schema_path, 'r') as f:
                    conn.executescript(f.read())
            logger.info(f"Database initialized: {self.db_path}")
    
    def get_connection(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def create_alert(self, alert_data: Dict) -> str:
        """
        Create a new alert entry.
        
        Args:
            alert_data: Alert information
            
        Returns:
            Alert ID
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            alert_id = f"ALERT_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
            
            cursor.execute("""
                INSERT INTO alerts (
                    id, alert_name, severity, pid, process_name, parent_pid,
                    cmdline, cpu_percent, memory_percent, start_time, owner,
                    alert_payload, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alert_id,
                alert_data.get('alert_name'),
                alert_data.get('severity'),
                alert_data.get('pid'),
                alert_data.get('process_name'),
                alert_data.get('parent_pid'),
                alert_data.get('cmdline'),
                alert_data.get('cpu_percent'),
                alert_data.get('memory_percent'),
                alert_data.get('start_time'),
                alert_data.get('owner'),
                json.dumps(alert_data.get('alert_payload', {})),
                'pending'
            ))
            
            conn.commit()
            logger.info(f"Created alert: {alert_id}")
            return alert_id
    
    def create_recommendation(self, alert_id: str, recommendation: Dict) -> int:
        """
        Store LLM recommendation.
        
        Args:
            alert_id: Associated alert ID
            recommendation: Recommendation details
            
        Returns:
            Recommendation ID
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO recommendations (
                    alert_id, llm_model, action, confidence, reasoning,
                    command, prompt_version, full_response, fallback
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alert_id,
                recommendation.get('llm_model', 'llama2'),
                recommendation.get('action'),
                recommendation.get('confidence'),
                recommendation.get('reasoning'),
                recommendation.get('command'),
                recommendation.get('prompt_version', 'v1.0'),
                json.dumps(recommendation.get('full_response', {})),
                recommendation.get('fallback', False)
            ))
            
            conn.commit()
            rec_id = cursor.lastrowid
            
            # Update alert status
            cursor.execute("""
                UPDATE alerts SET status = 'analyzing' WHERE id = ?
            """, (alert_id,))
            conn.commit()
            
            logger.info(f"Created recommendation {rec_id} for alert {alert_id}")
            return rec_id
    
    def create_action(self, alert_id: str, recommendation_id: Optional[int],
                     action_data: Dict) -> int:
        """
        Record an executed action.
        
        Args:
            alert_id: Associated alert ID
            recommendation_id: Associated recommendation ID (optional)
            action_data: Action details
            
        Returns:
            Action ID
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO actions (
                    alert_id, recommendation_id, action_type, pid, command,
                    executed, dry_run, success, error_message, executed_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alert_id,
                recommendation_id,
                action_data.get('action_type'),
                action_data.get('pid'),
                action_data.get('command'),
                action_data.get('executed', False),
                action_data.get('dry_run', False),
                action_data.get('success'),
                action_data.get('error_message'),
                action_data.get('executed_by', 'system')
            ))
            
            conn.commit()
            action_id = cursor.lastrowid
            
            # Update alert status
            new_status = 'executed' if action_data.get('executed') else 'approved'
            cursor.execute("""
                UPDATE alerts SET status = ? WHERE id = ?
            """, (new_status, alert_id))
            conn.commit()
            
            logger.info(f"Created action {action_id} for alert {alert_id}")
            return action_id
    
    def get_pending_alerts(self) -> List[Dict]:
        """Get all pending alerts."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT a.*, r.action, r.confidence, r.reasoning
                FROM alerts a
                LEFT JOIN recommendations r ON a.id = r.alert_id
                WHERE a.status IN ('pending', 'analyzing')
                ORDER BY a.timestamp DESC
            """)
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_alert_history(self, limit: int = 100) -> List[Dict]:
        """Get alert history."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT a.*, r.action, r.reasoning, act.success, act.error_message
                FROM alerts a
                LEFT JOIN recommendations r ON a.id = r.alert_id
                LEFT JOIN actions act ON a.id = act.alert_id
                ORDER BY a.timestamp DESC
                LIMIT ?
            """, (limit,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_process_rules(self, rule_type: Optional[str] = None) -> List[Dict]:
        """Get process allow/deny rules."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            if rule_type:
                cursor.execute("""
                    SELECT * FROM process_rules
                    WHERE rule_type = ? AND enabled = 1
                    ORDER BY created_at DESC
                """, (rule_type,))
            else:
                cursor.execute("""
                    SELECT * FROM process_rules
                    WHERE enabled = 1
                    ORDER BY rule_type, created_at DESC
                """)
            
            return [dict(row) for row in cursor.fetchall()]
    
    def add_process_rule(self, rule_type: str, pattern: str, pattern_type: str,
                        created_by: str, notes: Optional[str] = None) -> int:
        """Add a new process rule."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO process_rules (
                    rule_type, pattern, pattern_type, created_by, notes
                ) VALUES (?, ?, ?, ?, ?)
            """, (rule_type, pattern, pattern_type, created_by, notes))
            
            conn.commit()
            return cursor.lastrowid
    
    def log_audit_event(self, event_type: str, event_id: Optional[str],
                       user: Optional[str], details: Dict):
        """Log an audit event."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO audit_log (event_type, event_id, user, details)
                VALUES (?, ?, ?, ?)
            """, (event_type, event_id, user, json.dumps(details)))
            
            conn.commit()
    
    def get_config(self, key: str) -> Optional[str]:
        """Get configuration value."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM config WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row['value'] if row else None
    
    def set_config(self, key: str, value: str):
        """Set configuration value."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO config (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (key, value))
            conn.commit()
