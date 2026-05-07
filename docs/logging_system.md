# Logging System

## Overview

Structured logging with automatic sanitization and context tracking. All logs are written to `tmp/logs/` with correlation IDs for request tracing.

## Design Decisions

### Security-First Logging

All user input is automatically sanitized to prevent log injection attacks. Use `raw_*()` methods only for trusted internal data (stack traces, metrics).

### Context Propagation

Two context mechanisms enable request tracing:

- **Global Context**: Thread-scoped for HTTP requests via `LoggerContext.set_context()`
- **Persistent Context**: Logger-scoped via `logger.with_context()` for long operations

This ensures every log line includes correlation IDs without repetitive passing.

### Structured by Default

Log calls accept keyword arguments for structured fields:

```python
# Structured fields enable filtering/querying
logger.info("Task completed", task_id=task_id, duration=duration)
```

## Log Organization

```
tmp/logs/
├── agent-logs/          # AI agent interactions (prompts, responses)
├── system/              # Application logs (task lifecycle, tools, errors)
```

**Agent logs** capture Claude/Gemini interactions for debugging prompt issues.
**System logs** capture task execution flow and tool usage.

## Usage Patterns

### HTTP Request Handling

```python
# Set context at request start
LoggerContext.set_context(request_id=request_id, user_id=user_id)
try:
    # All logs automatically include context
    logger.info("Processing task", task_id=task_id)
finally:
    LoggerContext.clear_context()  # Prevent context leakage
```

### Long-Running Operations

```python
# Persistent context for multi-step operations
task_logger = logger.with_context(task_id=task_id, agent=agent_name)
task_logger.info("Starting processing")
task_logger.info("Step complete", step=1)  # Includes task_id and agent
```

## Integration Points

- **FastAPI**: `get_logger` dependency provides request-scoped loggers
- **Tasks**: `system_logger` captures task lifecycle and tool usage
- **Agents**: Agent logs capture AI interactions separately

## Log Format

```
2025-06-02T18:01:26 - service - INFO - Message [context: k=v] [fields: k=v]
```

Context fields identify the request/operation; structured fields contain event-specific data.
