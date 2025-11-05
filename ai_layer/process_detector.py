"""Process detection and analysis module."""
import psutil
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


class ProcessInfo:
    """Container for process information."""
    
    def __init__(self, process: psutil.Process):
        """Initialize process info from psutil.Process."""
        try:
            self.pid = process.pid
            self.name = process.name()
            self.exe = process.exe()
            self.cmdline = ' '.join(process.cmdline())
            self.status = process.status()
            self.create_time = process.create_time()
            self.cpu_percent = process.cpu_percent(interval=0.1)
            self.memory_percent = process.memory_percent()
            self.memory_info = process.memory_info()._asdict()
            self.num_threads = process.num_threads()
            
            # Get parent information safely
            try:
                parent = process.parent()
                self.parent_pid = parent.pid if parent else None
                self.parent_name = parent.name() if parent else None
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                self.parent_pid = None
                self.parent_name = None
            
            # Get username safely
            try:
                self.username = process.username()
            except (psutil.AccessDenied, AttributeError):
                self.username = "UNKNOWN"
                
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.warning(f"Error accessing process {process.pid}: {e}")
            raise
    
    def to_dict(self) -> Dict:
        """Convert to dictionary representation."""
        return {
            'pid': self.pid,
            'name': self.name,
            'exe': self.exe,
            'cmdline': self.cmdline,
            'status': self.status,
            'create_time': self.create_time,
            'cpu_percent': self.cpu_percent,
            'memory_percent': self.memory_percent,
            'memory_info': self.memory_info,
            'num_threads': self.num_threads,
            'parent_pid': self.parent_pid,
            'parent_name': self.parent_name,
            'username': self.username,
        }
    
    def __repr__(self):
        return (f"ProcessInfo(pid={self.pid}, name={self.name}, "
                f"cpu={self.cpu_percent:.1f}%, mem={self.memory_percent:.1f}%)")


class ProcessDetector:
    """Detects problematic processes on Windows 11."""
    
    def __init__(self, cpu_threshold: float, memory_threshold: float, 
                 protected_processes: List[str]):
        """
        Initialize process detector.
        
        Args:
            cpu_threshold: CPU usage percentage threshold
            memory_threshold: Memory usage percentage threshold
            protected_processes: List of process names that should never be terminated
        """
        self.cpu_threshold = cpu_threshold
        self.memory_threshold = memory_threshold
        self.protected_processes = set(protected_processes)
        self.process_history = {}  # Track processes over time
    
    def get_all_processes(self) -> List[ProcessInfo]:
        """Get information about all running processes."""
        processes = []
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                proc_info = ProcessInfo(proc)
                processes.append(proc_info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return processes
    
    def is_orphaned(self, proc_info: ProcessInfo) -> bool:
        """
        Check if a process is orphaned (parent doesn't exist).
        
        On Windows, orphaned processes are typically reparented to a system process,
        but we check if the original parent is gone and it's not a system process.
        """
        if proc_info.parent_pid is None:
            return False
        
        # Check if parent exists
        try:
            # Attempt to instantiate parent process; if it doesn't exist, exception is raised
            psutil.Process(proc_info.parent_pid)
            return False
        except psutil.NoSuchProcess:
            # Parent doesn't exist, but check if this is a system process
            if proc_info.name in self.protected_processes:
                return False
            return True
    
    def is_zombie(self, proc_info: ProcessInfo) -> bool:
        """
        Check if a process is in zombie/defunct state.
        
        Windows doesn't have traditional zombie processes like Unix,
        but we check for processes in unusual states.
        """
        # On Windows, check for processes that are suspended or not responding
        return proc_info.status in [psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD]
    
    def is_resource_leeching(self, proc_info: ProcessInfo) -> bool:
        """
        Check if a process is using excessive resources.
        
        A process is considered resource-leeching if it exceeds CPU or memory thresholds.
        """
        return (proc_info.cpu_percent > self.cpu_threshold or 
                proc_info.memory_percent > self.memory_threshold)
    
    def is_protected(self, proc_info: ProcessInfo) -> bool:
        """Check if a process is protected from termination."""
        return proc_info.name in self.protected_processes
    
    def detect_problematic_processes(self) -> Dict[str, List[ProcessInfo]]:
        """
        Scan all processes and categorize problematic ones.
        
        Returns:
            Dictionary with categories: 'orphaned', 'zombie', 'resource_leeching'
        """
        logger.info("Starting process scan...")
        
        all_processes = self.get_all_processes()
        
        categorized = {
            'orphaned': [],
            'zombie': [],
            'resource_leeching': []
        }
        
        for proc_info in all_processes:
            # Skip protected processes
            if self.is_protected(proc_info):
                continue
            
            # Categorize the process
            if self.is_orphaned(proc_info):
                categorized['orphaned'].append(proc_info)
                logger.debug(f"Orphaned process detected: {proc_info}")
            
            if self.is_zombie(proc_info):
                categorized['zombie'].append(proc_info)
                logger.debug(f"Zombie process detected: {proc_info}")
            
            if self.is_resource_leeching(proc_info):
                categorized['resource_leeching'].append(proc_info)
                logger.debug(f"Resource-leeching process detected: {proc_info}")
        
        logger.info(f"Scan complete. Found {len(categorized['orphaned'])} orphaned, "
                   f"{len(categorized['zombie'])} zombie, "
                   f"{len(categorized['resource_leeching'])} resource-leeching processes")
        
        return categorized
