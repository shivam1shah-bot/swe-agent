"""
Mock providers for testing.
"""
from unittest.mock import Mock, MagicMock

class MockWorkerProvider:
    """Mock worker provider."""
    
    def __init__(self):
        self.tasks = {}
        self.task_counter = 0
    
    def submit_task(self, task):
        """Mock task submission."""
        self.task_counter += 1
        task_id = f"task_{self.task_counter}"
        self.tasks[task_id] = {
            "id": task_id,
            "status": "submitted",
            "task": task
        }
        return task_id
    
    def get_task_status(self, task_id):
        """Mock get task status."""
        return self.tasks.get(task_id, {}).get("status", "not_found")

class MockLoggingProvider:
    """Mock logging provider."""
    
    def __init__(self):
        self.logs = []
    
    def log(self, level, message, **kwargs):
        """Mock logging."""
        self.logs.append({
            "level": level,
            "message": message,
            "metadata": kwargs
        })
    
    def get_logs(self):
        """Get all logs."""
        return self.logs.copy()

class MockMetricsProvider:
    """Mock metrics provider."""
    
    def __init__(self):
        self.metrics = {}
    
    def increment_counter(self, name, value=1, tags=None):
        """Mock counter increment."""
        key = f"counter_{name}"
        self.metrics[key] = self.metrics.get(key, 0) + value
    
    def set_gauge(self, name, value, tags=None):
        """Mock gauge set."""
        key = f"gauge_{name}"
        self.metrics[key] = value
    
    def record_histogram(self, name, value, tags=None):
        """Mock histogram record."""
        key = f"histogram_{name}"
        if key not in self.metrics:
            self.metrics[key] = []
        self.metrics[key].append(value)

def create_mock_providers():
    """Create mock providers for testing."""
    providers = MagicMock()
    providers.worker = MockWorkerProvider()
    providers.logging = MockLoggingProvider()
    providers.metrics = MockMetricsProvider()
    providers.storage = Mock()
    providers.auth = Mock()
    providers.cache = Mock()
    return providers 