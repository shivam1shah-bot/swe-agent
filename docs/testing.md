# Testing Guide

## Test Organization

```
tests/
├── unit/           # Fast, isolated component tests
├── integration/    # Multi-component tests
├── e2e/            # Full user journey tests
└── conftest.py     # Shared fixtures
```

## Test Categories

| Type        | Speed | Purpose               | When to Run        |
| ----------- | ----- | --------------------- | ------------------ |
| Unit        | <1s   | Component isolation   | During development |
| Integration | 1-10s | Component interaction | Pre-commit, CI     |
| E2E         | 10s+  | Full workflows        | Release, nightly   |

## Running Tests

```bash
make test-unit           # Unit tests only
make test-integration    # Integration tests
make test-coverage       # With coverage report
pytest -m "not slow"     # Skip slow tests
```

## Test Markers

Tests use markers for filtering:

- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.slow` - Long-running tests
- `@pytest.mark.github` - Requires GitHub token
- `@pytest.mark.database` - Requires database

## Fixtures

Common fixtures from `conftest.py`:

- `mock_providers` - Mocked infrastructure providers
- `sample_task` - Sample task data
- `temp_dir` - Temporary directory

## Test Isolation Principles

1. **No shared state** - Each test cleans up after itself
2. **Mock external services** - Use mocks for GitHub, AWS, etc.
3. **Database tests use transactions** - Roll back after test
4. **Use normal imports** - Don't use `sys.modules` manipulation; dependencies in `requirements.txt` are available to all tests

## Import Patterns

### Preferred: Direct Imports (Tier 1)

Use normal Python imports when dependencies don't have module-level initialization side effects:

```python
# Good - normal imports
from src.api.routers.pulse import router
from src.api.dependencies import get_db_session

# Override dependencies in tests via FastAPI's dependency overrides
app.dependency_overrides[get_db_session] = lambda: test_db_session
```

Rationale:

- All dependencies are in `requirements.txt` (not production-only)
- Modules are imported but not initialized during test collection
- Redis, Prometheus, etc. don't attempt connections at import time
- Normal imports are clearer and easier to debug

### Acceptable: Fixture-Based Module Mocking (Tier 2)

When testing code that imports subsystems with module-level initialization (DB connections, etc.), use fixture-scoped patching:

```python
# tests/unit/worker/test_example.py
import pytest
from unittest.mock import MagicMock, patch
import sys

@pytest.fixture(scope="module")
def mock_task_modules():
    """Mock modules that initialize DB connections at import time."""
    mock_tasks = MagicMock()
    mock_worker = MagicMock()

    with patch.dict(sys.modules, {
        'src.tasks': mock_tasks,
        'src.tasks.service': mock_tasks,
        'src.worker': mock_worker,
        'src.worker.queue_manager': mock_worker,
    }):
        yield mock_tasks, mock_worker

@pytest.fixture
def router(mock_task_modules):
    """Import router with mocked dependencies."""
    from src.api.routers.example import router
    return router
```

Benefits over module-level stubbing:

- Scoped to test module via fixture
- No cleanup needed (patch.dict handles restoration)
- Clearer intent - mocking unavailable subsystems, not preventing initialization

### Avoid: Module-Level Stubbing (Tier 3 - Deprecated)
Don't manipulate `sys.modules` at module level:

```python
# AVOID - hard to maintain, pollutes global state
import sys
from unittest.mock import MagicMock

_original_modules = {'src.worker': sys.modules.get('src.worker')}
sys.modules['src.worker'] = MagicMock()

# Complex cleanup fixture needed
@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    # Restore or pop modules
    for key, value in _original_modules.items():
        if value is None:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = value
```

Problems with this approach:

- Pollutes `sys.modules` globally
- Requires complex cleanup to avoid affecting other tests
- Error-prone if import chain changes
- Harder to understand than fixture-based approach

## Fixing Root Causes

When you find yourself needing Tier 2 mocking frequently, consider fixing the root cause - module-level initialization anti-patterns:

**Anti-pattern (causes need for mocking):**

```python
# src/tasks/__init__.py
from .service import task_manager  # Immediately creates TaskManager() → DB connection

# src/tasks/service.py
task_manager = TaskManager()  # Runs at IMPORT time
```

**Better approach (lazy initialization):**

```python
# src/tasks/__init__.py
_task_manager = None

def get_task_manager():
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager
```

Lazy initialization eliminates the need for import-time mocking and makes code more testable.

## Environment Variables

```bash
export ENABLE_GITHUB_TESTS=true        # Run GitHub integration tests
export GITHUB_PERSONAL_ACCESS_TOKEN=   # Required for GitHub tests
```

## CI Pipeline

Typical CI runs:

1. Unit tests on every PR
2. Integration tests on merge to main
3. E2E tests nightly
