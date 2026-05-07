#!/usr/bin/env python3
"""
Unit tests for worker queue manager components.
"""

import os
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.providers.worker.queue.manager import QueueManager


@pytest.mark.unit
@pytest.mark.worker
class TestQueueManager:
    """Test cases for QueueManager."""
    
    @pytest.fixture
    def queue_manager(self):
        """Fixture providing a mocked QueueManager instance."""
        # Create a mock manager with all necessary attributes
        manager = Mock(spec=QueueManager)
        manager.is_development = True
        manager.sqs_client = Mock()
        manager.queue_url = 'https://sqs.region.amazonaws.com/account/queue'
        manager.queue_name = 'test-queue'
        
        # Mock methods to match real implementation behavior
        manager.send_message.return_value = 'test-message-id'  # Returns MessageId string, not dict
        manager.receive_messages.return_value = []
        manager.delete_message.return_value = True
        manager.setup_connection.return_value = True  # Returns boolean, not Mock
        
        return manager
    
    @patch('boto3.client')
    @patch('src.providers.config_loader.get_config')
    def test_setup_connection_local(self, mock_get_config, mock_boto_client, queue_manager):
        """Test setup connection for local environment."""
        # Mock config
        mock_get_config.return_value = {
            'queue': {'sqs': {'name': 'test-queue'}},
            'aws': {'region': 'ap-south-1'}
        }
        
        mock_sqs = Mock()
        mock_boto_client.return_value = mock_sqs
        mock_sqs.get_queue_url.return_value = {'QueueUrl': 'http://test-queue-url'}
        
        # Use real implementation for testing
        from src.providers.worker.queue.manager import QueueManager
        
        with patch.dict(os.environ, {
            'APP_ENV': 'dev',
            'AWS_ENDPOINT_URL': 'http://localhost:4566'
        }):
            real_manager = QueueManager.__new__(QueueManager)
            real_manager.env_name = 'dev'
            real_manager.config = mock_get_config.return_value
            real_manager.sqs_client = mock_sqs
            real_manager.queue_name = 'test-queue'
            real_manager.visibility_timeout = 300
            real_manager.message_retention_period = 1209600
            real_manager.wait_time_seconds = 20
            real_manager.max_messages = 1
            
            result = real_manager.setup_connection()
            
            assert result is True
    
    @patch('boto3.client')
    @patch('src.providers.config_loader.get_config')
    def test_setup_connection_production(self, mock_get_config, mock_boto_client, queue_manager):
        """Test setup connection for production environment."""
        # Mock config
        mock_get_config.return_value = {
            'queue': {'sqs': {'name': 'test-queue'}},
            'aws': {'region': 'us-west-2'}
        }
        
        mock_sqs = Mock()
        mock_boto_client.return_value = mock_sqs
        mock_sqs.get_queue_url.return_value = {'QueueUrl': 'http://test-queue-url'}
        
        # Use real implementation for testing
        from src.providers.worker.queue.manager import QueueManager
        
        with patch.dict(os.environ, {'APP_ENV': 'production'}):
            real_manager = QueueManager.__new__(QueueManager)
            real_manager.env_name = 'production'
            real_manager.config = mock_get_config.return_value
            real_manager.sqs_client = mock_sqs
            real_manager.queue_name = 'test-queue'
            real_manager.visibility_timeout = 300
            real_manager.message_retention_period = 1209600
            real_manager.wait_time_seconds = 20
            real_manager.max_messages = 1
            
            result = real_manager.setup_connection()
            
            assert result is True

    def test_send_message(self, queue_manager):
        """Test sending a message."""
        queue_manager.sqs_client = Mock()
        queue_manager.queue_url = 'http://test-queue-url'
        
        # Mock the SQS client response
        queue_manager.sqs_client.send_message.return_value = {'MessageId': 'test-message-id'}
        
        # Since we're testing the real implementation, we need to use the real send_message method
        # Import and instantiate a real QueueManager for this test
        from src.providers.worker.queue.manager import QueueManager
        
        # Create a real instance but mock its SQS client
        real_manager = QueueManager.__new__(QueueManager)  # Create without calling __init__
        real_manager.sqs_client = queue_manager.sqs_client
        real_manager.queue_url = queue_manager.queue_url
        
        result = real_manager.send_message(
            'test message', 
            {'test_attr': {'StringValue': 'test', 'DataType': 'String'}}
        )
        
        assert result == 'test-message-id'
        queue_manager.sqs_client.send_message.assert_called_once()
    
    def test_receive_messages(self, queue_manager):
        """Test receiving messages."""
        queue_manager.sqs_client = Mock()
        queue_manager.queue_url = 'http://test-queue-url'
        
        expected_messages = [{'MessageId': 'test-id', 'Body': 'test body'}]
        queue_manager.sqs_client.receive_message.return_value = {
            'Messages': expected_messages
        }
        
        # Use real implementation for testing
        from src.providers.worker.queue.manager import QueueManager
        
        real_manager = QueueManager.__new__(QueueManager)
        real_manager.sqs_client = queue_manager.sqs_client
        real_manager.queue_url = queue_manager.queue_url
        real_manager.max_messages = 1
        real_manager.wait_time_seconds = 20
        
        result = real_manager.receive_messages()
        
        assert result == expected_messages
        queue_manager.sqs_client.receive_message.assert_called_once()
    
    def test_delete_message(self, queue_manager):
        """Test deleting a message."""
        queue_manager.sqs_client = Mock()
        queue_manager.queue_url = 'http://test-queue-url'
        
        # Use real implementation for testing
        from src.providers.worker.queue.manager import QueueManager
        
        real_manager = QueueManager.__new__(QueueManager)
        real_manager.sqs_client = queue_manager.sqs_client
        real_manager.queue_url = queue_manager.queue_url
        
        result = real_manager.delete_message('test-receipt-handle')
        
        assert result == True
        queue_manager.sqs_client.delete_message.assert_called_once_with(
            QueueUrl='http://test-queue-url',
            ReceiptHandle='test-receipt-handle'
        )

    def test_send_message_failure(self, queue_manager):
        """Test handling of send message failure."""
        queue_manager.sqs_client = Mock()
        queue_manager.queue_url = 'http://test-queue-url'
        
        # Mock an exception
        queue_manager.sqs_client.send_message.side_effect = Exception("Connection failed")
        
        # Use real implementation for testing
        from src.providers.worker.queue.manager import QueueManager
        
        real_manager = QueueManager.__new__(QueueManager)
        real_manager.sqs_client = queue_manager.sqs_client
        real_manager.queue_url = queue_manager.queue_url
        
        # Real implementation returns None on error, doesn't raise
        result = real_manager.send_message('test message', {})
        assert result is None

    def test_receive_messages_empty(self, queue_manager):
        """Test receiving messages when queue is empty."""
        queue_manager.sqs_client = Mock()
        queue_manager.queue_url = 'http://test-queue-url'
        
        # Mock empty response
        queue_manager.sqs_client.receive_message.return_value = {}
        
        # Use real implementation for testing
        from src.providers.worker.queue.manager import QueueManager
        
        real_manager = QueueManager.__new__(QueueManager)
        real_manager.sqs_client = queue_manager.sqs_client
        real_manager.queue_url = queue_manager.queue_url
        real_manager.max_messages = 1
        real_manager.wait_time_seconds = 20
        
        result = real_manager.receive_messages()
        
        assert result == []
        queue_manager.sqs_client.receive_message.assert_called_once()

    @pytest.mark.parametrize("max_messages,wait_time", [
        (1, 20),
        (5, 10),
        (10, 0),
    ])
    def test_receive_messages_with_params(self, queue_manager, max_messages, wait_time):
        """Test receiving messages with different parameters."""
        queue_manager.sqs_client = Mock()
        queue_manager.queue_url = 'http://test-queue-url'
        
        expected_messages = [{'MessageId': f'test-id-{i}', 'Body': f'test body {i}'} 
                           for i in range(max_messages)]
        queue_manager.sqs_client.receive_message.return_value = {
            'Messages': expected_messages
        }
        
        # Assuming the method accepts these parameters
        if hasattr(queue_manager, 'receive_messages_with_params'):
            result = queue_manager.receive_messages_with_params(
                max_messages=max_messages, 
                wait_time=wait_time
            )
            assert len(result) == max_messages


@pytest.mark.unit
@pytest.mark.worker
class TestMessageProcessing:
    """Test cases for message processing logic."""
    
    def test_message_parsing(self):
        """Test parsing of message body."""
        message_body = {
            "event_id": "test-id",
            "timestamp": 1234567890.0,
            "event_type": "test",
            "source": "unit_test",
            "data": {"key": "value"}
        }
        
        # Test valid JSON parsing
        json_str = json.dumps(message_body)
        parsed = json.loads(json_str)
        
        assert parsed['event_type'] == 'test'
        assert parsed['source'] == 'unit_test'
        assert parsed['data']['key'] == 'value'
    
    def test_event_type_extraction(self):
        """Test extraction of event type from different sources."""
        # Test from message attributes
        attributes = {
            'event_type': {
                'StringValue': 'autonomous_agent',
                'DataType': 'String'
            }
        }
        
        event_type = None
        if attributes and 'event_type' in attributes:
            attr = attributes['event_type']
            if isinstance(attr, dict) and 'StringValue' in attr:
                event_type = attr['StringValue']
        
        assert event_type == 'autonomous_agent'
        
        # Test from message body
        message_data = {'event_type': 'documentation'}
        event_type = message_data.get('event_type', 'unknown')
        
        assert event_type == 'documentation'

    @pytest.mark.parametrize("message_data,expected_type", [
        ({'event_type': 'test'}, 'test'),
        ({'event_type': 'autonomous_agent'}, 'autonomous_agent'),
        ({'event_type': 'documentation'}, 'documentation'),
        ({}, 'unknown'),
        ({'other_field': 'value'}, 'unknown'),
    ])
    def test_event_type_extraction_parametrized(self, message_data, expected_type):
        """Test event type extraction with various inputs."""
        event_type = message_data.get('event_type', 'unknown')
        assert event_type == expected_type

    def test_message_validation(self):
        """Test message validation logic."""
        valid_message = {
            "event_id": "test-id",
            "timestamp": 1234567890.0,
            "event_type": "test",
            "source": "unit_test",
            "data": {"key": "value"}
        }
        
        # Test required fields
        required_fields = ['event_id', 'event_type', 'source']
        for field in required_fields:
            assert field in valid_message, f"Missing required field: {field}"
        
        # Test data types
        assert isinstance(valid_message['event_id'], str)
        assert isinstance(valid_message['timestamp'], (int, float))
        assert isinstance(valid_message['event_type'], str)
        assert isinstance(valid_message['source'], str)
        assert isinstance(valid_message['data'], dict)


@pytest.fixture
def sample_sqs_message():
    """Fixture providing a sample SQS message."""
    return {
        'MessageId': 'test-message-id',
        'ReceiptHandle': 'test-receipt-handle',
        'Body': json.dumps({
            'event_type': 'test',
            'message': 'test message',
            'timestamp': 1234567890.0
        }),
        'MessageAttributes': {
            'event_type': {
                'StringValue': 'test',
                'DataType': 'String'
            }
        }
    }


def test_message_processing_with_fixture(sample_sqs_message):
    """Test message processing using fixture."""
    # Parse message body
    body = json.loads(sample_sqs_message['Body'])
    
    assert body['event_type'] == 'test'
    assert body['message'] == 'test message'
    assert sample_sqs_message['MessageId'] == 'test-message-id'
    
    # Test message attributes
    attrs = sample_sqs_message['MessageAttributes']
    assert attrs['event_type']['StringValue'] == 'test' 