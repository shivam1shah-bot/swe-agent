# Telemetry and Metrics

This document describes the telemetry and metrics system for the SWE Agent application, using Prometheus client library directly.

## Overview

The telemetry system provides a centralized, extensible metrics collection infrastructure. It uses `prometheus_client` directly for metrics collection and is designed to be extensible for future OpenTelemetry integration when packages are stable.

## Architecture

The telemetry system is implemented as a provider in `src/providers/telemetry/`:

- **`core.py`**: Core metrics provider with Prometheus client integration (`Meter` class, `setup_telemetry()`, `get_meter()`)
- **`metrics.py`**: Re-exports from `core.py` for backwards compatibility
- **`__init__.py`**: Package exports for easy importing
- **`domain/claude.py`**: Claude Code domain metrics (invocations, cost, tokens, errors)
- **`instrumentation/`**: Infrastructure instrumentation (cache, database, HTTP client, process)

### Key Features

- **Extensible Design**: Designed for future OpenTelemetry integration when packages are stable
- **Centralized Configuration**: All telemetry settings managed through application config
- **Automatic Integration**: Metrics endpoint automatically mounted in FastAPI apps
- **Service Labels**: Service name, version, and custom labels can be added to metrics

## Configuration

Telemetry configuration is managed through the application configuration file (environment variables or config files). The following settings are available:

```python
telemetry:
  enabled: true                    # Enable/disable telemetry (default: true)
  exporter: "prometheus"           # Exporter type (currently only "prometheus" supported)
  metrics_path: "/metrics"         # Path for metrics endpoint (default: "/metrics")
  service_name: "swe-agent-api"    # Service name for resource attributes
  service_version: "1.0.0"         # Service version for resource attributes
  labels:                          # Additional resource labels
    environment: "production"
    region: "us-east-1"
  prometheus:                      # Prometheus-specific configuration
    # Future configuration options can go here
```

### Environment Variables

You can configure telemetry using environment variables (following the config loader pattern):

```bash
# Enable/disable telemetry
TELEMETRY_ENABLED=true

# Exporter type
TELEMETRY_EXPORTER=prometheus

# Metrics endpoint path
TELEMETRY_METRICS_PATH=/metrics

# Service information
TELEMETRY_SERVICE_NAME=swe-agent-api
TELEMETRY_SERVICE_VERSION=1.0.0
```

## Usage

### Initialization

Telemetry is automatically initialized in the main API server, MCP server, and Worker during application startup:

**API Server (`src/api/api.py`)**:

- Initialized in the `lifespan` startup event
- Metrics endpoint mounted automatically after app creation

**MCP Server (`src/mcp_server/app.py`)**:

- Initialized in the `startup` event
- Metrics endpoint mounted automatically

**Worker (`src/worker/worker.py`)**:

- Initialized in the `__init__` method during worker startup
- If `metrics_port` is configured, a separate metrics server will be started automatically
- Metrics can be scraped from the configured port (if enabled)

### Creating Metrics

To create metrics in your code, use the `get_meter()` function:

```python
from src.providers.telemetry import get_meter

# Get a meter for your component
meter = get_meter("api.router")

# Create a counter
request_counter = meter.create_counter(
    "api_requests_total",
    description="Total number of API requests",
    labelnames=("method", "path", "status")
)

# Create a histogram
request_duration = meter.create_histogram(
    "api_request_duration_seconds",
    description="API request duration in seconds",
    labelnames=("method", "path")
)

# Use the metrics with labels
request_counter.labels(method="GET", path="/api/v1/health", status="200").inc()
request_duration.labels(method="GET", path="/api/v1/health").observe(0.123)
```

### Metric Types

The Prometheus client library supports the following metric types:

1. **Counter**: Monotonically increasing value (e.g., total requests)
2. **Gauge**: Value that can go up or down (e.g., current connections)
3. **Histogram**: Distribution of values (e.g., request duration)
4. **Summary**: Summary statistics (e.g., quantiles)

### Example: Adding Metrics to a Router

```python
from fastapi import APIRouter, Request
from src.providers.telemetry import get_meter
import time

router = APIRouter()

# Initialize metrics once
meter = get_meter("api.health")
request_counter = meter.create_counter(
    "health_check_requests_total",
    description="Total health check requests"
)
request_duration = meter.create_histogram(
    "health_check_duration_seconds",
    description="Health check duration"
)

@router.get("/health")
async def health_check(request: Request):
    start_time = time.time()

    try:
        # Your health check logic
        result = {"status": "healthy"}

        # Record metrics with labels
        request_counter.labels(status="healthy").inc()
        duration = time.time() - start_time
        request_duration.labels(status="healthy").observe(duration)

        return result
    except Exception as e:
        request_counter.labels(status="error").inc()
        raise
```

## Metrics Endpoint

The metrics endpoint is automatically available at `/metrics` (or the configured path) for Prometheus scraping:

```bash
# Scrape metrics from API server
curl http://localhost:8002/metrics

# Scrape metrics from MCP server
curl http://localhost:8003/metrics

# Scrape metrics from Worker (if metrics_port is configured)
curl http://localhost:<metrics_port>/metrics
```

### Prometheus Scraping

Metrics scraping is handled automatically by vmagents using Prometheus annotations on the pods:

- **Kube-manifest deployment config**: `prometheus.app/port: "8080"` and `prometheus.app/scrape: "true"`

These annotations are configured in the Kubernetes deployment manifests and enable automatic discovery and scraping by Prometheus.

## Metrics Reference

All metric names below are the full Prometheus metric names (meter prefix + metric name).

### Claude Code Metrics (`src/providers/telemetry/domain/claude.py`)

| Metric Name                         | Type      | Labels                                           | Description                                                                                  |
| ----------------------------------- | --------- | ------------------------------------------------ | -------------------------------------------------------------------------------------------- |
| `claude_invocations_total`          | Counter   | `agent_name`, `action`, `provider`, `status`     | Total Claude Code invocations (recorded by `@track_claude_execution` decorator)              |
| `claude_execution_duration_seconds` | Histogram | `agent_name`, `action`, `provider`, `status`     | Execution duration in seconds (recorded by decorator)                                        |
| `claude_mcp_interactions_total`     | Counter   | `mcp_name`, `action`, `status`                   | MCP server interactions                                                                      |
| `claude_tool_calls_total`           | Counter   | `tool_name`, `status`                            | Tool calls made by Claude                                                                    |
| `claude_errors_total`               | Counter   | `agent_name`, `error_type`, `action`, `provider` | Claude Code errors                                                                           |
| `claude_cost_usd_total`             | Counter   | `agent_name`, `action`, `provider`               | Total cost in USD (from `total_cost_usd`; recorded by decorator — single source of truth)    |
| `claude_code_token_usage`           | Counter   | `agent_name`, `provider`, `token_type`           | Tokens used; `token_type` is `input` or `output` (from `usage.input_tokens`/`output_tokens`) |
| `claude_code_active_time_total`     | Counter   | `agent_name`, `provider`                         | Active time in seconds (from `duration_ms / 1000`)                                           |

### HTTP Request Metrics (`src/api/middleware/metrics.py`)

| Metric Name                     | Type      | Labels                             | Description                   |
| ------------------------------- | --------- | ---------------------------------- | ----------------------------- |
| `http_requests_total`           | Counter   | `method`, `handler`, `status_code` | Total inbound HTTP requests   |
| `http_request_duration_seconds` | Histogram | `method`, `handler`, `status_code` | Inbound HTTP request duration |

### Agents Catalogue Metrics (`src/services/agents_catalogue/metrics_wrapper.py`)

| Metric Name                                         | Type      | Labels                                   | Description                      |
| --------------------------------------------------- | --------- | ---------------------------------------- | -------------------------------- |
| `agents_catalogue_agent_invocations_total`          | Counter   | `agent_name`, `execution_mode`, `status` | Agent invocations (auto-wrapped) |
| `agents_catalogue_agent_execution_duration_seconds` | Histogram | `agent_name`, `execution_mode`, `status` | Agent execution duration         |
| `agents_catalogue_agent_http_requests_total`        | Counter   | `agent_name`, `status`                   | HTTP requests made by agents     |
| `agents_catalogue_agent_db_queries_total`           | Counter   | `agent_name`, `status`                   | DB queries made by agents        |

### Dependency Instrumentation (`src/providers/telemetry/instrumentation/`)

#### Cache (`instrumentation/cache.py`)

| Metric Name                            | Type      | Labels                               | Description              |
| -------------------------------------- | --------- | ------------------------------------ | ------------------------ |
| `dependency_cache_op_duration_seconds` | Histogram | `operation`, `key_pattern`, `status` | Cache operation duration |

#### Database (`instrumentation/database.py`)

| Metric Name                            | Type      | Labels                            | Description                  |
| -------------------------------------- | --------- | --------------------------------- | ---------------------------- |
| `dependency_db_query_duration_seconds` | Histogram | `database`, `operation`, `status` | Database query duration      |
| `dependency_db_pool_connections`       | Gauge     | `database`                        | Total connections in pool    |
| `dependency_db_pool_checkedout`        | Gauge     | `database`                        | Connections currently in use |
| `dependency_db_pool_overflow`          | Gauge     | `database`                        | Overflow connections in use  |

#### External HTTP Client (`instrumentation/http_client.py`)

| Metric Name                                     | Type      | Labels                                                               | Description                |
| ----------------------------------------------- | --------- | -------------------------------------------------------------------- | -------------------------- |
| `dependency_external_api_call_duration_seconds` | Histogram | `service`, `operation`, `endpoint_template`, `method`, `status_code` | External API call duration |

#### Process (`instrumentation/process.py`)

Uses default `prometheus_client` process metrics (`process_open_fds`, `process_resident_memory_bytes`, etc.).

## Extending the System

### Future OpenTelemetry Integration

The system is designed to be extensible for future OpenTelemetry integration when packages are stable. The `Meter` class interface is designed to be compatible with OpenTelemetry's Meter interface, making migration straightforward.

### Adding a New Exporter

To add support for a new exporter (e.g., OTLP) in the future:

1. **Update `metrics.py`**:
   - Modify `initialize_metrics()` to handle the new exporter type
   - Update `Meter` class to support the new exporter backend

2. **Update Configuration**:
   - Add exporter-specific configuration section
   - Document new configuration options

3. **Update Dependencies**:
   - Add exporter package to `requirements.txt`
   - Example: `opentelemetry-exporter-otlp>=1.20.0` (when stable)

## Best Practices

1. **Meter Naming**: Use hierarchical names like `api.router`, `service.task`, `worker.queue`
2. **Metric Naming**: Follow Prometheus naming conventions:
   - Use snake_case
   - Include units in names (e.g., `_seconds`, `_bytes`, `_total`)
   - Use descriptive suffixes (`_total`, `_count`, `_sum`)
3. **Labels**: Keep label cardinality low to avoid metric explosion
4. **Resource Attributes**: Use resource attributes for service-level metadata (service name, version, environment)
5. **Error Handling**: Always handle cases where telemetry might not be initialized

## Troubleshooting

### Metrics Not Appearing

1. **Check Initialization**: Verify telemetry is enabled in configuration
2. **Check Logs**: Look for telemetry initialization messages in application logs
3. **Verify Endpoint**: Ensure metrics endpoint is mounted correctly
4. **Check Exporter**: Verify the exporter type is supported

### Common Issues

**Issue**: `RuntimeError: Metrics not initialized`

- **Solution**: Ensure `initialize_metrics(config)` is called during startup

**Issue**: Metrics endpoint returns 404

- **Solution**: Check that metrics path matches configuration and app.mount() was called

**Issue**: High cardinality warnings

- **Solution**: Reduce number of unique label combinations, use service labels for static values

**Issue**: Metric names not appearing correctly

- **Solution**: Ensure meter name is set correctly when calling `get_meter(name)`. Metric names are prefixed with the meter name.

## Future Enhancements

- [ ] OTLP exporter support for direct export to observability platforms
- [ ] Distributed tracing integration
- [ ] Automatic instrumentation for FastAPI routes
- [ ] Metrics middleware for automatic request/response metrics
- [ ] Custom metric exporters
- [ ] Metrics aggregation and sampling strategies

## References

- [Prometheus Client Python](https://github.com/prometheus/client_python)
- [Prometheus Metrics](https://prometheus.io/docs/concepts/metric_types/)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/naming/)
- [OpenTelemetry Python SDK](https://opentelemetry.io/docs/languages/python/) (for future integration)
