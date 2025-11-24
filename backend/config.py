"""
Configuration management for SignalController
Loads settings from environment variables with sensible defaults
"""

import os
from pathlib import Path


class Config:
    """Application configuration"""
    
    def __init__(self):
        # Data directories
        # Use /var/lib for writable data (systemd ProtectSystem=strict makes /opt read-only)
        self.DATA_DIR = Path('/var/lib/signal-controller')
        self.LOG_DIR = Path('/var/log/signal-controller')
        
        # Database
        self.DATABASE_PATH = os.getenv(
            'DATABASE_PATH',
            str(self.DATA_DIR / 'messages.db')
        )
        
        # Signal CLI configuration
        self.SIGNAL_CLI_URL = os.getenv(
            'SIGNAL_CLI_URL',
            'http://localhost:8080'
        )
        self.SIGNAL_PHONE_NUMBER = os.getenv('SIGNAL_PHONE_NUMBER', '')
        
        # API Security
        self.API_KEY = os.getenv('SIGNAL_API_KEY', 'CHANGE_ME_INSECURE_DEFAULT_KEY')
        
        # IP Whitelist for private interface (comma-separated)
        # Example: "192.168.1.100,192.168.1.101,127.0.0.1"
        whitelist_str = os.getenv('PRIVATE_API_WHITELIST', '127.0.0.1')
        self.PRIVATE_API_WHITELIST = [ip.strip() for ip in whitelist_str.split(',') if ip.strip()]
        
        # Create directories if they don't exist (only if writable)
        # systemd services have these directories created by install.sh
        try:
            self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError):
            # Directory should already exist from install.sh
            pass
            
        try:
            self.LOG_DIR.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError):
            # Directory should already exist from install.sh
            pass
        
    def validate(self):
        """Validate configuration"""
        errors = []
        
        if self.API_KEY == 'CHANGE_ME_INSECURE_DEFAULT_KEY':
            errors.append("API_KEY must be changed from default value")
        
        if not self.SIGNAL_PHONE_NUMBER:
            errors.append("SIGNAL_PHONE_NUMBER environment variable must be set")
        
        return errors
