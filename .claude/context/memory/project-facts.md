# Project Facts

## Project: SWE Agent

### Core Purpose
AI-powered orchestration system for automating SDLC workflows with clean layered architecture. Enables autonomous development task execution using Claude Code CLI and LangGraph workflows.

### Technology Stack

#### Backend
- **Language**: Python 3.11+
- **Framework**: FastAPI 0.104+
- **ORM**: SQLAlchemy 2.0
- **Validation**: Pydantic v2
- **Async**: asyncio, aiohttp
- **Task Queue**: AWS SQS (LocalStack for dev)

#### Frontend
- **Framework**: React 18
- **Language**: TypeScript 5
- **Build Tool**: Vite
- **State Management**: React Context
- **Routing**: React Router v6

#### Infrastructure
- **Database**: MySQL 8.0
- **Cache**: Redis 7.0
- **Containerization**: Docker, Docker Compose
- **Deployment**: Docker-based deployment

#### AI/Agent Tools
- **Primary Agent**: Claude Code CLI
- **Workflow Engine**: LangGraph
- **Protocol**: MCP (Model Context Protocol)
- **Version Control**: GitHub via gh CLI and PyGithub

### Architecture

#### Layered Architecture

```
API Layer (FastAPI)
├── REST endpoints
├── Request validation
└── Response serialization
↓
Service Layer (Business Logic)
├── Task orchestration
├── LangGraph workflows
└── Agent coordination
↓
Repository Layer (Data Access)
├── CRUD operations
├── Query optimization
└── Transaction management
↓
Model Layer (Domain Entities)
├── SQLAlchemy models
├── Pydantic schemas
└── Business entities
↓
Provider Layer (Infrastructure)
├── Database connections
├── Cache management
├── Queue operations
└── External integrations
```

#### Component Architecture
```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   API Server │────▶│     Queue    │────▶│    Worker    │
│  (FastAPI)   │     │    (SQS)     │     │  (Background)│
└──────────────┘     └──────────────┘     └───────┬──────┘
       │                                           │
       ▼                                           ▼
┌──────────────┐                         ┌──────────────┐
│   Database   │                         │    Agent     │
│   (MySQL)    │                         │(Claude Code) │
└──────────────┘                         └──────────────┘
       │                                           │
       ▼                                           ▼
┌──────────────┐                         ┌──────────────┐
│    Redis     │                         │ MCP Servers  │
│   (Cache)    │                         │ (GitHub,etc) │
└──────────────┘                         └──────────────┘
```

### Key Design Patterns
- **Repository Pattern**: Data access abstraction
- **Service Layer Pattern**: Business logic orchestration
- **Singleton Pattern**: Resource sharing (ClaudeCodeTool)
- **Delegation Pattern**: Task execution distribution
- **Template Method Pattern**: Lifecycle management
- **Factory Pattern**: Object creation (task handlers)
- **Strategy Pattern**: Task execution strategies
- **Observer Pattern**: Event publishing (task status updates)

### Development Workflow

#### Branch Strategy
- `master` - Production-ready code
- `feature/*` - New features
- `bugfix/*` - Bug fixes
- `refactor/*` - Code refactoring
- `docs/*` - Documentation updates

#### PR Process
1. Create feature branch
2. Implement changes with tests
3. Create draft PR for early feedback
4. Address review comments
5. Mark PR ready for review
6. Merge after approval and CI passes

#### Testing Requirements
- **Unit Tests**: 80%+ coverage
- **Integration Tests**: All component interactions
- **E2E Tests**: Critical user workflows
- **All tests must pass** before merge

#### Code Review Checklist
- [ ] Type hints on all functions
- [ ] Early error handling with guards
- [ ] Async/await for I/O
- [ ] Proper session cleanup
- [ ] Tests added/updated
- [ ] No hardcoded secrets
- [ ] Documentation updated

### Important Directories

#### Source Code (`src/`)
- **`api/`** - REST API endpoints and routers
  - `routers/` - API route definitions
  - `dependencies/` - Dependency injection
  - `middleware/` - Request/response middleware

- **`services/`** - Business logic layer
  - `task_service.py` - Task management
  - `workflow_service.py` - LangGraph workflows
  - `agents_catalogue/` - Service registry

- **`repositories/`** - Data access layer
  - `task_repository.py` - Task CRUD
  - `user_repository.py` - User CRUD
  - `base_repository.py` - Generic repository

- **`models/`** - Domain models and schemas
  - SQLAlchemy ORM models
  - Pydantic request/response schemas
  - Enums and constants

- **`providers/`** - Infrastructure abstractions
  - `database/` - Database connections
  - `redis/` - Cache provider
  - `queue/` - SQS provider
  - `github/` - GitHub integration
  - `mcp/` - MCP configuration
  - `config_loader/` - Configuration management

- **`agents/`** - Agent system
  - `autonomous_agent_tool.py` - Main orchestrator
  - `terminal_agents/` - Agent implementations
    - `claude_code.py` - Claude Code integration

- **`worker/`** - Background task processing
  - `tasks.py` - Task processor
  - `handlers/` - Task type handlers

- **`migrations/`** - Database migrations
  - `scripts/` - Migration scripts
  - `run_migrations.py` - Migration runner

- **`utils/`** - Utility functions
  - `logging.py` - Logging configuration
  - `decorators.py` - Common decorators
  - `validators.py` - Custom validators

#### Tests (`tests/`)
- **`unit/`** - Unit tests
- **`integration/`** - Integration tests
- **`e2e/`** - End-to-end tests
- **`mocks/`** - Mock providers
- **`fixtures/`** - Test fixtures
- **`config/`** - Test configuration

#### Configuration (`environments/`)
- `env.default.toml` - Default configuration
- `env.dev_docker.toml` - Docker development
- `env.dev_local.toml` - Local development
- `env.prod.toml` - Production configuration

#### Frontend (`ui/`)
- `src/` - React application
- `public/` - Static assets
- `package.json` - Dependencies
- `vite.config.ts` - Vite configuration

### Code Quality Standards

#### Python Code Style
- **PEP 8** compliance
- **Type hints** on all function signatures
- **Docstrings** for public APIs
- **Early error handling** with guard clauses
- **Async/await** for all I/O operations
- **Context managers** for resource management

#### Testing Standards
- **Arrange-Act-Assert** pattern
- **Isolated tests** with proper fixtures
- **Mock external dependencies**
- **Clear test names** describing behavior
- **Fast unit tests** (< 100ms per test)

#### Security Standards
- **No hardcoded secrets** in code
- **Environment variables** for configuration
- **Input validation** with Pydantic
- **SQL injection prevention** via ORM
- **Authentication** on all protected endpoints
- **Rate limiting** on API endpoints

### Service URLs

#### Docker (Default)
- **Web UI**: http://localhost:28001
- **API**: http://localhost:28002
- **API Docs**: http://localhost:28002/docs
- **Database**: localhost:23306
- **Redis**: localhost:26379
- **LocalStack**: http://localhost:4566

#### Local Development
- **Web UI**: http://localhost:8001
- **API**: http://localhost:8002

### Environment Variables

#### Required
```bash
# Database
DATABASE_URL=mysql://user:password@localhost:23306/swe_agent

# Redis
REDIS_URL=redis://localhost:26379/0

# GitHub
GITHUB_TOKEN=ghp_your_token_here

# SQS (LocalStack for dev)
AWS_ENDPOINT_URL=http://localhost:4566
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_DEFAULT_REGION=us-east-1
```

#### Optional
```bash
# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Worker
WORKER_CONCURRENCY=5
TASK_TIMEOUT=300

# API
API_CORS_ORIGINS=http://localhost:8001
```

### Key Concepts

#### Task Types
- `feature_implementation` - Implement new features
- `bug_fix` - Fix bugs and issues
- `refactoring` - Refactor code
- `documentation` - Generate documentation
- `testing` - Write tests

#### Task Lifecycle
```
PENDING → QUEUED → IN_PROGRESS → COMPLETED
                              ↘ FAILED
                              ↘ CANCELLED
```

#### Agent Execution Flow
1. Task created via API
2. Task queued to SQS
3. Worker picks up task
4. Worker delegates to AutonomousAgentTool
5. Agent uses ClaudeCodeTool with MCP servers
6. Results stored in database
7. Task status updated

### Performance Considerations

#### Database
- Connection pool size: 10 (adjustable)
- Query timeout: 30 seconds
- Use eager loading to prevent N+1 queries
- Index frequently queried columns

#### Redis Cache
- TTL: 1 hour default
- Max memory: 512MB
- Eviction policy: LRU

#### API
- Request timeout: 60 seconds
- Rate limit: 100 requests/minute per user
- Response compression enabled

#### Worker
- Max concurrent tasks: 5
- Task timeout: 300 seconds (configurable)
- Retry failed tasks: 3 attempts

### Common Issues

See `.claude/context/memory/known-issues.md` for detailed troubleshooting.

### External Integrations

#### GitHub
- **Purpose**: Repository operations, PR creation
- **Tool**: gh CLI + PyGithub
- **Authentication**: Personal Access Token

#### Claude Code
- **Purpose**: AI-powered code generation
- **Tool**: Claude Code CLI
- **Configuration**: MCP servers in `src/providers/mcp/mcp-servers.json`

#### MCP Servers
- **github**: GitHub operations
- **filesystem**: File system access
- **memory**: Persistent agent memory

### Deployment

#### Docker Deployment
```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

#### Local Development
```bash
# Start infrastructure
docker-compose up -d db redis localstack

# Run API locally
make api-local

# Run worker locally
make worker-local

# Run UI locally
cd ui && npm run dev
```

### Monitoring and Observability

#### Logging
- Structured JSON logging
- Correlation IDs for request tracking
- Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Log location: `tmp/logs/`

#### Health Checks
- API: `/health` endpoint
- Database: Connection pool status
- Redis: Ping check
- Worker: Heartbeat mechanism

#### Metrics
- Task execution duration
- Task success/failure rates
- API response times
- Queue depth

### Team Communication

#### GitHub
- Issues for bug tracking
- Pull requests for code review
- Discussions for proposals

#### Documentation
- README.md for project overview
- CLAUDE.md for development guidelines
- `.claude/` for agent-specific instructions

### Project Conventions

#### Naming Conventions
- Files: `snake_case.py`
- Classes: `PascalCase`
- Functions/variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Private members: `_leading_underscore`

#### Import Order
1. Standard library imports
2. Third-party imports
3. Local application imports
4. Blank line between groups

#### Commit Message Format
```
type(scope): subject

body

footer
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

### Learning Resources

#### Internal Documentation
- `/CLAUDE.md` - Project development guide
- `.claude/CLAUDE.md` - Claude operating instructions
- `.claude/context/memory/patterns.md` - Common patterns
- `.claude/skills/` - Specialized skills documentation

#### External Resources
- FastAPI: https://fastapi.tiangolo.com/
- SQLAlchemy 2.0: https://docs.sqlalchemy.org/
- LangGraph: https://langchain-ai.github.io/langgraph/
- MCP: https://modelcontextprotocol.io/
