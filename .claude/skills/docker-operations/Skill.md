---
name: Docker Operations
description: Manage and troubleshoot Docker-based development environments for SWE Agent
version: 1.0.0
---

## Overview

This skill covers Docker and Docker Compose operations for the SWE Agent platform, including container management, networking, troubleshooting, and best practices for development and production environments.

**When to Use This Skill:**
- Setting up development environment
- Troubleshooting container issues
- Managing multi-container applications
- Optimizing Docker configurations
- Debugging networking problems
- Performance tuning

## SWE Agent Docker Architecture

### Services Overview

```yaml
services:
  # Core Application Services
  api:          # FastAPI application server (port 28002)
  ui:           # React frontend application (port 28001)
  worker:       # Background task processor

  # Infrastructure Services
  db:           # MySQL database (port 23306)
  redis:        # Redis cache (port 26379)
  localstack:   # AWS LocalStack for SQS (port 4566)
```

### Network Architecture

```
Docker Network: swe-agent-network
    ├── api (swe-agent-api)
    ├── ui (swe-agent-ui)
    ├── worker (swe-agent-worker)
    ├── db (swe-agent-db)
    ├── redis (swe-agent-redis)
    └── localstack (swe-agent-localstack)
```

## Common Operations

### Starting Services

```bash
# Complete setup and start (recommended for first time)
./scripts/start_service.sh

# Start all services
make start
# or
docker-compose up -d

# Start specific service
docker-compose up -d api
docker-compose up -d worker

# Start with rebuild
make rebuild
# or
docker-compose up -d --build
```

### Stopping Services

```bash
# Stop all services
make stop
# or
docker-compose down

# Stop and remove volumes (clean slate)
docker-compose down -v

# Stop specific service
docker-compose stop api
```

### Restarting Services

```bash
# Restart app containers only (keeps DB, Redis, LocalStack running)
make restart

# Restart all services including infrastructure
make restart-all

# Restart specific service
docker-compose restart api
docker-compose restart worker
```

### Viewing Logs

```bash
# All logs
make logs
# or
docker-compose logs

# Tail logs (follow)
make logs-tail
# or
docker-compose logs -f

# Specific service logs
docker-compose logs api
docker-compose logs worker
docker-compose logs -f api  # Follow API logs

# Last N lines
docker-compose logs --tail=100 api
```

### Service Status

```bash
# Check system status
make status

# List running containers
docker-compose ps

# Detailed container info
docker inspect swe-agent-api
docker inspect swe-agent-worker
```

## Troubleshooting

### Container Not Starting

#### Check Container Status
```bash
# List all containers (including stopped)
docker-compose ps -a

# Check container logs for errors
docker-compose logs api
docker-compose logs worker

# Inspect container
docker inspect swe-agent-api
```

#### Common Causes

**1. Port Already in Use**
```bash
# Check what's using a port
lsof -i :28001  # UI port
lsof -i :28002  # API port
lsof -i :23306  # DB port

# Solution: Stop conflicting process or change port in docker-compose.yml
docker-compose down
# Kill the process using the port
kill -9 <PID>
# Restart
docker-compose up -d
```

**2. Volume Mount Errors**
```bash
# Check volume mounts
docker inspect swe-agent-api | grep -A 10 Mounts

# Verify paths exist
ls -la /path/to/mounted/directory

# Fix: Ensure directory exists and has correct permissions
mkdir -p /path/to/directory
chmod 755 /path/to/directory
```

**3. Build Failures**
```bash
# Rebuild with no cache
docker-compose build --no-cache api

# Build specific service
docker-compose build worker

# View build output
docker-compose up --build api
```

### Networking Issues

#### Container Can't Communicate

```bash
# Check network
docker network ls
docker network inspect swe-agent-network

# Verify containers are on same network
docker inspect swe-agent-api | grep NetworkMode
docker inspect swe-agent-db | grep NetworkMode

# Test connectivity between containers
docker exec swe-agent-api ping swe-agent-db
docker exec swe-agent-api nc -zv swe-agent-redis 6379

# Solution: Ensure all services use same network in docker-compose.yml
networks:
  swe-agent-network:
    driver: bridge
```

#### DNS Resolution Problems

```bash
# Test DNS inside container
docker exec swe-agent-api nslookup swe-agent-db
docker exec swe-agent-api getent hosts swe-agent-redis

# Check /etc/hosts inside container
docker exec swe-agent-api cat /etc/hosts

# Restart Docker daemon if needed (as last resort)
sudo systemctl restart docker
```

### Database Connection Issues

#### MySQL Connection Refused

```bash
# Check if MySQL is running
docker-compose ps db

# Check MySQL logs
docker-compose logs db

# Test connection from API container
docker exec swe-agent-api nc -zv swe-agent-db 3306

# Connect to MySQL directly
docker exec -it swe-agent-db mysql -u root -p

# Verify environment variables
docker exec swe-agent-api env | grep MYSQL
docker exec swe-agent-api env | grep DATABASE
```

#### Migration Failures

```bash
# Check migration logs
docker-compose logs worker | grep migration

# Run migrations manually
docker exec -it swe-agent-worker python -m src.migrations.run_migrations

# Reset database (development only!)
docker-compose down -v
docker volume rm swe-agent_mysql_data
docker-compose up -d db
# Wait for DB to initialize
sleep 10
docker-compose up -d worker  # Runs migrations
```

### Redis Connection Issues

```bash
# Check if Redis is running
docker-compose ps redis

# Test Redis connection
docker exec swe-agent-api redis-cli -h swe-agent-redis ping

# Check Redis logs
docker-compose logs redis

# Connect to Redis CLI
docker exec -it swe-agent-redis redis-cli

# Inside Redis CLI
ping
keys *
info
```

### LocalStack (SQS) Issues

```bash
# Check LocalStack status
docker-compose logs localstack

# Check SQS queues
aws --endpoint-url=http://localhost:4566 sqs list-queues

# Create queue manually if needed
aws --endpoint-url=http://localhost:4566 sqs create-queue --queue-name swe-agent-tasks

# Verify queue exists
docker exec swe-agent-worker aws --endpoint-url=http://localstack:4566 sqs list-queues
```

### Worker Not Processing Tasks

```bash
# Check worker status
docker-compose ps worker

# View worker logs
docker-compose logs -f worker

# Check worker is connecting to queue
docker-compose logs worker | grep SQS
docker-compose logs worker | grep queue

# Restart worker
docker-compose restart worker

# Check environment variables
docker exec swe-agent-worker env | grep SQS
docker exec swe-agent-worker env | grep AWS
```

## Performance Optimization

### Container Resource Limits

```yaml
# docker-compose.yml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 1G

  worker:
    deploy:
      resources:
        limits:
          cpus: '4.0'
          memory: 4G
        reservations:
          cpus: '2.0'
          memory: 2G
```

### Check Resource Usage

```bash
# View container stats
docker stats

# Specific container stats
docker stats swe-agent-api swe-agent-worker

# JSON output
docker stats --no-stream --format "{{json .}}" swe-agent-api
```

### Volume Performance

```bash
# Check volume disk usage
docker system df -v

# Clean up unused volumes
docker volume prune

# Optimize database volume (if using named volume)
docker volume inspect swe-agent_mysql_data
```

## Development Workflows

### Hot Reload Development

```bash
# API with hot reload
docker-compose up -d db redis localstack  # Start infrastructure
# Run API locally with hot reload
make api-local

# UI with hot reload
cd ui && npm run dev

# Worker with hot reload
make worker-local
```

### Running Tests in Containers

```bash
# Run all tests
docker-compose run --rm api pytest

# Run specific test file
docker-compose run --rm api pytest tests/unit/test_task_service.py

# Run with coverage
docker-compose run --rm api pytest --cov=src --cov-report=html

# Run in parallel
docker-compose run --rm api pytest -n auto
```

### Debugging Inside Containers

```bash
# Get shell in running container
docker exec -it swe-agent-api /bin/bash
docker exec -it swe-agent-worker /bin/bash

# Run one-off command
docker-compose run --rm api python -c "import src; print(src.__version__)"

# Check Python environment
docker exec swe-agent-api python --version
docker exec swe-agent-api pip list

# Check file system
docker exec swe-agent-api ls -la /app/src
docker exec swe-agent-api cat /app/environments/env.dev_docker.toml
```

### Environment Variables

```bash
# View all environment variables in container
docker exec swe-agent-api env

# Check specific variable
docker exec swe-agent-api env | grep DATABASE_URL
docker exec swe-agent-api printenv REDIS_URL

# Set environment variable for single command
docker-compose run --rm -e DEBUG=true api python script.py
```

## Docker Compose Best Practices

### Health Checks

```yaml
services:
  db:
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s

  api:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
```

### Dependency Management

```yaml
services:
  api:
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
      localstack:
        condition: service_started

  worker:
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
      localstack:
        condition: service_started
```

### Environment Files

```yaml
services:
  api:
    env_file:
      - .env
      - .env.local  # Override with local settings
    environment:
      - ENV=dev_docker
      - LOG_LEVEL=INFO
```

## Maintenance

### Cleanup

```bash
# Remove stopped containers
docker-compose rm

# Remove all unused containers, networks, images
docker system prune

# Remove all unused volumes
docker volume prune

# Complete cleanup (careful!)
docker system prune -a --volumes

# Clean up SWE Agent specifically
docker-compose down -v
docker system prune -f
```

### Backup and Restore

#### Backup Database

```bash
# Backup MySQL database
docker exec swe-agent-db mysqldump -u root -p<password> swe_agent > backup.sql

# Backup with docker-compose
docker-compose exec db mysqldump -u root -p<password> swe_agent > backup_$(date +%Y%m%d).sql
```

#### Restore Database

```bash
# Restore from backup
docker exec -i swe-agent-db mysql -u root -p<password> swe_agent < backup.sql

# Or with docker-compose
docker-compose exec -T db mysql -u root -p<password> swe_agent < backup.sql
```

#### Backup Volumes

```bash
# Backup volume to tar
docker run --rm \
  -v swe-agent_mysql_data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/mysql_data_backup.tar.gz -C /data .

# Restore volume from tar
docker run --rm \
  -v swe-agent_mysql_data:/data \
  -v $(pwd):/backup \
  alpine tar xzf /backup/mysql_data_backup.tar.gz -C /data
```

### Updates and Rebuilds

```bash
# Pull latest images
docker-compose pull

# Rebuild after code changes
docker-compose up -d --build api worker

# Force rebuild (no cache)
docker-compose build --no-cache api
docker-compose up -d api

# Update specific service
docker-compose build api
docker-compose up -d api
```

## Production Considerations

### Multi-Stage Builds

```dockerfile
# Dockerfile for API
FROM python:3.11-slim as builder

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# Final stage
FROM python:3.11-slim

WORKDIR /app

# Copy wheels and install
COPY --from=builder /app/wheels /wheels
RUN pip install --no-cache /wheels/*

# Copy application code
COPY src/ /app/src/
COPY environments/ /app/environments/

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Security Hardening

```dockerfile
# Run as non-root user
RUN addgroup --system app && adduser --system --group app
USER app

# Read-only root filesystem
docker run --read-only --tmpfs /tmp swe-agent-api

# Drop capabilities
docker run --cap-drop=ALL --cap-add=NET_BIND_SERVICE swe-agent-api
```

### Logging Configuration

```yaml
services:
  api:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
        labels: "service=api"
```

## Integration with Make Commands

The SWE Agent project uses Make for simplified Docker operations:

```makefile
# From Makefile
start:
    docker-compose up -d

stop:
    docker-compose down

restart:
    docker-compose restart api ui worker

rebuild:
    docker-compose down
    docker-compose build --no-cache
    docker-compose up -d

status:
    docker-compose ps
    curl -f http://localhost:28002/health || echo "API unhealthy"

logs:
    docker-compose logs --tail=100

logs-tail:
    docker-compose logs -f
```

## Common Docker Commands Reference

```bash
# Container Management
docker ps                           # List running containers
docker ps -a                        # List all containers
docker start <container>            # Start container
docker stop <container>             # Stop container
docker restart <container>          # Restart container
docker rm <container>               # Remove container
docker exec -it <container> bash    # Shell into container

# Image Management
docker images                       # List images
docker build -t name:tag .          # Build image
docker rmi <image>                  # Remove image
docker pull <image>                 # Pull image

# Network Management
docker network ls                   # List networks
docker network inspect <network>    # Inspect network
docker network create <network>     # Create network

# Volume Management
docker volume ls                    # List volumes
docker volume inspect <volume>      # Inspect volume
docker volume rm <volume>           # Remove volume

# System Management
docker system df                    # Show disk usage
docker system prune                 # Clean up unused resources
docker stats                        # Show container stats
```

## Reference

- Docker Compose file: `docker-compose.yml`
- Dockerfiles: `Dockerfile.api`, `Dockerfile.worker`, `ui/Dockerfile`
- Startup script: `scripts/start_service.sh`
- Makefile: `Makefile`
- Environment config: `environments/env.dev_docker.toml`
