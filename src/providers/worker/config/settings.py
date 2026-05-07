"""
Configuration settings for SWE-Agent Worker System using centralized environments
"""
import os
import sys
from typing import Dict, Any, Optional

# Add project root to path to access config_loader
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import centralized config loader
from src.providers.config_loader import get_config

class WorkerConfig:
    """Worker configuration class for compatibility with tests."""
    
    def __init__(self):
        """Initialize worker configuration."""
        self._env_name = os.getenv('APP_ENV', 'dev')
        self._config = get_config()
    
    @property
    def env_name(self) -> str:
        """Get environment name."""
        return self._env_name
    
    @property
    def is_local(self) -> bool:
        """Check if running in local environment."""
        return self._env_name in ['dev', 'dev_docker']
    
    @property
    def aws_region(self) -> str:
        """Get AWS region."""
        return self._config.get('aws', {}).get('region', 'ap-south-1')
    
    @property
    def max_retries(self) -> int:
        """Get max retries."""
        return self._config.get('worker', {}).get('max_retries', 3)
    
    @property
    def queue_name(self) -> str:
        """Get queue name."""
        queue_name = self._config.get('queue', {}).get('sqs', {}).get('name')
        if not queue_name:
            raise ValueError("Queue name must be configured in queue.sqs.name")
        return queue_name
    
    @property
    def endpoint_url(self) -> str:
        """Get endpoint URL for local development."""
        if self.is_local:
            return 'http://localhost:4566'
        return None


class WorkerSettings:
    """
    Configuration settings for worker processes.
    """
    
    def __init__(self):
        """Initialize worker settings."""
        self._env_name = os.getenv('APP_ENV', 'dev')
        self._config = get_config()
    
    @property
    def env_name(self) -> str:
        """Get the environment name."""
        return self._env_name
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self._env_name in ['dev', 'dev_docker']
    
    @property
    def aws_region(self) -> str:
        """Get AWS region."""
        return self._config.get('aws', {}).get('region', 'ap-south-1')
    
    @property
    def aws_endpoint_url(self) -> Optional[str]:
        """Get AWS endpoint URL (for LocalStack)."""
        return self._config.get('aws', {}).get('endpoint_url')
    
    @property
    def max_retries(self) -> int:
        """Get maximum number of retries for tasks."""
        return self._config.get('worker', {}).get('max_retries', 3)
    
    @property
    def retry_delay(self) -> int:
        """Get retry delay in seconds."""
        return self._config.get('worker', {}).get('retry_delay', 5)
    
    @property
    def environment(self) -> str:
        """Get the environment name."""
        return self._config.get('environment', {}).get('name', 'dev')
    
    @property
    def debug(self) -> bool:
        """Check if debug mode is enabled."""
        return self._config.get('environment', {}).get('debug', False)
    
    def get_aws_config(self) -> Dict[str, Any]:
        """Get AWS configuration."""
        config = {
            'region_name': self.aws_region,
        }
        
        if self.is_development:
            config['endpoint_url'] = 'http://localhost:4566'
            # LocalStack requires explicit test credentials
            config['aws_access_key_id'] = 'test'
            config['aws_secret_access_key'] = 'test'
        # For stage/prod: only set region, let boto3 use default credential chain (IAM roles)
                
        return config
    
    def get_queue_config(self) -> Dict[str, Any]:
        """Get queue configuration."""
        return {
            'name': self._config.get('queue', {}).get('sqs', {}).get('name'),
            'visibility_timeout': self._config.get('queue', {}).get('sqs', {}).get('visibility_timeout', 300),
            'message_retention_period': self._config.get('queue', {}).get('sqs', {}).get('message_retention_period', 1209600),
            'wait_time_seconds': self._config.get('queue', {}).get('sqs', {}).get('wait_time_seconds', 20),
            'max_messages': self._config.get('queue', {}).get('sqs', {}).get('max_messages', 1)
        }
    
    def get_worker_config(self) -> Dict[str, Any]:
        """Get worker configuration."""
        return {
            'name': self._config.get('worker', {}).get('name', 'swe-agent-task-execution-worker'),
            'max_retries': self.max_retries,
            'retry_delay': self.retry_delay,
            'log_level': self._config.get('worker', {}).get('log_level', 'INFO'),
            'max_messages': self._config.get('worker', {}).get('max_messages', 1),
            'wait_time_seconds': self._config.get('worker', {}).get('wait_time_seconds', 20),
            'visibility_timeout': self._config.get('worker', {}).get('visibility_timeout', 300)
        }

# Create default settings instance
settings = WorkerSettings()

def get_worker_config():
    """Get worker configuration instance."""
    return WorkerConfig() 