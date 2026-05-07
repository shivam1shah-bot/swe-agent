# Pre-Commit Hook

## Trigger
This hook is triggered before committing code changes.

## Instructions
Before committing, ensure the following:

1. **Code Quality Checks**
   - All files follow project coding standards
   - Type hints are present on all function signatures
   - Early error handling pattern is used
   - Async/await is used for I/O operations

2. **Import Organization**
   - Remove unused imports
   - Organize imports properly (standard lib, third-party, local)
   - No circular dependencies

3. **Security Checks**
   - No hardcoded secrets or credentials
   - No sensitive data in logs
   - Proper data sanitization in place

4. **Documentation**
   - Critical functions have docstrings
   - Complex logic is commented
   - API changes are documented

5. **Testing**
   - Unit tests exist for new code
   - All tests pass: `make test-unit`
   - No failing tests being committed

6. **Cleanup**
   - Remove debug print statements
   - Remove commented-out code
   - Remove temporary files or debug code

## Auto-Checks (if applicable)
- Linting passes
- Type checking passes
- No security vulnerabilities detected

## Prompt for Review
Before proceeding with commit, ask:
- "Are all changes intended and reviewed?"
- "Do all tests pass?"
- "Is documentation updated?"
