# GitHub Authentication System

Multi-pod GitHub authentication system with automatic token type detection, background refresh, and comprehensive monitoring.

## Architecture

### Multi-Pod Design

- **API Pods**: Consume tokens from Redis cache + background CLI sync
- **Worker Pods**: Generate and refresh tokens + background CLI sync
- **Redis Cache**: Central token storage with TTL management
- **CLI Sync Service**: Background synchronization across all pods (every 5 minutes)
- **Automatic Failover**: Personal token fallback in development

### Authentication Types

| Type               | Format      | TTL    | Environment      | Auto-Refresh   |
| ------------------ | ----------- | ------ | ---------------- | -------------- |
| **GitHub App**     | `ghs_xxxxx` | 1 hour | Production/Stage | ✅ Every 10min |
| **Personal Token** | `ghp_xxxxx` | Manual | Development      | ❌ Manual      |

## System Flow

```mermaid
graph TD
    A[App Startup] --> B[Bootstrap Check]
    B --> C{Token in Cache?}
    C -->|Yes + Valid TTL| D[Use Cached Token]
    C -->|No/Expired| E[Detect Auth Type]
    E --> F{GitHub App Config?}
    F -->|Yes| G[Generate App Token]
    F -->|No| H[Use Personal Token]
    G --> I[Cache Token + CLI Setup]
    H --> I
    I --> J[Start CLI Sync Service]
    J --> K[Schedule Refresh]
    K --> L[Background Worker]
    L --> M{TTL < 15min?}
    M -->|Yes| G
    M -->|No| N[Reschedule Check]
    J --> O[Background CLI Sync]
    O --> P{Token Changed?}
    P -->|Yes| Q[Update Local CLI]
    P -->|No| R[Wait 5min]
    Q --> R
    R --> O
```

## Core Components

### Service Layer

| Component                | File                                       | Purpose                                    |
| ------------------------ | ------------------------------------------ | ------------------------------------------ |
| **GitHubAuthService**    | `src/providers/github/auth_service.py`     | Token consumption for API pods             |
| **GitHubCliSyncService** | `src/providers/github/cli_sync_service.py` | Background CLI synchronization across pods |
| **GitHubAuthBootstrap**  | `src/providers/github/bootstrap.py`        | Application startup integration            |
| **TaskProcessor**        | `src/worker/tasks.py`                      | Background token refresh                   |

### Key Features

- **Smart Detection**: Auto-selects auth type based on configuration availability
- **TTL Management**: Only refreshes when token expires within 15 minutes
- **Multi-Pod Sync**: Background CLI synchronization across all pods every 5 minutes
- **Queue Efficiency**: Queue-only tasks for background operations
- **CLI Integration**: Automatic git/gh CLI authentication with atomic updates
- **Error Recovery**: Automatic retry with exponential backoff

## Configuration

### Development (Personal Token)

```toml
[github]
token = ""  # Falls back to environment variables

# Environment fallback chain:
# GITHUB_TOKEN → GITHUB_PERSONAL_ACCESS_TOKEN → GH_TOKEN
```

### Production (GitHub App)

```toml
[github.rzp_swe_agent_app]
app_id = "1490969"
installation_id = "73973932"
private_key = "-----BEGIN RSA PRIVATE KEY-----..."
```

### Environment Detection Logic

```python
# Uses GitHub App if ALL present:
- app_id
- private_key
- installation_id

# Otherwise uses Personal Token
```

## Token Lifecycle

### Refresh Strategy

- **Check Interval**: Every 10 minutes (GitHub App only)
- **Refresh Trigger**: TTL < 15 minutes remaining
- **Cache TTL**: 50 minutes (or 5 minutes before actual expiry)
- **Fallback**: Personal token in development environments

### Background Processing

```python
# Smart refresh logic
if token_ttl > 900:  # > 15 minutes
    reschedule_check(delay=600)  # Check in 10 minutes
else:
    refresh_token()
    schedule_next_check()
```

## API Endpoints

### Status Check

```bash
GET /api/v1/admin/github/status
Authorization: Basic admin:admin123
```

**Response**:

```json
{
  "authenticated": true,
  "token_type": "github_app",
  "environment": "prod",
  "ttl_minutes": 45,
  "git_configured": true,
  "gh_authenticated": true,
  "api_access": true
}
```

### Health Check

```bash
GET /api/v1/health/github
```

### Diagnosis & Auto-Fix

```bash
POST /api/v1/admin/github/diagnose-and-fix
Authorization: Basic admin:admin123
```

## Monitoring

### Status Indicators

| Field              | Description                  | Healthy Value |
| ------------------ | ---------------------------- | ------------- |
| `authenticated`    | Token cached and valid       | `true`        |
| `ttl_minutes`      | Minutes until refresh needed | `> 10`        |
| `git_configured`   | Git CLI authenticated        | `true`        |
| `gh_authenticated` | GitHub CLI authenticated     | `true`        |
| `api_access`       | GitHub API accessible        | `true`        |

### Background Refresh Status

```bash
# Check worker logs
docker logs swe-agent-worker | grep -i github

# Check CLI sync service
curl -u admin:admin123 localhost:28002/api/v1/admin/github/cli-sync-status

# Redis token inspection
redis-cli GET github:token
redis-cli TTL github:token
```

## Troubleshooting

### Common Issues

| Issue                     | Symptom                    | Solution                                     |
| ------------------------- | -------------------------- | -------------------------------------------- |
| **No background refresh** | TTL decreasing, no refresh | Check worker is running and processing tasks |
| **CLI sync not working**  | Pods have different tokens | Check CLI sync service status on each pod    |
| **Auth detection fails**  | Wrong token type used      | Verify GitHub App config completeness        |
| **CLI commands fail**     | `gh auth status` fails     | Run auto-fix endpoint or restart services    |
| **Token expires**         | API calls return 401       | Check worker logs, verify App permissions    |

### Debug Commands

```bash
# Check authentication status
curl -u admin:admin123 localhost:28002/api/v1/admin/github/status

# Check CLI sync service status
curl -u admin:admin123 localhost:28002/api/v1/admin/github/cli-sync-status

# Force refresh
curl -u admin:admin123 -X POST localhost:28002/api/v1/admin/github/diagnose-and-fix

# Check worker health
curl localhost:28002/api/v1/health/worker

# Inspect Redis cache
redis-cli KEYS github:*
redis-cli GET github:token:metadata
```

### Error Recovery

1. **Auto-Fix**: POST to `/admin/github/diagnose-and-fix`
2. **Worker Restart**: `docker restart swe-agent-worker`
3. **Full Reset**: Clear Redis cache + restart services
4. **Fallback**: Use personal token in development

## Performance

- **Token Lookup**: ~2ms (Redis cache)
- **Status Check**: ~20ms (cached 5 minutes)
- **Token Refresh**: ~1.2s (GitHub App API)
- **Background Check**: Every 10 minutes
- **Cache Efficiency**: 50-minute TTL with 15-minute refresh buffer

## Security

### Token Scope

- **GitHub App**: Installation permissions only
- **Personal Token**: User permissions (development only)

### Storage

- **Cache**: Redis with TTL expiration
- **Transit**: HTTPS only for external APIs
- **CLI**: Local git credential storage

### Rotation

- **Automatic**: GitHub App tokens (1-hour expiry)
- **Manual**: Personal tokens (no expiry)
