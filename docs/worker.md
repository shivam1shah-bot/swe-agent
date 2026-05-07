# Worker System

Queue-based background task processing using AWS SQS (LocalStack for local dev).

## Architecture

```
API/Task Service → SQS Queue → Worker → Task Handler → Result Storage
```

The worker polls SQS, dispatches messages to registered handlers, and manages task lifecycle.

## Design Decisions

### Why Queue-Based?

Agent tasks run minutes to hours. Queue-based processing:

- Survives API restarts
- Enables horizontal worker scaling
- Prevents HTTP timeout failures

### LocalStack for Development

LocalStack provides local SQS implementation:

- No AWS credentials needed for development
- Deterministic testing
- Same API surface as production

## Key Components

- **Sender** (`src/providers/worker/sender.py`): Submit tasks to queue
- **Worker** (`src/providers/worker/worker.py`): Poll and process messages
- **Queue Manager** (`src/providers/worker/queue/`): Connection handling

## Usage

Submit a task:

```python
from src.providers.worker import send_to_worker

send_to_worker({
    'event_type': 'my_task',
    'task_id': task_id,
    'data': {...}
})
```

The worker dispatches to handlers registered in `src/worker/tasks.py`.

## Environment Configuration

- `APP_ENV=dev` or `dev_docker`: Uses LocalStack
- `APP_ENV=stage/prod`: Uses AWS SQS (requires AWS credentials)

## Testing

Run integration tests:

```bash
pytest tests/integration/test_worker_sqs.py -v
```

## Troubleshooting

| Issue                   | Solution                                                        |
| ----------------------- | --------------------------------------------------------------- |
| Worker not receiving    | Check LocalStack is running: `docker logs swe-agent-localstack` |
| Queue connection fail   | Verify `AWS_ENDPOINT_URL` points to LocalStack                  |
| Messages not processing | Check handler is registered in `tasks.py`                       |
