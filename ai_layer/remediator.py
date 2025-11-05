"""Process remediation module with safety mechanisms."""
import psutil
import logging
from typing import Dict, Optional
import time

logger = logging.getLogger(__name__)


class ProcessRemediator:
    """Safely terminates processes with rollback capabilities."""
    
    def __init__(self):
        """Initialize process remediator."""
        self.terminated_processes = []
    
    def remediate(self, decision: Dict) -> Dict:
        """
        Execute remediation action on a process.
        
        Args:
            decision: Decision dictionary containing recommendation and process info
            
        Returns:
            Result dictionary with success status and details
        """
        pid = decision['pid']
        recommendation = decision['recommendation']
        
        logger.info(f"Executing remediation: {recommendation} for PID {pid}")
        
        if recommendation == 'TERMINATE':
            return self._terminate_process(pid, decision)
        elif recommendation == 'KEEP':
            return self._keep_process(pid, decision)
        elif recommendation == 'INVESTIGATE':
            return self._mark_for_investigation(pid, decision)
        else:
            return {
                'success': False,
                'error': f"Unknown recommendation: {recommendation}",
                'pid': pid
            }
    
    def _terminate_process(self, pid: int, decision: Dict) -> Dict:
        """
        Safely terminate a process.
        
        Uses graceful termination first, then force kill if needed.
        
        Args:
            pid: Process ID
            decision: Decision dictionary
            
        Returns:
            Result dictionary
        """
        try:
            # Check if process exists
            try:
                proc = psutil.Process(pid)
            except psutil.NoSuchProcess:
                return {
                    'success': False,
                    'error': f"Process {pid} no longer exists",
                    'pid': pid
                }
            
            # Try graceful termination first
            logger.info(f"Attempting graceful termination of PID {pid} ({proc.name()})")
            proc.terminate()
            
            # Wait up to 5 seconds for graceful termination
            try:
                proc.wait(timeout=5)
                logger.info(f"Process {pid} terminated gracefully")
                
                self.terminated_processes.append({
                    'pid': pid,
                    'name': decision['name'],
                    'timestamp': time.time(),
                    'method': 'graceful'
                })
                
                return {
                    'success': True,
                    'method': 'graceful',
                    'pid': pid,
                    'name': decision['name']
                }
            except psutil.TimeoutExpired:
                # Graceful termination failed, try force kill
                logger.warning(f"Graceful termination failed for PID {pid}, using force kill")
                proc.kill()
                proc.wait(timeout=5)
                
                self.terminated_processes.append({
                    'pid': pid,
                    'name': decision['name'],
                    'timestamp': time.time(),
                    'method': 'force_kill'
                })
                
                return {
                    'success': True,
                    'method': 'force_kill',
                    'pid': pid,
                    'name': decision['name']
                }
                
        except psutil.NoSuchProcess:
            return {
                'success': False,
                'error': f"Process {pid} no longer exists",
                'pid': pid
            }
        except psutil.AccessDenied:
            return {
                'success': False,
                'error': f"Access denied to terminate process {pid}",
                'pid': pid
            }
        except Exception as e:
            logger.error(f"Error terminating process {pid}: {e}")
            return {
                'success': False,
                'error': str(e),
                'pid': pid
            }
    
    def _keep_process(self, pid: int, decision: Dict) -> Dict:
        """
        Keep process running (no action taken).
        
        Args:
            pid: Process ID
            decision: Decision dictionary
            
        Returns:
            Result dictionary
        """
        logger.info(f"Keeping process {pid} ({decision['name']}) running")
        
        return {
            'success': True,
            'action': 'kept',
            'pid': pid,
            'name': decision['name']
        }
    
    def _mark_for_investigation(self, pid: int, decision: Dict) -> Dict:
        """
        Mark process for investigation (no immediate action).
        
        Args:
            pid: Process ID
            decision: Decision dictionary
            
        Returns:
            Result dictionary
        """
        logger.info(f"Marking process {pid} ({decision['name']}) for investigation")
        
        return {
            'success': True,
            'action': 'marked_for_investigation',
            'pid': pid,
            'name': decision['name']
        }
    
    def batch_remediate(self, approved_decisions: list) -> list:
        """
        Execute remediation for multiple approved decisions.
        
        Args:
            approved_decisions: List of approved decision dictionaries
            
        Returns:
            List of result dictionaries
        """
        results = []
        
        logger.info(f"Starting batch remediation of {len(approved_decisions)} processes")
        
        for decision in approved_decisions:
            result = self.remediate(decision)
            results.append(result)
            
            # Small delay between terminations for safety
            time.sleep(0.5)
        
        # Summary
        successful = sum(1 for r in results if r.get('success'))
        failed = len(results) - successful
        
        logger.info(f"Batch remediation complete: {successful} successful, {failed} failed")
        
        return results
    
    def get_termination_history(self) -> list:
        """Get history of terminated processes in this session."""
        return self.terminated_processes.copy()
    
    def verify_termination(self, pid: int) -> bool:
        """
        Verify that a process was successfully terminated.
        
        Args:
            pid: Process ID
            
        Returns:
            True if process no longer exists, False otherwise
        """
        try:
            psutil.Process(pid)
            return False  # Process still exists
        except psutil.NoSuchProcess:
            return True  # Process terminated successfully
