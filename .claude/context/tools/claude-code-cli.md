# Claude Code CLI Tool

## Overview
Claude Code is the primary AI agent tool used by SWE Agent for autonomous code development tasks. It provides a command-line interface to Claude AI with extended capabilities through MCP (Model Context Protocol) servers.

## Installation
```bash
# Install Claude Code CLI (macOS/Linux)
curl -fsSL https://claude.ai/install.sh | sh

# Verify installation
claude --version
```

## Basic Usage

### Interactive Mode
```bash
# Start interactive session
claude

# In specific directory
claude --directory /path/to/project
```

### Command Mode
```bash
# Execute single command
claude "implement user authentication"

# With specific file context
claude --file src/api/routes.py "add authentication middleware"
```

## MCP Integration

### Configuration
Claude Code uses MCP servers configured in `mcp-servers.json`:

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"
      }
    }
  }
}
```

### Using with MCP Servers
```bash
# Specify MCP configuration
claude --mcp-config /path/to/mcp-servers.json "create PR for feature"
```

## SWE Agent Integration

### In Python Code
```python
from src.agents.terminal_agents.claude_code import ClaudeCodeTool

# Get singleton instance
claude_code = await ClaudeCodeTool.get_instance(config=agent_config)

# Execute command
result = await claude_code.execute_command(
    command="implement feature X",
    workspace_path="/path/to/repo",
    mcp_config="/path/to/mcp-servers.json"
)

# Stream output
async for output in result.stream():
    print(output)
```

### Streaming Output
```python
# With callback
async def on_output(output: str):
    logger.info(f"Agent: {output}")

result = await claude_code.execute_command(
    command="analyze codebase",
    stream_callback=on_output
)
```

## Best Practices

1. **Always specify workspace path** for file operations
2. **Use MCP servers** for extended capabilities (GitHub, filesystem, etc.)
3. **Implement streaming** for long-running operations
4. **Handle timeouts** appropriately
5. **Clean up resources** after execution

## Common Commands

```bash
# Implement feature
claude "implement user authentication with JWT"

# Fix bug
claude "fix null pointer exception in TaskProcessor"

# Refactor code
claude "refactor authentication service to use dependency injection"

# Write tests
claude "add integration tests for task execution workflow"

# Generate documentation
claude "document the agent orchestration system"
```

## Troubleshooting

### Claude Code not found
```bash
# Check installation
which claude

# Reinstall if needed
curl -fsSL https://claude.ai/install.sh | sh
```

### MCP server connection issues
```bash
# Validate MCP configuration
cat /path/to/mcp-servers.json | jq

# Test MCP server manually
npx -y @modelcontextprotocol/server-github
```

### Streaming timeouts
```python
# Increase timeout
result = await claude_code.execute_command(
    command="complex task",
    timeout=600  # 10 minutes
)
```

## Reference
- Location in SWE Agent: `src/agents/terminal_agents/claude_code.py`
- MCP configuration: `src/providers/mcp/mcp-servers.json`
- Documentation: https://claude.ai/code
