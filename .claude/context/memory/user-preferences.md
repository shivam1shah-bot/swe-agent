# User Preferences

## Working Style
- **Development Approach**: Test-driven development with comprehensive coverage
- **Code Quality**: Emphasis on early error handling, type hints, and async patterns
- **Documentation**: Code should be self-documenting; avoid over-commenting
- **Architecture**: Strict adherence to layered architecture (API → Service → Repository → Model → Provider)

## Communication Preferences
- **Clarity**: Prefer detailed implementation plans before execution
- **Approval**: Always get explicit approval before proceeding with major changes
- **Feedback**: Constructive, specific feedback with code examples

## Development Environment
- **Primary Environment**: Docker-based development (docker-compose)
- **Local Development**: Support for running services locally outside Docker
- **Testing**: Use pytest with comprehensive test suite (unit, integration, E2E)

## Code Standards
- **Python Style**: PEP 8 compliance with type hints on all functions
- **Async Patterns**: Prefer async/await for all I/O operations
- **Error Handling**: Early returns with guard clauses
- **Validation**: Pydantic v2 for all input/output validation
- **Session Management**: Proper cleanup of resources and sessions

## Tool Preferences
- **Version Control**: GitHub with gh CLI for operations
- **Branching Strategy**: Feature branches with draft PRs for review
- **Commits**: Descriptive commit messages following conventional commits
- **Code Review**: Thorough reviews focusing on security, performance, and maintainability

## Project-Specific Preferences
- **Agent Development**: Singleton pattern for agent tools, delegation for task execution
- **Configuration**: TOML-based layered configuration (default → environment → runtime)
- **Database**: Repository pattern with SQLAlchemy 2.0
- **API Design**: FastAPI with dependency injection and proper HTTP status codes
- **Task Processing**: Asynchronous worker pattern with SQS queues

## File Creation Rules
- **NEVER create files unless absolutely necessary**
- **ALWAYS prefer editing existing files** over creating new ones
- **NEVER proactively create documentation files** (*.md) unless explicitly requested
- Clean up temporary files and artifacts before session completion

## Learning Preferences
- **Pattern Recognition**: Document emerging patterns in patterns.md
- **Issue Tracking**: Log known issues and workarounds in known-issues.md
- **Context Building**: Update project-facts.md with important discoveries
