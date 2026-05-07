# Health Check Report Output Style

## Format

Use this format for system health check reports.

```markdown
# System Health Check Report

**Overall Status**: {✅ Healthy | ⚠️ Degraded | ❌ Unhealthy}
**Timestamp**: {timestamp}
**Environment**: {dev/staging/production}
**Report ID**: {report_id}

## Executive Summary

- **Components Checked**: {total_components}
- **Healthy**: {healthy_count} ✅
- **Degraded**: {degraded_count} ⚠️
- **Unhealthy**: {unhealthy_count} ❌
- **Response Time**: {total_check_time}ms

## Component Status

### ✅ API Server (Healthy)
```
Status: Running
Version: {version}
Uptime: {uptime}
Response Time: {response_time}ms
Endpoints Checked: {endpoint_count}/{total_endpoints}
Error Rate: {error_rate}%
```

**Details**:
- Health endpoint: `/health` → 200 OK
- API docs: `/docs` → Accessible
- Active connections: {active_connections}
- Request rate: {requests_per_minute}/min

### ✅ Database (Healthy)
```
Type: {database_type}
Version: {version}
Status: Connected
Connection Pool: {available}/{total} available
Query Time (avg): {avg_query_time}ms
```

**Details**:
- Connection established successfully
- Migrations: Up to date (v{migration_version})
- Active transactions: {active_transactions}
- Slow queries: {slow_query_count}

### ✅ Cache (Healthy)
```
Type: Redis
Version: {version}
Status: Connected
Memory Usage: {used_memory}/{max_memory}
Hit Rate: {hit_rate}%
Keys: {key_count}
```

**Details**:
- Ping response: < 1ms
- Eviction policy: LRU
- Connected clients: {connected_clients}
- Uptime: {uptime}

### ✅ Queue (Healthy)
```
Type: SQS (LocalStack)
Status: Accessible
Messages Available: {messages_available}
Messages In Flight: {messages_in_flight}
Messages Delayed: {messages_delayed}
```

**Details**:
- Queue name: swe-agent-tasks
- Visibility timeout: 300s
- Message retention: 14 days
- Dead letter queue: Configured

### ⚠️ Worker (Degraded)
```
Status: Running with warnings
Uptime: {uptime}
Tasks Processed: {total_tasks}
Success Rate: {success_rate}%
Current Load: {current_load}%
```

**Warnings**:
- ⚠️ Error rate above threshold ({error_rate}% > 5%)
- ⚠️ Memory usage high ({memory_usage}% of limit)
- ℹ️ Recommended: Restart worker to free memory

**Details**:
- Tasks successful: {successful_tasks}
- Tasks failed: {failed_tasks}
- Current task: {current_task_id}
- Last heartbeat: {last_heartbeat} ({seconds_ago}s ago)

### ✅ Agent System (Healthy)
```
Claude Code: Installed (v{version})
MCP Servers: {healthy_count}/{total_count} healthy
```

**MCP Server Status**:
- ✅ github: Healthy (authenticated)
- ✅ filesystem: Healthy
- ✅ memory: Healthy

### ✅ Docker Containers (Healthy)
```
Total Containers: {total}
Running: {running}
Stopped: {stopped}
```

**Container Details**:
| Container | Status | Uptime | CPU | Memory |
|-----------|--------|--------|-----|--------|
| api       | Up     | 2h 34m | 12% | 245MB  |
| ui        | Up     | 2h 34m | 3%  | 128MB  |
| worker    | Up     | 2h 30m | 25% | 512MB  |
| db        | Up     | 3d 5h  | 8%  | 1.2GB  |
| redis     | Up     | 3d 5h  | 2%  | 128MB  |
| localstack| Up     | 3d 5h  | 5%  | 256MB  |

## Performance Metrics

### API Performance
- **Average Response Time**: {avg_response_time}ms
- **p50 Response Time**: {p50}ms
- **p95 Response Time**: {p95}ms
- **p99 Response Time**: {p99}ms
- **Request Rate**: {requests_per_second} req/s

### Database Performance
- **Query Response Time (avg)**: {avg_query_time}ms
- **Slow Queries (>100ms)**: {slow_query_count}
- **Active Connections**: {active_connections}/{max_connections}
- **Lock Wait Time**: {lock_wait_time}ms

### Cache Performance
- **Hit Rate**: {hit_rate}%
- **Miss Rate**: {miss_rate}%
- **Average Get Time**: {avg_get_time}ms
- **Evictions**: {eviction_count}

## Critical Issues

{IF has_critical_issues}
### 🔴 Critical Issue 1: {issue_title}
- **Severity**: Critical
- **Component**: {component}
- **Impact**: {impact_description}
- **First Detected**: {detected_at}
- **Frequency**: {occurrence_count} times
- **Action Required**: {required_action}

{ELSE}
✅ No critical issues detected
{END IF}

## Warnings and Advisories

{IF has_warnings}
### ⚠️ Warning 1: {warning_title}
- **Component**: {component}
- **Description**: {warning_description}
- **Recommendation**: {recommendation}
- **Priority**: {high/medium/low}

{ELSE}
✅ No warnings
{END IF}

## Resource Utilization

### System Resources
| Resource | Used | Total | Percentage | Status |
|----------|------|-------|------------|--------|
| CPU      | {used_cpu} cores | {total_cpu} cores | {cpu_percent}% | {status} |
| Memory   | {used_memory}GB | {total_memory}GB | {memory_percent}% | {status} |
| Disk     | {used_disk}GB | {total_disk}GB | {disk_percent}% | {status} |

### Container Resources
| Container | CPU Limit | Memory Limit | CPU Usage | Memory Usage |
|-----------|-----------|--------------|-----------|--------------|
| api       | 2.0       | 2G           | 0.24      | 245MB        |
| worker    | 4.0       | 4G           | 1.0       | 512MB        |
| db        | 2.0       | 2G           | 0.16      | 1.2GB        |

## Network Status

- **External Connectivity**: ✅ Healthy
- **GitHub API**: ✅ Accessible (rate limit: {remaining}/{limit})
- **LocalStack**: ✅ Accessible
- **DNS Resolution**: ✅ Working

## Recent Events

### Last 1 Hour
- 10:45:23 - Worker restarted (scheduled maintenance)
- 10:30:15 - High memory usage warning (worker)
- 10:15:42 - Database slow query detected
- 10:00:00 - Hourly health check completed

## Recommendations

### Immediate Actions (Today)
{IF has_immediate_actions}
1. ✅ {action_1}
2. ✅ {action_2}
{ELSE}
✅ No immediate actions required
{END IF}

### Short-term Actions (This Week)
{IF has_shortterm_actions}
1. 🔧 {action_1}
2. 🔧 {action_2}
{ELSE}
✅ No short-term actions required
{END IF}

### Long-term Actions (This Month)
{IF has_longterm_actions}
1. 📋 {action_1}
2. 📋 {action_2}
{ELSE}
✅ No long-term actions required
{END IF}

## Quick Actions

```bash
# View component logs
docker-compose logs {component} --tail=100

# Restart specific component
docker-compose restart {component}

# Restart all services
make restart-all

# Check detailed status
make status

# Run health check again
/check-health
```

## Monitoring Links

- **API Health**: http://localhost:28002/health
- **API Docs**: http://localhost:28002/docs
- **Grafana Dashboard**: {grafana_url} (if configured)
- **Logs**: `tmp/logs/`

## Trend Analysis

{IF has_trend_data}
### Last 24 Hours
- **Availability**: {availability}%
- **Average Response Time**: {avg_response_time}ms (↑ 5% from yesterday)
- **Error Rate**: {error_rate}% (↓ 2% from yesterday)
- **Tasks Processed**: {tasks_processed} (↑ 15% from yesterday)

**Trends**:
- ↗️ Task volume increasing
- ↘️ Error rate decreasing
- → Response time stable
{END IF}

## Next Health Check

Scheduled: {next_check_time}
Frequency: Every {interval} minutes

---

**Generated by**: /check-health command
**Report Duration**: {check_duration}ms
**Components Checked**: {component_list}
```

## Usage

Use this format when:
- Running `/check-health` command
- Performing scheduled health checks
- Debugging system issues
- Reporting system status

## Variables

- `{overall_status}`: Healthy, Degraded, or Unhealthy
- `{component}`: Specific component name
- `{status}`: Component-specific status
- `{metric}`: Specific metric value
- `{threshold}`: Alert threshold value
- `{recommendation}`: Suggested action

## Status Indicators

- ✅ Healthy/OK/Success
- ⚠️ Degraded/Warning
- ❌ Unhealthy/Failed/Critical
- 🔄 In Progress/Restarting
- ℹ️ Information/Note
- 🔧 Action Required
- 📋 Planned/Scheduled
- ↗️ Increasing Trend
- ↘️ Decreasing Trend
- → Stable/No Change
