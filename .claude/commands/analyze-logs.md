# Analyze Logs Command

## Purpose
Analyze system logs to identify errors, patterns, performance issues, and provide actionable insights for debugging and optimization.

## Usage
```
/analyze-logs [component] [time-range] [options]
```

## Instructions

When this command is invoked, perform the following:

### 1. Identify Log Sources

Determine which logs to analyze:

**Log Locations**:
- API logs: `tmp/logs/api/`
- Worker logs: `tmp/logs/worker/`
- Agent logs: `tmp/logs/agent/`
- Database logs: Docker container logs
- System logs: `tmp/logs/system/`

**Docker Logs**:
- API: `docker-compose logs api`
- Worker: `docker-compose logs worker`
- Database: `docker-compose logs db`
- Redis: `docker-compose logs redis`

### 2. Parse and Filter Logs

Apply filters based on parameters:

```python
# Time range filter
if time_range == "1h":
    start_time = datetime.now() - timedelta(hours=1)
elif time_range == "24h":
    start_time = datetime.now() - timedelta(hours=24)
elif time_range == "7d":
    start_time = datetime.now() - timedelta(days=7)

# Component filter
if component == "api":
    log_paths = ["tmp/logs/api/*.log"]
elif component == "worker":
    log_paths = ["tmp/logs/worker/*.log"]
elif component == "all":
    log_paths = ["tmp/logs/**/*.log"]

# Severity filter
log_levels = ["ERROR", "WARNING", "INFO", "DEBUG"]
if options.get("errors_only"):
    log_levels = ["ERROR"]
elif options.get("warnings_and_errors"):
    log_levels = ["ERROR", "WARNING"]
```

### 3. Analyze Log Patterns

Perform pattern analysis:

```python
analysis_results = {
    "error_summary": {},
    "warning_summary": {},
    "performance_metrics": {},
    "patterns": [],
    "anomalies": []
}

# Error analysis
for log_entry in error_logs:
    error_type = extract_error_type(log_entry)
    analysis_results["error_summary"][error_type] = \
        analysis_results["error_summary"].get(error_type, 0) + 1

# Warning analysis
for log_entry in warning_logs:
    warning_type = extract_warning_type(log_entry)
    analysis_results["warning_summary"][warning_type] = \
        analysis_results["warning_summary"].get(warning_type, 0) + 1

# Performance metrics
response_times = extract_response_times(logs)
analysis_results["performance_metrics"] = {
    "avg_response_time": statistics.mean(response_times),
    "p50_response_time": statistics.median(response_times),
    "p95_response_time": statistics.quantiles(response_times, n=20)[18],
    "p99_response_time": statistics.quantiles(response_times, n=100)[98]
}

# Pattern detection
patterns = detect_patterns(logs)
analysis_results["patterns"] = patterns

# Anomaly detection
anomalies = detect_anomalies(logs, baseline_metrics)
analysis_results["anomalies"] = anomalies
```

### 4. Generate Insights

Create actionable insights from analysis:

```python
insights = []

# High error rate
if error_rate > threshold:
    insights.append({
        "severity": "high",
        "type": "error_rate",
        "message": f"Error rate ({error_rate:.1%}) exceeds threshold ({threshold:.1%})",
        "recommendation": "Review recent code changes and error logs"
    })

# Slow response times
if avg_response_time > 500:  # ms
    insights.append({
        "severity": "medium",
        "type": "performance",
        "message": f"Average response time ({avg_response_time}ms) is slow",
        "recommendation": "Profile slow endpoints and optimize database queries"
    })

# Repeated errors
for error_type, count in error_summary.items():
    if count > 10:
        insights.append({
            "severity": "medium",
            "type": "repeated_error",
            "message": f"{error_type} occurred {count} times",
            "recommendation": f"Investigate root cause of {error_type}"
        })
```

### 5. Format Output

Present analysis results:

```markdown
# Log Analysis Report

**Component**: {component}
**Time Range**: {time_range}
**Log Entries Analyzed**: {total_entries}
**Analysis Timestamp**: {timestamp}

## Executive Summary

- **Total Errors**: {error_count} ({error_rate:.1%})
- **Total Warnings**: {warning_count}
- **Average Response Time**: {avg_response_time}ms
- **Critical Issues Found**: {critical_count}

## Error Summary

### Top Errors
1. **DatabaseConnectionError** (45 occurrences)
   - First seen: 2024-01-15 10:23:45
   - Last seen: 2024-01-15 14:15:32
   - Example:
     ```
     [ERROR] Failed to connect to database: Connection refused
     Location: src/providers/database/db_provider.py:45
     ```
   - **Recommendation**: Check database connection settings and ensure DB is running

2. **TaskExecutionTimeout** (23 occurrences)
   - Pattern: Occurs during large refactoring tasks
   - **Recommendation**: Increase timeout for complex tasks or implement task chunking

3. **AgentStreamingError** (12 occurrences)
   - Pattern: Occurs when agent output exceeds buffer
   - **Recommendation**: Implement streaming backpressure handling

## Warning Summary

### Top Warnings
1. **SlowQueryWarning** (156 occurrences)
   - Queries taking > 100ms
   - Affected endpoints: /api/v1/tasks, /api/v1/results
   - **Recommendation**: Add database indexes on frequently queried columns

2. **RedisConnectionWarning** (89 occurrences)
   - Intermittent Redis connectivity issues
   - **Recommendation**: Implement connection retry logic with backoff

## Performance Metrics

### Response Time Distribution
- Average: 245ms
- Median (p50): 180ms
- 95th percentile (p95): 520ms
- 99th percentile (p99): 1,240ms

### Slow Endpoints (p95 > 500ms)
1. `POST /api/v1/tasks` - 520ms average
   - Cause: Database insertion + queue publishing
   - **Optimization**: Batch queue operations

2. `GET /api/v1/tasks/{id}/results` - 680ms average
   - Cause: Large result set serialization
   - **Optimization**: Implement pagination

### Request Volume
- Total Requests: 12,450
- Requests/minute: 173
- Peak requests/minute: 320 (at 14:23)

## Patterns Detected

### Pattern 1: Database Connection Exhaustion
- **Frequency**: Every 2-3 hours
- **Duration**: 5-10 minutes
- **Impact**: Service degradation
- **Root Cause**: Connection pool too small for peak load
- **Solution**: Increase connection pool from 10 to 20

### Pattern 2: Memory Growth in Worker
- **Trend**: Steady 5% increase per hour
- **Impact**: Worker restart required after 8 hours
- **Root Cause**: Potential memory leak in agent cleanup
- **Solution**: Review agent resource cleanup in src/agents/autonomous_agent_tool.py

## Anomalies

### Anomaly 1: Sudden Error Spike
- **Time**: 2024-01-15 14:15:00 - 14:25:00
- **Magnitude**: 300% increase in error rate
- **Type**: DatabaseConnectionError
- **Correlation**: Database container restart
- **Action Taken**: None (automatic recovery)

### Anomaly 2: Unusual Task Distribution
- **Time**: 2024-01-15 11:00:00 - 12:00:00
- **Magnitude**: 500% increase in task submissions
- **Type**: Load spike
- **Correlation**: Automated batch job
- **Action Needed**: Consider rate limiting for batch operations

## Critical Issues

### 🔴 Critical Issue 1: Unhandled Exceptions
- **Count**: 8 occurrences
- **Impact**: Worker crashes
- **Stack Trace**:
  ```python
  File "src/worker/tasks.py", line 145, in process_task
      result = await self.agent.execute_task(task)
  File "src/agents/autonomous_agent_tool.py", line 89, in execute_task
      output = await self._parse_agent_output(raw_output)
  AttributeError: 'NoneType' object has no attribute 'strip'
  ```
- **Fix Required**: Add null check before calling strip()
- **Priority**: HIGH

### 🔴 Critical Issue 2: Deadlock Detection
- **Count**: 3 occurrences
- **Impact**: Task processing halts
- **Evidence**: Multiple tasks stuck "IN_PROGRESS" for > 1 hour
- **Affected Tasks**: task-xyz789, task-abc456, task-def123
- **Fix Required**: Implement task timeout and automatic cleanup
- **Priority**: HIGH

## Recommendations

### Immediate Actions (Today)
1. ✅ Fix NoneType error in agent output parsing (HIGH)
2. ✅ Add null checks in src/agents/autonomous_agent_tool.py:89
3. ✅ Increase database connection pool size (MEDIUM)
4. ✅ Investigate and restart stuck tasks (MEDIUM)

### Short-term Actions (This Week)
1. 🔧 Implement task timeout mechanism
2. 🔧 Add database indexes for slow queries
3. 🔧 Review and fix memory leak in worker
4. 🔧 Implement Redis connection retry logic

### Long-term Actions (This Month)
1. 📋 Implement comprehensive monitoring and alerting
2. 📋 Add performance profiling to identify bottlenecks
3. 📋 Implement rate limiting for API endpoints
4. 📋 Add circuit breakers for external dependencies

## Affected Tasks

### Failed Tasks Requiring Attention
- task-abc123: DatabaseConnectionError at 14:15
  - **Action**: Retry task
  - **Command**: `PUT /api/v1/tasks/task-abc123/retry`

- task-xyz789: Stuck in IN_PROGRESS for 3 hours
  - **Action**: Cancel and investigate
  - **Command**: `POST /api/v1/tasks/task-xyz789/cancel`

## Log Samples

### Sample Error Log Entry
```json
{
  "timestamp": "2024-01-15T14:15:32.123Z",
  "level": "ERROR",
  "logger": "src.providers.database.db_provider",
  "message": "Failed to connect to database",
  "error": "Connection refused",
  "context": {
    "correlation_id": "req-abc123",
    "task_id": "task-xyz789",
    "user_id": "user-456"
  },
  "stack_trace": "..."
}
```

## Next Steps

1. **Review and fix critical issues** identified above
2. **Monitor system** for 24 hours after applying fixes
3. **Re-run analysis** to verify improvements
4. **Update known issues** in `.claude/context/memory/known-issues.md`

---

**Generated by**: /analyze-logs command
**Report ID**: analysis-{timestamp}
```

## Analysis Options

### Time Range
```bash
/analyze-logs --last 1h       # Last hour
/analyze-logs --last 24h      # Last 24 hours
/analyze-logs --last 7d       # Last 7 days
/analyze-logs --since "2024-01-15 10:00"
/analyze-logs --between "2024-01-15 10:00" "2024-01-15 14:00"
```

### Component Filter
```bash
/analyze-logs api             # API logs only
/analyze-logs worker          # Worker logs only
/analyze-logs database        # Database logs only
/analyze-logs all             # All components
```

### Severity Filter
```bash
/analyze-logs --errors-only
/analyze-logs --warnings-and-errors
/analyze-logs --level ERROR
/analyze-logs --level WARNING,ERROR,CRITICAL
```

### Pattern Search
```bash
/analyze-logs --pattern "DatabaseConnectionError"
/analyze-logs --pattern "timeout"
/analyze-logs --pattern "task.*failed"  # Regex
```

### Performance Analysis
```bash
/analyze-logs --performance
/analyze-logs --slow-queries
/analyze-logs --response-times
```

### Task-Specific
```bash
/analyze-logs --task task-abc123
/analyze-logs --task task-abc123 --verbose
```

### Output Format
```bash
/analyze-logs --format json
/analyze-logs --format markdown
/analyze-logs --format summary
```

## Integration

This command integrates with:
- Logging infrastructure: `src/utils/logging.py`
- Log files: `tmp/logs/`
- Docker logs: `docker-compose logs`
- Analysis tools: Custom log parsers

## Automation

Can be used in monitoring scripts:

```bash
#!/bin/bash
# Automated log analysis

# Analyze last hour
/analyze-logs --last 1h --errors-only > hourly-errors.txt

# Check for critical issues
if grep -q "CRITICAL" hourly-errors.txt; then
    send_alert "Critical errors detected" hourly-errors.txt
fi
```

## Output Style

Use structured format for clear presentation of findings.

## Reference

- Logging setup: `src/utils/logging.py`
- Log locations: `tmp/logs/`
- Docker logs: `docker-compose logs <service>`
- Known issues: `.claude/context/memory/known-issues.md`
