#!/usr/bin/env python3
"""
SQS Sender Provider - Function to send messages to SQS queue.
"""

import json
import logging
import os
import time
from typing import Dict, Any, Optional
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from src.providers.config_loader import get_config

# Configure logging
logger = logging.getLogger(__name__)


class SQSSender:
    """SQS Sender provider to push messages to queue."""
    
    def __init__(self):
        """Initialize the SQS sender."""
        self.env_name = os.getenv('APP_ENV', 'dev')
        self.config = get_config()
        self.sqs_client = self._create_sqs_client()
        self.queue_url = None
        self.setup_sqs()
    
    def _create_sqs_client(self) -> Any:
        """Create SQS client based on environment."""
        try:
            import boto3
            
            env_name = self.config.get('environment.name', 'dev')
            
            if env_name == 'dev':
                # LocalStack configuration
                return boto3.client(
                    'sqs',
                    region_name=self.config.get('aws.region', 'ap-south-1'),
                    endpoint_url='http://localhost:4566',
                    aws_access_key_id='test',
                    aws_secret_access_key='test'
                )
            else:
                # Stage/Prod - only set region, let boto3 use default credential chain (IAM roles)
                return boto3.client(
                    'sqs',
                    region_name=self.config.get('aws.region', 'ap-south-1')
                )
        except Exception as e:
            logger.error(f"Error creating SQS client: {e}")
            raise
    
    def get_queue_config(self) -> Dict[str, Any]:
        """Get queue configuration from config file."""
        return self.config.get('queue', {}).get('sqs', {}).get('queues', {}).get('default_task_execution', {})
    
    def setup_sqs(self):
        """Setup SQS connection."""
        try:
            # Get or create queue
            self.setup_queue()
            logger.info("✅ SQS sender connection established")
            
        except NoCredentialsError:
            logger.error("❌ AWS credentials not found")
            raise
        except Exception as e:
            logger.error(f"❌ Failed to setup SQS sender: {e}")
            raise
    
    def setup_queue(self):
        """Get or create the SQS queue."""
        queue_name = self.config.get('queue', {}).get('sqs', {}).get('name')
        if not queue_name:
            raise ValueError("Queue name must be configured in queue.sqs.name")
        
        try:
            # Try to get existing queue
            response = self.sqs_client.get_queue_url(QueueName=queue_name)
            self.queue_url = response['QueueUrl']
            logger.info(f"Using existing queue: {queue_name}")
        except ClientError as e:
            if e.response['Error']['Code'] == 'AWS.SimpleQueueService.NonExistentQueue':
                # Create new queue with config values
                logger.info(f"Creating new queue: {queue_name}")
                
                # Get queue configuration from config file
                queue_config = self.get_queue_config()
                attributes = {
                    'VisibilityTimeout': str(queue_config.get('visibility_timeout', 10800)),  # Default 3 hours
                    'MessageRetentionPeriod': str(queue_config.get('message_retention_period', 1209600)),  # 14 days
                    'ReceiveMessageWaitTimeSeconds': str(queue_config.get('wait_time_seconds', 20))
                }
                
                response = self.sqs_client.create_queue(
                    QueueName=queue_name,
                    Attributes=attributes
                )
                self.queue_url = response['QueueUrl']
                logger.info(f"✅ Created queue: {queue_name} with VisibilityTimeout: {attributes['VisibilityTimeout']}s")
            else:
                logger.error(f"❌ Error with queue {queue_name}: {e}")
                raise
    
    def send_to_worker(self, event_data: Dict[str, Any]) -> bool:
        """
        Send an event to the worker via SQS.
        
        Args:
            event_data: Dictionary containing the event data to send
            
        Returns:
            bool: True if message sent successfully, False otherwise
        """
        try:
            # Add metadata
            message_data = {
                'timestamp': time.time(),
                'event_type': event_data.get('event_type', 'generic'),
                'source': 'swe-agent',
                'data': event_data
            }
            
            # Convert to JSON
            message_body = json.dumps(message_data, indent=2)
            
            # Send message to SQS
            response = self.sqs_client.send_message(
                QueueUrl=self.queue_url,
                MessageBody=message_body,
                MessageAttributes={
                    'event_type': {
                        'StringValue': event_data.get('event_type', 'generic'),
                        'DataType': 'String'
                    },
                    'source': {
                        'StringValue': 'swe-agent',
                        'DataType': 'String'
                    }
                }
            )
            
            message_id = response.get('MessageId')
            logger.info(f"✅ Message sent to worker: {message_id}")
            logger.info(f"Event type: {event_data.get('event_type', 'generic')}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to send message to worker: {e}")
            return False


# Global sender instance
_sender = None

def get_sender() -> SQSSender:
    """Get or create the global sender instance."""
    global _sender
    if _sender is None:
        _sender = SQSSender()
    return _sender


def send_to_worker(event_data: Dict[str, Any]) -> bool:
    """
    Simple function to send event to worker.
    
    Args:
        event_data: Event data to send
        
    Returns:
        bool: True if sent successfully
    """
    try:
        sender = get_sender()
        return sender.send_to_worker(event_data)
    except Exception as e:
        logger.error(f"❌ Failed to send to worker: {e}")
        return False


# Example usage functions
def send_autonomous_agent_event(repo_url: str, task_description: str) -> bool:
    """Send an autonomous agent event to worker."""
    event_data = {
        'event_type': 'autonomous_agent',
        'repository_url': repo_url,
        'task_description': task_description,
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
    }
    return send_to_worker(event_data)


def send_custom_event(event_type: str, **kwargs) -> bool:
    """Send a custom event to worker."""
    event_data = {
        'event_type': event_type,
        **kwargs
    }
    return send_to_worker(event_data) 