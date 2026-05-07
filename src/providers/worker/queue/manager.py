"""
SQS Queue Manager for SWE-Agent Worker System
"""
import os
import sys
import boto3
import logging
from typing import Optional, Dict, Any
from botocore.exceptions import ClientError

# Add project root to path to access config_loader
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.providers.config_loader import get_config

logger = logging.getLogger(__name__)


class QueueManager:
    """Manages SQS queue connections and operations."""
    
    def __init__(self):
        self.env_name = os.getenv('APP_ENV', 'dev')
        self.config = get_config()
        self.sqs_client = self._create_sqs_client()
        self.queue_url = None
        # Get configuration from TOML
        queue_config = self.config.get('queue', {}).get('sqs', {}).get('queues', {}).get('default_task_execution', {})
        self.queue_name = queue_config.get('name')
        if not self.queue_name:
            raise ValueError("Queue name must be configured in queue.sqs.queues.default_task_execution.name")
        # Validate and set queue configuration with proper error handling
        visibility = queue_config.get('visibility_timeout', 10800)
        if not isinstance(visibility, int) or visibility <= 0:
            raise ValueError("visibility_timeout must be a positive integer")
        self.visibility_timeout = visibility
        
        retention = queue_config.get('message_retention_period', 1209600)
        if not isinstance(retention, int) or retention <= 0:
            raise ValueError("message_retention_period must be a positive integer")
        self.message_retention_period = retention
        
        wait = queue_config.get('wait_time_seconds', 20)
        if not isinstance(wait, int) or wait < 0:
            raise ValueError("wait_time_seconds must be a non-negative integer")
        self.wait_time_seconds = wait
        
        max_msgs = queue_config.get('max_messages', 1)
        if not isinstance(max_msgs, int) or max_msgs <= 0:
            raise ValueError("max_messages must be a positive integer")
        self.max_messages = max_msgs
        
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.env_name in ['dev', 'dev_docker']

    @property
    def aws_region(self) -> str:
        """Get AWS region."""
        return self.config.get('aws', {}).get('region', 'ap-south-1')

    def _create_sqs_client(self) -> Any:
        """Create SQS client based on environment."""
        try:
            import boto3
            
            if self.is_development:
                # LocalStack configuration
                return boto3.client(
                    'sqs',
                    region_name=self.aws_region,
                    endpoint_url='http://localhost:4566',
                    aws_access_key_id='test',
                    aws_secret_access_key='test'
                )
            else:
                # Stage/Prod - only set region, let boto3 use default credential chain (IAM roles)
                return boto3.client(
                    'sqs',
                    region_name=self.aws_region
                )
        except Exception as e:
            logger.error(f"Error creating SQS client: {e}")
            raise

    def setup_connection(self) -> bool:
        """Setup SQS connection with retry logic."""
        max_retries = 3  # Reduced retries since permission issues won't resolve with retries
        retry_delay = 5  # seconds
        
        for attempt in range(max_retries):
            try:
                # Get or create queue
                self.queue_url = self._get_or_create_queue()
                logger.info("✅ SQS connection established successfully")
                return True
                
            except Exception as e:
                # Don't retry on permission errors
                if 'AccessDenied' in str(e) or 'not authorized' in str(e):
                    logger.error(f"❌ Access denied: {e}")
                    logger.error(f"Please ensure the queue '{self.queue_name}' exists and you have proper permissions.")
                    raise
                
                logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    import time
                    time.sleep(retry_delay)
                else:
                    logger.error("❌ Failed to establish SQS connection after all retries")
                    raise
        
        return False
    
    def _get_or_create_queue(self) -> str:
        """Get existing queue or create new one."""
        try:
            # Try to get existing queue first
            response = self.sqs_client.get_queue_url(QueueName=self.queue_name)
            queue_url = response['QueueUrl']
            logger.info(f"✅ Using existing queue: {self.queue_name}")
            return queue_url
        except self.sqs_client.exceptions.QueueDoesNotExist:
            # Only try to create queue in local/dev environments
            if self.env_name in ['dev', 'dev_docker']:
                logger.info(f"Creating new queue: {self.queue_name}")
                try:
                    response = self.sqs_client.create_queue(
                        QueueName=self.queue_name,
                        Attributes={
                            'VisibilityTimeout': str(self.visibility_timeout),
                            'MessageRetentionPeriod': str(self.message_retention_period)
                        }
                    )
                    queue_url = response['QueueUrl']
                    logger.info(f"✅ Created queue: {self.queue_name}")
                    return queue_url
                except Exception as create_error:
                    if 'AccessDenied' in str(create_error) or 'not authorized' in str(create_error):
                        logger.error(f"❌ No permission to create queue '{self.queue_name}'. Please ensure the queue exists or contact your administrator.")
                    else:
                        logger.error(f"❌ Failed to create queue '{self.queue_name}': {create_error}")
                    raise
            else:
                # In production environments, queue should already exist
                logger.error(f"❌ Queue '{self.queue_name}' does not exist and cannot be created in production environment.")
                logger.error(f"Please ensure the queue '{self.queue_name}' is provisioned or set the correct SQS_QUEUE_NAME environment variable.")
                raise RuntimeError(f"Queue '{self.queue_name}' does not exist")
    
    def receive_messages(self, max_messages: int = None, wait_time: int = None) -> list:
        """Receive messages from the queue."""
        if not self.sqs_client or not self.queue_url:
            raise RuntimeError("Queue connection not established")
            
        # Use config values if not provided
        if max_messages is None:
            max_messages = self.max_messages
        if wait_time is None:
            wait_time = self.wait_time_seconds
            
        try:
            response = self.sqs_client.receive_message(
                QueueUrl=self.queue_url,
                MaxNumberOfMessages=max_messages,
                WaitTimeSeconds=wait_time,
                MessageAttributeNames=['All']
            )
            return response.get('Messages', [])
        except Exception as e:
            logger.error(f"Error receiving messages: {e}")
            return []
    
    def delete_message(self, receipt_handle: str) -> bool:
        """Delete a processed message from the queue."""
        if not self.sqs_client or not self.queue_url:
            raise RuntimeError("Queue connection not established")
            
        try:
            self.sqs_client.delete_message(
                QueueUrl=self.queue_url,
                ReceiptHandle=receipt_handle
            )
            return True
        except Exception as e:
            logger.error(f"Error deleting message: {e}")
            return False
    
    def send_message(self, message_body: str, attributes: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Send a message to the queue."""
        if not self.sqs_client or not self.queue_url:
            raise RuntimeError("Queue connection not established")
            
        try:
            params = {
                'QueueUrl': self.queue_url,
                'MessageBody': message_body
            }
            
            if attributes:
                params['MessageAttributes'] = attributes
                
            response = self.sqs_client.send_message(**params)
            return response.get('MessageId')
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return None
    
    def get_queue_attributes(self, queue_url: str, attribute_names: list = None) -> Dict[str, Any]:
        """Get queue attributes."""
        try:
            params = {'QueueUrl': queue_url}
            if attribute_names:
                params['AttributeNames'] = attribute_names
            else:
                params['AttributeNames'] = ['All']
                
            response = self.sqs_client.get_queue_attributes(**params)
            return response.get('Attributes', {})
        except ClientError as e:
            logger.error(f"Error getting queue attributes: {e}")
            return {}

    def health_check(self) -> Dict[str, Any]:
        """Check health of queue manager."""
        try:
            # Try to list queues as a health check
            response = self.sqs_client.list_queues()
            
            endpoint_url = None
            if self.env_name in ['dev', 'dev_docker']:
                endpoint_url = 'http://localhost:4566'

            return {
                'status': 'healthy',
                'queue_count': len(response.get('QueueUrls', [])),
                'endpoint': endpoint_url if endpoint_url else 'aws',
                'region': self.config.get('aws.region', 'ap-south-1')
            }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e)
            } 