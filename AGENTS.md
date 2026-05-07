# SWE Agent

AI orchestration system for automating SDLC workflows.

## Quick Start

```bash
./scripts/start_service.sh        # Complete Docker setup
make start                        # Or use Make
```

**URLs:** UI http://localhost:28001 | API http://localhost:28002/docs

## Development Setup

### Prerequisites

- **Yarn** - Package manager (uses Corepack)

```bash
# Install Corepack if not present (one-time)
npm install -g corepack

# Enable Yarn (uses version from packageManager field)
corepack enable

# Verify
yarn --version
```

### Environment Setup

```bash
# GitHub authentication (required)
gh auth login
export GITHUB_TOKEN=$(gh auth token)

# Environment config
cp environments/env.default.toml environments/env.dev_docker.toml
# Edit with your configuration
```

## Architecture

**Layered design** with clean separation:

- `api/` - HTTP routes and dependency injection
- `services/` - Business logic, LangGraph workflows
- `repositories/` - Data access layer
- `providers/` - Infrastructure abstractions
- `agents/` - AI agent implementations
- `worker/` - Background task processing

**Patterns**: Repository, Service, Dependency Injection

## Code Standards

- **Python** with type hints on all functions
- **Async/await** for all I/O operations
- **Early error handling** with guard clauses
- **80%+ test coverage** on new code
- **Edit existing files** over creating new ones when possible

## Testing

```bash
make test-unit              # Fast unit tests
make test-integration       # Integration tests
make test-coverage          # Coverage report
```

See [docs/testing.md](./docs/testing.md) for import patterns and test organization.

## Key Commands

```bash
make start                  # Start all services
make stop                   # Stop all services
make restart                # Restart app containers
make destroy                # Remove containers, keep volumes (DB data preserved)
make clean                  # Full teardown including volumes (DB data lost)
make logs                   # View logs
make status                 # Health check
make api-local              # Run API locally (port 8002)
make ui-local               # Run UI locally (port 8001)

# Script commands
./scripts/start_service.sh              # Complete setup
./scripts/start_service.sh rebuild      # Rebuild (with cache) - for code changes
./scripts/start_service.sh rebuild-no-cache  # Rebuild (no cache) - for Dockerfile changes
./scripts/start_service.sh destroy      # Fresh start, keep database
./scripts/start_service.sh teardown     # Clean slate - delete everything
```

## Discover Integration

Vyom proxies Discover UI API requests to the Discover backend service using **HTTP Basic Authentication** for service-to-service authentication.

### Quick Links

- **Integration Guide**: [docs/discover.md](docs/discover.md)
- **Quick Reference**: [docs/discover-quick-ref.md](docs/discover-quick-ref.md)
- **Service-to-Service Auth**: [docs/service_to_service_auth.md](docs/service_to_service_auth.md)

### Configuration

```toml
[discover]
backend_url = "https://discover-api.concierge.stage.razorpay.in"
timeout = 30

[auth.users]
discover_service = ""  # Set via AUTH__USERS__DISCOVER_SERVICE env var
```

### Architecture

```
User → Vyom (validates Vyom JWT)
            ↓
    Add Basic Auth + X-User-Email header
            ↓
    Proxy request to Discover
```

See [docs/discover.md](docs/discover.md) for complete documentation.

## Adding Features

1. Create service in `src/services/` (inherit from `BaseService`)
2. Add API routes in `src/api/routers/`
3. Create repository if needed in `src/repositories/`
4. Add database models in `src/models/` if required
5. Write tests in `tests/unit/` and `tests/integration/`
6. Database migrations auto-run on worker startup

## Error Handling

Use guard clauses for early returns:

```python
async def process_task(task_id: str) -> TaskResult:
    if not task_id:
        raise HTTPException(status_code=400, detail="Task ID required")

    task = await task_repo.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Main logic here
    return result
```

## Security

- No hardcoded credentials - use environment config
- Sensitive data auto-sanitized in structured logs
- RBAC in `src/providers/auth/rbac.py`
- GitHub OAuth via `src/providers/github/global_auth.py`
- Clean up temporary files after use

## Documentation

- **Architecture**: `/docs/architecture.md`
- **Setup**: `/docs/setup.md`
- **API Docs**: http://localhost:28002/docs (when running)
- **Health**: `/health` and `/health/detailed` endpoints
