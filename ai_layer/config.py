"""Configuration management for OVERWATCH."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Application configuration."""
    
    # Ollama Proxy Settings
    OLLAMA_PROXY_URL = os.getenv('OLLAMA_PROXY_URL', 'http://localhost:8081')
    OLLAMA_API_KEY = os.getenv('OLLAMA_API_KEY', '')
    
    # Process Monitoring Thresholds
    CPU_THRESHOLD = float(os.getenv('CPU_THRESHOLD', '80.0'))
    MEMORY_THRESHOLD = float(os.getenv('MEMORY_THRESHOLD', '80.0'))
    SCAN_INTERVAL_SECONDS = int(os.getenv('SCAN_INTERVAL_SECONDS', '60'))
    
    # Logging Configuration
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    AUDIT_LOG_PATH = Path(os.getenv('AUDIT_LOG_PATH', './audit_logs'))
    
    # Safety Settings
    PROTECTED_PROCESSES = [
        'System', 'svchost.exe', 'csrss.exe', 'smss.exe', 
        'wininit.exe', 'services.exe', 'lsass.exe', 'winlogon.exe',
        'explorer.exe', 'dwm.exe', 'RuntimeBroker.exe'
    ]
    
    @classmethod
    def validate(cls):
        """Validate configuration settings."""
        errors = []
        
        if not cls.OLLAMA_API_KEY:
            errors.append("OLLAMA_API_KEY is not set")
        
        if cls.CPU_THRESHOLD <= 0 or cls.CPU_THRESHOLD > 100:
            errors.append("CPU_THRESHOLD must be between 0 and 100")
        
        if cls.MEMORY_THRESHOLD <= 0 or cls.MEMORY_THRESHOLD > 100:
            errors.append("MEMORY_THRESHOLD must be between 0 and 100")
        
        return errors
    
    @classmethod
    def ensure_directories(cls):
        """Ensure required directories exist."""
        cls.AUDIT_LOG_PATH.mkdir(parents=True, exist_ok=True)
