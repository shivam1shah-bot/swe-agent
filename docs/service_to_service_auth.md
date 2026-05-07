# Service-to-Service Authentication

This document describes the authentication patterns used for service-to-service communication in SWE Agent, specifically for the MCP server and DevOps automation integrations.

## Overview

SWE Agent uses **HTTP Basic Authentication** for machine-to-machine communication. This pattern is used when:

- The **MCP Server** (port 8003) calls the **API Service** (port 8002)
- **DevOps automation tools** interact with the API
- **External services** (like Splitz) need authenticated access

## Service Account Types

| Account | Purpose | Access Level |
|---------|---------|--------------|
| `mcp_read_user` | MCP Server → API communication | Read-only |
| `devops` | DevOps automation, CI/CD pipelines | Read + Agent execution |
| `splitz` | Splitz service integration | Service-specific |
| `admin` | Administrative automation | Full access |

## Authentication Flow

```
┌─────────────┐         Basic Auth           ┌─────────────┐
│   Service   │  ───── username:password ────> │  API Server │
│   (Client)  │         Authorization:         │  (Port 8002)│
│             │         Basic base64(...)     │             │
└─────────────┘                                └──────┬──────┘
                                                      │
                                                      ▼
                                              ┌─────────────┐
                                              │  BasicAuth   │
                                              │  Middleware  │
                                              └──────┬──────┘
                                                      │
                                                      ▼
                                              ┌─────────────┐
                                              │   RBAC      │
                                              │  Role Check  │
                                              └─────────────┘
```

## 1. MCP Server Authentication (`mcp_read_user`)

### Pattern

The MCP Server acts as a client to the main API service. It uses a dedicated service account with read-only access.

**Configuration** (`src/mcp_server/config/settings.py`):

```python
class MCPSettings:
    @property
    def auth_username(self) -> str:
        """Service account identity - hardcoded."""
        return "mcp_read_user"

    @property
    def auth_password(self) -> str:
        """Password loaded from environment configuration."""
        auth_config = self.config.get("auth", {})
        users = auth_config.get("users", {})
        return users.get("mcp_read_user", "")
```

**API Client** (`src/mcp_server/clients/api_client.py`):

```python
class SWEAgentAPIClient:
    def __init__(self, settings: Optional[MCPSettings] = None):
        self.settings = settings or get_mcp_settings()
        
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "SWE-Agent-MCP/1.0.0",
        }
        
        # Add Basic Auth header
        if self.settings.auth_enabled and self.settings.auth_password:
            credentials = f"{self.settings.auth_username}:{self.settings.auth_password}"
            encoded = base64.b64encode(credentials.encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"
```

### Access Rights

`mcp_read_user` can access these endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/health` | GET | Health checks |
| `/api/v1/tasks` | GET | List tasks |
| `/api/v1/tasks/{id}` | GET | Get task details |
| `/api/v1/tasks/{id}/logs` | GET | Get task logs |
| `/api/v1/agents-catalogue/*` | GET | Agents catalogue |

### RBAC Protection

```python
# src/mcp_server/security/rbac_validator.py
def _get_tool_permissions(self) -> Dict[str, List[str]]:
    return {
        "overall_health": ["mcp_read_user", "admin"],
        "get_task": ["mcp_read_user", "admin"],
        "list_tasks": ["mcp_read_user", "admin"],
        "get_task_execution_logs": ["mcp_read_user", "admin"],
        # ...
    }
```

## 2. DevOps Automation Authentication (`devops`)

### Purpose

The `devops` service account is used for:
- CI/CD pipeline integrations
- Infrastructure automation
- Deployment scripts
- Monitoring tools

### Access Rights

`devops` has broader access than `mcp_read_user`:

| Endpoint | Method | Access |
|----------|--------|--------|
| `/api/v1/tasks/stats` | GET | ✅ Yes |
| `/api/v1/tasks/users` | GET | ✅ Yes |
| `/api/v1/tasks/{id}` | GET | ✅ Yes |
| `/api/v1/tasks` | GET | ✅ Yes |
| `/api/v1/agents/run` | POST | ✅ Yes |
| `/api/v1/agents/batch` | POST | ✅ Yes |
| `/api/v1/agents/multi-repo` | POST | ✅ Yes |
| `/api/v1/tasks` | POST | ❌ No (admin only) |
| `/api/v1/tasks/batch` | POST | ❌ No (admin only) |

### Route Protection Example

```python
# src/api/routers/agents.py
@router.post("/run")
@require_role(["dashboard", "admin", "splitz", "devops"])
async def run_agent(...):
    """Execute autonomous agent - accessible to devops."""
    ...

# src/api/routers/tasks.py
@router.get("/stats")
@require_role(["dashboard", "admin", "devops"])
async def get_task_statistics(...):
    """Get task statistics - accessible to devops."""
    ...
```

## 3. Role Resolution

The system uses a **username-as-role convention**:

```python
# src/providers/auth/rbac.py AND basic_auth.py
def get_user_role(self, username: str) -> str:
    """Role name matches username by convention.
    
    Examples:
        "devops" → "devops"
        "mcp_read_user" → "mcp_read_user"
        "admin" → "admin"
    """
    return username
```

### Role Checker Usage

```python
from src.providers.auth.rbac import require_role, AdminRole, DashboardOrAdminRole

# Require specific roles
@require_role(["dashboard", "admin", "devops"])
async def my_endpoint(request: Request):
    ...

# Use predefined dependencies
@router.get("/admin-only")
async def admin_endpoint(user_role: str = AdminRole):
    ...
```

## 4. Credential Management

### Local Development

In local development, credentials are defined in TOML configuration files:

```toml
# environments/env.default.toml
[auth]
enabled = true

[auth.users]
dashboard = "dashboard123"      # Human users (SSO required)
admin = "admin123"             # Admin access
mcp_read_user = "mcp123"       # MCP service account
devops = "devops123"           # DevOps automation
splitz = "splitz123"           # Splitz service
```

### Stage / Production

In production environments, credentials are **never** in TOML files. They are injected via environment variables.

#### Environment Variable Format

Use **double underscores** (`__`) to represent nested TOML structure:

```bash
# Format: SECTION__SUBSECTION__KEY=value
# Maps to: config['section']['subsection']['key'] = value

export AUTH__USERS__MCP_READ_USER="actual-secret-password"
export AUTH__USERS__DEVOPS="actual-secret-password"
export AUTH__USERS__ADMIN="actual-secret-password"
export AUTH__USERS__SPLITZ="actual-secret-password"
```

#### How It Works

**Config Loading Order** (`src/providers/config_loader/env_loader.py`):

1. Load `environments/env.default.toml`
2. Load `environments/env.{APP_ENV}.toml` (e.g., `env.stage.toml`)
3. Override with environment variables (double underscore format)

```python
class EnvConfigLoader:
    def update_from_env(self) -> None:
        """Update configuration from environment variables."""
        for env_key, env_value in os.environ.items():
            if '__' in env_key:
                # AUTH__USERS__MCP_READ_USER → ['auth', 'users', 'mcp_read_user']
                parts = env_key.lower().split('__')
                
                # Navigate to nested location in config
                current = self.config
                for part in parts[:-1]:
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                
                # Set the value (with type conversion)
                current[parts[-1]] = self._convert_value(env_value)
```

**Type Conversion**:
- `true`/`false` → Boolean
- `123` → Integer
- `1.5` → Float
- Everything else → String

### Example: Complete Flow

**Local Development**:
```toml
# env.default.toml
[auth.users]
mcp_read_user = "mcp123"
```

**Production (Environment Variables)**:
```bash
export AUTH__USERS__MCP_READ_USER="prod-secure-password-xyz789"
```

**Application Code**:
```python
config = get_config()
password = config.get("auth", {}).get("users", {}).get("mcp_read_user")
# Local: "mcp123"
# Prod:   "prod-secure-password-xyz789"
```

## 5. Security Considerations

### Authentication Middleware

The `BasicAuthMiddleware` (`src/api/middleware/basic_auth.py`) handles authentication:

```python
class BasicAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 1. Check if path is excluded (health, docs, etc.)
        if self._should_skip_auth(request):
            return await call_next(request)
        
        # 2. Try JWT Bearer token first (for human users)
        auth_header = request.headers.get("Authorization")
        if auth_header.startswith("Bearer "):
            payload = verify_token(token)
            # ... JWT handling ...
        
        # 3. Fallback to Basic Auth (for service accounts)
        user_info = self.auth_provider.validate_auth_header(auth_header)
        
        # 4. Block dashboard users from Basic Auth (SSO enforced)
        if user_info.get("username") == "dashboard":
            return self._create_sso_required_response()
        
        # 5. Set user info in request state for downstream RBAC
        request.state.current_user = user_info
        return await call_next(request)
```

### Key Security Points

| Consideration | Implementation |
|--------------|----------------|
| **Password Storage** | Never commit production passwords; use env vars |
| **SSO Enforcement** | `dashboard` users blocked from Basic Auth |
| **Role Separation** | Service accounts (`mcp_read_user`, `devops`) have limited access |
| **Constant-Time Comparison** | Uses `hmac.compare_digest()` to prevent timing attacks |
| **HTTPS Required** | Production must use TLS to protect credentials |

## 6. Testing

### Unit Tests

Dedicated test file for `devops` role:

```python
# tests/unit/test_providers/test_devops_role.py
@pytest.mark.unit
class TestDevopsBasicAuth:
    def test_devops_credentials_valid(self, provider):
        assert provider.validate_credentials("devops", "devops123") is True

    def test_devops_role_matches_username(self, provider):
        assert provider.get_user_role("devops") == "devops"

    def test_devops_allowed_on_agents_run(self, checker):
        allowed = ["dashboard", "admin", "splitz", "devops"]
        assert checker.check_role_access("devops", allowed) is True
```

### Mock Configuration in Tests

```python
MOCK_CONFIG = {
    "auth": {
        "enabled": True,
        "users": {
            "admin": "admin123",
            "dashboard": "dashboard123",
            "mcp_read_user": "mcp123",
            "splitz": "splitz123",
            "devops": "devops123",
        }
    }
}
```

## 7. Adding New Service Accounts

To add a new service account:

1. **Add to TOML** (for local dev):
   ```toml
   [auth.users]
   new_service = "local_dev_password"
   ```

2. **Add environment variable** (for prod):
   ```bash
   export AUTH__USERS__NEW_SERVICE="actual_secret"
   ```

3. **Update RBAC** (where needed):
   ```python
   @require_role(["dashboard", "admin", "new_service"])
   async def protected_endpoint(...):
       ...
   ```

4. **Add tests**:
   ```python
   def test_new_service_role(self, provider):
       assert provider.get_user_role("new_service") == "new_service"
   ```

## 8. Quick Reference

### Environment Variable Cheat Sheet

```bash
# Auth users
AUTH__USERS__MCP_READ_USER="..."
AUTH__USERS__DEVOPS="..."
AUTH__USERS__ADMIN="..."
AUTH__USERS__SPLITZ="..."

# Database
DATABASE__USER="..."
DATABASE__PASSWORD="..."

# GitHub
GITHUB__TOKEN="..."
GITHUB__RZP_SWE_AGENT_APP__PRIVATE_KEY="..."

# AWS
AWS__ACCESS_KEY_ID="..."
AWS__SECRET_ACCESS_KEY="..."
```

### Service Account Comparison

| Account | Read | Write Tasks | Run Agents | Admin Ops |
|---------|------|-------------|------------|-----------|
| `mcp_read_user` | ✅ | ❌ | ❌ | ❌ |
| `devops` | ✅ | ❌ | ✅ | ❌ |
| `splitz` | ✅ | ✅ | ✅ | ❌ |
| `admin` | ✅ | ✅ | ✅ | ✅ |

---

## Related Documentation

- [MCP Implementation](./mcp_implementation.md) - MCP server details
- [Architecture](./architecture.md) - Overall system architecture
- [Secret Management](./secret_management.md) - General secret handling
