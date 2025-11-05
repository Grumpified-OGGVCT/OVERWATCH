"""Audit trail and logging system."""
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class AuditLogger:
    """Manages audit trail for all process operations."""
    
    def __init__(self, audit_log_path: Path):
        """
        Initialize audit logger.
        
        Args:
            audit_log_path: Directory path for audit logs
        """
        self.audit_log_path = audit_log_path
        self.audit_log_path.mkdir(parents=True, exist_ok=True)
    
    def _get_log_file(self) -> Path:
        """Get the current log file path (one per day)."""
        today = datetime.now().strftime("%Y-%m-%d")
        return self.audit_log_path / f"audit_{today}.jsonl"
    
    def log_scan(self, categorized_processes: Dict[str, List]) -> str:
        """
        Log a process scan event.
        
        Args:
            categorized_processes: Dictionary of categorized processes
            
        Returns:
            Event ID
        """
        event_id = self._generate_event_id()
        
        event = {
            'event_id': event_id,
            'event_type': 'SCAN',
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'orphaned_count': len(categorized_processes.get('orphaned', [])),
                'zombie_count': len(categorized_processes.get('zombie', [])),
                'resource_leeching_count': len(categorized_processes.get('resource_leeching', []))
            }
        }
        
        self._write_event(event)
        logger.info(f"Logged scan event: {event_id}")
        return event_id
    
    def log_analysis(self, decisions: List[Dict]) -> str:
        """
        Log LLM analysis results.
        
        Args:
            decisions: List of decision dictionaries
            
        Returns:
            Event ID
        """
        event_id = self._generate_event_id()
        
        event = {
            'event_id': event_id,
            'event_type': 'ANALYSIS',
            'timestamp': datetime.now().isoformat(),
            'decisions': decisions,
            'summary': {
                'total_analyzed': len(decisions),
                'terminate_recommended': sum(1 for d in decisions if d['recommendation'] == 'TERMINATE'),
                'keep_recommended': sum(1 for d in decisions if d['recommendation'] == 'KEEP'),
                'investigate_recommended': sum(1 for d in decisions if d['recommendation'] == 'INVESTIGATE')
            }
        }
        
        self._write_event(event)
        logger.info(f"Logged analysis event: {event_id}")
        return event_id
    
    def log_human_decision(self, decision: Dict, approved: bool, 
                          human_notes: Optional[str] = None) -> str:
        """
        Log human approval/rejection decision.
        
        Args:
            decision: The decision dictionary
            approved: Whether the human approved the action
            human_notes: Optional notes from human reviewer
            
        Returns:
            Event ID
        """
        event_id = self._generate_event_id()
        
        event = {
            'event_id': event_id,
            'event_type': 'HUMAN_DECISION',
            'timestamp': datetime.now().isoformat(),
            'pid': decision['pid'],
            'process_name': decision['name'],
            'llm_recommendation': decision['recommendation'],
            'human_approved': approved,
            'human_notes': human_notes,
            'decision_details': decision
        }
        
        self._write_event(event)
        logger.info(f"Logged human decision event: {event_id} - Approved: {approved}")
        return event_id
    
    def log_remediation(self, decision: Dict, success: bool, 
                       error: Optional[str] = None) -> str:
        """
        Log process remediation action.
        
        Args:
            decision: The decision dictionary
            success: Whether remediation was successful
            error: Error message if failed
            
        Returns:
            Event ID
        """
        event_id = self._generate_event_id()
        
        event = {
            'event_id': event_id,
            'event_type': 'REMEDIATION',
            'timestamp': datetime.now().isoformat(),
            'pid': decision['pid'],
            'process_name': decision['name'],
            'action': decision['recommendation'],
            'success': success,
            'error': error,
            'decision_details': decision
        }
        
        self._write_event(event)
        
        if success:
            logger.info(f"Logged successful remediation event: {event_id}")
        else:
            logger.error(f"Logged failed remediation event: {event_id} - Error: {error}")
        
        return event_id
    
    def log_error(self, error_type: str, error_message: str, 
                  context: Optional[Dict] = None) -> str:
        """
        Log an error event.
        
        Args:
            error_type: Type of error
            error_message: Error message
            context: Optional context information
            
        Returns:
            Event ID
        """
        event_id = self._generate_event_id()
        
        event = {
            'event_id': event_id,
            'event_type': 'ERROR',
            'timestamp': datetime.now().isoformat(),
            'error_type': error_type,
            'error_message': error_message,
            'context': context
        }
        
        self._write_event(event)
        logger.error(f"Logged error event: {event_id} - {error_type}: {error_message}")
        return event_id
    
    def _generate_event_id(self) -> str:
        """Generate a unique event ID."""
        return f"EVT_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    
    def _write_event(self, event: Dict):
        """Write event to audit log file."""
        log_file = self._get_log_file()
        
        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(event, ensure_ascii=False) + '\n')
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
    
    def get_recent_events(self, event_type: Optional[str] = None, 
                         limit: int = 100) -> List[Dict]:
        """
        Retrieve recent events from audit log.
        
        Args:
            event_type: Filter by event type (optional)
            limit: Maximum number of events to return
            
        Returns:
            List of event dictionaries
        """
        log_file = self._get_log_file()
        
        if not log_file.exists():
            return []
        
        events = []
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        event = json.loads(line)
                        if event_type is None or event.get('event_type') == event_type:
                            events.append(event)
        except Exception as e:
            logger.error(f"Failed to read audit log: {e}")
        
        # Return most recent events up to limit
        return events[-limit:] if len(events) > limit else events
