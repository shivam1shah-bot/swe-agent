# Migration API Endpoints

This document describes the FastAPI endpoints for managing database migrations through HTTP requests.

## Overview

The SWE Agent now provides REST API endpoints for managing database migrations, allowing you to:

- Check migration status
- Run pending migrations
- Rollback migrations to specific versions
- Get comprehensive system status

All migration endpoints are available under `/api/admin/` and require the application to be running.

## Endpoints

### 1. Get Migration Status

**GET** `/api/admin/migrations/status`

Returns the current status of database migrations.

#### Response

```json
{
  "current_version": 2,
  "latest_version": 2,
  "applied_count": 2,
  "available_count": 2,
  "pending_count": 0,
  "up_to_date": true,
  "applied_migrations": [1, 2],
  "pending_migrations": []
}
```

#### Example Usage

```bash
# Using curl
curl -X GET "http://localhost:8002/api/admin/migrations/status"

# Using httpie
http GET localhost:8002/api/admin/migrations/status
```

### 2. Run Pending Migrations

**POST** `/api/admin/migrations/run`

Executes all pending database migrations.

#### Response

```json
{
  "success": true,
  "message": "Successfully applied 1 migrations",
  "migrations_applied": 1,
  "total_migrations": 1,
  "duration_ms": 125.34,
  "timestamp": 1672531200.123
}
```

#### Example Usage

```bash
# Using curl
curl -X POST "http://localhost:8002/api/admin/migrations/run"

# Using httpie
http POST localhost:8002/api/admin/migrations/run
```

### 3. Rollback Migrations

**POST** `/api/admin/migrations/rollback/{target_version}`

Rolls back migrations to a specific version.

#### Parameters

- `target_version` (path parameter): The version number to rollback to

#### Response

```json
{
  "success": true,
  "message": "Successfully rolled back 1 migrations to version 1",
  "rollback_to_version": 1,
  "migrations_rolled_back": 1,
  "duration_ms": 89.56,
  "timestamp": 1672531200.123
}
```

#### Example Usage

```bash
# Rollback to version 1
curl -X POST "http://localhost:8002/api/admin/migrations/rollback/1"

# Using httpie
http POST localhost:8002/api/admin/migrations/rollback/1
```

### 4. Admin Info

**GET** `/api/admin/info`

Returns information about all available admin endpoints.

#### Response

```json
{
  "admin_endpoints": {
    "migration_status": {
      "method": "GET",
      "path": "/api/admin/migrations/status",
      "description": "Get current migration status"
    },
    "run_migrations": {
      "method": "POST",
      "path": "/api/admin/migrations/run",
      "description": "Run pending migrations"
    },
    "rollback_migrations": {
      "method": "POST",
      "path": "/api/admin/migrations/rollback/{target_version}",
      "description": "Rollback migrations to specific version"
    }
  },
  "timestamp": 1672531200.123
}
```

## Usage Examples

### Basic Migration Workflow

```bash
# 1. Check current migration status
curl -X GET "http://localhost:8002/api/admin/migrations/status"

# 2. Run pending migrations (if any)
curl -X POST "http://localhost:8002/api/admin/migrations/run"

# 3. Verify migrations completed
curl -X GET "http://localhost:8002/api/admin/migrations/status"
```

### Rollback Workflow

```bash
# 1. Check current status
curl -X GET "http://localhost:8002/api/admin/migrations/status"

# 2. Rollback to previous version
curl -X POST "http://localhost:8002/api/admin/migrations/rollback/1"

# 3. Verify rollback completed
curl -X GET "http://localhost:8002/api/admin/migrations/status"
```

## Integration with Scripts

You can integrate these API endpoints with deployment scripts or automation tools:

### Python Example

```python
import requests
import time

def run_migrations(base_url="http://localhost:8002"):
    """Run migrations via API."""

    # Check status
    status_response = requests.get(f"{base_url}/api/admin/migrations/status")
    status = status_response.json()

    print(f"Current version: {status['current_version']}")
    print(f"Pending migrations: {status['pending_count']}")

    if status['pending_count'] > 0:
        # Run migrations
        print("Running migrations...")
        run_response = requests.post(f"{base_url}/api/admin/migrations/run")
        result = run_response.json()

        if result['success']:
            print(f"✅ Successfully applied {result['migrations_applied']} migrations")
            print(f"Duration: {result['duration_ms']}ms")
        else:
            print(f"❌ Migration failed: {result['message']}")
            return False
    else:
        print("✅ No pending migrations")

    return True

# Usage
if __name__ == "__main__":
    run_migrations()
```

### Shell Script Example

```bash
#!/bin/bash

API_BASE="http://localhost:8002"

# Function to check migration status
check_migrations() {
    echo "Checking migration status..."
    curl -s -X GET "$API_BASE/api/admin/migrations/status" | jq '.'
}

# Function to run migrations
run_migrations() {
    echo "Running migrations..."
    RESULT=$(curl -s -X POST "$API_BASE/api/admin/migrations/run")
    echo "$RESULT" | jq '.'

    SUCCESS=$(echo "$RESULT" | jq -r '.success')
    if [ "$SUCCESS" = "true" ]; then
        echo "✅ Migrations completed successfully"
        return 0
    else
        echo "❌ Migrations failed"
        return 1
    fi
}

# Main workflow
check_migrations
run_migrations
check_migrations
```

## Error Handling

All endpoints return appropriate HTTP status codes:

- **200 OK**: Success
- **500 Internal Server Error**: Migration operation failed
- **503 Service Unavailable**: Database not available

Error responses include detailed error messages:

```json
{
  "detail": "Failed to run migrations: Connection refused"
}
```

## Security Considerations

⚠️ **Important**: These admin endpoints should be protected in production environments:

1. **Network Security**: Restrict access to admin endpoints via firewall rules
2. **Authentication**: Add authentication middleware for admin routes
3. **Authorization**: Implement role-based access control
4. **Monitoring**: Log all migration operations for audit trails

## Interactive Documentation

When the application is running, you can access interactive API documentation at:

- **Swagger UI**: `http://localhost:8002/docs`
- **ReDoc**: `http://localhost:8002/redoc`

The admin endpoints will be listed under the "admin" tag in the interactive documentation.
