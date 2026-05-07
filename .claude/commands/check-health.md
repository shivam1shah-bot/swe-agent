# Check Health Command

## Purpose
Perform comprehensive health checks across all SWE Agent system components, providing detailed diagnostics and status information.

## Usage
```
/check-health [component] [options]
```

## Instructions

When this command is invoked, perform the following:

### 1. Determine Scope

Identify what to check:
- **No arguments**: Check all components (full system health)
- **Specific component**: Check only that component
- **With options**: Apply filters or focus areas

### 2. Execute Health Checks

Perform multi-layer health checks:

#### API Layer
```python
# Check API server
response = requests.get("http://localhost:28002/health")

check_results["api"] = {
    "status": "healthy" if response.status_code == 200 else "unhealthy",
    "response_time_ms": response.elapsed.total_seconds() * 1000,
    "version": response.json().get("version"),
    "uptime": response.json().get("uptime_seconds")
}

# Check API endpoints
endpoints = ["/health", "/api/v1/tasks", "/api/v1/workers"]
for endpoint in endpoints:
    test_response = requests.get(f"http://localhost:28002{endpoint}")
    check_results["api"]["endpoints"][endpoint] = {
        "accessible": test_response.status_code < 500,
        "status_code": test_response.status_code
    }
```

#### Database Layer
```python
# Check database connectivity
try:
    conn = await db_provider.get_connection()
    result = await conn.execute("SELECT 1")

    check_results["database"] = {
        "status": "healthy",
        "type": "MySQL",
        "version": await get_db_version(),
        "connection_pool": {
            "size": pool.size(),
            "available": pool.available(),
            "in_use": pool.in_use()
        }
    }

    # Check migrations
    migration_status = await check_migration_status()
    check_results["database"]["migrations"] = {
        "current_version": migration_status.current_version,
        "latest_version": migration_status.latest_version,
        "up_to_date": migration_status.current_version == migration_status.latest_version
    }

except Exception as e:
    check_results["database"] = {
        "status": "unhealthy",
        "error": str(e)
    }
```

#### Cache Layer (Redis)
```python
# Check Redis connectivity
try:
    redis_client = await redis_provider.get_client()
    await redis_client.ping()

    check_results["cache"] = {
        "status": "healthy",
        "type": "Redis",
        "info": {
            "version": await redis_client.info("server")["redis_version"],
            "used_memory_human": await redis_client.info("memory")["used_memory_human"],
            "connected_clients": await redis_client.info("clients")["connected_clients"],
            "uptime_days": await redis_client.info("server")["uptime_in_days"]
        },
        "keys_count": await redis_client.dbsize()
    }

except Exception as e:
    check_results["cache"] = {
        "status": "unhealthy",
        "error": str(e)
    }
```

#### Queue Layer (SQS)
```python
# Check SQS queue
try:
    queue_url = await sqs_provider.get_queue_url("swe-agent-tasks")

    # Get queue attributes
    attributes = await sqs_provider.get_queue_attributes(queue_url)

    check_results["queue"] = {
        "status": "healthy",
        "type": "SQS (LocalStack)" if is_dev else "SQS (AWS)",
        "queue_name": "swe-agent-tasks",
        "metrics": {
            "messages_available": int(attributes.get("ApproximateNumberOfMessages", 0)),
            "messages_in_flight": int(attributes.get("ApproximateNumberOfMessagesNotVisible", 0)),
            "messages_delayed": int(attributes.get("ApproximateNumberOfMessagesDelayed", 0))
        }
    }

except Exception as e:
    check_results["queue"] = {
        "status": "unhealthy",
        "error": str(e)
    }
```

#### Worker Status
```python
# Check worker processes
try:
    # Check if worker is running
    worker_status = await check_worker_process()

    check_results["worker"] = {
        "status": "healthy" if worker_status.is_running else "stopped",
        "process_id": worker_status.pid if worker_status.is_running else None,
        "uptime_seconds": worker_status.uptime if worker_status.is_running else 0,
        "tasks_processed": {
            "total": worker_status.tasks_total,
            "successful": worker_status.tasks_successful,
            "failed": worker_status.tasks_failed
        },
        "current_task": worker_status.current_task_id,
        "last_heartbeat": worker_status.last_heartbeat.isoformat()
    }

except Exception as e:
    check_results["worker"] = {
        "status": "unhealthy",
        "error": str(e)
    }
```

#### Agent System
```python
# Check agent availability
try:
    # Check Claude Code CLI
    claude_code_version = subprocess.run(
        ["claude", "--version"],
        capture_output=True,
        text=True
    )

    check_results["agent"] = {
        "status": "healthy",
        "claude_code": {
            "installed": claude_code_version.returncode == 0,
            "version": claude_code_version.stdout.strip()
        }
    }

    # Check MCP servers
    mcp_config = load_mcp_config("src/providers/mcp/mcp-servers.json")
    mcp_health = await check_mcp_servers(mcp_config)

    check_results["agent"]["mcp_servers"] = mcp_health

except Exception as e:
    check_results["agent"] = {
        "status": "unhealthy",
        "error": str(e)
    }
```

#### Docker Containers (if running in Docker)
```python
if running_in_docker():
    # Check container statuses
    containers = subprocess.run(
        ["docker-compose", "ps", "--format", "json"],
        capture_output=True,
        text=True
    )

    check_results["docker"] = {
        "status": "healthy",
        "containers": parse_container_status(containers.stdout)
    }
```

### 3. Aggregate Results

Compile overall system health:

```python
# Determine overall status
critical_components = ["api", "database", "worker"]
overall_healthy = all(
    check_results.get(comp, {}).get("status") == "healthy"
    for comp in critical_components
)

overall_status = {
    "status": "healthy" if overall_healthy else "degraded",
    "timestamp": datetime.now().isoformat(),
    "components_checked": len(check_results),
    "components_healthy": sum(
        1 for r in check_results.values()
        if r.get("status") == "healthy"
    ),
    "components_unhealthy": sum(
        1 for r in check_results.values()
        if r.get("status") != "healthy"
    )
}
```

### 4. Format Output

Present results in clear, actionable format:

```markdown
# System Health Check Report

**Overall Status**: {✅ Healthy | ⚠️  Degraded | ❌ Unhealthy}
**Timestamp**: {timestamp}
**Components Checked**: {count}

## Component Status

### ✅ API Server (Healthy)
- Status: Running
- Version: 1.0.0
- Uptime: 2h 34m
- Response Time: 23ms
- Endpoints: 15/15 accessible

### ✅ Database (Healthy)
- Type: MySQL 8.0.35
- Status: Connected
- Connection Pool: 8/10 available
- Migrations: Up to date (v12)

### ✅ Cache (Healthy)
- Type: Redis 7.0
- Status: Connected
- Memory: 45.2 MB / 512 MB
- Keys: 1,234
- Uptime: 3 days

### ✅ Queue (Healthy)
- Type: SQS (LocalStack)
- Messages Available: 3
- Messages In Flight: 1
- Messages Delayed: 0

### ⚠️  Worker (Degraded)
- Status: Running
- Warning: High error rate (12% failures)
- Tasks Processed: 450
- Tasks Successful: 396
- Tasks Failed: 54
- Current Task: task-abc123

### ✅ Agent System (Healthy)
- Claude Code: v0.8.0 (installed)
- MCP Servers:
  - github: ✅ Healthy
  - filesystem: ✅ Healthy
  - memory: ✅ Healthy

### ✅ Docker Containers (Healthy)
- api: Up 2 hours
- ui: Up 2 hours
- worker: Up 2 hours
- db: Up 3 days
- redis: Up 3 days
- localstack: Up 3 days

## Recommendations

{If any issues detected}:
1. **Worker Error Rate**: Investigate recent task failures in logs
   - Check: docker-compose logs worker --tail=100
   - Review: /tmp/logs/worker-errors.log

2. **Database Connection Pool**: Consider increasing pool size
   - Current: 8/10 available
   - Recommendation: Increase to 20 for higher concurrency

## Quick Actions

- View API logs: `docker-compose logs api`
- View worker logs: `docker-compose logs worker`
- Restart unhealthy components: `docker-compose restart <component>`
- Full system restart: `make restart-all`
```

## Component-Specific Checks

### Check API Only
```bash
/check-health api
```

### Check Database Only
```bash
/check-health database
```

### Check Worker Only
```bash
/check-health worker
```

### Check All Infrastructure
```bash
/check-health infrastructure
```

## Options

```bash
# Verbose mode (detailed diagnostics)
/check-health --verbose

# JSON output (for automation)
/check-health --json

# Watch mode (continuous monitoring)
/check-health --watch --interval 30

# Check specific endpoint
/check-health api --endpoint /api/v1/tasks

# Include performance metrics
/check-health --metrics

# Run deep health checks (slower but more thorough)
/check-health --deep
```

## Exit Codes

When used programmatically:
- `0`: All components healthy
- `1`: One or more components unhealthy
- `2`: Critical component failure
- `3`: Health check itself failed

## Integration

This command integrates with:
- Health check endpoints: `src/api/routers/health.py`
- Database provider: `src/providers/database/db_provider.py`
- Redis provider: `src/providers/redis/redis_provider.py`
- Queue provider: `src/providers/queue/sqs_provider.py`
- Worker status: `src/worker/tasks.py`

## Automation

Can be used in monitoring scripts:

```bash
#!/bin/bash
# Health check automation

if /check-health --json > health.json; then
    echo "System healthy"
else
    echo "System unhealthy - triggering alerts"
    send_alert "SWE Agent health check failed" health.json
fi
```

## Output Style

Use the `health-check-report` output style for formatting results.

## Reference

- Health check implementation: `src/api/routers/health.py`
- Provider health checks: `src/providers/*/health.py`
- Output style: `.claude/output-styles/health-check-report.md`
