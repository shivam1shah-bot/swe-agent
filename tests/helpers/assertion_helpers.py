"""
Custom assertion helpers for testing.
"""
import json
from typing import Any, Dict, List

# Workflow assertion helpers removed - workflow system deleted

def assert_task_successful(task_result):
    """Assert that a task completed successfully."""
    assert task_result is not None, "Task result should not be None"
    assert task_result.get("success") is True, f"Expected task success=True, got {task_result.get('success')}"

def assert_api_response_ok(response):
    """Assert that an API response is OK."""
    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
    assert response.json() is not None, "Response should have JSON data"

def assert_contains_keys(data: Dict, required_keys: List[str]):
    """Assert that a dictionary contains all required keys."""
    missing_keys = [key for key in required_keys if key not in data]
    assert not missing_keys, f"Missing required keys: {missing_keys}"

def assert_valid_json(json_string: str):
    """Assert that a string is valid JSON."""
    try:
        json.loads(json_string)
    except json.JSONDecodeError as e:
        assert False, f"Invalid JSON: {e}"

def assert_provider_initialized(provider):
    """Assert that a provider is properly initialized."""
    assert provider is not None, "Provider should not be None"
    assert hasattr(provider, '__class__'), "Provider should be a class instance"

def assert_metrics_recorded(metrics_provider, metric_name):
    """Assert that a metric was recorded."""
    assert hasattr(metrics_provider, 'metrics'), "Metrics provider should have metrics attribute"
    metric_keys = list(metrics_provider.metrics.keys())
    matching_keys = [key for key in metric_keys if metric_name in key]
    assert matching_keys, f"No metrics found containing '{metric_name}'. Available metrics: {metric_keys}"

def assert_logs_contain(logging_provider, expected_message):
    """Assert that logs contain a specific message."""
    assert hasattr(logging_provider, 'logs'), "Logging provider should have logs attribute"
    log_messages = [log.get('message', '') for log in logging_provider.logs]
    matching_logs = [msg for msg in log_messages if expected_message in msg]
    assert matching_logs, f"Expected message '{expected_message}' not found in logs: {log_messages}"

# assert_workflow_steps_executed removed - workflow system deleted 