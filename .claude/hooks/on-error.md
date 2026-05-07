# On Error Hook

## Trigger
This hook is triggered when an error occurs during task execution.

## Instructions
When an error occurs:

1. **Error Analysis**
   - Capture the full error message and stack trace
   - Identify the error type (syntax, runtime, logic, configuration, etc.)
   - Determine the context where error occurred

2. **Check Common Issues**
   - Review logs in `tmp/logs/` for detailed information
   - Check configuration in `environments/` files
   - Verify service health: `make status`
   - Check for missing dependencies or environment variables

3. **Debugging Steps**
   - Isolate the failing component
   - Try to reproduce in minimal context
   - Check recent changes that might have caused the issue
   - Review related code for similar patterns

4. **Gather Context**
   - What was the task being performed?
   - What was the expected behavior?
   - What actually happened?
   - Can the error be reproduced consistently?

5. **Attempt Resolution**
   - Try common fixes based on error type
   - Consult project documentation and CLAUDE.md
   - Check for known issues or patterns

6. **Report to User**
   - Explain the error in clear terms
   - Describe what was being attempted
   - Show relevant error messages
   - Suggest potential solutions or next steps

7. **Request Help if Needed**
   - If error is unclear or complex, ask user for guidance
   - Provide all relevant context for troubleshooting
   - Suggest debugging commands to run

## Error Categories

### Configuration Errors
- Check `environments/` files
- Verify secrets and API keys
- Check database connection strings

### Dependency Errors
- Run `make setup` to reinstall dependencies
- Check Python version compatibility
- Verify Docker containers are running

### Code Errors
- Review recent changes
- Check for typos or syntax errors
- Verify type hints and imports

### Runtime Errors
- Check logs for detailed stack traces
- Review database state
- Verify external service availability
