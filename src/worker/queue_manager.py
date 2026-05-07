"""
Queue Manager for SWE Agent worker system.
Handles SQS operations with support for LocalStack in local development.
"""

import json
import logging
import os
import time
from typing import Dict, Any, Optional, List
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import redis
from src.providers.config_loader import get_config

logger = logging.getLogger(__name__)


class QueueManager:
    """
    Manages queue operations for SWE Agent tasks.
    Supports SQS (with LocalStack for local dev) and Redis fallback.
    """
    
    def __init__(self):
        """Initialize queue manager with configuration."""
        # Load configuration
        from src.providers.config_loader import get_config
        self.config = get_config()
        self.env_name = self.config.get('environment', {}).get('name', 'dev')

        # Initialize queue configuration
        self.queue_type = self.config.get('queue', {}).get('type', 'sqs')

        # Initialize queue URL cache (for multi-queue support)
        self.queue_urls = {}

        # Load queue names from config
        self._load_queue_names()

        # Initialize SQS client
        self._init_sqs()

        # Initialize Redis client
        self._init_redis()
            
    def _determine_queue_type(self) -> str:
        """Determine which queue type to use based on configuration."""
        queue_type = self.config.get('queue', {}).get('type', 'sqs')
        logger.info(f"Using queue type: {queue_type}")
        return queue_type
    
    def _init_sqs(self):
        """Initialize SQS client and queue URLs for all configured queues."""
        try:
            self.sqs_client = self._get_sqs_client()
            self.queue_urls = {}

            # Initialize URLs for all configured queues
            for queue_alias, queue_config in self.queue_configs.items():
                queue_name = queue_config['name']

                try:
                    response = self.sqs_client.get_queue_url(QueueName=queue_name)
                    url = response['QueueUrl']
                    logger.info(f"Found existing SQS queue: {queue_name} (alias: {queue_alias})")
                except self.sqs_client.exceptions.QueueDoesNotExist:
                    logger.info(f"Queue {queue_name} does not exist, creating it...")
                    # Create queue with attributes from config
                    attributes = {
                        'VisibilityTimeout': str(queue_config.get('visibility_timeout', 300)),
                        'MessageRetentionPeriod': str(queue_config.get('message_retention_period', 1209600)),
                        'ReceiveMessageWaitTimeSeconds': str(queue_config.get('wait_time_seconds', 20))
                    }

                    response = self.sqs_client.create_queue(
                        QueueName=queue_name,
                        Attributes=attributes
                    )
                    url = response['QueueUrl']
                    logger.info(f"Created SQS queue: {queue_name} (alias: {queue_alias})")

                # Cache URL by queue name
                self.queue_urls[queue_name] = url

            logger.info(f"Initialized {len(self.queue_urls)} SQS queue URL(s)")

        except Exception as e:
            logger.error(f"Failed to initialize SQS: {e}")
            raise
    
    def _init_redis(self):
        """Initialize Redis client."""
        try:
            redis_config = self.config.get('cache', {}).get('redis', {})
            self.redis_client = redis.Redis(
                host=redis_config.get('host', 'localhost'),
                port=redis_config.get('port', 6379),
                password=redis_config.get('password', ''),
                db=redis_config.get('db', 0),
                decode_responses=True,
                socket_timeout=redis_config.get('timeout', 1)
            )
            
            # Test the connection
            self.redis_client.ping()
            logger.info("Redis client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {e}")
            raise
    
    def _load_queue_names(self):
        """Load queue names and configurations from configuration."""
        # Get the queue configurations
        queues_config = self.config.get('queue', {}).get('sqs', {}).get('queues', {})
        
        if not queues_config:
            raise ValueError("Queue configuration must be specified in queue.sqs.queues")
        
        # Load queue configurations
        self.queue_configs = {}
        for queue_alias, queue_config in queues_config.items():
            self.queue_configs[queue_alias] = queue_config
        
        # Set default queue
        default_queue = self.config.get('queue', {}).get('default_queue', 'default_task_execution')
        if default_queue in self.queue_configs:
            self.main_queue_name = self.queue_configs[default_queue]['name']
            self.default_queue_alias = default_queue
        else:
            # Use first queue as default if specified default doesn't exist
            first_alias = list(self.queue_configs.keys())[0]
            self.main_queue_name = self.queue_configs[first_alias]['name']
            self.default_queue_alias = first_alias
            logger.warning(f"Default queue '{default_queue}' not found. Using '{first_alias}' as default.")
        
        logger.info(f"Loaded {len(self.queue_configs)} queue configuration(s)")
        for alias, config in self.queue_configs.items():
            logger.info(f"  - {alias}: {config['name']}")
        logger.info(f"Default queue: {self.default_queue_alias} ({self.main_queue_name})")

    def get_queue_config(self, queue_alias: Optional[str] = None) -> Dict[str, Any]:
        """Get configuration for a specific queue."""
        if queue_alias is None:
            queue_alias = self.default_queue_alias
        
        if queue_alias not in self.queue_configs:
            raise ValueError(f"Queue alias '{queue_alias}' not found. Available: {list(self.queue_configs.keys())}")
        
        return self.queue_configs[queue_alias]

    def get_queue_for_task_type(self, task_type: str) -> str:
        """Get the appropriate queue alias for a task type."""
        # With single queue configuration, all tasks go to the default queue
        # This method is kept for future extensibility when multiple queues are needed
        task_routing = self.config.get('queue', {}).get('task_routing', {})
        
        # Check if there's a specific mapping for this task type
        if task_routing and task_type in task_routing:
            return task_routing[task_type]
        
        # Use default queue (single queue for all tasks)
        return self.default_queue_alias

    def send_task(self, task_data: Dict[str, Any], queue_alias: Optional[str] = None) -> bool:
        """
        Send a task to the specified queue.
        
        Args:
            task_data: Task data to send
            queue_alias: Alias of the queue to send to (defaults to queue for task type)
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Determine which queue to use
        if queue_alias is None:
            task_type = task_data.get('task_type', 'unknown')
            queue_alias = self.get_queue_for_task_type(task_type)
        
        queue_config = self.get_queue_config(queue_alias)
        queue_name = queue_config['name']
        
        try:
            if self.queue_type == 'sqs':
                return self._send_sqs_message(task_data, queue_config)
            elif self.queue_type == 'redis':
                return self._send_redis_message(task_data, queue_name)
        except Exception as e:
            logger.error(f"Failed to send task to queue {queue_alias}: {e}")
            return False
    
    def _send_sqs_message(self, task_data: Dict[str, Any], queue_config: Dict[str, Any]) -> bool:
        """Send message to SQS queue with optional delay support."""
        try:
            # Extract queue name from config and get cached URL
            queue_name = queue_config['name']
            queue_url = self.queue_urls.get(queue_name)

            if not queue_url:
                logger.error(f"Queue URL not available for {queue_name}")
                return False

            message_body = json.dumps(task_data)

            # Extract delay_seconds from task_data for SQS DelaySeconds
            delay_seconds = task_data.get('delay_seconds', 0)

            message_params = {
                'QueueUrl': queue_url,
                'MessageBody': message_body,
                'MessageAttributes': {
                    'task_type': {
                        'StringValue': task_data.get('task_type', 'unknown'),
                        'DataType': 'String'
                    },
                    'priority': {
                        'StringValue': str(task_data.get('priority', 0)),
                        'DataType': 'Number'
                    }
                }
            }

            # Add DelaySeconds if specified (max 900 seconds = 15 minutes for SQS)
            if delay_seconds > 0:
                # SQS DelaySeconds has a maximum of 900 seconds (15 minutes)
                delay_seconds = min(delay_seconds, 900)
                message_params['DelaySeconds'] = delay_seconds
                logger.debug(f"Scheduling message with {delay_seconds} seconds delay")

            response = self.sqs_client.send_message(**message_params)

            if delay_seconds > 0:
                logger.info(f"Message scheduled for delivery in {delay_seconds} seconds to {queue_name}: {response['MessageId']}")
            else:
                logger.info(f"Message sent to SQS queue {queue_name}: {response['MessageId']}")
            return True

        except Exception as e:
            logger.error(f"Failed to send SQS message: {e}")
            return False
    
    def _send_redis_message(self, task_data: Dict[str, Any], queue_name: str) -> bool:
        """Send message to Redis queue."""
        try:
            message_body = json.dumps(task_data)
            self.redis_client.lpush(queue_name, message_body)
            logger.info(f"Message sent to Redis queue: {queue_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to send Redis message: {e}")
            return False
    
    def receive_tasks(self, queue_alias: Optional[str] = None, max_messages: Optional[int] = None, wait_time: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Receive tasks from the specified queue.
        
        Args:
            queue_alias: Alias of the queue to receive from (defaults to default queue)
            max_messages: Maximum number of messages to receive (uses queue config if not specified)
            wait_time: Long polling wait time in seconds (uses queue config if not specified)
            
        Returns:
            List of task messages
        """
        if queue_alias is None:
            queue_alias = self.default_queue_alias
            
        queue_config = self.get_queue_config(queue_alias)
        queue_name = queue_config['name']
        
        # Use queue-specific defaults if not provided
        max_messages = max_messages or queue_config.get('max_messages', 1)
        wait_time = wait_time or queue_config.get('wait_time_seconds', 20)
        
        try:
            if self.queue_type == 'sqs':
                return self._receive_sqs_messages(queue_config, max_messages, wait_time)
            elif self.queue_type == 'redis':
                return self._receive_redis_messages(queue_name, max_messages, wait_time)
        except Exception as e:
            logger.error(f"Failed to receive tasks from queue {queue_alias}: {e}")
            return []
    
    def _receive_sqs_messages(self, queue_config: Dict[str, Any], max_messages: int, wait_time: int) -> List[Dict[str, Any]]:
        """Receive messages from SQS queue."""
        try:
            # Extract queue name from config and get cached URL
            queue_name = queue_config['name']
            queue_url = self.queue_urls.get(queue_name)

            if not queue_url:
                logger.error(f"Queue URL not available for {queue_name}")
                return []

            response = self.sqs_client.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=max_messages,
                WaitTimeSeconds=wait_time,
                MessageAttributeNames=['All']
            )

            messages = response.get('Messages', [])

            # Parse messages
            parsed_messages = []
            for message in messages:
                try:
                    task_data = json.loads(message['Body'])
                    task_data['_queue_metadata'] = {
                        'receipt_handle': message['ReceiptHandle'],
                        'message_id': message['MessageId'],
                        'queue_type': 'sqs',
                        'queue_name': queue_name  # Store queue name for delete operation
                    }
                    parsed_messages.append(task_data)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse message: {e}")
                    continue

            return parsed_messages

        except Exception as e:
            logger.error(f"Failed to receive SQS messages: {e}")
            return []
    
    def _receive_redis_messages(self, queue_name: str, max_messages: int, wait_time: int) -> List[Dict[str, Any]]:
        """Receive messages from Redis queue."""
        try:
            messages = []
            
            for _ in range(max_messages):
                # Use blocking pop with timeout
                result = self.redis_client.brpop(queue_name, timeout=wait_time)
                if not result:
                    break
                
                _, message_body = result
                try:
                    task_data = json.loads(message_body)
                    task_data['_queue_metadata'] = {
                        'queue_type': 'redis',
                        'message_body': message_body
                    }
                    messages.append(task_data)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse Redis message: {e}")
                    continue
                    
                # If we got a message immediately, don't wait for more
                wait_time = 1
            
            return messages
            
        except Exception as e:
            logger.error(f"Failed to receive Redis messages: {e}")
            return []
    
    def delete_task(self, task_data: Dict[str, Any]) -> bool:
        """
        Delete a processed task from the queue.
        
        Args:
            task_data: Task data containing queue metadata
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            metadata = task_data.get('_queue_metadata', {})
            
            if metadata.get('queue_type') == 'sqs':
                return self._delete_sqs_message(metadata)
            elif metadata.get('queue_type') == 'redis':
                # Redis messages are automatically removed when popped
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to delete task: {e}")
            return False
    
    def _delete_sqs_message(self, metadata: Dict[str, Any]) -> bool:
        """Delete message from SQS queue."""
        try:
            receipt_handle = metadata.get('receipt_handle')
            if not receipt_handle:
                logger.error("No receipt handle found for SQS message deletion")
                return False

            # Get queue name from metadata
            queue_name = metadata.get('queue_name', self.main_queue_name)
            queue_url = self.queue_urls.get(queue_name)

            if not queue_url:
                logger.error(f"Queue URL not available for {queue_name}")
                return False

            self.sqs_client.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=receipt_handle
            )

            logger.debug(f"SQS message deleted successfully from {queue_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete SQS message: {e}")
            return False

    def return_task_to_queue(self, task_data: Dict[str, Any]) -> bool:
        """
        Return a task to the queue immediately by setting visibility to 0.
        Used when a worker receives a task type it doesn't handle.

        Args:
            task_data: Task data containing queue metadata

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            metadata = task_data.get('_queue_metadata', {})

            if metadata.get('queue_type') != 'sqs':
                logger.warning("return_task_to_queue only supported for SQS")
                return False

            receipt_handle = metadata.get('receipt_handle')
            queue_name = metadata.get('queue_name', self.main_queue_name)
            queue_url = self.queue_urls.get(queue_name)

            if not receipt_handle:
                logger.error("No receipt handle found for returning task to queue")
                return False

            if not queue_url:
                logger.error(f"Queue URL not available for {queue_name}")
                return False

            # Set visibility timeout to 0 - message immediately available
            self.sqs_client.change_message_visibility(
                QueueUrl=queue_url,
                ReceiptHandle=receipt_handle,
                VisibilityTimeout=0
            )

            task_id = task_data.get('task_id', 'unknown')
            task_type = task_data.get('task_type', 'unknown')
            logger.info(f"Returned task {task_id} (type: {task_type}) to queue {queue_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to return task to queue: {e}")
            return False
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get statistics about queue usage."""
        try:
            if self.queue_type == 'sqs':
                return self._get_sqs_stats()
            elif self.queue_type == 'redis':
                return self._get_redis_stats()
        except Exception as e:
            logger.error(f"Failed to get queue stats: {e}")
            return {}
    
    def _get_sqs_stats(self) -> Dict[str, Any]:
        """Get SQS queue statistics for ALL configured queues."""
        stats = {}

        if not self.queue_urls:
            return {'error': 'No queue URLs available'}

        # Iterate over all queues
        for queue_name, queue_url in self.queue_urls.items():
            try:
                response = self.sqs_client.get_queue_attributes(
                    QueueUrl=queue_url,
                    AttributeNames=[
                        'ApproximateNumberOfMessages',
                        'ApproximateNumberOfMessagesNotVisible',
                        'ApproximateNumberOfMessagesDelayed'
                    ]
                )

                attrs = response.get('Attributes', {})
                stats[queue_name] = {
                    'available_messages': int(attrs.get('ApproximateNumberOfMessages', 0)),
                    'in_flight_messages': int(attrs.get('ApproximateNumberOfMessagesNotVisible', 0)),
                    'delayed_messages': int(attrs.get('ApproximateNumberOfMessagesDelayed', 0))
                }
            except Exception as e:
                logger.error(f"Failed to get stats for queue {queue_name}: {e}")
                stats[queue_name] = {'error': str(e)}

        return stats
    
    def _get_redis_stats(self) -> Dict[str, Any]:
        """Get Redis queue statistics."""
        stats = {}
        
        try:
            length = self.redis_client.llen(self.main_queue_name)
            stats[self.main_queue_name] = {
                'available_messages': length,
                'in_flight_messages': 0,  # Redis doesn't have this concept with simple lists
                'delayed_messages': 0
            }
        except Exception as e:
            logger.error(f"Failed to get Redis stats for queue {self.main_queue_name}: {e}")
            stats[self.main_queue_name] = {'error': str(e)}
        
        return stats 

    def _get_sqs_client(self):
        """Get SQS client based on environment."""
        import boto3
        
        env_name = self.config.get('environment', {}).get('name', 'dev')
        
        if env_name == 'dev':
            # LocalStack for dev
            return boto3.client(
                'sqs',
                region_name=self.config.get('aws', {}).get('region', 'ap-south-1'),
                endpoint_url='http://localhost:4566',
                aws_access_key_id='test',
                aws_secret_access_key='test'
            )
        elif env_name == 'dev_docker':
            # LocalStack for docker dev
            return boto3.client(
                'sqs',
                region_name=self.config.get('aws', {}).get('region', 'ap-south-1'),
                endpoint_url='http://localstack:4566',
                aws_access_key_id='test',
                aws_secret_access_key='test'
            )
        else:
            # Stage/Prod - only set region, let boto3 use default credential chain (IAM roles)
            return boto3.client(
                'sqs',
                region_name=self.config.get('aws', {}).get('region', 'ap-south-1')
            ) 