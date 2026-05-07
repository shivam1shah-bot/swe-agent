---
name: worker-queue-processing
description: SQS worker queue processing and task lifecycle management
version: 1.0.0
tags: [worker, sqs, queue, background-processing]
context: codebase
---

# Worker Queue Processing

## Overview

SWE Agent uses AWS SQS (Simple Queue Service) for reliable background task processing. The worker polls SQS for tasks, processes them asynchronously, and updates task status.

**Flow**: API → SQS Queue → Worker Poll → Task Processing → Status Update → Queue Message Delete

**Key Components**:
- **Sender** (`src/providers/worker/sender.py`) - Queue message to SQS
- **Worker** (`src/providers/worker/worker.py`) - Poll and process messages
- **TaskProcessor** (`src/worker/tasks.py`) - Execute task logic
- **QueueManager** (`src/providers/worker/queue/manager.py`) - Queue operations

## Architecture

### Queue Configuration

**LocalStack (Development)**:
```toml
# environments/env.dev_docker.toml
[aws]
region = "ap-south-1"
endpoint_url = "http://localhost:4566"  # LocalStack
access_key_id = "test"
secret_access_key = "test"

[queue]
default_queue = "default_task_execution"

[queue.sqs.queues.default_task_execution]
name = "swe-agent-dev-tasks"
visibility_timeout = 300
message_retention_period = 86400
receive_wait_time_seconds = 20
```

**Production (AWS SQS)**:
```toml
# environments/env.prod.toml
[aws]
region = "ap-south-1"
# No endpoint_url (uses real AWS SQS)
# No credentials (uses IAM role)

[queue.sqs.queues.default_task_execution]
name = "swe-agent-prod-tasks"
visibility_timeout = 600
message_retention_period = 345600  # 4 days
```

### Queue URLs

- **Dev (LocalStack)**: http://localhost:4566/000000000000/swe-agent-dev-tasks
- **Prod (AWS)**: https://sqs.ap-south-1.amazonaws.com/123456789/swe-agent-prod-tasks

## Phase 1: Queue Message Sending

### Sender (`src/providers/worker/sender.py`)

**Usage**:
```python
from src.providers.worker.sender import send_task_to_queue

# Send task to queue
result = await send_task_to_queue(
    task_type="autonomous_agent",
    task_id="task-uuid",
    metadata={
        "prompt": "Fix the bug in payment processing",
        "repository_url": "https://github.com/org/repo",
        "branch": "feature/bug-fix"
    }
)
```

**Message Format**:
```json
{
  "task_type": "autonomous_agent",
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "metadata": {
    "prompt": "Task description",
    "repository_url": "https://github.com/org/repo",
    "branch": "feature/fix",
    "github_token": "encrypted-token"
  },
  "created_at": "2025-02-10T12:00:00Z"
}
```

**Queue Configuration**:
- **Message Retention**: 1-4 days (configurable)
- **Visibility Timeout**: 5-10 minutes (task processing time)
- **Receive Wait Time**: 20 seconds (long polling)

### Error Handling in Sending

**Queue Not Found**:
```python
try:
    await send_task_to_queue(...)
except Exception as e:
    logger.error(f"Failed to queue task: {e}")
    # Update task status to FAILED
    # Return error to API caller
```

**LocalStack Not Running** (dev):
```bash
# Check LocalStack
curl http://localhost:4566/_localstack/health

# Start if not running
make start
```

## Phase 2: Worker Polling & Processing

### Worker Initialization (`src/providers/worker/worker.py`)

**Startup Sequence**:

1. **Load Configuration**:
   ```python
   config = get_config()
   env_name = config.get('environment', {}).get('name', 'dev')
   ```

2. **Create SQS Client**:
   - **Dev**: LocalStack endpoint (http://localhost:4566)
   - **Prod**: AWS SQS (IAM role credentials)

3. **Setup Queue Connection**:
   ```python
   queue_name = config['queue']['sqs']['queues'][default_queue]['name']
   response = sqs_client.get_queue_url(QueueName=queue_name)
   queue_url = response['QueueUrl']
   ```

4. **Auto-Create Queue** (dev only):
   - If queue doesn't exist, create it
   - Set visibility timeout, retention period
   - Configure dead letter queue (optional)

5. **Run Database Migrations**:
   ```python
   from src.migrations.manager import MigrationManager
   MigrationManager().run_migrations()
   ```

6. **Initialize TaskProcessor**:
   ```python
   task_processor = TaskProcessor()
   task_processor.set_worker_instance(worker)
   ```

### Polling Loop

**Long Polling** (20 seconds):
```python
while is_running:
    messages = sqs_client.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=1,  # Process one at a time
        WaitTimeSeconds=20,     # Long polling
        VisibilityTimeout=300   # 5 minutes to process
    )

    for message in messages.get('Messages', []):
        await process_message(message)
```

**Visibility Timeout**:
- Message hidden from other workers while processing
- If worker crashes, message reappears after timeout
- Prevents duplicate processing

**Graceful Shutdown**:
```python
def signal_handler(signum, frame):
    logger.info("Received shutdown signal")
    worker.stop()  # Sets is_running = False
    # Current task completes before exit
```

### Message Processing (`src/providers/worker/worker.py: process_message()`)

**Processing Steps**:

1. **Parse Message Body**:
   ```python
   task_data = json.loads(message['Body'])
   task_type = task_data['task_type']
   task_id = task_data['task_id']
   ```

2. **Check for Cancellation**:
   ```python
   if task_is_cancelled(task_id):
       delete_message()
       return  # Skip processing
   ```

3. **Delegate to TaskProcessor**:
   ```python
   result = await task_processor.process_task(task_data)
   ```

4. **Handle Result**:
   - **Success** → Delete message from queue
   - **Failure** → Log error, delete message (avoid retry loop)
   - **Exception** → Log traceback, delete message

5. **Delete Queue Message**:
   ```python
   sqs_client.delete_message(
       QueueUrl=queue_url,
       ReceiptHandle=message['ReceiptHandle']
   )
   ```

## Phase 3: Task Processing

### Task Processor (`src/worker/tasks.py`)

**Handler Registry**:
```python
task_handlers = {
    "autonomous_agent": self._handle_autonomous_agent,
    "agents_catalogue_execution": self._handle_agents_catalogue_execution,
    "github_token_refresh": self._handle_github_token_refresh,
}
```

**Processing Flow**:

1. **Pre-Processing Validation**:
   ```python
   # Check if already in terminal state
   if current_status in ['cancelled', 'failed', 'completed']:
       return {'success': True, 'skipped': True}
   ```

2. **Update Status → RUNNING**:
   ```python
   task_manager.update_task_status(
       task_id=task_id,
       status=TaskStatus.RUNNING,
       message="Task processing started"
   )
   ```

3. **Set Thread-Local Context**:
   ```python
   # For subprocess cancellation tracking
   current_thread.task_id = task_id
   current_thread.worker_instance = worker_instance
   ```

4. **Execute Task Handler**:
   ```python
   handler = task_handlers.get(task_type)
   if not handler:
       raise ValueError(f"Unknown task type: {task_type}")

   result = await handler(task_data)
   ```

5. **Update Final Status**:
   - **Success** → `COMPLETED` with result
   - **Failure** → `FAILED` with error details
   - **Cancelled** → `CANCELLED` with message

### Cancellation Support

**How It Works**:

1. **User Cancels Task**:
   ```bash
   # Via API
   POST /api/tasks/{task_id}/cancel
   ```

2. **Status Updated** → `CANCELLED`:
   ```python
   task_manager.update_task_status(
       task_id=task_id,
       status=TaskStatus.CANCELLED
   )
   ```

3. **Worker Checks Cancellation**:
   ```python
   # Before processing
   if task_is_cancelled(task_id):
       skip_processing()

   # During processing (in subprocess)
   if current_thread.worker_instance.is_task_cancelled(task_id):
       kill_subprocess()
       cleanup()
       return
   ```

4. **Subprocess Killed**:
   - Send SIGTERM to subprocess
   - Wait for graceful shutdown (5s)
   - Send SIGKILL if still running

## Queue Configuration Best Practices

### Visibility Timeout

**Rule**: Set to 2x expected processing time

**Examples**:
- Quick tasks (< 1 min): 120 seconds
- Autonomous agent (2-5 min): 300-600 seconds
- Long-running (> 10 min): 1200+ seconds

**Too Short**: Message reappears while still processing → duplicate processing
**Too Long**: Delayed retry on worker crash

### Message Retention

**Rule**: Long enough to handle worker downtime

**Examples**:
- Dev: 1 day (86400 seconds)
- Prod: 4 days (345600 seconds)

**After retention**: Message deleted, task lost

### Dead Letter Queue (DLQ)

**Purpose**: Capture messages that fail repeatedly

**Configuration**:
```toml
[queue.sqs.queues.default_task_execution]
name = "swe-agent-tasks"
dead_letter_queue_arn = "arn:aws:sqs:region:account:swe-agent-dlq"
max_receive_count = 3  # Move to DLQ after 3 failures
```

**Use Case**: Investigate permanently failing tasks

## Monitoring & Debugging

### Worker Logs

```bash
# View worker logs
make logs-worker

# Tail worker logs
docker logs -f swe-agent-worker

# Search for specific task
grep "task_id=550e8400" tmp/logs/worker.log
```

### Queue Metrics

**LocalStack**:
```bash
# List queues
aws --endpoint-url=http://localhost:4566 sqs list-queues

# Get queue attributes
aws --endpoint-url=http://localhost:4566 sqs get-queue-attributes \
  --queue-url http://localhost:4566/000000000000/swe-agent-dev-tasks \
  --attribute-names All
```

**AWS SQS**:
```bash
# CloudWatch metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/SQS \
  --metric-name ApproximateNumberOfMessagesVisible \
  --dimensions Name=QueueName,Value=swe-agent-prod-tasks
```

### Health Checks

```bash
# Worker health
curl http://localhost:28002/health/worker

# Queue connectivity
curl http://localhost:28002/health/queue
```

## Common Issues

### Issue: Messages not being processed
**Symptoms**: Tasks stuck in "queued" status
**Causes**:
1. Worker not running
2. Queue URL incorrect
3. LocalStack not running (dev)

**Debugging**:
```bash
# Check worker status
docker ps | grep worker
make logs-worker

# Check LocalStack
curl http://localhost:4566/_localstack/health

# Check queue exists
aws --endpoint-url=http://localhost:4566 sqs list-queues
```

### Issue: Duplicate task processing
**Cause**: Visibility timeout too short
**Fix**: Increase visibility timeout:
```toml
[queue.sqs.queues.default_task_execution]
visibility_timeout = 600  # 10 minutes
```

### Issue: Messages disappearing
**Cause**: Message retention expired
**Fix**: Increase retention period:
```toml
[queue.sqs.queues.default_task_execution]
message_retention_period = 345600  # 4 days
```

### Issue: Worker crashes on message processing
**Cause**: Unhandled exception in task handler
**Fix**: Add try/except in handler, log error, update task status to FAILED

### Issue: Task status not updating
**Cause**: Database connection lost
**Fix**: Check database health, restart worker

## Key Files

- `src/providers/worker/sender.py` - Queue message sending
- `src/providers/worker/worker.py` - Worker polling and processing
- `src/providers/worker/queue/manager.py` - Queue operations
- `src/worker/tasks.py` - Task processor and handlers
- `src/tasks/service.py` - Task status management
- `environments/env.dev_docker.toml` - Queue configuration

## Testing

```bash
# Unit tests
pytest tests/unit/providers/worker/

# Integration tests
pytest tests/integration/test_queue_processing.py

# E2E tests
pytest tests/e2e/test_worker_task_flow.py
```

## Commands

```bash
# Start worker
make worker-local           # Local development
make start                  # Docker (includes worker)

# Monitor worker
make logs-worker            # View logs
make status                 # Health check

# Restart worker
make restart-worker         # Restart worker only
make restart                # Restart all app containers

# Queue operations
make queue-stats            # Show queue statistics
make queue-purge            # Clear all messages (dev only)
```
