---
name: autonomous-task-execution
description: Complete autonomous agent task lifecycle in SWE Agent
version: 1.0.0
tags: [autonomous-agent, task-lifecycle, workflow]
context: codebase
---

# Autonomous Task Execution Workflow

## Overview

Handles autonomous agent task execution from request → queue → processing → completion. Tasks use Claude Code CLI to execute development workflows autonomously.

**Task Flow**: API Request → Validation → Queue → Worker Polls → Agent Executes → Result Storage → Status Update

## Phase 1: Task Creation & Validation

### Request Validation (`src/services/agents_catalogue/autonomous_agent/validations.py`)

**Required Parameters:**
- `prompt` (str) - Task description for the agent
- `working_dir` (str, optional) - Working directory path
- `repository_url` (str, optional) - GitHub repository URL
- `branch` (str, optional) - Git branch name

**Validation Rules:**

1. **Branch Protection**:
   - ❌ BLOCKED: `main`, `master` branches
   - ✅ ALLOWED: Feature branches only
   - Error: "Branch 'main' is not allowed. Please use a feature branch."

2. **Repository Access Validation** (if `repository_url` provided):
   - Check repository exists and is accessible
   - Verify GitHub authentication
   - Validate user has read/write access
   - Determine if repository is private (affects token handling)

3. **Parameter Validation**:
   - Prompt cannot be empty
   - Repository URL must be valid GitHub URL format
   - Branch name must follow Git naming conventions

### Task Creation (`src/services/agents_catalogue/autonomous_agent/service.py`)

**Synchronous Execute** (returns immediately, queues task):
```python
def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
    # 1. Validate parameters
    # 2. Check branch protection rules
    # 3. Validate repository access
    # 4. Queue task to SQS
    # 5. Return task_id immediately
```

**Returns**:
```json
{
  "status": "queued",
  "task_id": "uuid-here",
  "message": "Task queued successfully"
}
```

## Phase 2: Task Processing

### Worker Task Handler (`src/worker/tasks.py`)

**Task Processor Initialization**:
- Creates `AutonomousAgentTool` instance (singleton)
- Sets up task handler registry
- Connects worker instance for cancellation monitoring

**Task Processing Steps**:

1. **Pre-Processing Checks**:
   ```python
   # Check if task already in terminal state
   terminal_states = ['cancelled', 'failed', 'completed']
   if current_status in terminal_states:
       skip_processing()  # Don't re-process completed tasks
   ```

2. **Status Update** → `RUNNING`:
   - Update task status in database
   - Set start timestamp
   - Log processing start

3. **Thread-Local Context Setup**:
   - Set `task_id` in thread-local storage
   - Set `worker_instance` for subprocess tracking
   - Allows subprocesses to access cancellation state

4. **Execute Task Handler**:
   - Route to `_handle_autonomous_agent()`
   - Pass task data to handler
   - Monitor for cancellation signals

### Autonomous Agent Handler (`src/worker/tasks.py: _handle_autonomous_agent()`)

**Execution Flow**:

1. **Extract Parameters**:
   ```python
   prompt = metadata.get('prompt')
   working_dir = metadata.get('working_dir')
   repository_url = metadata.get('repository_url')
   branch = metadata.get('branch')
   github_token = metadata.get('github_token')  # For private repos
   ```

2. **Prepare Agent Configuration**:
   - Build combined prompt (base + user prompt + context)
   - Set working directory (default: `/tmp/swe-agent/{task_id}`)
   - Configure Git settings if repository specified

3. **Execute Autonomous Agent** (`src/agents/autonomous_agent.py`):
   ```python
   result = await autonomous_agent_tool.execute(
       prompt=combined_prompt,
       working_dir=working_dir,
       repository_url=repository_url,
       branch=branch,
       github_token=github_token,
       task_id=task_id
   )
   ```

4. **Handle Result**:
   - Success → Status: `completed`, store output
   - Failure → Status: `failed`, store error details
   - Cancelled → Status: `cancelled`, cleanup

## Phase 3: Autonomous Agent Execution

### Agent Tool (`src/agents/autonomous_agent.py`)

**AutonomousAgentTool** (singleton pattern):

1. **Initialize Working Directory**:
   - Create temp directory if needed
   - Clone repository if URL provided
   - Checkout branch if specified

2. **Repository Cloning** (if `repository_url`):
   ```bash
   # For private repos with token
   git clone https://{token}@github.com/owner/repo.git

   # For public repos
   git clone https://github.com/owner/repo.git

   # Checkout branch
   cd repo && git checkout {branch}
   ```

3. **Execute Claude Code CLI**:
   - Use `ClaudeCodeTool` (singleton)
   - Stream output to logs
   - Monitor cancellation signals
   - Capture exit code and output

4. **Handle Cancellation**:
   - Check cancellation flag in thread-local context
   - Kill subprocess if cancelled
   - Clean up resources
   - Return early with cancellation status

5. **Result Collection**:
   - Capture stdout/stderr
   - Collect file changes
   - Parse agent output
   - Determine success/failure

## Phase 4: Task Completion

### Status Updates (`src/tasks/service.py`)

**Completed**:
```python
task_manager.update_task_status(
    task_id=task_id,
    status=TaskStatus.COMPLETED,
    result={"output": agent_output, "files_changed": [...]}
)
```

**Failed**:
```python
task_manager.update_task_status(
    task_id=task_id,
    status=TaskStatus.FAILED,
    error={"message": error_msg, "traceback": stack_trace}
)
```

**Cancelled**:
```python
task_manager.update_task_status(
    task_id=task_id,
    status=TaskStatus.CANCELLED,
    message="Task cancelled by user"
)
```

## Edge Cases & Error Handling

### Protected Branch Violation
**Symptom**: User specifies `main` or `master` branch
**Handling**: Fail fast at validation, return error immediately
**Status**: `failed` (before queuing)

### Repository Access Denied
**Symptom**: GitHub token invalid or repo doesn't exist
**Handling**: Fail at validation phase, don't queue task
**Status**: `failed` (before queuing)

### Task Already Terminal
**Symptom**: Task already completed/failed/cancelled
**Handling**: Skip re-processing, delete queue message
**Status**: No change (preserve existing state)

### Cancellation During Execution
**Symptom**: User cancels task while agent is running
**Handling**:
1. Set cancellation flag in thread-local context
2. Kill subprocess (Claude Code CLI)
3. Clean up working directory
4. Update status to `cancelled`

### Agent Execution Timeout
**Symptom**: Agent runs longer than configured timeout
**Handling**: Kill subprocess, mark as failed with timeout error
**Status**: `failed` with timeout metadata

### Working Directory Conflicts
**Symptom**: Directory already exists from previous task
**Handling**: Clean up old directory, create fresh one
**Action**: Always use unique paths with task_id

## Key Files

- `src/services/agents_catalogue/autonomous_agent/service.py` - Service layer (API → Queue)
- `src/services/agents_catalogue/autonomous_agent/validations.py` - Parameter validation
- `src/services/agents_catalogue/autonomous_agent/prompts.py` - Prompt building
- `src/worker/tasks.py` - Task processor and handler registry
- `src/agents/autonomous_agent.py` - Agent tool (execution logic)
- `src/tasks/service.py` - Task status management
- `src/models/task.py` - Task entity and status enum

## Testing

```bash
# Unit tests
pytest tests/unit/services/agents_catalogue/test_autonomous_agent.py
pytest tests/unit/agents/test_autonomous_agent.py

# Integration tests
pytest tests/integration/test_autonomous_agent_flow.py

# E2E tests
pytest tests/e2e/test_autonomous_agent_execution.py
```

## Monitoring & Debugging

**Logs**:
- Service: `tmp/logs/autonomous_agent_service.log`
- Worker: `tmp/logs/worker.log`
- Agent: `tmp/logs/autonomous_agent.log`

**Health Checks**:
- Task status: `GET /api/tasks/{task_id}`
- Worker health: `GET /health/worker`

**Debugging**:
```bash
# View worker logs
make logs-worker

# View specific task logs
grep "task_id={task_id}" tmp/logs/worker.log

# Check task status in DB
psql -d swe_agent -c "SELECT * FROM tasks WHERE id='{task_id}';"
```

## Common Issues

**Issue**: Task stuck in "queued" status
**Cause**: Worker not running or queue connection issue
**Fix**: Check worker status (`make status`), restart worker (`make restart-worker`)

**Issue**: "Repository validation failed"
**Cause**: Invalid GitHub token or insufficient permissions
**Fix**: Refresh token: `export GITHUB_TOKEN=$(gh auth token)`

**Issue**: "Branch 'main' is not allowed"
**Cause**: Attempting to use protected branch
**Fix**: Use feature branch instead: `branch: "feature/my-task"`

**Issue**: Task cancelled but still shows "running"
**Cause**: Race condition in status update
**Fix**: Cancellation handler updates status atomically, refresh status
