# Agent Development Guide

Creating backend AI agent services for the Agents Catalogue.

## Architecture

Agent services follow a dual-execution pattern:

```
API Request → execute() → Queue Task → Worker → async_execute() → Autonomous Agent → Results
```

- **execute()**: Synchronous, queues task, returns task ID immediately
- **async_execute()**: Asynchronous, runs in worker, performs actual AI processing

This separation enables long-running agent tasks (5-30 minutes) without HTTP timeouts.

## Service Structure

Extend `BaseAgentsCatalogueService` and implement:

```python
class MyAgentService(BaseAgentsCatalogueService):
    @property
    def description(self) -> str: ...

    def execute(self, parameters: dict) -> dict: ...
    def async_execute(self, parameters: dict, ctx: Context) -> dict: ...
    def _validate_parameters(self, parameters: dict) -> None: ...
    def _create_agent_prompt(self, parameters: dict) -> str: ...
```

## Key Patterns

### Validation

- Validate in both `execute()` and `async_execute()`
- Use modular validator classes for complex validation
- Fail fast with clear error messages

### Prompt Engineering

- Define clear role and expertise domain
- Structure input parameters explicitly
- Specify output format with examples
- Include validation steps in prompt

### Error Handling

- Log with context via `get_logging_context(ctx)`
- Return structured error responses
- Don't leak internal exceptions to API responses

### Registration

Register at module level:

```python
service_registry.register("my-usecase-name", MyAgentService)
```

Use kebab-case names that describe the use case clearly.

## Location Options

**Agents Catalogue** (`src/services/agents_catalogue/`): Team-wide agents with UI integration and service registry.

**Custom Agents** (`/agents/`): Standalone experimental agents without catalogue integration.

Study existing agents in both locations for patterns.

## Testing

Test both paths:

- Unit test `execute()` with mocked queue
- Unit test `async_execute()` with mocked agent
- Integration test through API endpoint

## Reference Implementations

Study these for patterns:

- `SpinnakerPipelineService` - Complex workflow with validation
- `RepoContextGeneratorService` - Documentation generation
- `GatewayIntegrationsCommonService` - Gateway integration patterns
