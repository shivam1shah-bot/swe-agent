# MCP Servers Reference

## Overview
Model Context Protocol (MCP) servers extend Claude Code's capabilities by providing standardized interfaces to external tools and services. This document lists available MCP servers and their usage in SWE Agent.

## Installed MCP Servers

### GitHub MCP Server
**Package**: `@modelcontextprotocol/server-github`
**Purpose**: GitHub operations (repos, PRs, issues, branches)

**Configuration**:
```json
{
  "github": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-github"],
    "env": {
      "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"
    }
  }
}
```

**Capabilities**:
- Create and manage repositories
- Create pull requests and issues
- Search code and files
- Manage branches and commits
- Access repository metadata

**Usage Example**:
```bash
# With Claude Code
claude "Create a PR for the authentication feature"
```

### Filesystem MCP Server
**Package**: `@modelcontextprotocol/server-filesystem`
**Purpose**: Secure file system access

**Configuration**:
```json
{
  "filesystem": {
    "command": "npx",
    "args": [
      "-y",
      "@modelcontextprotocol/server-filesystem",
      "/workspace",
      "/tmp/swe-agent"
    ]
  }
}
```

**Capabilities**:
- Read file contents
- Write files
- List directories
- Search files
- Get file metadata

**Security**: Only paths specified in args are accessible

### Memory MCP Server
**Package**: `@modelcontextprotocol/server-memory`
**Purpose**: Persistent memory across sessions

**Configuration**:
```json
{
  "memory": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-memory"]
  }
}
```

**Capabilities**:
- Store key-value pairs
- Retrieve stored information
- Search memory
- Context persistence across sessions

## Available MCP Servers (Not Yet Installed)

### PostgreSQL MCP Server
**Package**: `@modelcontextprotocol/server-postgres`
**Purpose**: Database queries and schema analysis

**Configuration**:
```json
{
  "postgres": {
    "command": "npx",
    "args": [
      "-y",
      "@modelcontextprotocol/server-postgres",
      "postgresql://user:password@localhost:5432/dbname"
    ]
  }
}
```

### Slack MCP Server
**Package**: `@modelcontextprotocol/server-slack`
**Purpose**: Slack messaging and notifications

**Configuration**:
```json
{
  "slack": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-slack"],
    "env": {
      "SLACK_BOT_TOKEN": "${SLACK_BOT_TOKEN}",
      "SLACK_TEAM_ID": "${SLACK_TEAM_ID}"
    }
  }
}
```

### Brave Search MCP Server
**Package**: `@modelcontextprotocol/server-brave-search`
**Purpose**: Web search capabilities

**Configuration**:
```json
{
  "brave-search": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-brave-search"],
    "env": {
      "BRAVE_API_KEY": "${BRAVE_API_KEY}"
    }
  }
}
```

## Configuration Management

### Main Configuration File
**Location**: `src/providers/mcp/mcp-servers.json`

### Dynamic Configuration
```python
from src.services.mcp_configuration_service import MCPConfigurationService

# Get configuration for task
mcp_service = MCPConfigurationService(config)
mcp_config_path = await mcp_service.get_config_for_agent(
    task_type=TaskType.FEATURE_IMPLEMENTATION,
    workspace_path="/path/to/repo"
)
```

## Testing MCP Servers

### Test Server Manually
```bash
# Test GitHub server
npx -y @modelcontextprotocol/server-github

# Test filesystem server
npx -y @modelcontextprotocol/server-filesystem /tmp
```

### Health Check
```python
from src.providers.mcp.health_checker import MCPHealthChecker

checker = MCPHealthChecker()
results = await checker.check_all_servers("src/providers/mcp/mcp-servers.json")

for server, status in results.items():
    print(f"{server}: {status['status']}")
```

## Environment Variables Required

```bash
# GitHub
export GITHUB_TOKEN=ghp_your_token

# Slack (if using)
export SLACK_BOT_TOKEN=xoxb-your-token
export SLACK_TEAM_ID=T1234567890

# Brave Search (if using)
export BRAVE_API_KEY=your_api_key

# Database (if using)
export DATABASE_URL=postgresql://user:pass@localhost:5432/db
```

## Best Practices

1. **Minimal Permissions**: Only grant necessary access to each server
2. **Path Restrictions**: Limit filesystem server to specific paths
3. **Environment Variables**: Use env vars for secrets, never hardcode
4. **Health Checks**: Regularly verify MCP servers are operational
5. **Error Handling**: Handle MCP server failures gracefully

## Troubleshooting

### Server Won't Start
```bash
# Check if command exists
which npx

# Test server manually
npx -y @modelcontextprotocol/server-github

# Check environment variables
echo $GITHUB_TOKEN
```

### Permission Denied
```bash
# For filesystem server
# Verify paths exist and are accessible
ls -la /workspace
chmod 755 /workspace
```

### Authentication Failures
```bash
# Verify tokens are set
echo $GITHUB_TOKEN
echo $SLACK_BOT_TOKEN

# Test token validity
gh auth status  # For GitHub
```

## Creating Custom MCP Servers

### Basic Structure
```python
from mcp.server import MCPServer, MCPTool

class CustomServer(MCPServer):
    def __init__(self):
        super().__init__("custom-server")

    @MCPTool(
        name="custom_operation",
        description="Perform custom operation"
    )
    async def custom_operation(self, param: str) -> dict:
        # Implementation
        return {"result": "success"}

if __name__ == "__main__":
    server = CustomServer()
    server.run()
```

### Registration
```json
{
  "custom-server": {
    "command": "python",
    "args": ["/path/to/custom_server.py"],
    "env": {
      "CUSTOM_VAR": "${CUSTOM_VAR}"
    }
  }
}
```

## Reference
- MCP Protocol: https://modelcontextprotocol.io
- MCP Servers Registry: https://github.com/modelcontextprotocol/servers
- SWE Agent MCP Integration: `.claude/skills/mcp-integration/Skill.md`
- Configuration Service: `src/services/mcp_configuration_service.py`
