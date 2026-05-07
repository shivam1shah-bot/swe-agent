# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Docker Services

```bash
# Complete setup and start all services
./scripts/start_service.sh

# Quick commands using Makefile
make start         # Start all services
make stop          # Stop all services
make restart       # Restart app containers (API, UI, worker) - keeps infrastructure
make restart-all   # Restart all services including DB, Redis, LocalStack
make rebuild       # Complete rebuild and restart
make status        # Show system status and health checks
make logs          # Show all logs
make logs-tail     # Show recent logs
```

### Testing

```bash
# Setup Python environment
make setup                    # Setup virtual environment and install dependencies

# Run tests
make test                     # Run all tests
make test-unit               # Run unit tests only (fast)
make test-integration        # Run integration tests
make test-coverage           # Run tests with coverage report
make test-parallel           # Run tests in parallel
make test-ci                 # Run tests for CI/CD with reports
```

### Development Servers

```bash
# Run services locally (outside Docker)
make api-local              # Run API server locally on port 8002
make ui-local               # Run React UI dev server locally
make worker-local           # Run task execution worker locally
make app-local              # Run API, worker, and React UI locally
```

**Prerequisites:**

- UI development requires **Node.js** and **Yarn**
- Yarn is managed via Corepack

```bash
# Install Corepack (one-time)
npm install -g corepack

# Enable Yarn (uses version from packageManager field)
corepack enable
```

### Frontend Commands

```bash
cd ui/
yarn dev            # Start development server
yarn build          # Build for production
yarn lint           # Run ESLint
```

### PR Review Prompts Management

```bash
# IMPORTANT: Set GITHUB_TOKEN before running prompt sync commands
export GITHUB_TOKEN=$(gh auth token)

# Update pr-prompt-kit package to latest version
make sync-prompts              # Quick update: Reinstall pr-prompt-kit and restart worker
make sync-prompts-rebuild      # Full rebuild: Rebuild Docker image with latest prompts

# Code review worker commands
make logs-review-worker        # Show code review worker logs
make restart-review-worker     # Restart code review worker only
make build-review-worker       # Rebuild code review worker image
```

**Note**: All commands that install/update `pr-prompt-kit` require `GITHUB_TOKEN` to access the private repository.

## Architecture Overview

SWE Agent is an AI-powered orchestration system for automating SDLC workflows with a clean layered architecture:

### Core Architecture Layers

- **API Layer** (`src/api/`): FastAPI-based REST endpoints with dependency injection
- **Service Layer** (`src/services/`): Business logic, LangGraph workflows, agent orchestration
- **Repository Layer** (`src/repositories/`): Data access abstraction with SQLAlchemy
- **Model Layer** (`src/models/`): Domain entities and Pydantic schemas
- **Provider Layer** (`src/providers/`): Infrastructure abstractions (database, cache, config, GitHub)

### Key Components

#### Agent System (`src/agents/`)

- **AutonomousAgentTool**: Main orchestrator for autonomous task execution
- **ClaudeCodeTool**: Core interface to Claude Code CLI with MCP configuration
- **Terminal Agents**: Specialized agents for different AI providers
- Uses singleton pattern for resource sharing and delegation pattern for task execution

#### Task Processing

- **Worker Pattern**: `SWEAgentWorker` with SQS-based queue processing
- **Task Flow**: API → Queue → Worker → Agent → Result Storage
- **Handler Registry**: Task types mapped to specific handler methods
- **Cancellation Support**: Tasks can be cancelled during execution

#### Service Registry (`src/services/agents_catalogue/`)

- **Dynamic Service Discovery**: Registry pattern for agent catalogue functionality
- **Gateway Integrations**: Spinnaker pipeline generation, documentation generation
- **Template System**: Code generation with template-based approaches

### Configuration Management

- **TOML-based Configuration**: Environment files in `environments/`
- **Layered Config**: Default → Environment-specific → Runtime overrides
- **Environment Files**: `env.default.toml`, `env.dev_docker.toml`, `env.prod.toml`, etc.

### Database & Migrations

- **SQLAlchemy 2.0**: ORM with repository pattern
- **Migration System**: Automated schema management in `src/migrations/`
- **Health Monitoring**: Multi-layer health checks across database, cache, and services

### External Integrations

- **Claude Code**: Primary AI agent via CLI interface with streaming support
- **GitHub**: Authentication and repository operations via PyGithub
- **MCP Protocol**: Model Context Protocol for extending AI capabilities
- **SQS**: AWS SQS for reliable task queuing and worker coordination

## Development Patterns

### Service Layer Patterns

All services inherit from `BaseService` with:

- Common initialization and health check patterns
- Context management for resource cleanup
- Template method pattern for lifecycle management

### Repository Pattern

- Generic `BaseRepository[T]` with CRUD operations
- SQLAlchemy implementation with session management
- Context managers for proper resource lifecycle

### Provider Pattern

Infrastructure providers implement external dependencies:

- Database: Connection management with session factory
- Cache: Redis abstraction with health monitoring
- Configuration: Deep merge strategy for layered config
- Context: Request context with correlation IDs and cancellation support

### Error Handling

- Comprehensive error handling with proper status transitions
- Early error handling pattern in all functions
- HTTPException for expected errors, middleware for unexpected errors
- Context propagation through entire execution pipeline

## Environment Setup

### Service URLs (Docker)

- **Web UI**: http://localhost:28001
- **API**: http://localhost:28002
- **API Docs**: http://localhost:28002/docs
- **Database**: localhost:23306
- **Redis**: localhost:26379
- **LocalStack (SQS)**: http://localhost:4566

### Service URLs (Local Development)

- **Web UI**: http://localhost:8001
- **API**: http://localhost:8002

### Environment Configuration

#### Prerequisites

1. **GitHub Token Setup** (Required for private repo access):

   ```bash
   # Authenticate with GitHub CLI
   gh auth login

   # Export GITHUB_TOKEN for Docker builds
   export GITHUB_TOKEN=$(gh auth token)

   # Verify token is set
   echo $GITHUB_TOKEN
   ```

2. Copy default environment: `cp environments/env.default.toml environments/env.dev_docker.toml`
3. Update secrets and configuration for your local setup
4. Use `./scripts/start_service.sh` for automated setup

**Note**: The `GITHUB_TOKEN` is required to install the private `pr-prompt-kit` package during Docker builds. Without it, the build will fail.

## Testing Strategy

### Test Structure

- **Unit Tests** (`tests/unit/`): Fast, isolated component tests
- **Integration Tests** (`tests/integration/`): Cross-component integration
- **E2E Tests** (`tests/e2e/`): Full system workflow tests
- **Performance Tests** (`tests/performance/`): Load and performance testing

### Test Configuration

- Uses pytest with comprehensive plugins (pytest-cov, pytest-xdist, pytest-mock)
- Test configuration in `tests/config/pytest.ini`
- Factory Boy and Faker for test data generation
- Mock providers in `tests/mocks/` for external dependencies

## Code Quality Standards

Following the Cursor rules in `.cursor/rules/`:

- **Python FastAPI patterns**: Async/await, Pydantic v2, dependency injection
- **Early error handling**: Handle errors at function start, use guard clauses
- **Type hints**: All function signatures must include type hints
- **Clean architecture**: Layered architecture with clear separation of concerns
- **Performance optimization**: Async operations for I/O, caching with Redis

## Logging and Monitoring

### Structured Logging

- JSON-based logging with correlation IDs
- Context propagation through request lifecycle
- Automatic sanitization of sensitive data
- Logs stored in `tmp/logs/` with organized structure

### Health Monitoring

- Multi-layer health checks (API, database, cache, worker)
- Performance metrics and task execution timing
- Error tracking with comprehensive logging

## Common Workflows

### Adding New Agent Services

1. Create service class inheriting from `BaseService` in `src/services/agents_catalogue/`
2. Register in service registry (`src/services/agents_catalogue/registry.py`)
3. Add corresponding API routes in `src/api/routers/agents_catalogue.py`
4. Add database entities if needed in `src/models/`

### Adding New Task Types

1. Add task handler method in `TaskProcessor` (`src/worker/tasks.py`)
2. Register handler in `task_handlers` mapping
3. Update task metadata schema in `src/models/task.py`
4. Add API endpoints in `src/api/routers/tasks.py`

### Database Schema Changes

1. Create migration script in `src/migrations/scripts/`
2. Update SQLAlchemy models in `src/models/`
3. Run migrations with worker startup or manual execution
4. Update repository interfaces if needed

## Important Development Guidelines

### Before Implementation

Following `.cursor/rules/general.mdc`:

1. **Create a detailed plan** with specific steps
2. **Ask clarification questions** for unclear requirements
3. **Get explicit user approval** before proceeding

### File Creation Rules

- **NEVER create files unless absolutely necessary** for achieving your goal
- **ALWAYS prefer editing existing files** to creating new ones
- **NEVER proactively create documentation files** (\*.md) or README files unless explicitly requested

### Code Quality Requirements

- **Early error handling**: Handle errors at function start with guard clauses
- **Type hints required**: All function signatures must include complete type hints
- **Use async/await**: For all I/O operations (database calls, external APIs)
- **Pydantic v2**: Use BaseModel for input/output validation and response schemas
- **HTTPException**: Use for expected errors with proper HTTP status codes

### Session Cleanup

- **Always delete temporary files** created during development session
- **Remove debug files, test artifacts** before completion
- **Clean up helper scripts or temporary directories** used for iteration

## Key Development Patterns

### MCP Integration

- **Model Context Protocol**: Located in `src/providers/mcp/mcp-servers.json`
- **Claude Code Tool**: Primary interface with MCP configuration in `src/agents/terminal_agents/claude_code.py`
- **Singleton pattern**: ClaudeCodeTool uses singleton for resource sharing

### Configuration System

- **Layered TOML config**: Default → Environment-specific → Runtime overrides
- **Environment loading**: Uses `src/providers/config_loader/env_loader.py`
- **Deep merge strategy**: For combining configuration layers

### Authentication & Security

- **GitHub OAuth**: Global authentication via `src/providers/github/global_auth.py`
- **Role-based access**: RBAC implementation in `src/providers/auth/rbac.py`
- **Token management**: JWT handling with refresh token support
- **Data sanitization**: Automatic sensitive data removal in logging

### Task Execution Flow

1. **API receives request** → Creates task in database
2. **Task queued to SQS** → Background processing
3. **Worker polls queue** → Picks up task
4. **Agent processes task** → Uses Claude Code or other tools
5. **Results stored** → Database and logs updated
6. **Status updates** → Real-time via API
