# SWE Agent Setup Guide

Complete Docker setup guide for the SWE Agent.

## Prerequisites

- **Docker** & **Docker Compose**
- **Make** (for convenient commands)
- **Git** (for version control)
- **Yarn** - Package manager (uses Corepack)

### Yarn Setup

The UI uses Yarn via the `packageManager` field in `package.json`. Corepack manages the Yarn version:

```bash
# Install Corepack if not present (one-time)
npm install -g corepack

# Enable Yarn (uses version from packageManager field)
corepack enable

# Verify
yarn --version
```

## Quick Setup

### 🚀 **One-Command Setup** (Recommended)

```bash
# Clone and start
git clone https://github.com/razorpay/swe-agent.git
cd swe-agent
./scripts/start_service.sh
```

This automatically:

- ✅ Creates `env.dev_docker.toml` from defaults
- ✅ Starts all services (API, UI, Database, Redis, LocalStack)
- ✅ Runs database migrations and seeds data

### 🔧 **Manual Setup**

```bash
# 1. Create environment config
cp environments/env.default.toml environments/env.dev_docker.toml

# 2. Build and start
make build && make run

# 3. Check status
make status
```

## Services & Access Points

| Service        | Port  | URL                         |
| -------------- | ----- | --------------------------- |
| **Web UI**     | 28001 | http://localhost:28001      |
| **API**        | 28002 | http://localhost:28002      |
| **API Docs**   | 28002 | http://localhost:28002/docs |
| **Database**   | 23306 | localhost:23306             |
| **Redis**      | 26379 | localhost:26379             |
| **LocalStack** | 4566  | http://localhost:4566       |

## Configuration

### Required Environment Variables

```bash
# AWS credentials for Claude
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=us-east-1

# GitHub Personal Access Token
export GITHUB_PERSONAL_ACCESS_TOKEN=your_token
```

### Claude Code Setup

**Claude Code Documentation**: [Claude Code Overview](https://docs.anthropic.com/en/docs/claude-code/overview)

**Getting AWS Bedrock Keys for Local Development**: [Bedrock Keys Setup Guide](https://docs.google.com/document/d/1265_wjKAyc-TN3mitzRbw_kR_3ZMga9riXqi8KWBw4w/edit?pli=1&tab=t.0#heading=h.tldv7aoeayu8)

## Service Management

### Basic Commands

```bash
# Start/stop/restart
./scripts/start_service.sh
./scripts/start_service.sh stop
./scripts/start_service.sh restart

# Check status and logs
./scripts/start_service.sh status
make logs
make logs-tail

# Rebuild after code changes (uses cache - fast)
./scripts/start_service.sh rebuild

# Rebuild after Dockerfile changes (no cache - slower)
./scripts/start_service.sh rebuild-no-cache

# Remove containers, keep database data (for fresh start)
./scripts/start_service.sh destroy

# Full teardown - removes everything including data
./scripts/start_service.sh teardown
```

### Docker Compose Commands

All Docker commands use `COMPOSE_PROJECT_NAME=swe-agent` for consistent container naming regardless of directory.

```bash
# Individual services
make build-api          # Build API only
make build-ui           # Build UI only
make build-worker       # Build worker only
make restart-review-worker      # Restart code review worker

# System management
make destroy            # Remove containers, keep volumes (data preserved)
make clean              # Remove containers and volumes (data lost)
docker-compose down -v  # Reset with data (legacy)
```

### UI Docker Build (Yarn 4)

Both production and development UI Dockerfiles use Yarn 4 with automated smoke tests:

| File | Purpose | Smoke Tests |
|------|---------|-------------|
| `build/docker/prod/Dockerfile.ui` | Production image (multi-stage) | Prod deps, artifacts, server startup |
| `build/docker/dev/Dockerfile.ui.dev` | Development image | All deps, source files, build, server |

**Why smoke tests in both?**
- Catches Yarn 4 issues early in development (before production)
- Ensures dev/prod parity - if dev builds, prod should too
- Validates source code is properly copied before runtime

**Key features:**
- **Multi-stage build** (prod): Builder has dev deps, final image only production deps
- **Yarn 4 with Corepack**: Consistent package management
- **Production install**: Uses `yarn workspaces focus --all --production` (Yarn 4 replacement for deprecated `--production` flag)
- **Automated smoke tests**: Build fails if dependencies missing or server won't start
- **No Go binaries in prod**: esbuild (Go-compiled) stays in builder stage only

**Build arguments:**
```bash
# Production build
docker build \
  --build-arg GIT_COMMIT_HASH=$(git rev-parse --short HEAD) \
  -f build/docker/prod/Dockerfile.ui \
  -t swe-agent-ui:latest .

# Development build
docker build \
  --build-arg GIT_COMMIT_HASH=$(git rev-parse --short HEAD) \
  -f build/docker/dev/Dockerfile.ui.dev \
  -t swe-agent-ui:dev .
```

**Yarn 4 commands by stage:**

| Stage | Command | Purpose |
|-------|---------|---------|
| Builder (prod) | `yarn install --immutable` | Install all deps (dev + prod) with lockfile verification |
| Production | `yarn workspaces focus --all --production` | Install only production deps (Yarn 4 way) |
| Development | `yarn install --immutable` | Install all deps (dev + prod) for development |

**Smoke test scripts:**

| Script | Tests |
|--------|-------|
| `build/docker/scripts/smoke-test-ui.sh` (prod) | Runtime deps (express, pino, dotenv), build artifacts, server responds to `/health` |
| `build/docker/scripts/smoke-test-ui-dev.sh` (dev) | All deps (incl. vite, typescript), source files, `yarn build` succeeds, server startup |

**Health endpoint:**
The UI server provides a `/health` endpoint for container orchestration:
```bash
curl http://localhost:8001/health
# {"status":"healthy","timestamp":1711234567}
```

## Database Management

```bash
# Access database
make db-shell

# Manual migrations
docker exec swe-agent-api python -c "
from src.providers.database.provider import DatabaseProvider
from src.providers.config_loader import get_config
db = DatabaseProvider()
db.initialize(get_config())
db.run_migrations()
"

# Reset database
docker-compose down -v && docker-compose up -d
```

## Health Checks & Monitoring

```bash
# Service health
curl http://localhost:28002/api/health

# Container status
docker ps
docker stats

# Troubleshooting
docker-compose logs swe-agent-api
docker system info
```

## Troubleshooting

### Common Issues

**Services won't start (orphan container warnings):**

This happens when running from different directories. Use the `destroy` command for a clean start:

```bash
# Remove old containers and start fresh (keeps database data)
./scripts/start_service.sh destroy
./scripts/start_service.sh start

# Or full reset (loses all data)
./scripts/start_service.sh teardown
./scripts/start_service.sh setup
```

**Port conflicts:**

```bash
# Check ports
lsof -i :28001 :28002 :23306

# Kill conflicts
kill -9 $(lsof -t -i:28001)

# Check Docker
docker info
```

**Database issues:**

```bash
# Check container
docker logs swe-agent-db

# Reset database
docker-compose restart db
```

**Build issues:**

```bash
# Clean rebuild
docker system prune -a
docker-compose build --no-cache
```

**UI Docker build failures:**

If the UI build fails with smoke test errors:

```bash
# Check smoke test output - shows which dependency is missing
# Common issues:
# - "express not found" -> yarn workspaces focus failed
# - "Server failed to start" -> production deps incomplete

# Build with verbose output to debug
DOCKER_BUILDKIT=0 docker build -f build/docker/prod/Dockerfile.ui .
```

**Yarn 4 migration issues:**

- `yarn install --production` is deprecated in Yarn 4 - use `yarn workspaces focus --all --production`
- `--immutable` only works with `yarn install`, not with `workspaces focus`
- `--network-timeout` only works with `yarn install`, not with `workspaces focus`

## Development

### Making Changes

- **API**: Auto-reload enabled
- **UI**: Hot module replacement active
- **Database**: Restart API service after migrations

### Testing

```bash
# Run tests
docker exec swe-agent-api python -m pytest tests/

# With coverage
docker exec swe-agent-api python -m pytest --cov=src tests/
```

## Next Steps

1. **Explore UI**: http://localhost:28001
2. **Try agents**: Start with Spinnaker Pipeline Generator
3. **Read docs**: [Architecture](./architecture.md) | [Agents Catalogue](./agents_catalogue.md)

For detailed troubleshooting, check container logs with `make logs`.
