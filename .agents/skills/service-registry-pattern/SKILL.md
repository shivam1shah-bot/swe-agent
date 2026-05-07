---
name: service-registry-pattern
description: Dynamic service registration and discovery for agents catalogue
version: 1.0.0
tags: [registry, service-discovery, agents-catalogue, patterns]
context: codebase
---

# Service Registry Pattern

## Overview

SWE Agent uses a dynamic service registry pattern for the agents catalogue. Services self-register on startup, enabling runtime discovery, health monitoring, and metrics tracking.

**Purpose**: Decouple service implementation from service consumption, enable dynamic service management

**Pattern**: Registry + Decorator + Metrics Wrapper

**Key Components**:
- **ServiceRegistry** (`src/services/agents_catalogue/registry.py`) - Central registry
- **BaseAgentsCatalogueService** - Base class for services
- **@register_service()** - Decorator for automatic registration
- **Metrics Wrapper** - Automatic Prometheus metrics

## Architecture

### Service Registry Structure

```python
class ServiceRegistry:
    _services: Dict[str, ServiceRegistration]  # service_name → registration
    _health_check_interval: int = 300          # 5 minutes

    def register(service_name, service_class)  # Register service
    def get_service(service_name)              # Get service instance
    def list_services()                        # List all services
    def get_service_info(service_name)         # Get service metadata
    def update_service_metrics(...)            # Track execution metrics
    def get_registry_health()                  # Health status
```

**ServiceRegistration** (per service):
```python
@dataclass
class ServiceRegistration:
    name: str                      # Service name (e.g., "autonomous-agent")
    service_class: Type            # Service class
    instance: Any                  # Singleton instance
    registered_at: datetime        # Registration timestamp
    health_status: str             # "healthy", "degraded", "unhealthy"
    last_health_check: datetime    # Last health check time
    metrics: ServiceMetrics        # Execution metrics
    description: str               # Service description
    capabilities: List[str]        # Service capabilities
    version: str                   # Service version
```

**ServiceMetrics** (per service):
```python
@dataclass
class ServiceMetrics:
    total_executions: int          # Total times executed
    successful_executions: int     # Successful executions
    failed_executions: int         # Failed executions
    total_execution_time: float    # Total time spent
    average_execution_time: float  # Average execution time
    error_rate: float              # Error percentage
    last_execution: datetime       # Last execution timestamp
```

## Pattern 1: Service Registration

### Decorator-Based Registration

**Recommended Method**:
```python
from src.services.agents_catalogue.registry import register_service
from src.services.agents_catalogue.base_service import BaseAgentsCatalogueService

@register_service("my-service")
class MyService(BaseAgentsCatalogueService):
    @property
    def description(self) -> str:
        return "My service description"

    @property
    def capabilities(self) -> List[str]:
        return ["capability1", "capability2"]

    @property
    def version(self) -> str:
        return "1.0.0"

    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        # Synchronous execution (queues task)
        return {"status": "queued", "task_id": "..."}

    async def async_execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        # Asynchronous execution (processes task)
        result = await self.do_work(parameters)
        return {"status": "completed", "result": result}
```

**What Happens on Registration**:

1. **Service Instantiation**:
   ```python
   service_instance = service_class()
   ```

2. **Metrics Wrapper Applied**:
   - `execute()` wrapped with `track_agent_execution()`
   - `async_execute()` wrapped with `track_agent_execution()`
   - Automatic Prometheus metrics (invocation count, duration, errors)

3. **Metadata Extraction**:
   ```python
   description = service_instance.description
   capabilities = service_instance.capabilities
   version = service_instance.version
   ```

4. **Health Check Performed**:
   - Check instance exists
   - Verify `execute()` method exists
   - Set initial health status: "healthy"

5. **Registration Stored**:
   ```python
   service_registry._services[service_name] = ServiceRegistration(...)
   ```

### Manual Registration (Alternative)

```python
from src.services.agents_catalogue.registry import service_registry

class MyService(BaseAgentsCatalogueService):
    pass

# Register manually
service_registry.register("my-service", MyService)
```

## Pattern 2: Service Discovery

### Getting Service Instance

**By Service Name**:
```python
from src.services.agents_catalogue.registry import service_registry

# Get service
service = service_registry.get_service("autonomous-agent")

if service:
    result = service.execute(parameters)
else:
    # Handle service not found
    raise ValueError("Service not found")
```

**By Use Case** (alias):
```python
from src.services.agents_catalogue.registry import get_service_for_usecase

service = get_service_for_usecase("autonomous-agent")
```

### Listing Services

**All Services**:
```python
service_names = service_registry.list_services()
# Returns: ["autonomous-agent", "gateway-integration", "qcc-onboarding", ...]
```

**Service Info**:
```python
info = service_registry.get_service_info("autonomous-agent")
# Returns:
{
    "name": "autonomous-agent",
    "description": "Execute autonomous agent tasks",
    "capabilities": ["code-generation", "bug-fixing"],
    "version": "1.0.0",
    "class": "AutonomousAgentService",
    "registered_at": "2025-02-10T12:00:00",
    "health_status": "healthy",
    "last_health_check": "2025-02-10T12:05:00",
    "metrics": {
        "total_executions": 42,
        "successful_executions": 40,
        "failed_executions": 2,
        "error_rate": 4.76,
        "average_execution_time": 120.5,
        "last_execution": "2025-02-10T12:04:30"
    }
}
```

**All Services Info**:
```python
all_info = service_registry.get_all_services_info()
# Returns: Dict[service_name, service_info]
```

## Pattern 3: Health Monitoring

### Service Health Checks

**Health Status Levels**:
- **"healthy"** - Service functioning normally
- **"degraded"** - Service has issues but operational (error rate 20-50%, or slow)
- **"unhealthy"** - Service not functioning (error rate >50%, or missing required methods)

**Health Check Criteria**:

1. **Instance Exists**: Service instance must be valid
2. **Required Methods**: Must have `execute()` method
3. **Error Rate**:
   - < 20% → healthy
   - 20-50% → degraded
   - \> 50% → unhealthy
4. **Performance**:
   - Average execution time > 600s → degraded

**Automatic Health Checks**:
- Performed every 5 minutes (configurable)
- Triggered on `get_service()` if interval elapsed
- Registry-wide check available

**Health Check on Service Retrieval**:
```python
service = service_registry.get_service("my-service")
# Automatically performs health check if 5+ minutes since last check
# Returns instance even if unhealthy (logs warning)
```

### Registry Health

**Overall Health**:
```python
health = service_registry.get_registry_health()
# Returns:
{
    "status": "healthy",  # or "degraded", "unhealthy"
    "timestamp": "2025-02-10T12:00:00",
    "total_services": 5,
    "healthy_services": 4,
    "degraded_services": 1,
    "unhealthy_services": 0,
    "last_health_check": "2025-02-10T12:00:00",
    "service_details": {
        "autonomous-agent": {
            "status": "healthy",
            "last_check": "2025-02-10T12:00:00"
        },
        ...
    }
}
```

**Status Rules**:
- **healthy**: All services healthy
- **degraded**: Any service degraded, none unhealthy
- **unhealthy**: Any service unhealthy

## Pattern 4: Metrics Tracking

### Automatic Metrics (via Wrapper)

**What Gets Tracked**:
- Invocation count (total, success, failure)
- Execution duration (total, average)
- Error rate percentage
- Last execution timestamp

**Prometheus Metrics**:
```python
# Auto-generated metrics for each service
agent_execution_total{agent="autonomous-agent", status="success"}
agent_execution_total{agent="autonomous-agent", status="failure"}
agent_execution_duration_seconds{agent="autonomous-agent"}
```

**How It Works**:
```python
# On registration, execute() wrapped like this:
@track_agent_execution(agent_name, "sync")
def execute(self, parameters):
    # Original execute logic
    pass

# Wrapper records:
# - Start time
# - Success/failure
# - End time
# - Updates metrics
```

### Manual Metrics Update

**Direct Update**:
```python
from src.services.agents_catalogue.registry import update_service_metrics

update_service_metrics(
    service_name="my-service",
    success=True,
    execution_time=42.5  # seconds
)
```

**In Service Implementation**:
```python
async def async_execute(self, parameters):
    start_time = time.time()
    try:
        result = await self.do_work(parameters)
        execution_time = time.time() - start_time

        # Manual update (only if wrapper not applied)
        update_service_metrics(self.name, success=True, execution_time)

        return {"status": "completed", "result": result}
    except Exception as e:
        execution_time = time.time() - start_time
        update_service_metrics(self.name, success=False, execution_time)
        raise
```

### Aggregated Metrics

**Registry Metrics**:
```python
metrics = service_registry.get_registry_metrics()
# Returns:
{
    "timestamp": "2025-02-10T12:00:00",
    "overall": {
        "total_executions": 250,
        "successful_executions": 240,
        "failed_executions": 10,
        "overall_error_rate": 4.0,
        "overall_avg_execution_time": 95.3
    },
    "by_service": {
        "autonomous-agent": {
            "executions": 100,
            "success_rate": 96.0,
            "error_rate": 4.0,
            "avg_execution_time": 120.5,
            "last_execution": "2025-02-10T11:59:00"
        },
        ...
    },
    "registry": {
        "total_services": 5,
        "active_services": 5
    }
}
```

## Pattern 5: Service Lifecycle

### Service Registration Flow

```
1. Service Class Defined
   ↓
2. @register_service() decorator applied
   ↓
3. Service instantiated (singleton per service)
   ↓
4. Metrics wrapper applied to execute()/async_execute()
   ↓
5. Metadata extracted (description, capabilities, version)
   ↓
6. Initial health check performed
   ↓
7. ServiceRegistration created and stored
   ↓
8. Service ready for use
```

### Service Execution Flow

```
1. API receives request for service
   ↓
2. Get service from registry: get_service(service_name)
   ↓
3. Health check performed (if interval elapsed)
   ↓
4. Service instance returned
   ↓
5. Execute method called: service.execute(parameters)
   ↓
6. Metrics wrapper tracks start time
   ↓
7. Service logic executes
   ↓
8. Metrics wrapper records result (success/failure, duration)
   ↓
9. Metrics updated in ServiceRegistration
   ↓
10. Result returned to caller
```

### Service Unregistration

**Manual Unregister**:
```python
success = service_registry.unregister("my-service")
# Returns: True if unregistered, False if not found
```

**Use Cases**:
- Hot reloading service implementations
- Removing deprecated services
- Testing (cleanup after tests)

## Adding New Service to Registry

### Step-by-Step Guide

**1. Create Service Class** (`src/services/agents_catalogue/my_service/service.py`):
```python
from typing import Dict, Any
from ..base_service import BaseAgentsCatalogueService
from ..registry import register_service

@register_service("my-service")
class MyService(BaseAgentsCatalogueService):
    @property
    def description(self) -> str:
        return "My service description"

    @property
    def capabilities(self) -> List[str]:
        return ["capability1", "capability2"]

    @property
    def version(self) -> str:
        return "1.0.0"

    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        # Sync execute: queue task and return immediately
        # Validate parameters
        # Queue to SQS
        # Return task_id
        return {"status": "queued", "task_id": task_id}

    async def async_execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        # Async execute: called by worker to process task
        # Perform actual work
        result = await self.do_work(parameters)
        return {"status": "completed", "result": result}
```

**2. Import Service in __init__.py** (`src/services/agents_catalogue/my_service/__init__.py`):
```python
from .service import MyService  # noqa: F401
```

**3. Register in Module** (ensure import happens on startup):
```python
# In src/services/agents_catalogue/__init__.py or app startup
from .my_service import MyService  # Triggers @register_service()
```

**4. Verify Registration**:
```python
from src.services.agents_catalogue.registry import service_registry

# List services
services = service_registry.list_services()
assert "my-service" in services

# Get service info
info = service_registry.get_service_info("my-service")
print(info)
```

**5. Add API Route** (`src/api/routers/agents_catalogue.py`):
```python
@router.post("/agents-catalogue/my-service")
async def execute_my_service(request: MyServiceRequest):
    service = service_registry.get_service("my-service")
    result = service.execute(request.dict())
    return result
```

## API Integration

### Agents Catalogue Router

**List Services** (`GET /api/agents-catalogue/services`):
```python
@router.get("/services")
async def list_services():
    return service_registry.get_all_services_info()
```

**Get Service Info** (`GET /api/agents-catalogue/services/{service_name}`):
```python
@router.get("/services/{service_name}")
async def get_service_info(service_name: str):
    info = service_registry.get_service_info(service_name)
    if not info:
        raise HTTPException(status_code=404, detail="Service not found")
    return info
```

**Execute Service** (`POST /api/agents-catalogue/{service_name}/execute`):
```python
@router.post("/{service_name}/execute")
async def execute_service(service_name: str, parameters: Dict[str, Any]):
    service = service_registry.get_service(service_name)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    result = service.execute(parameters)
    return result
```

**Registry Health** (`GET /api/agents-catalogue/health`):
```python
@router.get("/health")
async def get_registry_health():
    return service_registry.get_registry_health()
```

**Registry Metrics** (`GET /api/agents-catalogue/metrics`):
```python
@router.get("/metrics")
async def get_registry_metrics():
    return service_registry.get_registry_metrics()
```

## Best Practices

### Service Naming
- Use kebab-case: `autonomous-agent`, `gateway-integration`
- Be descriptive: Avoid generic names like `service-1`
- Match use case: Service name should reflect its purpose

### Service Implementation
- **Always inherit from `BaseAgentsCatalogueService`**
- **Implement both `execute()` and `async_execute()`**
- **Set `description`, `capabilities`, `version` properties**
- **Use early error handling** with guard clauses
- **Include comprehensive type hints**

### Error Handling
- **Validate parameters** in `execute()` before queuing
- **Handle errors gracefully** in `async_execute()`
- **Update task status** on failures
- **Log errors** with context

### Health & Metrics
- **Don't manually update metrics** (wrapper does it automatically)
- **Monitor health status** in production
- **Set up alerts** for degraded/unhealthy services
- **Review error rates** periodically

## Monitoring & Debugging

### View Registry State

```python
# Get all services
from src.services.agents_catalogue.registry import service_registry

services = service_registry.list_services()
print(f"Registered services: {services}")

# Get health status
health = service_registry.get_registry_health()
print(f"Registry health: {health['status']}")

# Get metrics
metrics = service_registry.get_registry_metrics()
print(f"Total executions: {metrics['overall']['total_executions']}")
```

### Logs

```bash
# View service registration logs
grep "Successfully registered service" tmp/logs/api.log

# View health check logs
grep "health status changed" tmp/logs/api.log

# View metrics updates
grep "Updated metrics for service" tmp/logs/api.log
```

### API Endpoints

```bash
# List all services
curl http://localhost:28002/api/agents-catalogue/services

# Get service info
curl http://localhost:28002/api/agents-catalogue/services/autonomous-agent

# Check registry health
curl http://localhost:28002/api/agents-catalogue/health

# Get registry metrics
curl http://localhost:28002/api/agents-catalogue/metrics
```

## Key Files

- `src/services/agents_catalogue/registry.py` - Service registry implementation
- `src/services/agents_catalogue/base_service.py` - Base service class
- `src/services/agents_catalogue/metrics_wrapper.py` - Metrics tracking wrapper
- `src/api/routers/agents_catalogue.py` - API routes for catalogue
- `src/services/agents_catalogue/*/service.py` - Individual service implementations

## Testing

```bash
# Unit tests
pytest tests/unit/services/agents_catalogue/test_registry.py

# Integration tests
pytest tests/integration/test_service_registry.py

# Test service registration
pytest tests/unit/services/agents_catalogue/test_service_registration.py
```
