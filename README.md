# SWE Agent

An AI-powered orchestration system for automating SDLC workflows.

## What is SWE Agent?

SWE Agent is an AI-powered automation platform that streamlines repetitive engineering SDLC tasks through intelligent workflows powered by LangGraph and custom agentic toolkits.

## Core Capabilities

**🤖 AI Agent Orchestration**: Autonomous agents with LangGraph workflows and context-aware processing

**🏗️ Modern Architecture**: Layered design with FastAPI backend, React frontend, and background workers

**🛠️ Developer Experience**: Interactive UI, REST API, real-time monitoring, and tool integrations

## Quick Start

```bash
# Start everything
./scripts/start_service.sh
```

**Service URLs:**

- **Web UI**: http://localhost:28001
- **API**: http://localhost:28002
- **API Docs**: http://localhost:28002/docs

**Useful Commands:**

```bash
./scripts/start_service.sh status         # Check status
./scripts/start_service.sh restart        # Restart services
./scripts/start_service.sh rebuild        # Rebuild (cached) - for code changes
./scripts/start_service.sh rebuild-no-cache  # Rebuild (no cache) - for Dockerfile changes
./scripts/start_service.sh destroy        # Fresh start, keep database data
./scripts/start_service.sh teardown       # Clean slate - delete everything
make logs                                 # View logs
```

> 📖 **See [Setup Guide](./docs/setup.md) for details**

## Documentation

| Category              | Document                                             | Description                                          |
| --------------------- | ---------------------------------------------------- | ---------------------------------------------------- |
| **Getting Started**   | [📖 Setup Guide](./docs/setup.md)                    | Complete installation and configuration instructions |
|                       | [🏗️ Architecture](./docs/architecture.md)            | System design and component overview                 |
| **Frontend**          | [🎨 Frontend Guide](./docs/frontend.md)              | React UI development and setup                       |
|                       | [📋 UI Quick Start](./ui/README.md)                  | Component reference and examples                     |
|                       | [⚙️ UI Config System](./ui/environments/README.md)   | Environment configuration for UI                     |
| **Core Concepts**     | [🤖 Agents Catalogue](./docs/agents_catalogue/)      | AI agent development and registry                    |
|                       | [📝 Testing Guide](./docs/testing.md)                | Testing strategies and best practices                |
|                       | [🔧 Worker Guide](./docs/worker.md)                  | Background task processing                           |
| **Infrastructure**    | [🔐 GitHub Auth](./docs/github_authentication.md)    | Authentication and token management                  |
|                       | [🔑 Secrets Management](./docs/secret_management.md) | Secure credential handling                           |
|                       | [🌍 Environments](./docs/environments.md)            | Environment configuration                            |
| **Advanced**          | [📊 Logging System](./docs/logging_system.md)        | Observability and debugging                          |
|                       | [🔄 Migration APIs](./docs/db_migration_apis.md)     | Database migration automation                        |
|                       | [📡 Telemetry](./docs/telemetry.md)                  | Metrics and monitoring                               |
| **All Documentation** | [📚 View All Docs](./docs/README.md)                 | Complete documentation index                         |

## Technology Stack

**Backend**: Python, FastAPI, SQLAlchemy, LangGraph
**Frontend**: React, TypeScript, Vite, Tailwind CSS
**Infrastructure**: MySQL, AWS SQS, Redis, Docker

## Contributing

See **[Contributing Guide](./CONTRIBUTING.md)** for development workflow and guidelines.

## License

Copyright © Razorpay
