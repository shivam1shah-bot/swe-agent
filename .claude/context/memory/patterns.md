# Common Patterns and Solutions

## Architecture Patterns

### Layered Architecture Pattern
**When to Use**: All new features and components
**Implementation**:
```
API Layer (FastAPI)
  → Service Layer (Business Logic)
    → Repository Layer (Data Access)
      → Model Layer (Domain Entities)
        → Provider Layer (Infrastructure)
```
**Example**:
```python
# API Layer
@router.post("/tasks")
async def create_task(request: TaskRequest, service: TaskService = Depends()):
    return await service.create_task(request)

# Service Layer
class TaskService(BaseService):
    async def create_task(self, request: TaskRequest) -> Task:
        task = await self.task_repository.create(request)
        await self.queue_provider.enqueue(task.id)
        return task

# Repository Layer
class TaskRepository(BaseRepository[Task]):
    async def create(self, request: TaskRequest) -> Task:
        async with self.db.session() as session:
            task = Task(**request.dict())
            session.add(task)
            await session.commit()
            return task
```

### Repository Pattern
**When to Use**: All database access operations
**Purpose**: Abstract data access logic from business logic
**Implementation**:
```python
class BaseRepository(Generic[T]):
    def __init__(self, db_provider: DatabaseProvider):
        self.db = db_provider

    async def get_by_id(self, id: str) -> Optional[T]:
        async with self.db.session() as session:
            return await session.get(self.model_class, id)

    async def create(self, entity: T) -> T:
        async with self.db.session() as session:
            session.add(entity)
            await session.commit()
            await session.refresh(entity)
            return entity
```

### Singleton Pattern for Agent Tools
**When to Use**: Agent tools that should be shared across tasks
**Purpose**: Resource sharing and consistent state
**Implementation**:
```python
class ClaudeCodeTool:
    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    async def get_instance(cls, config: AgentConfig) -> "ClaudeCodeTool":
        async with cls._lock:
            if cls._instance is None:
                cls._instance = cls(config)
                await cls._instance.initialize()
            return cls._instance
```

### Service Registry Pattern
**When to Use**: Dynamic service discovery and registration
**Purpose**: Extensibility without modifying core code
**Implementation**:
```python
class ServiceRegistry:
    _services: Dict[str, Type[BaseService]] = {}

    @classmethod
    def register(cls, name: str):
        def decorator(service_class: Type[BaseService]):
            cls._services[name] = service_class
            return service_class
        return decorator

    @classmethod
    def get_service(cls, name: str) -> Optional[Type[BaseService]]:
        return cls._services.get(name)
```

## Error Handling Patterns

### Early Return with Guard Clauses
**When to Use**: Input validation, error checking
**Purpose**: Reduce nesting and improve readability
**Implementation**:
```python
async def process_task(task_id: str) -> TaskResult:
    # Guard clauses at the top
    if not task_id:
        raise ValueError("Task ID is required")

    task = await task_repository.get_by_id(task_id)
    if not task:
        raise TaskNotFoundError(task_id)

    if task.status != TaskStatus.PENDING:
        raise InvalidTaskStateError(f"Task {task_id} is not pending")

    # Main logic after all guards
    result = await execute_task(task)
    return result
```

### Comprehensive Error Context
**When to Use**: All error handling
**Purpose**: Provide actionable error information
**Implementation**:
```python
try:
    result = await risky_operation()
except Exception as e:
    logger.error(
        "Operation failed",
        extra={
            "error": str(e),
            "task_id": task_id,
            "context": {"step": "execution", "attempt": retry_count},
            "traceback": traceback.format_exc()
        }
    )
    raise OperationError(
        f"Failed to execute task {task_id}: {str(e)}"
    ) from e
```

## Async Patterns

### Async Context Managers
**When to Use**: Resource management (DB sessions, connections)
**Purpose**: Ensure proper cleanup in async contexts
**Implementation**:
```python
class AsyncSessionManager:
    async def __aenter__(self):
        self.session = self.session_factory()
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is None:
                await self.session.commit()
            else:
                await self.session.rollback()
        finally:
            await self.session.close()
```

### Concurrent Task Execution
**When to Use**: Independent async operations
**Purpose**: Improve performance through parallelism
**Implementation**:
```python
async def process_multiple_tasks(task_ids: List[str]) -> List[TaskResult]:
    # Create tasks concurrently
    tasks = [process_task(task_id) for task_id in task_ids]

    # Wait for all to complete
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Handle results and errors
    successful = [r for r in results if not isinstance(r, Exception)]
    failed = [r for r in results if isinstance(r, Exception)]

    return successful
```

### Async Timeouts
**When to Use**: Operations that may hang
**Purpose**: Prevent indefinite waiting
**Implementation**:
```python
async def execute_with_timeout(operation: Awaitable[T], timeout: int = 300) -> T:
    try:
        return await asyncio.wait_for(operation, timeout=timeout)
    except asyncio.TimeoutError:
        raise OperationTimeoutError(f"Operation timed out after {timeout}s")
```

## Testing Patterns

### Test Fixtures with Proper Cleanup
**When to Use**: All tests requiring setup
**Purpose**: Isolated, repeatable tests
**Implementation**:
```python
@pytest.fixture
async def task_service(db_provider):
    service = TaskService(db_provider)
    yield service
    # Cleanup
    await service.cleanup()

@pytest.fixture
async def sample_task(task_repository):
    task = await task_repository.create(TaskRequest(name="test"))
    yield task
    # Cleanup
    await task_repository.delete(task.id)
```

### Mock Providers
**When to Use**: Tests requiring external dependencies
**Purpose**: Isolate tests from external systems
**Implementation**:
```python
class MockGitHubProvider:
    def __init__(self):
        self.repos = {}

    async def get_repo(self, name: str) -> MockRepo:
        return self.repos.get(name, MockRepo(name))

    async def create_pr(self, repo: str, **kwargs) -> MockPR:
        return MockPR(id=str(uuid.uuid4()), **kwargs)
```

## Configuration Patterns

### Layered Configuration
**When to Use**: Environment-specific settings
**Purpose**: Flexible configuration across environments
**Implementation**:
```python
# Load order: default → environment → runtime
config = ConfigLoader.load(
    default_path="environments/env.default.toml",
    env_path=f"environments/env.{ENV}.toml",
    overrides=runtime_overrides
)
```

### Configuration Validation
**When to Use**: Application startup
**Purpose**: Fail fast on misconfiguration
**Implementation**:
```python
class AppConfig(BaseModel):
    database_url: str
    redis_url: str
    github_token: SecretStr

    @validator('database_url')
    def validate_db_url(cls, v):
        if not v.startswith(('mysql://', 'postgresql://')):
            raise ValueError('Invalid database URL')
        return v
```

## Agent Orchestration Patterns

### Task Delegation Pattern
**When to Use**: Autonomous agent task execution
**Purpose**: Separate orchestration from execution
**Implementation**:
```python
class AutonomousAgentTool:
    async def execute_task(self, task: Task) -> TaskResult:
        # Delegate to specialized agent based on task type
        agent = self._get_agent_for_task(task)

        try:
            result = await agent.execute(task)
            await self._store_result(task.id, result)
            return result
        except Exception as e:
            await self._handle_error(task.id, e)
            raise
```

### State Machine Pattern (LangGraph)
**When to Use**: Complex workflows with multiple states
**Purpose**: Manage workflow state transitions
**Implementation**:
```python
workflow = StateGraph(WorkflowState)

workflow.add_node("analyze", analyze_node)
workflow.add_node("plan", plan_node)
workflow.add_node("execute", execute_node)
workflow.add_node("verify", verify_node)

workflow.add_edge("analyze", "plan")
workflow.add_edge("plan", "execute")
workflow.add_conditional_edges("execute", should_retry, {
    "retry": "plan",
    "verify": "verify"
})

app = workflow.compile()
```

## Database Patterns

### Eager Loading for Performance
**When to Use**: Queries with related entities
**Purpose**: Avoid N+1 query problems
**Implementation**:
```python
# Load tasks with related user data in single query
tasks = await session.execute(
    select(Task)
    .options(joinedload(Task.user))
    .options(selectinload(Task.executions))
    .where(Task.status == TaskStatus.PENDING)
)
```

### Batch Operations
**When to Use**: Multiple insert/update operations
**Purpose**: Reduce database round trips
**Implementation**:
```python
async def create_multiple_tasks(tasks: List[TaskRequest]) -> List[Task]:
    async with session.begin():
        task_entities = [Task(**task.dict()) for task in tasks]
        session.add_all(task_entities)
        await session.flush()  # Get IDs without committing
        return task_entities
```

## Logging Patterns

### Structured Logging with Context
**When to Use**: All logging statements
**Purpose**: Enable log aggregation and analysis
**Implementation**:
```python
logger.info(
    "Task execution started",
    extra={
        "task_id": task.id,
        "task_type": task.type,
        "correlation_id": context.correlation_id,
        "user_id": context.user_id
    }
)
```

### Sensitive Data Sanitization
**When to Use**: Logging user data or credentials
**Purpose**: Prevent secret leakage
**Implementation**:
```python
def sanitize_log_data(data: Dict[str, Any]) -> Dict[str, Any]:
    sensitive_keys = {'password', 'token', 'secret', 'api_key'}
    return {
        k: '***REDACTED***' if k.lower() in sensitive_keys else v
        for k, v in data.items()
    }
```

## Common Solutions

### Retry with Exponential Backoff
**Use Case**: Transient failures (network, rate limits)
**Implementation**:
```python
async def retry_with_backoff(
    operation: Callable,
    max_retries: int = 3,
    base_delay: float = 1.0
) -> Any:
    for attempt in range(max_retries):
        try:
            return await operation()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt)
            await asyncio.sleep(delay)
```

### Circuit Breaker Pattern
**Use Case**: Protect against cascading failures
**Implementation**:
```python
class CircuitBreaker:
    def __init__(self, threshold: int = 5, timeout: int = 60):
        self.threshold = threshold
        self.timeout = timeout
        self.failures = 0
        self.last_failure_time = None
        self.state = "closed"

    async def call(self, operation: Callable) -> Any:
        if self.state == "open":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "half-open"
            else:
                raise CircuitBreakerOpen()

        try:
            result = await operation()
            self.failures = 0
            self.state = "closed"
            return result
        except Exception as e:
            self.failures += 1
            self.last_failure_time = time.time()
            if self.failures >= self.threshold:
                self.state = "open"
            raise
```

## Anti-Patterns to Avoid

### ❌ God Objects
Don't create classes that do everything. Follow Single Responsibility Principle.

### ❌ Blocking I/O in Async Functions
Never use `time.sleep()` or blocking operations in async functions. Use `asyncio.sleep()`.

### ❌ Ignoring Exceptions
Always handle exceptions appropriately. Don't use bare `except:` clauses.

### ❌ Hardcoded Configuration
Never hardcode URLs, credentials, or environment-specific values. Use configuration files.

### ❌ SQL String Concatenation
Never build SQL queries with string concatenation. Use parameterized queries or ORMs.

### ❌ Missing Type Hints
Always include type hints on function signatures for better IDE support and type checking.
