#!/usr/bin/env python3
"""
SQS Worker Provider - Connects to SQS and processes received events.
"""

import json
import logging
import os
import signal
import sys
import time
from typing import Dict, Any, List
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

# Add project root to path to access config_loader
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.providers.config_loader import get_config

# Configure logging
logger = logging.getLogger(__name__)


class Worker:
    """
    Worker class for processing tasks from SQS queue.
    """

    def __init__(self):
        """Initialize worker."""
        self.env_name = os.getenv('APP_ENV', 'dev')
        self.config = get_config()
        self.sqs_client = self._create_sqs_client()
        self.queue_url = None
        self.is_running = False

    def _create_sqs_client(self) -> Any:
        """Create SQS client based on environment."""
        try:
            import boto3

            env_name = self.config.get('environment', {}).get('name', 'dev')

            if env_name in ['dev', 'dev_docker']:
                # LocalStack configuration for dev environments
                aws_config = self.config.get('aws', {})
                endpoint_url = aws_config.get('endpoint_url', 'http://localhost:4566')

                return boto3.client(
                    'sqs',
                    region_name=aws_config.get('region', 'ap-south-1'),
                    endpoint_url=endpoint_url,
                    aws_access_key_id=aws_config.get('access_key_id', 'test'),
                    aws_secret_access_key=aws_config.get('secret_access_key', 'test')
                )
            else:
                # Stage/Prod - only set region, let boto3 use default credential chain (IAM roles)
                return boto3.client(
                    'sqs',
                    region_name=self.config.get('aws', {}).get('region', 'ap-south-1')
                )
        except Exception as e:
            logger.error(f"Error creating SQS client: {e}")
            raise

    def setup_queue(self) -> bool:
        """Setup queue connection."""
        try:
            # Try to get queue name from new configuration structure first
            queue_name = None

            # New structure: queue.sqs.queues.{queue_alias}.name
            default_queue = self.config.get('queue', {}).get('default_queue', 'default_task_execution')
            queues_config = self.config.get('queue', {}).get('sqs', {}).get('queues', {})

            if default_queue in queues_config:
                queue_name = queues_config[default_queue].get('name')

            # Fallback to old structure: queue.sqs.name
            if not queue_name:
                queue_name = self.config.get('queue', {}).get('sqs', {}).get('name')

            if not queue_name:
                raise ValueError("Queue name must be configured in queue configuration")

            # Get queue URL
            try:
                response = self.sqs_client.get_queue_url(QueueName=queue_name)
                self.queue_url = response['QueueUrl']
                logger.info(f"Connected to queue: {queue_name}")
                return True
            except ClientError as e:
                if e.response['Error']['Code'] == 'AWS.SimpleQueueService.NonExistentQueue':
                    # Create queue if it doesn't exist (only in dev environments)
                    if self.env_name in ['dev', 'dev_docker']:
                        logger.info(f"Creating queue: {queue_name}")

                        # Get queue attributes from config
                        queue_config = queues_config.get(default_queue, {})
                        attributes = {
                            'VisibilityTimeout': str(queue_config.get('visibility_timeout', 300)),
                            'MessageRetentionPeriod': str(queue_config.get('message_retention_period', 1209600)),
                            'ReceiveMessageWaitTimeSeconds': str(queue_config.get('wait_time_seconds', 20))
                        }

                        response = self.sqs_client.create_queue(
                            QueueName=queue_name,
                            Attributes=attributes
                        )
                        self.queue_url = response['QueueUrl']
                        logger.info(f"Created queue: {queue_name}")
                        return True
                    else:
                        logger.error(f"Queue {queue_name} does not exist and cannot be created in {self.env_name}")
                        return False
                else:
                    logger.error(f"Error getting queue URL: {e}")
                    return False

        except Exception as e:
            logger.error(f"Error setting up queue: {e}")
            return False

    def start(self):
        """Start the worker."""
        if not self.setup_queue():
            logger.error("Failed to setup queue")
            return

        self.is_running = True
        logger.info("Worker started")

        while self.is_running:
            try:
                self.poll_and_process()
            except KeyboardInterrupt:
                logger.info("Worker stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in worker loop: {e}")
                continue

    def stop(self):
        """Stop the worker."""
        self.is_running = False
        logger.info("Worker stopped")

    def poll_and_process(self):
        """Poll for messages and process them."""
        try:
            # Receive messages
            response = self.sqs_client.receive_message(
                QueueUrl=self.queue_url,
                MaxNumberOfMessages=self.config.get('worker', {}).get('max_messages', 1),
                WaitTimeSeconds=self.config.get('worker', {}).get('wait_time_seconds', 20),
                MessageAttributeNames=['All']
            )

            messages = response.get('Messages', [])

            for message in messages:
                try:
                    # Process message
                    task_data = json.loads(message['Body'])
                    self.process_task(task_data)

                    # Delete message after successful processing
                    self.sqs_client.delete_message(
                        QueueUrl=self.queue_url,
                        ReceiptHandle=message['ReceiptHandle']
                    )

                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error polling messages: {e}")

    def process_task(self, task_data: Dict[str, Any]):
        """Process a task."""
        task_type = task_data.get('task_type', 'unknown')
        task_id = task_data.get('task_id', 'unknown')

        logger.info(f"Processing task {task_id} of type {task_type}")

        # Basic task processing - this would be expanded with actual task handlers
        try:
            # Simulate task processing
            import time
            time.sleep(1)

            logger.info(f"Task {task_id} completed successfully")

        except Exception as e:
            logger.error(f"Error processing task {task_id}: {e}")
            raise

    def health_check(self) -> Dict[str, Any]:
        """Check health of worker."""
        try:
            # Try to list queues as a health check
            response = self.sqs_client.list_queues()

            endpoint_url = None
            if self.env_name in ['dev', 'dev_docker']:
                endpoint_url = 'http://localstack:4566'

            return {
                'status': 'healthy',
                'queue_count': len(response.get('QueueUrls', [])),
                'endpoint': endpoint_url if endpoint_url else 'aws',
                'region': self.config.get('aws', {}).get('region', 'ap-south-1'),
                'is_running': self.is_running
            }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e)
            } 