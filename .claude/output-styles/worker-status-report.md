# Worker Status Report Output Style

## Format

Use this format for worker status and task queue monitoring reports.

```markdown
# Worker Status Report

**Overall Status**: {✅ Healthy | ⚠️ Degraded | ❌ Critical}
**Timestamp**: {timestamp}
**Reporting Period**: {period}

## Worker Summary

| Metric | Value | Status |
|--------|-------|--------|
| Active Workers | {active_count} | {status} |
| Total Tasks Processed | {total_tasks} | ℹ️ |
| Tasks Successful | {successful_tasks} | ✅ |
| Tasks Failed | {failed_tasks} | {status} |
| Success Rate | {success_rate}% | {status} |
| Average Task Duration | {avg_duration}s | {status} |
| Current Queue Depth | {queue_depth} | {status} |

## Worker Instances

### Worker 1
```
Status: Running ✅
PID: {process_id}
Uptime: {uptime}
Current Task: {task_id}
Tasks Processed: {count}
Success Rate: {rate}%
Memory Usage: {memory}MB
CPU Usage: {cpu}%
```

**Recent Tasks**:
| Task ID | Type | Duration | Status |
|---------|------|----------|--------|
| task-001 | feature | 3m 45s | ✅ Completed |
| task-002 | bugfix | 2m 12s | ✅ Completed |
| task-003 | refactor | 5m 30s | 🔄 In Progress |

**Performance**:
- Average task duration: {avg_duration}s
- Peak CPU: {peak_cpu}%
- Peak memory: {peak_memory}MB
- Last heartbeat: {last_heartbeat}

## Queue Status

### Task Queue (swe-agent-tasks)
```
Messages Available: {available}
Messages In Flight: {in_flight}
Messages Delayed: {delayed}
Oldest Message Age: {age}
```

**Queue Metrics**:
- Enqueue rate: {enqueue_rate} tasks/min
- Dequeue rate: {dequeue_rate} tasks/min
- Processing rate: {processing_rate} tasks/min
- Average wait time: {avg_wait_time}s

### Dead Letter Queue
```
Messages: {dlq_messages}
Threshold: {dlq_threshold}
Status: {✅ OK | ⚠️ Warning | ❌ Critical}
```

{IF dlq_messages > 0}
**Recent Failures**:
1. Task {task_id}: {error_message}
2. Task {task_id}: {error_message}
{END IF}

## Task Statistics

### By Type
| Task Type | Count | Success Rate | Avg Duration |
|-----------|-------|--------------|--------------|
| feature_implementation | {count} | {rate}% | {duration}s |
| bug_fix | {count} | {rate}% | {duration}s |
| refactoring | {count} | {rate}% | {duration}s |
| documentation | {count} | {rate}% | {duration}s |
| testing | {count} | {rate}% | {duration}s |

### By Status
```
✅ Completed: {completed_count} ({completed_percent}%)
🔄 In Progress: {in_progress_count} ({in_progress_percent}%)
⏸️ Pending: {pending_count} ({pending_percent}%)
❌ Failed: {failed_count} ({failed_percent}%)
⛔ Cancelled: {cancelled_count} ({cancelled_percent}%)
```

### Recent Activity (Last Hour)
- Tasks started: {started_count}
- Tasks completed: {completed_count}
- Tasks failed: {failed_count}
- Peak queue depth: {peak_depth}

## Performance Analysis

### Task Duration Distribution
```
Min: {min_duration}s
p50: {p50_duration}s
p75: {p75_duration}s
p95: {p95_duration}s
p99: {p99_duration}s
Max: {max_duration}s
```

### Throughput
```
Tasks/hour: {tasks_per_hour}
Tasks/minute: {tasks_per_minute}
Peak throughput: {peak_throughput} tasks/min
Low throughput: {low_throughput} tasks/min
```

### Resource Utilization
```
Average CPU: {avg_cpu}%
Peak CPU: {peak_cpu}%
Average Memory: {avg_memory}MB
Peak Memory: {peak_memory}MB
```

## Error Analysis

{IF has_errors}
### Top Errors (Last 24h)
1. **{error_type}** ({count} occurrences)
   - First seen: {first_seen}
   - Last seen: {last_seen}
   - Affected tasks: {affected_task_ids}
   - Impact: {impact_description}

2. **{error_type}** ({count} occurrences)
   - First seen: {first_seen}
   - Last seen: {last_seen}
   - Affected tasks: {affected_task_ids}
   - Impact: {impact_description}

### Error Rate Trend
```
Last hour: {error_rate_1h}%
Last 6 hours: {error_rate_6h}%
Last 24 hours: {error_rate_24h}%
Trend: {↗️ Increasing | ↘️ Decreasing | → Stable}
```

{ELSE}
✅ No errors in reporting period
{END IF}

## Active Tasks

### Currently Processing
| Task ID | Type | Started | Duration | Progress | Worker |
|---------|------|---------|----------|----------|--------|
| task-123 | feature | 10:45:23 | 3m 12s | 60% | Worker 1 |
| task-124 | bugfix | 10:46:01 | 2m 34s | 40% | Worker 2 |

### Queued Tasks
| Task ID | Type | Priority | Queued Since | Wait Time |
|---------|------|----------|--------------|-----------|
| task-125 | feature | HIGH | 10:47:15 | 1m 20s |
| task-126 | refactor | NORMAL | 10:48:03 | 32s |
| task-127 | testing | LOW | 10:48:30 | 5s |

## Alerts and Warnings

{IF has_alerts}
### 🔴 Critical Alerts
1. **High error rate**
   - Current: {error_rate}%
   - Threshold: {threshold}%
   - Action: Investigate recent failures

### ⚠️ Warnings
1. **Queue depth increasing**
   - Current: {queue_depth}
   - Trend: Increased {percent}% in last hour
   - Action: Consider scaling workers

2. **Worker memory usage high**
   - Current: {memory_usage}MB
   - Threshold: {threshold}MB
   - Action: Restart worker soon

{ELSE}
✅ No active alerts or warnings
{END IF}

## Health Indicators

### Worker Health
- ✅ All workers responding to heartbeat
- ✅ No stuck tasks detected
- ✅ Memory usage within limits
- ✅ CPU usage normal
- {✅ | ⚠️ | ❌} Error rate acceptable

### Queue Health
- ✅ Queue accessible
- ✅ No message backlog
- ✅ Dead letter queue empty
- {✅ | ⚠️ | ❌} Processing rate adequate

### System Health
- ✅ Database connections stable
- ✅ Redis cache accessible
- ✅ Agent system operational
- ✅ GitHub API accessible

## Recommendations

### Immediate Actions
{IF needs_immediate_action}
1. 🔴 {action_description}
   - Reason: {reason}
   - Command: `{command}`

{ELSE}
✅ No immediate actions required
{END IF}

### Optimization Suggestions
{IF has_optimization_suggestions}
1. 🔧 {suggestion_1}
2. 🔧 {suggestion_2}
{ELSE}
✅ Worker operating optimally
{END IF}

## Capacity Planning

### Current Capacity
- Worker capacity: {worker_capacity} tasks/hour
- Current load: {current_load}% of capacity
- Headroom: {headroom}%

### Scaling Recommendations
{IF needs_scaling}
- Current workers: {current_workers}
- Recommended workers: {recommended_workers}
- Reason: {scaling_reason}
{ELSE}
✅ Current worker count sufficient
{END IF}

## Historical Trends

{IF has_trend_data}
### Last 7 Days
```
Total tasks: {total_tasks} (↑ {percent}% from previous week)
Success rate: {success_rate}% (↑ {change}%)
Avg duration: {avg_duration}s (↓ {change}%)
Peak queue: {peak_queue} tasks
```

**Notable Events**:
- {date}: Highest daily volume ({count} tasks)
- {date}: Best success rate ({rate}%)
- {date}: Fastest avg duration ({duration}s)

{END IF}

## Quick Actions

```bash
# View worker logs
docker-compose logs worker --tail=100 -f

# Restart worker
docker-compose restart worker

# Check queue status
aws --endpoint-url=http://localhost:4566 sqs get-queue-attributes \
  --queue-url {queue_url} \
  --attribute-names All

# Purge dead letter queue (use with caution)
aws --endpoint-url=http://localhost:4566 sqs purge-queue \
  --queue-url {dlq_url}

# Scale workers (if using orchestration)
docker-compose up -d --scale worker={count}
```

## Monitoring Dashboards

- **Worker Logs**: `tmp/logs/worker/`
- **Task Logs**: `tmp/logs/tasks/`
- **Queue Monitoring**: http://localhost:4566 (LocalStack)
- **Metrics**: Available via API at `/api/v1/metrics`

## Next Report

Scheduled: {next_report_time}
Frequency: Every {interval} minutes

---

**Generated by**: Worker monitoring system
**Report Duration**: {report_duration}ms
**Data Sources**: Worker heartbeats, SQS metrics, task database
```

## Usage

Use this format when:
- Monitoring worker status
- Analyzing task queue performance
- Troubleshooting task failures
- Planning worker capacity

## Variables

- `{worker_count}`: Number of active workers
- `{queue_depth}`: Current queue depth
- `{task_count}`: Task count by status/type
- `{success_rate}`: Task success percentage
- `{error_rate}`: Task error percentage
- `{avg_duration}`: Average task duration
- `{throughput}`: Tasks processed per time unit

## Status Indicators

- ✅ Healthy/Success
- ⚠️ Warning/Degraded
- ❌ Critical/Failed
- 🔄 In Progress
- ⏸️ Pending
- ⛔ Cancelled
- 🔴 Critical Alert
- 🔧 Optimization Needed
- ℹ️ Information
- ↗️ Increasing
- ↘️ Decreasing
- → Stable
