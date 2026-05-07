---
name: mcp-server-integration
description: Model Context Protocol (MCP) server setup and integration
version: 1.0.0
tags: [mcp, integration, ai-context]
context: codebase
---

# MCP Server Integration

## Overview

SWE Agent implements Model Context Protocol (MCP) in two ways:
1. **MCP Client** - Consumes external MCP servers (Sequential Thinking, Memory, DevRev, Blade)
2. **MCP Server** - Exposes SWE Agent API as MCP tools for AI agents

**Purpose**: Extend AI agent capabilities with specialized tools and context

## Part 1: MCP Client Configuration

### MCP Servers Configuration (`src/providers/mcp/mcp-servers.json`)

**Active MCP Servers**:

1. **Sequential Thinking** - Enhanced reasoning capabilities
   ```json
   "sequentialthinking": {
     "command": "npx",
     "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"]
   }
   ```

2. **Memory** - Persistent memory across sessions
   ```json
   "memory": {
     "command": "npx",
     "args": ["-y", "@modelcontextprotocol/server-memory"]
   }
   ```

3. **Blade MCP** - Razorpay Blade Design System integration
   ```json
   "blade-mcp": {
     "command": "npx",
     "args": ["-y", "@razorpay/blade-mcp@latest"]
   }
   ```

4. **E2E Tests MCP** - End-to-end testing capabilities (remote)
   ```json
   "end-to-end-tests": {
     "command": "npx",
     "args": ["mcp-remote", "https://e2e-mcp-server.dev.razorpay.in/mcp"]
   }
   ```

5. **DevRev MCP** - DevRev platform integration (with auth)
   ```json
   "devrev-mcp": {
     "command": "npx",
     "args": [
       "mcp-remote",
       "https://api.devrev.ai/mcp/v1",
       "--header",
       "Authorization:${DEVREV_API_TOKEN}"
     ],
     "env": {
       "DEVREV_API_TOKEN": "${DEVREV_API_TOKEN}"
     }
   }
   ```

### Adding New MCP Server

**Local MCP Server**:
```json
{
  "mcpServers": {
    "your-server-name": {
      "command": "npx",
      "args": ["-y", "@your-org/mcp-server-package@latest"]
    }
  }
}
```

**Remote MCP Server**:
```json
{
  "mcpServers": {
    "your-remote-server": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "https://your-server.example.com/mcp"
      ]
    }
  }
}
```

**With Authentication**:
```json
{
  "mcpServers": {
    "authenticated-server": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "https://api.example.com/mcp",
        "--header",
        "Authorization:${YOUR_API_TOKEN}"
      ],
      "env": {
        "YOUR_API_TOKEN": "${YOUR_API_TOKEN}"
      }
    }
  }
}
```

**Environment Variables**:
- Set in shell: `export DEVREV_API_TOKEN=your-token`
- Or in `.env` file (loaded by Claude Code)
- Or in environment config: `environments/env.dev_docker.toml`

## Part 2: MCP Server Implementation

### Architecture (`src/mcp_server/`)

SWE Agent exposes its API as MCP tools that AI agents can use.

**Components**:
```
src/mcp_server/
├── app.py                    # FastAPI application
├── router.py                 # MCP protocol routes
├── config/
│   ├── settings.py           # MCP server configuration
│   └── transport_config.py   # Transport layer config
├── server/
│   ├── http_server.py        # HTTP/SSE transport
│   ├── request_handler.py    # MCP request handling
│   ├── session_manager.py    # Session lifecycle
│   └── stream_manager.py     # Streaming responses
├── security/
│   ├── input_sanitizer.py    # Input validation
│   ├── origin_validator.py   # CORS/origin checks
│   ├── rate_limiter.py       # Rate limiting
│   └── rbac_validator.py     # Role-based access
├── schemas/
│   ├── mcp_protocol.py       # MCP protocol schemas
│   ├── tool_definitions.py   # Tool schemas
│   └── enhanced_openapi.py   # OpenAPI generation
└── tools/
    ├── tasks/                # Task management tools
    ├── agents_catalogue/     # Agent catalog tools
    ├── health/               # Health check tools
    └── admin/                # Admin tools
```

### MCP Server Startup

**Standalone Server** (separate from main API):
```python
# src/mcp_server/app.py
app = create_mcp_app()

# Configuration
settings = get_mcp_settings()
# - host: 0.0.0.0
# - port: 28003 (different from main API)
# - api_base_url: http://localhost:28002
```

**Running**:
```bash
# Via Docker (included in docker-compose)
make start

# Standalone
python -m src.mcp_server.app
```

**Service URLs**:
- MCP Server: http://localhost:28003
- MCP Docs: http://localhost:28003/docs
- MCP Health: http://localhost:28003/health

### MCP Protocol Routes (`src/mcp_server/router.py`)

**Core Routes**:

1. **JSON-RPC Endpoint** (POST `/`):
   - Handles MCP protocol messages
   - Request/Response via JSON-RPC 2.0
   - Methods: `initialize`, `tools/list`, `tools/call`

2. **SSE Streaming** (GET `/sse`):
   - Server-Sent Events for real-time updates
   - Session-based streaming
   - Task progress updates

3. **Health Check** (GET `/health`):
   - MCP server health status
   - API connectivity check
   - Dependency status

### MCP Tools Registry (`src/mcp_server/tools/registry.py`)

**Registered Tools**:

**Task Management**:
- `get_task` - Get task details by ID
- `list_tasks` - List all tasks with filters
- `get_task_execution_logs` - Get task execution logs

**Agents Catalogue**:
- `list_agents_catalogue_services` - List available agent services
- `get_agents_catalogue_items` - Get catalog items
- `get_agents_catalogue_config` - Get service configuration

**Health**:
- `overall_health` - System health check

**Admin**:
- Admin tools (RBAC protected)

### Adding New MCP Tool

**Step 1: Create Tool** (`src/mcp_server/tools/your_category/your_tool.py`):
```python
from ..base_tool import BaseMCPTool
from src.mcp_server.schemas.tool_definitions import ToolDefinition, ToolParameter

class YourTool(BaseMCPTool):
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="your_tool_name",
            description="What your tool does",
            inputSchema={
                "type": "object",
                "properties": {
                    "param1": ToolParameter(
                        type="string",
                        description="Parameter description",
                        required=True
                    )
                }
            }
        )

    async def execute(self, arguments: dict) -> dict:
        # Tool implementation
        result = await your_service.do_something(arguments)
        return {"result": result}
```

**Step 2: Register Tool** (`src/mcp_server/tools/registry.py`):
```python
from .your_category.your_tool import YourTool

async def get_tool_registry():
    registry = ToolRegistry()

    # ... existing tools
    registry.register_tool(YourTool())

    return registry
```

**Step 3: Add Tests**:
```python
# tests/unit/mcp_server/tools/test_your_tool.py
async def test_your_tool():
    tool = YourTool()
    result = await tool.execute({"param1": "value"})
    assert result["success"] == True
```

## Security & Best Practices

### Input Validation (`src/mcp_server/security/input_sanitizer.py`)

**Always sanitize inputs**:
```python
from src.mcp_server.security.input_sanitizer import sanitize_input

# Sanitize before processing
sanitized = sanitize_input(user_input)
```

**Validation rules**:
- Remove SQL injection patterns
- Sanitize XSS attempts
- Validate file paths (no directory traversal)
- Check command injection patterns

### Rate Limiting (`src/mcp_server/security/rate_limiter.py`)

**Default limits**:
- 100 requests per minute per client
- 1000 requests per hour per client

**Override in config**:
```toml
[mcp_server]
rate_limit_per_minute = 200
rate_limit_per_hour = 2000
```

### RBAC Authorization (`src/mcp_server/security/rbac_validator.py`)

**Protected tools require roles**:
```python
@require_role("admin")
async def execute(self, arguments: dict) -> dict:
    # Only admin users can execute
    pass
```

**Available roles**:
- `user` - Basic access
- `developer` - Development tools
- `admin` - Administrative access

## Testing MCP Server

### Unit Tests
```bash
pytest tests/unit/mcp_server/
```

### Integration Tests
```bash
pytest tests/integration/test_mcp_server_integration.py
```

### Manual Testing

**Using Claude Code**:
1. Add SWE Agent MCP server to `mcp-servers.json`:
```json
{
  "mcpServers": {
    "swe-agent": {
      "command": "npx",
      "args": ["mcp-remote", "http://localhost:28003"]
    }
  }
}
```

2. Restart Claude Code
3. Use tools: "List my tasks using swe-agent"

**Using MCP Inspector**:
```bash
npx @modelcontextprotocol/inspector http://localhost:28003
```

## Monitoring & Debugging

**Logs**:
- MCP Server: `tmp/logs/mcp_server.log`
- Request logs: `tmp/logs/mcp_requests.log`

**Health Checks**:
```bash
# MCP server health
curl http://localhost:28003/health

# Full system health
curl http://localhost:28003/health/detailed
```

**Debugging**:
```bash
# View MCP server logs
make logs-mcp-server

# Test MCP protocol
curl -X POST http://localhost:28003/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
```

## Common Issues

**Issue**: MCP server not starting
**Cause**: Port 28003 already in use
**Fix**: Change port in `environments/env.dev_docker.toml`

**Issue**: "API connectivity failed"
**Cause**: Main API server not running
**Fix**: Start main API: `make start`

**Issue**: "Tool not found"
**Cause**: Tool not registered in registry
**Fix**: Check `src/mcp_server/tools/registry.py`

**Issue**: "Rate limit exceeded"
**Cause**: Too many requests
**Fix**: Wait 1 minute or increase rate limits in config

**Issue**: MCP client can't connect
**Cause**: CORS or network issue
**Fix**: Check CORS settings, ensure server accessible

## Key Files

- `src/providers/mcp/mcp-servers.json` - MCP client configuration
- `src/mcp_server/app.py` - MCP server application
- `src/mcp_server/router.py` - MCP protocol routes
- `src/mcp_server/tools/registry.py` - Tool registration
- `src/mcp_server/security/` - Security implementations
- `environments/env.dev_docker.toml` - MCP server config
