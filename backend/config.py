"""
Configuration management for SignalController
Loads settings from environment variables with sensible defaults
"""

import os
from pathlib import Path


class Config:
    """Application configuration"""
    
    def __init__(self):
        # Base paths
        self.BASE_DIR = Path(os.getenv('SIGNAL_CONTROLLER_BASE', '/opt/signal-controller'))
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
        
        # SSL Certificates for public interface
        self.SSL_CERT_FILE = os.getenv(
            'SSL_CERT_FILE',
            '/etc/ssl/certs/signal-controller.crt'
        )
        self.SSL_KEY_FILE = os.getenv(
            'SSL_KEY_FILE',
            '/etc/ssl/private/signal-controller.key'
        )
        
        # Rate limiting (requests per minute)
        self.RATE_LIMIT_PUBLIC = int(os.getenv('RATE_LIMIT_PUBLIC', '60'))
        self.RATE_LIMIT_PRIVATE = int(os.getenv('RATE_LIMIT_PRIVATE', '120'))
        
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
        
        # SSL certificates are optional (e.g., when using Cloudflare)
        # if not Path(self.SSL_CERT_FILE).exists():
        #     errors.append(f"SSL certificate not found: {self.SSL_CERT_FILE}")
        #     
        # if not Path(self.SSL_KEY_FILE).exists():
        #     errors.append(f"SSL key not found: {self.SSL_KEY_FILE}")
        
        return errors
