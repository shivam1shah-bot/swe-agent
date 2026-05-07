---
name: MCP Integration
description: Configure and integrate Model Context Protocol (MCP) servers to extend AI agent capabilities
version: 1.0.0
---

## Overview

The Model Context Protocol (MCP) extends AI agent capabilities by providing standardized interfaces to external tools, data sources, and services. This skill covers MCP server configuration, integration patterns, and best practices for the SWE Agent platform.

**When to Use This Skill:**
- Extending agent capabilities with external tools
- Integrating with GitHub, databases, filesystems, or custom services
- Providing agents with real-time data access
- Building custom MCP servers for specific needs
- Troubleshooting MCP server connections

## Core Concepts

### What is MCP?

MCP (Model Context Protocol) is a protocol that allows AI models to securely interact with:
- **File Systems**: Read/write files, navigate directories
- **Databases**: Query and modify database content
- **APIs**: Call external REST/GraphQL APIs
- **Version Control**: Interact with Git, GitHub, GitLab
- **Custom Tools**: Any tool exposed via MCP interface

### MCP Architecture

```
Claude Code CLI
    ↓
MCP Client (built into Claude Code)
    ↓
MCP Servers (configured in mcp-servers.json)
    ↓
External Systems (GitHub, DB, Filesystem, etc.)
```

## MCP Configuration

### Configuration File Location

**SWE Agent**: `src/providers/mcp/mcp-servers.json`

### Basic Configuration Structure

```json
{
  "mcpServers": {
    "server-name": {
      "command": "command-to-start-server",
      "args": ["--arg1", "value1"],
      "env": {
        "ENV_VAR": "value"
      }
    }
  }
}
```

## Common MCP Server Configurations

### GitHub MCP Server

Enables GitHub operations (PR creation, issue management, repository operations):

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-github"
      ],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"
      }
    }
  }
}
```

**Capabilities:**
- Create, update, and search repositories
- Manage issues and pull requests
- Create and manage branches
- Search code and files
- Access repository metadata

**Usage Example:**
```python
# Agent can now use GitHub operations
result = await claude_code.execute_command(
    command="Create a pull request for the authentication feature",
    mcp_config="path/to/mcp-servers.json"
)
```

### Filesystem MCP Server

Provides secure file system access:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/allowed/path/1",
        "/allowed/path/2"
      ]
    }
  }
}
```

**Capabilities:**
- Read file contents
- Write files
- List directories
- Search files
- Get file metadata

**Security Note**: Only paths specified in args are accessible

### Database MCP Server (PostgreSQL)

Enables database queries and operations:

```json
{
  "mcpServers": {
    "postgres": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-postgres",
        "postgresql://user:password@localhost:5432/dbname"
      ]
    }
  }
}
```

**Capabilities:**
- Execute SELECT queries
- Analyze schema
- Get table information
- View indexes and constraints

**Security Note**: Connection string should use environment variables

### Brave Search MCP Server

Provides web search capabilities:

```json
{
  "mcpServers": {
    "brave-search": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-brave-search"
      ],
      "env": {
        "BRAVE_API_KEY": "${BRAVE_API_KEY}"
      }
    }
  }
}
```

**Capabilities:**
- Web search
- Local search
- News search

### Slack MCP Server

Enables Slack integration:

```json
{
  "mcpServers": {
    "slack": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-slack"
      ],
      "env": {
        "SLACK_BOT_TOKEN": "${SLACK_BOT_TOKEN}",
        "SLACK_TEAM_ID": "${SLACK_TEAM_ID}"
      }
    }
  }
}
```

## Complete SWE Agent MCP Configuration

### Production Configuration

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-github"
      ],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"
      }
    },
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/workspace",
        "/tmp/swe-agent"
      ]
    },
    "memory": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-memory"
      ]
    }
  }
}
```

## Integration Patterns

### Pattern 1: Dynamic MCP Configuration

Generate MCP configuration based on task requirements:

```python
class MCPConfigurationBuilder:
    """Build MCP configuration dynamically based on task needs"""

    def __init__(self, base_config_path: str):
        self.base_config = self._load_base_config(base_config_path)

    def build_for_task(self, task: Task) -> str:
        """Build MCP config for specific task"""
        config = self.base_config.copy()

        # Add GitHub if task involves PRs
        if task.metadata.get("create_pr"):
            config["mcpServers"]["github"] = self._github_config(
                token=os.getenv("GITHUB_TOKEN")
            )

        # Add filesystem for workspace access
        config["mcpServers"]["filesystem"] = self._filesystem_config(
            allowed_paths=[task.workspace_path, "/tmp"]
        )

        # Add database if task involves data operations
        if task.metadata.get("database_operations"):
            config["mcpServers"]["database"] = self._database_config(
                connection_string=os.getenv("DATABASE_URL")
            )

        # Write config to temp file
        config_path = f"/tmp/mcp-config-{task.id}.json"
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)

        return config_path

    def _github_config(self, token: str) -> dict:
        return {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": token}
        }

    def _filesystem_config(self, allowed_paths: List[str]) -> dict:
        return {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem"] + allowed_paths
        }

    def _database_config(self, connection_string: str) -> dict:
        return {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-postgres", connection_string]
        }
```

### Pattern 2: MCP Configuration Service

Service layer for managing MCP configurations:

```python
from src.providers.config_loader.env_loader import EnvironmentConfig

class MCPConfigurationService(BaseService):
    """Manage MCP server configurations"""

    def __init__(self, config: EnvironmentConfig):
        self.config = config
        self.mcp_base_path = "src/providers/mcp/mcp-servers.json"

    async def get_config_for_agent(
        self,
        task_type: TaskType,
        workspace_path: str
    ) -> str:
        """Get MCP configuration for specific agent task"""

        # Load base configuration
        base_config = await self._load_base_config()

        # Customize based on task type
        if task_type == TaskType.FEATURE_IMPLEMENTATION:
            config = self._add_development_servers(base_config, workspace_path)
        elif task_type == TaskType.BUG_FIX:
            config = self._add_debugging_servers(base_config, workspace_path)
        elif task_type == TaskType.DOCUMENTATION:
            config = self._add_documentation_servers(base_config, workspace_path)
        else:
            config = base_config

        # Inject environment variables
        config = self._inject_env_vars(config)

        # Validate configuration
        await self._validate_config(config)

        # Save to temp location
        return await self._save_config(config, task_type)

    def _add_development_servers(
        self,
        config: dict,
        workspace_path: str
    ) -> dict:
        """Add servers needed for development tasks"""
        config["mcpServers"].update({
            "github": self._github_server_config(),
            "filesystem": self._filesystem_server_config([workspace_path]),
            "memory": self._memory_server_config()
        })
        return config

    def _add_debugging_servers(
        self,
        config: dict,
        workspace_path: str
    ) -> dict:
        """Add servers needed for debugging"""
        config["mcpServers"].update({
            "filesystem": self._filesystem_server_config([
                workspace_path,
                f"{workspace_path}/tmp/logs"
            ]),
            "github": self._github_server_config()
        })
        return config

    async def _validate_config(self, config: dict):
        """Validate MCP configuration"""
        required_fields = ["mcpServers"]

        for field in required_fields:
            if field not in config:
                raise ConfigurationError(f"Missing required field: {field}")

        for server_name, server_config in config["mcpServers"].items():
            if "command" not in server_config:
                raise ConfigurationError(
                    f"Server {server_name} missing 'command' field"
                )

    def _inject_env_vars(self, config: dict) -> dict:
        """Replace environment variable placeholders"""
        config_str = json.dumps(config)

        # Replace ${VAR_NAME} with actual values
        import re
        def replace_env_var(match):
            var_name = match.group(1)
            value = os.getenv(var_name)
            if value is None:
                raise ConfigurationError(f"Environment variable {var_name} not set")
            return value

        config_str = re.sub(r'\$\{([^}]+)\}', replace_env_var, config_str)

        return json.loads(config_str)
```

### Pattern 3: Claude Code with MCP Integration

```python
from src.agents.terminal_agents.claude_code import ClaudeCodeTool

class AgentWithMCP:
    """Execute agent tasks with MCP-enabled capabilities"""

    def __init__(self):
        self.claude_code = None
        self.mcp_config_service = MCPConfigurationService(config)

    async def execute_task_with_mcp(self, task: Task) -> TaskResult:
        """Execute task with appropriate MCP servers"""

        # Get MCP configuration for this task
        mcp_config_path = await self.mcp_config_service.get_config_for_agent(
            task_type=task.type,
            workspace_path=task.workspace_path
        )

        # Initialize Claude Code with MCP config
        self.claude_code = await ClaudeCodeTool.get_instance(
            config=agent_config,
            mcp_config_path=mcp_config_path
        )

        try:
            # Execute task with MCP capabilities
            result = await self.claude_code.execute_command(
                command=task.description,
                workspace_path=task.workspace_path
            )

            return result

        finally:
            # Cleanup temp MCP config
            if os.path.exists(mcp_config_path):
                os.remove(mcp_config_path)
```

## Custom MCP Server Development

### Building a Custom MCP Server

```python
# custom_mcp_server.py
from mcp.server import MCPServer, MCPTool

class CustomToolServer(MCPServer):
    """Custom MCP server for SWE Agent specific tools"""

    def __init__(self):
        super().__init__("custom-swe-tools")

    @MCPTool(
        name="analyze_codebase",
        description="Analyze codebase structure and patterns"
    )
    async def analyze_codebase(self, path: str) -> dict:
        """Analyze codebase at given path"""
        # Implementation
        return {
            "files_count": 150,
            "languages": ["python", "typescript"],
            "architecture": "layered"
        }

    @MCPTool(
        name="check_test_coverage",
        description="Check test coverage for codebase"
    )
    async def check_test_coverage(self, path: str) -> dict:
        """Check test coverage"""
        # Run coverage analysis
        return {
            "coverage_percentage": 85,
            "uncovered_files": ["src/utils/helpers.py"]
        }

# Run server
if __name__ == "__main__":
    server = CustomToolServer()
    server.run()
```

### Register Custom MCP Server

```json
{
  "mcpServers": {
    "custom-swe-tools": {
      "command": "python",
      "args": [
        "/path/to/custom_mcp_server.py"
      ],
      "env": {
        "PYTHONPATH": "/path/to/src"
      }
    }
  }
}
```

## Troubleshooting MCP Servers

### Common Issues

#### 1. Server Not Starting

**Symptoms**: Agent reports MCP server unavailable

**Solutions**:
```python
async def diagnose_mcp_server(server_name: str, config: dict):
    """Diagnose MCP server issues"""

    server_config = config["mcpServers"].get(server_name)

    if not server_config:
        return f"Server {server_name} not found in configuration"

    # Check command exists
    command = server_config["command"]
    if not shutil.which(command):
        return f"Command '{command}' not found in PATH"

    # Check environment variables
    for env_var in server_config.get("env", {}).values():
        if env_var.startswith("${") and env_var.endswith("}"):
            var_name = env_var[2:-1]
            if not os.getenv(var_name):
                return f"Environment variable {var_name} not set"

    return "Configuration appears valid"
```

#### 2. Permission Errors

**Symptoms**: "Permission denied" errors when accessing resources

**Solution**: Ensure filesystem server has correct paths configured

```json
{
  "filesystem": {
    "command": "npx",
    "args": [
      "-y",
      "@modelcontextprotocol/server-filesystem",
      "/workspace",          // Ensure this path is accessible
      "/tmp/swe-agent"       // Ensure this path exists and is writable
    ]
  }
}
```

#### 3. Authentication Failures

**Symptoms**: "Unauthorized" or "Invalid token" errors

**Solution**: Verify environment variables are correctly set

```python
def validate_mcp_auth():
    """Validate MCP authentication credentials"""
    required_tokens = {
        "GITHUB_TOKEN": "GitHub Personal Access Token",
        "SLACK_BOT_TOKEN": "Slack Bot Token",
        "BRAVE_API_KEY": "Brave Search API Key"
    }

    missing = []
    for var, description in required_tokens.items():
        if not os.getenv(var):
            missing.append(f"{var} ({description})")

    if missing:
        raise ConfigurationError(
            f"Missing required environment variables: {', '.join(missing)}"
        )
```

## Security Best Practices

### 1. Environment Variable Management

```python
# ❌ Bad: Hardcoded secrets
config = {
    "env": {
        "GITHUB_TOKEN": "ghp_actual_token_here"
    }
}

# ✅ Good: Use environment variables
config = {
    "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
    }
}
```

### 2. Filesystem Access Restrictions

```python
# ❌ Bad: Unrestricted access
{
    "filesystem": {
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/"]
    }
}

# ✅ Good: Restrict to specific paths
{
    "filesystem": {
        "args": [
            "-y",
            "@modelcontextprotocol/server-filesystem",
            "/workspace/specific-project",
            "/tmp/swe-agent"
        ]
    }
}
```

### 3. Database Access Control

```python
# ✅ Use read-only database connections for analysis tasks
def get_database_connection_string(task_type: TaskType) -> str:
    if task_type in [TaskType.ANALYSIS, TaskType.DOCUMENTATION]:
        # Read-only user
        return os.getenv("DATABASE_URL_READONLY")
    else:
        # Full access user
        return os.getenv("DATABASE_URL")
```

## MCP Server Health Checks

```python
class MCPHealthChecker:
    """Check health of MCP servers"""

    async def check_all_servers(self, config_path: str) -> dict:
        """Check health of all configured MCP servers"""

        with open(config_path) as f:
            config = json.load(f)

        results = {}
        for server_name, server_config in config["mcpServers"].items():
            results[server_name] = await self.check_server(
                server_name,
                server_config
            )

        return results

    async def check_server(
        self,
        server_name: str,
        server_config: dict
    ) -> dict:
        """Check health of individual MCP server"""

        try:
            # Check command is available
            command = server_config["command"]
            if not shutil.which(command):
                return {
                    "status": "unhealthy",
                    "reason": f"Command '{command}' not found"
                }

            # Attempt to start server (with timeout)
            proc = await asyncio.create_subprocess_exec(
                command,
                *server_config.get("args", []),
                env={**os.environ, **server_config.get("env", {})},
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Wait briefly for startup
            try:
                await asyncio.wait_for(proc.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                # Server is still running, which is good
                proc.terminate()
                await proc.wait()
                return {"status": "healthy"}

            # Server exited immediately, check output
            stdout, stderr = await proc.communicate()
            return {
                "status": "unhealthy",
                "reason": f"Server exited: {stderr.decode()}"
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "reason": str(e)
            }
```

## Integration with Worker

```python
# In src/worker/tasks.py
class TaskProcessor:
    async def process_task_with_mcp(self, task: Task):
        """Process task with MCP capabilities"""

        # Build MCP configuration
        mcp_config_path = await self.mcp_service.get_config_for_agent(
            task_type=task.type,
            workspace_path=task.workspace_path
        )

        # Health check MCP servers
        health_results = await self.mcp_health_checker.check_all_servers(
            mcp_config_path
        )

        unhealthy = [
            name for name, result in health_results.items()
            if result["status"] != "healthy"
        ]

        if unhealthy:
            raise MCPServerError(
                f"Unhealthy MCP servers: {', '.join(unhealthy)}"
            )

        # Execute task with MCP
        result = await self.agent_with_mcp.execute_task_with_mcp(task)

        return result
```

## Reference

- MCP Documentation: https://modelcontextprotocol.io
- MCP Server Registry: https://github.com/modelcontextprotocol/servers
- SWE Agent MCP Config: `src/providers/mcp/mcp-servers.json`
- Claude Code MCP Integration: `src/agents/terminal_agents/claude_code.py`
