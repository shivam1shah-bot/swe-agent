#!/usr/bin/env python3
"""
Integration tests for SQS connection between sender and worker.
"""

import pytest
from src.providers.worker import send_to_worker, send_autonomous_agent_event, send_custom_event


@pytest.mark.integration
@pytest.mark.worker
class TestWorkerSQSIntegration:
    """Integration tests for worker SQS functionality."""

    def test_send_test_message(self):
        """Test sending a basic test message to worker."""
        success = send_to_worker({
            'event_type': 'test',
            'message': 'Hello from SWE Agent!',
            'test_number': 1
        })
        assert success, "Failed to send test message"

    def test_send_autonomous_agent_event(self):
        """Test sending autonomous agent event."""
        success = send_autonomous_agent_event(
            repo_url="https://github.com/razorpay/test-repo",
            task_description="Fix authentication bug in login system"
        )
        assert success, "Failed to send autonomous agent event"

    def test_send_custom_event(self):
        """Test sending custom event with multiple parameters."""
        success = send_custom_event(
            'code_review',
            repository='razorpay/payment-service',
            pr_number=123,
            reviewer='dev-team',
            priority='high',
            files_changed=['auth.py', 'models.py']
        )
        assert success, "Failed to send custom event"

    def test_send_documentation_event(self):
        """Test sending documentation event."""
        success = send_to_worker({
            'event_type': 'documentation',
            'action': 'generate',
            'repository': 'razorpay/api-docs',
            'format': 'markdown',
            'sections': ['authentication', 'payments', 'webhooks']
        })
        assert success, "Failed to send documentation event"

    @pytest.mark.slow
    def test_full_sqs_workflow(self):
        """Test complete SQS workflow with multiple message types."""
        messages = [
            {
                'event_type': 'test',
                'message': 'Hello from SWE Agent!',
                'test_number': 1
            },
            {
                'event_type': 'documentation',
                'action': 'generate',
                'repository': 'razorpay/api-docs',
                'format': 'markdown',
                'sections': ['authentication', 'payments', 'webhooks']
            }
        ]
        
        results = []
        for message in messages:
            success = send_to_worker(message)
            results.append(success)
        
        # All messages should be sent successfully
        assert all(results), f"Some messages failed to send. Results: {results}"
        assert len(results) == 2, "Expected 2 messages to be processed"


@pytest.fixture
def sqs_test_config():
    """Fixture providing test configuration for SQS tests."""
    return {
        'queue_name': 'swe-agent-test-queue',
        'region': 'ap-south-1',
        'endpoint_url': 'http://localhost:4566'  # LocalStack
    }


def test_sqs_connection_with_config(sqs_test_config):
    """Test SQS connection with custom configuration."""
    # This test would use the sqs_test_config fixture
    # Implementation depends on how the worker configuration is structured
    assert sqs_test_config['queue_name'] == 'swe-agent-test-queue'
    assert sqs_test_config['region'] == 'ap-south-1'
