# Tools

This directory defines external tools and integrations available to Claude.

## Purpose
Document external tools, APIs, and integrations that Claude can use to accomplish tasks.

## Available Tools

### Development Tools
- **gh CLI**: GitHub operations (repos, PRs, issues)
- **Docker**: Container management
- **make**: Build automation and task runner

### Testing Tools
- **pytest**: Test framework
- **pytest-cov**: Coverage reporting
- **pytest-xdist**: Parallel test execution

### Database Tools
- **SQLAlchemy**: ORM and database operations
- **Migration Scripts**: Schema management

### AI Tools
- **Claude Code CLI**: Primary AI agent interface
- **MCP Protocol**: Model Context Protocol for extending capabilities

### Monitoring Tools
- **Logs**: `tmp/logs/` directory
- **Health Checks**: `make status`
- **Service Status**: Docker compose status

## Tool Configuration
Each tool may have specific configuration requirements documented in the root CLAUDE.md or environment files.

## Usage Guidelines
- Always use gh CLI for GitHub operations
- Prefer make commands for common tasks
- Use async operations for database queries
- Check logs for debugging information
