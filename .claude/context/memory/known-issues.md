# Known Issues and Workarounds

## Infrastructure Issues

### Docker Container Networking
**Issue**: Containers may fail to communicate when using service names
**Workaround**:
- Ensure all services are on the same Docker network
- Check `docker-compose.yml` network configuration
- Use `docker network ls` and `docker network inspect` to verify

### LocalStack SQS Configuration
**Issue**: SQS queues may not persist between container restarts
**Workaround**:
- Recreate queues on worker startup
- Check `src/providers/queue/sqs_provider.py` initialization
- Verify LocalStack health before starting worker

## Development Environment

### Python Virtual Environment
**Issue**: Dependencies may conflict between system and venv packages
**Workaround**:
- Always activate venv before running commands: `source venv/bin/activate`
- Use `make setup` to ensure clean environment
- Keep `requirements.txt` and `requirements-dev.txt` in sync

### Port Conflicts
**Issue**: Default ports may already be in use
**Workaround**:
- Check for conflicts: `lsof -i :8001`, `lsof -i :8002`
- Update port mappings in `docker-compose.yml` if needed
- Use environment-specific configuration in `environments/`

## Database and Migrations

### Migration Version Conflicts
**Issue**: Migration scripts may run out of order or conflict
**Workaround**:
- Check current migration version in database
- Review migration scripts in `src/migrations/scripts/`
- Manually resolve conflicts if needed
- Consider fresh database for development

### SQLAlchemy Session Management
**Issue**: Session leaks or stale sessions
**Workaround**:
- Always use context managers for sessions
- Ensure proper session cleanup in finally blocks
- Check `src/providers/database/db_provider.py` session factory

## Agent System

### Claude Code CLI Streaming
**Issue**: Streaming may buffer or timeout on long-running tasks
**Workaround**:
- Monitor output in real-time using `src/agents/terminal_agents/claude_code.py`
- Adjust timeout settings in agent configuration
- Check for process zombies: `ps aux | grep claude`

### MCP Server Configuration
**Issue**: MCP servers may fail to initialize or timeout
**Workaround**:
- Verify MCP configuration in `src/providers/mcp/mcp-servers.json`
- Check server logs for initialization errors
- Ensure required environment variables are set
- Test MCP servers independently before integration

### Task Cancellation
**Issue**: Tasks may not cancel immediately due to agent processing
**Workaround**:
- Check task status in database
- Use `SWEAgentWorker._should_cancel()` to verify cancellation state
- Force cleanup if needed via worker management commands

## Testing

### Test Database Isolation
**Issue**: Tests may interfere with each other due to shared database state
**Workaround**:
- Use test fixtures with proper setup/teardown
- Consider test database per test class
- Review `tests/config/pytest.ini` configuration

### Async Test Execution
**Issue**: Async tests may hang or timeout
**Workaround**:
- Ensure pytest-asyncio is properly configured
- Check for blocking operations in async functions
- Use `asyncio.wait_for()` with appropriate timeouts

### Mock Configuration
**Issue**: Mocks may not properly isolate external dependencies
**Workaround**:
- Review mock providers in `tests/mocks/`
- Ensure mocks match actual provider interfaces
- Verify mock setup in test fixtures

## GitHub Integration

### Authentication Tokens
**Issue**: GitHub tokens may expire or have insufficient permissions
**Workaround**:
- Regenerate personal access token with required scopes
- Update token in configuration
- Verify permissions: repo, workflow, admin:org

### Rate Limiting
**Issue**: GitHub API rate limits may be exceeded
**Workaround**:
- Use authenticated requests (higher rate limit)
- Implement caching for frequently accessed data
- Add retry logic with exponential backoff

## Performance

### N+1 Query Issues
**Issue**: Repository methods may trigger N+1 query patterns
**Workaround**:
- Use SQLAlchemy eager loading: `joinedload()`, `selectinload()`
- Batch fetch operations where possible
- Profile queries using SQLAlchemy query logging

### Memory Leaks
**Issue**: Long-running workers may accumulate memory
**Workaround**:
- Implement periodic worker restarts
- Profile memory usage with `memory_profiler`
- Ensure proper cleanup of large objects

## Logging

### Log Volume
**Issue**: Logs in `tmp/logs/` may grow large quickly
**Workaround**:
- Implement log rotation
- Adjust log levels for production (INFO vs DEBUG)
- Use structured logging with proper filtering

### Sensitive Data in Logs
**Issue**: Logs may inadvertently contain secrets or PII
**Workaround**:
- Use sanitization in `src/utils/logging.py`
- Review log statements for sensitive data
- Implement log scrubbing before external transmission

## Common Error Messages

### "No module named 'X'"
**Cause**: Missing dependency or incorrect Python path
**Solution**: `pip install -r requirements.txt` or check PYTHONPATH

### "Connection refused" errors
**Cause**: Service not running or incorrect host/port
**Solution**: Check service status with `make status`, verify configuration

### "Task execution timeout"
**Cause**: Long-running agent operation or blocked worker
**Solution**: Increase timeout in configuration, check agent logs for hangs

### "Database migration failed"
**Cause**: Schema conflict or migration script error
**Solution**: Review migration script, consider manual schema fix

## Resolution Tracking

When resolving issues:
1. Document the root cause
2. Update this file with the solution
3. Consider if code changes are needed to prevent recurrence
4. Update relevant documentation in `/CLAUDE.md` or `.claude/CLAUDE.md`
