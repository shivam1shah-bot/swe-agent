---
name: Agent Orchestration
description: Master the art of orchestrating autonomous agents for complex SDLC automation tasks using the SWE Agent platform
version: 1.0.0
---

## Overview

This skill enables effective orchestration of autonomous AI agents for software development lifecycle automation. It covers the use of AutonomousAgentTool, ClaudeCodeTool, and related components to execute complex, multi-step development tasks.

**When to Use This Skill:**
- Executing autonomous development tasks (feature implementation, bug fixes, refactoring)
- Coordinating between multiple agent tools and capabilities
- Managing long-running agent operations with streaming output
- Implementing task delegation patterns
- Handling agent failures and recovery

## Core Concepts

### Agent Architecture

The SWE Agent platform uses a layered agent architecture:

```
AutonomousAgentTool (Orchestrator)
    ↓
ClaudeCodeTool (Primary Executor)
    ↓
MCP Servers (Extended Capabilities)
    ↓
Terminal/System Operations
```

### Key Components

#### AutonomousAgentTool
- **Location**: `src/agents/autonomous_agent_tool.py`
- **Purpose**: Main orchestrator for autonomous task execution
- **Pattern**: Delegation pattern - delegates to specialized tools
- **Responsibilities**:
  - Task decomposition and planning
  - Workflow coordination
  - Error handling and recovery
  - Result aggregation

#### ClaudeCodeTool
- **Location**: `src/agents/terminal_agents/claude_code.py`
- **Purpose**: Interface to Claude Code CLI
- **Pattern**: Singleton pattern for resource sharing
- **Responsibilities**:
  - Execute Claude Code commands
  - Manage streaming output
  - Handle MCP server configuration
  - Process cleanup

#### Terminal Agents
- **Location**: `src/agents/terminal_agents/`
- **Purpose**: Specialized agents for different AI providers
- **Types**:
  - `claude_code.py` - Claude Code CLI integration
  - Base agent patterns for extensibility

## Agent Orchestration Patterns

### Pattern 1: Basic Task Execution

```python
from src.agents.autonomous_agent_tool import AutonomousAgentTool
from src.models.task import Task, TaskType
from src.providers.context.context_provider import ContextProvider

async def execute_simple_task(task: Task) -> TaskResult:
    """Execute a simple autonomous task"""

    # Create execution context
    context = ContextProvider.create_context(
        correlation_id=f"task-{task.id}",
        user_id=task.user_id
    )

    # Get agent instance
    agent = AutonomousAgentTool(config=agent_config)

    try:
        # Execute task
        result = await agent.execute_task(
            task=task,
            context=context
        )

        return result

    except Exception as e:
        logger.error(f"Task execution failed: {e}", exc_info=True)
        raise TaskExecutionError(f"Failed to execute task {task.id}") from e
```

### Pattern 2: Task with Streaming Output

```python
async def execute_task_with_streaming(task: Task) -> TaskResult:
    """Execute task with real-time output monitoring"""

    agent = AutonomousAgentTool(config=agent_config)

    # Set up streaming callback
    async def on_output(output: str):
        logger.info(f"Agent output: {output}")
        await update_task_progress(task.id, output)

    # Execute with streaming
    result = await agent.execute_task(
        task=task,
        context=context,
        stream_callback=on_output
    )

    return result
```

### Pattern 3: Multi-Step Workflow Orchestration

```python
async def execute_complex_workflow(task: Task) -> TaskResult:
    """Orchestrate a multi-step workflow"""

    agent = AutonomousAgentTool(config=agent_config)

    # Step 1: Analyze requirements
    analysis = await agent.execute_step(
        task=task,
        step="analyze_requirements",
        prompt="Analyze the requirements and identify all files that need changes"
    )

    # Step 2: Create implementation plan
    plan = await agent.execute_step(
        task=task,
        step="create_plan",
        prompt=f"Based on this analysis: {analysis}, create a detailed implementation plan",
        context={"analysis": analysis}
    )

    # Step 3: Implement changes
    implementation = await agent.execute_step(
        task=task,
        step="implement",
        prompt=f"Implement the following plan: {plan}",
        context={"analysis": analysis, "plan": plan}
    )

    # Step 4: Run tests
    test_results = await agent.execute_step(
        task=task,
        step="test",
        prompt="Run all relevant tests and verify the implementation",
        context={"implementation": implementation}
    )

    # Aggregate results
    return TaskResult(
        task_id=task.id,
        steps={
            "analysis": analysis,
            "plan": plan,
            "implementation": implementation,
            "tests": test_results
        },
        success=test_results.get("all_passed", False)
    )
```

### Pattern 4: Delegation Pattern

```python
class TaskOrchestrator:
    """Orchestrate tasks by delegating to specialized agents"""

    def __init__(self):
        self.claude_code_agent = ClaudeCodeTool.get_instance()
        self.github_agent = GitHubAgent()
        self.test_agent = TestingAgent()

    async def execute_feature_implementation(self, task: Task) -> TaskResult:
        """Implement a feature using multiple specialized agents"""

        # 1. Use Claude Code for code implementation
        code_result = await self.claude_code_agent.execute(
            prompt=f"Implement feature: {task.description}",
            workspace=task.workspace_path
        )

        # 2. Use testing agent for test creation
        test_result = await self.test_agent.create_tests(
            code_files=code_result.modified_files
        )

        # 3. Use GitHub agent for PR creation
        pr_result = await self.github_agent.create_pr(
            branch=code_result.branch,
            title=f"Feature: {task.name}",
            body=self._generate_pr_body(code_result, test_result)
        )

        return TaskResult(
            task_id=task.id,
            code_changes=code_result,
            tests=test_result,
            pull_request=pr_result,
            success=True
        )
```

### Pattern 5: Error Recovery and Retry

```python
async def execute_with_retry(
    task: Task,
    max_retries: int = 3
) -> TaskResult:
    """Execute task with automatic retry on failure"""

    agent = AutonomousAgentTool(config=agent_config)
    last_error = None

    for attempt in range(max_retries):
        try:
            logger.info(f"Attempt {attempt + 1} of {max_retries}")

            result = await agent.execute_task(task=task, context=context)

            # Validate result
            if result.success:
                return result

            # If not successful but no exception, prepare for retry
            last_error = result.error_message
            logger.warning(f"Task failed: {last_error}, retrying...")

        except RetryableError as e:
            # Retry on retryable errors
            last_error = str(e)
            logger.warning(f"Retryable error: {e}, attempt {attempt + 1}")
            await asyncio.sleep(2 ** attempt)  # Exponential backoff

        except FatalError as e:
            # Don't retry on fatal errors
            logger.error(f"Fatal error: {e}")
            raise

    # All retries exhausted
    raise TaskExecutionError(
        f"Task failed after {max_retries} attempts. Last error: {last_error}"
    )
```

## Claude Code CLI Integration

### Basic Claude Code Execution

```python
from src.agents.terminal_agents.claude_code import ClaudeCodeTool

# Get singleton instance
claude_code = await ClaudeCodeTool.get_instance(config=agent_config)

# Execute command
result = await claude_code.execute_command(
    command="implement authentication middleware",
    workspace_path="/path/to/project",
    mcp_config="/path/to/mcp-servers.json"
)

# Process streaming output
async for output in result.stream():
    logger.info(f"Claude output: {output}")
    await broadcast_progress(output)
```

### MCP Server Configuration

```python
# Configure MCP servers for extended capabilities
mcp_config = {
    "mcpServers": {
        "github": {
            "command": "mcp-server-github",
            "args": ["--repo", f"{org}/{repo}"],
            "env": {
                "GITHUB_TOKEN": github_token
            }
        },
        "filesystem": {
            "command": "mcp-server-filesystem",
            "args": [workspace_path]
        },
        "database": {
            "command": "mcp-server-database",
            "args": ["--connection", db_connection_string]
        }
    }
}

# Save config
with open(mcp_config_path, 'w') as f:
    json.dump(mcp_config, f, indent=2)

# Use with Claude Code
result = await claude_code.execute_command(
    command="analyze database schema and suggest optimizations",
    workspace_path=workspace_path,
    mcp_config=mcp_config_path
)
```

### Handling Long-Running Operations

```python
async def execute_long_running_task(task: Task) -> TaskResult:
    """Handle long-running agent operations with timeout and cancellation"""

    claude_code = await ClaudeCodeTool.get_instance()

    # Create cancellation event
    cancel_event = asyncio.Event()

    # Set up cancellation check
    async def check_cancellation():
        while not cancel_event.is_set():
            if await should_cancel_task(task.id):
                cancel_event.set()
                await claude_code.cancel_execution()
            await asyncio.sleep(1)

    # Start cancellation checker
    cancel_task = asyncio.create_task(check_cancellation())

    try:
        # Execute with timeout
        result = await asyncio.wait_for(
            claude_code.execute_command(
                command=task.description,
                workspace_path=task.workspace_path
            ),
            timeout=task.timeout_seconds
        )

        return result

    except asyncio.TimeoutError:
        await claude_code.cancel_execution()
        raise TaskTimeoutError(f"Task {task.id} timed out")

    finally:
        cancel_event.set()
        await cancel_task
```

## Context Management

### Creating Execution Context

```python
from src.providers.context.context_provider import ContextProvider

# Create context with correlation ID
context = ContextProvider.create_context(
    correlation_id=f"task-{task.id}",
    user_id=task.user_id,
    metadata={
        "task_type": task.type,
        "workspace": task.workspace_path
    }
)

# Use context for logging and tracking
logger.info(
    "Starting task execution",
    extra={
        "correlation_id": context.correlation_id,
        "user_id": context.user_id,
        "task_id": task.id
    }
)

# Execute with context
result = await agent.execute_task(task=task, context=context)
```

### Cancellation Support

```python
# Set cancellation signal in context
context.set_cancellation_requested()

# Check for cancellation during execution
if context.is_cancellation_requested():
    logger.info("Cancellation requested, stopping execution")
    await cleanup_resources()
    raise TaskCancelledError(task.id)
```

## Best Practices

### 1. Resource Management

```python
class AgentManager:
    """Manage agent lifecycle and resources"""

    def __init__(self):
        self._agents = {}
        self._lock = asyncio.Lock()

    async def get_agent(self, agent_type: str) -> BaseAgent:
        """Get or create agent instance"""
        async with self._lock:
            if agent_type not in self._agents:
                self._agents[agent_type] = await self._create_agent(agent_type)
            return self._agents[agent_type]

    async def cleanup(self):
        """Cleanup all agent resources"""
        for agent in self._agents.values():
            await agent.cleanup()
        self._agents.clear()
```

### 2. Logging and Monitoring

```python
async def execute_with_monitoring(task: Task) -> TaskResult:
    """Execute task with comprehensive monitoring"""

    start_time = time.time()

    try:
        # Log start
        logger.info(
            "Task execution started",
            extra={
                "task_id": task.id,
                "task_type": task.type,
                "timestamp": datetime.now().isoformat()
            }
        )

        # Execute
        result = await agent.execute_task(task)

        # Log success
        duration = time.time() - start_time
        logger.info(
            "Task execution completed",
            extra={
                "task_id": task.id,
                "duration_seconds": duration,
                "success": result.success
            }
        )

        return result

    except Exception as e:
        # Log failure
        duration = time.time() - start_time
        logger.error(
            "Task execution failed",
            extra={
                "task_id": task.id,
                "duration_seconds": duration,
                "error": str(e),
                "traceback": traceback.format_exc()
            }
        )
        raise
```

### 3. State Persistence

```python
async def execute_with_checkpoints(task: Task) -> TaskResult:
    """Execute task with state checkpoints for resumability"""

    checkpoint_manager = CheckpointManager()

    # Try to resume from checkpoint
    checkpoint = await checkpoint_manager.get_latest_checkpoint(task.id)

    if checkpoint:
        logger.info(f"Resuming from checkpoint: {checkpoint.name}")
        state = checkpoint.state
    else:
        state = initialize_state(task)

    # Execute with checkpoints
    for step in workflow_steps:
        # Execute step
        state = await execute_step(step, state)

        # Save checkpoint
        await checkpoint_manager.save_checkpoint(
            task_id=task.id,
            checkpoint_name=step.name,
            state=state
        )

    return create_result_from_state(state)
```

## Common Pitfalls and Solutions

### Pitfall 1: Agent Resource Leaks
**Problem**: Not properly cleaning up agent resources
**Solution**: Use context managers and ensure cleanup

```python
async with AgentContext(config) as agent:
    result = await agent.execute_task(task)
# Agent automatically cleaned up
```

### Pitfall 2: Ignoring Streaming Output
**Problem**: Missing important agent output and progress
**Solution**: Always implement streaming callbacks

```python
async def on_output(output: str):
    await process_output(output)

result = await agent.execute_task(task, stream_callback=on_output)
```

### Pitfall 3: No Timeout Handling
**Problem**: Tasks hanging indefinitely
**Solution**: Always use timeouts

```python
result = await asyncio.wait_for(
    agent.execute_task(task),
    timeout=task.timeout_seconds or 300
)
```

## Integration Points

- **Worker**: `src/worker/tasks.py` - Task queue processing
- **Service**: `src/services/task_service.py` - Business logic
- **Repository**: `src/repositories/task_repository.py` - Data persistence
- **Provider**: `src/providers/` - Infrastructure abstractions

## Reference

- Agent implementation: `src/agents/`
- Configuration: `environments/` TOML files
- MCP servers: `src/providers/mcp/mcp-servers.json`
- Project patterns: `.claude/context/memory/patterns.md`
