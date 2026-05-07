# Review PR Command

## Purpose
Perform a comprehensive code review on a pull request.

## Instructions
When this command is invoked with a PR number or branch name:

1. **Fetch PR Details**
   - Get the PR diff and changed files
   - Review commit messages and PR description
   - Check linked issues or tickets

2. **Code Review**
   - Check adherence to coding standards (see root CLAUDE.md)
   - Verify type hints and async/await usage
   - Review error handling and guard clauses
   - Check for proper Pydantic v2 usage
   - Verify database session cleanup and resource management

3. **Architecture Review**
   - Ensure changes fit within layered architecture
   - Check for proper separation of concerns
   - Review service, repository, and model changes
   - Verify API contract consistency

4. **Testing Review**
   - Check for adequate test coverage
   - Review test quality (unit, integration, E2E)
   - Verify mock usage and test isolation

5. **Security & Performance**
   - Check for security vulnerabilities
   - Review authentication and authorization
   - Verify async operations for I/O
   - Check for proper caching usage

6. **Provide Feedback**
   - Categorize issues by severity (critical, major, minor)
   - Provide specific, actionable suggestions
   - Highlight positive aspects
   - Suggest improvements with code examples

## Output Format
Use the "code-review" output style if available.
