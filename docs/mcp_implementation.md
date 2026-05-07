# MCP (Model Context Protocol) Implementation

## Overview

SWE Agent implements a **Model Context Protocol (MCP) server** that exposes AI-powered software engineering capabilities through a standardized protocol. This implementation enables AI agents and models to interact with SWE Agent's functionality through structured tools and streaming capabilities.

## Architecture

### Core Components

```
src/mcp_server/
├── server/          # HTTP server and protocol handling
├── tools/           # MCP tools organized by domain
├── schemas/         # Protocol schemas and OpenAPI specs
└── config/          # Configuration management
```

### Key Classes

- **`MCPHttpServer`** - Main HTTP server using Streamable HTTP transport
- **`MCPRequestHandler`** - JSON-RPC request processing and routing
- **`MCPToolRegistry`** - Centralized tool registration and management
- **`MCPSessionManager`** - Session lifecycle and tracking
- **`MCPStreamManager`** - Server-Sent Events stream management

## Transport Protocol

### Streamable HTTP Transport

The implementation uses **Streamable HTTP** as the transport layer:

- **POST `/mcp`** - JSON-RPC 2.0 request/response messages
- **GET `/mcp/stream/{stream_id}`** - Server-Sent Events for streaming
- **Session management** via `Mcp-Session-Id` header
- **Event resumability** with `Last-Event-ID` header

### JSON-RPC 2.0 Methods

| Method       | Description                                     |
| ------------ | ----------------------------------------------- |
| `initialize` | Initialize MCP session with server capabilities |
| `tools/list` | List all available MCP tools                    |
| `tools/call` | Execute a specific MCP tool                     |
| `ping`       | Health check and connectivity test              |

## Available Tools

Tools are organized by functional domains:

### Health Domain

- **`overall_health`** - System-wide health status

### Tasks Domain

- **`get_task`** - Retrieve task details and status
- **`list_tasks`** - List tasks with filtering options
- **`get_task_execution_logs`** - Retrieve task execution logs

### Agents Catalogue Domain

- **`get_agents_catalogue_config`** - Retrieve catalogue configuration
- **`get_agents_catalogue_items`** - List available catalogue items
- **`list_agents_catalogue_services`** - List available services

## API Endpoints

| Endpoint                  | Method | Description                      |
| ------------------------- | ------ | -------------------------------- |
| `/mcp`                    | POST   | JSON-RPC message handling        |
| `/mcp/stream/{stream_id}` | GET    | Server-Sent Events streaming     |
| `/mcp/health`             | GET    | Server health check              |
| `/mcp/info`               | GET    | Server capabilities and metadata |
| `/mcp/tools`              | GET    | List all available tools         |

## Configuration

### Server Configuration

```python
{
  "name": "swe-agent-mcp-server",
  "version": "1.0.0",
  "protocol_version": "2025-03-26",
  "transport": "streamable_http"
}
```

## Client Integration

### MCP Client Configuration

#### Local Development

```json
{
  "swe-agent": {
    "name": "SWE Agent",
    "type": "streamable-http",
    "url": "http://localhost:28003/mcp",
    "streamable": true
  }
}
```

#### Stage Environment

```json
{
  "swe-agent": {
    "name": "SWE Agent",
    "type": "streamable-http",
    "url": "https://swe-agent-mcp.concierge.stage.razorpay.in/mcp",
    "streamable": true
  }
}
```

### Example Usage

#### Direct HTTP API Usage

```bash
# Check server health
curl http://localhost:28003/mcp/health

# Get server info and capabilities
curl http://localhost:28003/mcp/info

# List all available tools
curl http://localhost:28003/mcp/tools

# Execute a tool (JSON-RPC format)
curl -X POST \
  -H "Content-Type: application/json" \
  http://localhost:28003/mcp \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "overall_health",
      "arguments": {}
    },
    "id": 1
  }'
```

#### JavaScript/Node.js Client Usage

```javascript
// Initialize MCP client
const client = new MCPClient("http://localhost:28003/mcp");

// Initialize session
const session = await client.request({
  jsonrpc: "2.0",
  method: "initialize",
  params: {
    protocolVersion: "2025-03-26",
    capabilities: { tools: true },
  },
  id: 1,
});

// List available tools
const tools = await client.request({
  jsonrpc: "2.0",
  method: "tools/list",
  id: 2,
});

// Execute a tool
const result = await client.request({
  jsonrpc: "2.0",
  method: "tools/call",
  params: {
    name: "get_task",
    arguments: {
      task_id: "task-123",
    },
  },
  id: 3,
});
```

## Development

### Adding New Tools

1. **Create tool class** extending `BaseMCPTool`
2. **Implement required methods** (`name`, `description`, `input_schema`, `execute`)
3. **Register in tool registry** within appropriate domain
4. **Add comprehensive tests** for tool functionality

### Testing

- **Unit tests** - `tests/unit/test_mcp/`
- **Integration tests** - `tests/integration/test_mcp_integration.py`

## Deployment

### Local Development

```bash
# Start SWE Agent with MCP server
make build && make restart

# MCP server will be available at:
# http://localhost:28003/mcp
```

### Production Deployment

The MCP server is automatically included in the SWE Agent deployment and inherits all configurations from the main application.

## Standards Compliance

- **MCP Protocol Version**: 2025-03-26
- **Transport**: Streamable HTTP
- **Message Format**: JSON-RPC 2.0
- **Streaming**: Server-Sent Events (SSE)
