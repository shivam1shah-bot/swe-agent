# Run Task Command

## Purpose
Execute an autonomous development task through the SWE Agent system, handling the complete lifecycle from task creation to result delivery.

## Usage
```
/run-task [task-description] --type [task-type] [options]
```

## Instructions

When this command is invoked, perform the following steps:

### 1. Parse Task Parameters

Extract and validate task parameters:
- **Task Description**: The main requirement or objective
- **Task Type**: Type of task (feature, bugfix, refactor, documentation, test)
- **Options**: Additional configuration (workspace path, timeout, priority)

### 2. Validate Prerequisites

Before executing the task, verify:

```python
# Check system health
- API server is running and healthy
- Database is accessible
- Redis cache is available
- SQS queue is operational (LocalStack for dev)
- Worker is running and ready

# Check workspace
- Workspace path exists and is accessible
- Git repository is in clean state (or has expected changes)
- Required dependencies are installed

# Check permissions
- User has permission to execute this task type
- Required credentials are available (GitHub token, etc.)
```

### 3. Create Task

Create task in the system:

```python
# Prepare task request
task_request = {
    "name": "<concise task name>",
    "description": "<detailed description>",
    "type": "<task_type>",
    "workspace_path": "<path>",
    "metadata": {
        "create_pr": True/False,
        "run_tests": True/False,
        "auto_commit": True/False
    }
}

# Submit via API
POST /api/v1/tasks
```

### 4. Monitor Execution

Monitor task execution in real-time:

```python
# Poll task status
while task.status in [TaskStatus.PENDING, TaskStatus.IN_PROGRESS]:
    # Get current status
    task = GET /api/v1/tasks/{task_id}

    # Display progress
    print(f"Status: {task.status}")
    print(f"Progress: {task.progress}%")

    # Show agent output if available
    if task.latest_output:
        print(f"Agent: {task.latest_output}")

    await asyncio.sleep(2)
```

### 5. Handle Completion

When task completes (success or failure):

```python
# Retrieve final results
task = GET /api/v1/tasks/{task_id}
result = GET /api/v1/tasks/{task_id}/results

if task.status == TaskStatus.COMPLETED:
    # Display success information
    print("✅ Task completed successfully!")
    print(f"\nResults:")
    print(f"  Files modified: {len(result.files_changed)}")

    for file in result.files_changed:
        print(f"    - {file}")

    if result.pr_url:
        print(f"\n  Pull Request: {result.pr_url}")

    if result.test_results:
        print(f"\n  Tests:")
        print(f"    Passed: {result.test_results.passed}")
        print(f"    Failed: {result.test_results.failed}")

elif task.status == TaskStatus.FAILED:
    # Display error information
    print("❌ Task failed")
    print(f"\nError: {task.error_message}")

    if result.error_details:
        print(f"\nDetails:")
        print(result.error_details)

    # Suggest remediation steps
    print(f"\nSuggested Actions:")
    print("  1. Check agent logs for detailed error information")
    print("  2. Review task requirements and parameters")
    print("  3. Verify workspace state and dependencies")
```

### 6. Provide Summary

Generate comprehensive summary:

```
## Task Execution Summary

**Task ID**: {task_id}
**Type**: {task_type}
**Status**: {status}
**Duration**: {duration}

### Changes Made
- Files modified: {count}
- Tests added: {test_count}
- Lines added: {lines_added}
- Lines removed: {lines_removed}

### Results
{detailed_results}

### Next Steps
{recommended_actions}
```

## Task Types

### Feature Implementation
```bash
/run-task "Add user authentication middleware" --type feature
```

**Expected Workflow:**
1. Analyze requirements and existing code
2. Design implementation approach
3. Implement the feature
4. Write/update tests
5. Run test suite
6. Create pull request

### Bug Fix
```bash
/run-task "Fix null pointer exception in task processor" --type bugfix
```

**Expected Workflow:**
1. Reproduce the bug
2. Analyze root cause
3. Implement fix
4. Add regression test
5. Verify fix works
6. Create pull request

### Refactoring
```bash
/run-task "Refactor authentication service to use dependency injection" --type refactor
```

**Expected Workflow:**
1. Analyze current implementation
2. Plan refactoring strategy
3. Apply refactoring incrementally
4. Ensure tests pass continuously
5. Update documentation
6. Create pull request

### Documentation
```bash
/run-task "Document the agent orchestration system" --type documentation
```

**Expected Workflow:**
1. Analyze code to document
2. Generate comprehensive documentation
3. Add code examples
4. Update README if needed
5. Create pull request

### Testing
```bash
/run-task "Add integration tests for task execution workflow" --type test
```

**Expected Workflow:**
1. Identify test scenarios
2. Implement test cases
3. Set up test fixtures
4. Run test suite
5. Verify coverage
6. Create pull request

## Options

### Common Options

```bash
# Specify workspace path
/run-task "..." --workspace /path/to/repo

# Set timeout (in seconds)
/run-task "..." --timeout 600

# Set priority
/run-task "..." --priority high

# Skip PR creation
/run-task "..." --no-pr

# Skip running tests
/run-task "..." --skip-tests

# Enable verbose output
/run-task "..." --verbose

# Specify branch name
/run-task "..." --branch feature/new-feature
```

### Advanced Options

```bash
# Provide context files
/run-task "..." --context file1.py,file2.py

# Specify MCP servers to use
/run-task "..." --mcp-servers github,filesystem

# Use specific agent configuration
/run-task "..." --agent-config path/to/config.json

# Enable experimental features
/run-task "..." --experimental
```

## Examples

### Example 1: Simple Feature Implementation

```bash
/run-task "Add email validation to user registration form" --type feature
```

**Expected Output:**
```
🔄 Creating task...
✅ Task created: task-abc123

🔄 Executing task...
📊 Status: IN_PROGRESS (0%)
   Agent: Analyzing requirements...

📊 Status: IN_PROGRESS (20%)
   Agent: Identified affected files: src/api/routes/auth.py, src/models/user.py

📊 Status: IN_PROGRESS (40%)
   Agent: Implementing email validation...

📊 Status: IN_PROGRESS (60%)
   Agent: Writing tests...

📊 Status: IN_PROGRESS (80%)
   Agent: Running test suite...

📊 Status: IN_PROGRESS (90%)
   Agent: Creating pull request...

✅ Task completed successfully!

Results:
  Files modified: 3
    - src/api/routes/auth.py
    - src/models/user.py
    - tests/test_auth.py

  Tests:
    Passed: 15
    Failed: 0

  Pull Request: https://github.com/org/repo/pull/123

Duration: 3m 45s
```

### Example 2: Bug Fix with Context

```bash
/run-task "Fix race condition in worker task processing" \
  --type bugfix \
  --context src/worker/tasks.py \
  --verbose
```

### Example 3: Large Refactoring

```bash
/run-task "Migrate from SQLAlchemy 1.4 to 2.0" \
  --type refactor \
  --timeout 1800 \
  --priority high
```

## Error Handling

### Task Creation Failed
```
❌ Failed to create task

Error: Invalid task type 'invalid-type'

Valid task types:
  - feature_implementation
  - bug_fix
  - refactoring
  - documentation
  - testing

Please try again with a valid task type.
```

### Task Execution Failed
```
❌ Task failed

Error: Agent execution timed out after 300 seconds

Possible causes:
  1. Task is too complex for the specified timeout
  2. Agent is stuck or hanging
  3. System resource constraints

Suggested actions:
  1. Increase timeout with --timeout option
  2. Break down task into smaller subtasks
  3. Check system resources and agent logs
```

### Prerequisites Not Met
```
❌ Cannot execute task

Prerequisites check failed:
  ❌ Worker is not running
  ✅ Database is accessible
  ✅ Redis is accessible

Please start the worker:
  make worker-local   # Local development
  docker-compose up -d worker  # Docker
```

## Cancellation

To cancel a running task:

```bash
# In another terminal or session
/cancel-task task-abc123
```

The command should detect cancellation and provide graceful cleanup:

```
⚠️  Task cancellation requested
🔄 Cleaning up resources...
✅ Task cancelled successfully

Partial results saved:
  - Files modified: 2 (not committed)
  - Changes can be reviewed at: /path/to/workspace
```

## Integration with Project

This command integrates with:
- **API**: `/api/v1/tasks` endpoint
- **Worker**: Background task processing
- **Agent**: AutonomousAgentTool execution
- **Database**: Task and result persistence
- **Queue**: SQS task queuing

## Output Style

Use the `task-execution-report` output style for formatting results.

## Reference

- Task service: `src/services/task_service.py`
- Agent tool: `src/agents/autonomous_agent_tool.py`
- Worker: `src/worker/tasks.py`
- API endpoints: `src/api/routers/tasks.py`
- Output style: `.claude/output-styles/task-execution-report.md`
