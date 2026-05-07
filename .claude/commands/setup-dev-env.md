# Setup Dev Environment Command

## Purpose
Guide user through setting up their development environment for the SWE Agent project.

## Instructions
When this command is invoked, guide the user through:

1. **Prerequisites Check**
   - Verify Docker and Docker Compose installation
   - Check Python 3.11+ availability
   - Verify Node.js and npm for UI development
   - Check gh CLI for GitHub operations

2. **Environment Configuration**
   - Copy `environments/env.default.toml` to `environments/env.dev_docker.toml`
   - Guide configuration of required secrets:
     - ANTHROPIC_API_KEY
     - GITHUB_TOKEN
     - Database credentials
     - Redis configuration
     - AWS credentials for SQS (LocalStack)

3. **Service Setup**
   - Run `./scripts/start_service.sh` for complete setup
   - Verify all services are running with `make status`
   - Check service URLs:
     - Web UI: http://localhost:28001
     - API: http://localhost:28002
     - API Docs: http://localhost:28002/docs

4. **Development Environment**
   - Set up Python virtual environment: `make setup`
   - Install dependencies
   - Configure IDE/editor settings
   - Review Cursor rules in `.cursor/rules/`

5. **Verification**
   - Run health checks
   - Execute test suite: `make test-unit`
   - Verify API endpoints via Swagger UI
   - Test task execution workflow

## Output Format
Provide step-by-step checklist format with verification commands.
