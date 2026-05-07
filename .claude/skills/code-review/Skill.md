---
name: Code Review
description: Perform comprehensive code reviews with focus on quality, security, performance, and best practices for pull requests and code changes
version: 1.0.0
---

## Overview

This Skill enables Claude to perform thorough, professional code reviews that follow industry best practices and project-specific standards. The code review process systematically examines code changes for quality, security, performance, maintainability, and adherence to coding standards.

**When to Use This Skill:**
- Reviewing pull requests before merging
- Analyzing code changes for quality assurance
- Providing feedback on code submissions
- Identifying potential bugs and security vulnerabilities
- Ensuring adherence to project coding standards

## Code Review Process

### 1. Initial Assessment
- **Understand the Context**: Read the PR/commit description, linked issues, and change scope
- **Identify Change Type**: Feature addition, bug fix, refactoring, performance optimization, etc.
- **Check Completeness**: Verify all necessary files are included (tests, documentation, migrations)

### 2. Code Quality Review

#### Readability & Maintainability
- **Naming**: Are variables, functions, and classes well-named and descriptive?
- **Function Length**: Are functions focused and of reasonable size (ideally < 50 lines)?
- **Complexity**: Is the code's cyclomatic complexity reasonable? Are there overly nested conditionals?
- **Comments**: Are complex logic blocks properly commented? Is there unnecessary commented-out code?
- **Code Duplication**: Is there duplicated logic that should be extracted?

#### Architecture & Design
- **Separation of Concerns**: Is business logic properly separated from presentation/data access?
- **SOLID Principles**: Does the code follow Single Responsibility, Open/Closed, etc.?
- **Design Patterns**: Are appropriate design patterns used correctly?
- **Dependencies**: Are dependencies properly managed and injected?
- **Layer Violations**: Does the code respect the project's layered architecture?

#### Error Handling
- **Guard Clauses**: Are early returns used to handle error cases first?
- **Exception Handling**: Are exceptions caught at appropriate levels?
- **Error Messages**: Are error messages clear and actionable?
- **Edge Cases**: Are edge cases and boundary conditions handled?
- **Validation**: Is input validation comprehensive and secure?

### 3. Security Review

#### Common Security Issues
- **SQL Injection**: Are database queries parameterized/using ORM properly?
- **XSS Prevention**: Is user input properly sanitized before rendering?
- **Authentication**: Are authentication checks in place for protected endpoints?
- **Authorization**: Are proper permission checks enforced?
- **Secrets Management**: Are API keys, passwords, and secrets kept out of code?
- **CSRF Protection**: Are state-changing operations protected?
- **Rate Limiting**: Are expensive operations rate-limited?
- **Data Exposure**: Is sensitive data properly masked/encrypted?

#### Input Validation
- **Type Validation**: Are input types validated?
- **Range Checks**: Are numeric values validated for acceptable ranges?
- **Format Validation**: Are strings validated for expected formats (email, URL, etc.)?
- **Sanitization**: Is user input sanitized before use?

### 4. Performance Review

#### Efficiency Concerns
- **N+1 Queries**: Are there database query optimization opportunities?
- **Async Operations**: Are I/O operations using async/await properly?
- **Caching**: Should results be cached? Is caching invalidation correct?
- **Lazy Loading**: Should data be loaded on-demand vs. eagerly?
- **Algorithm Complexity**: Is the algorithm's time complexity reasonable?
- **Memory Usage**: Are there memory leaks or excessive memory consumption?

#### Database Optimization
- **Indexes**: Are appropriate indexes in place?
- **Query Efficiency**: Can queries be optimized or combined?
- **Connection Pooling**: Are database connections managed efficiently?
- **Batch Operations**: Should operations be batched?

### 5. Testing Review

#### Test Coverage
- **Unit Tests**: Are there unit tests for new/changed logic?
- **Integration Tests**: Are integration points tested?
- **Edge Cases**: Are edge cases and error paths tested?
- **Test Quality**: Are tests clear, focused, and maintainable?
- **Test Data**: Is test data realistic and comprehensive?

#### Test Best Practices
- **Isolation**: Are tests isolated and independent?
- **Assertions**: Are assertions specific and meaningful?
- **Setup/Teardown**: Is test setup and cleanup proper?
- **Mocking**: Are external dependencies properly mocked?

### 6. Documentation Review

#### Code Documentation
- **Function Documentation**: Are complex functions documented with docstrings?
- **API Documentation**: Are API endpoints documented (OpenAPI/Swagger)?
- **README Updates**: Are README files updated if needed?
- **Changelog**: Are significant changes logged?
- **Migration Guides**: Are breaking changes documented?

### 7. Project-Specific Standards

When reviewing code, reference the project's specific standards:
- **Coding Style**: Follow project's style guide (PEP 8, ESLint config, etc.)
- **Type Hints**: Use type annotations as per project standards
- **Async Patterns**: Follow project's async/await patterns
- **Import Organization**: Follow project's import ordering
- **Configuration**: Use project's configuration management patterns

## Review Output Format

Provide structured feedback following this format:

### Summary
Brief overview of changes and overall assessment (2-3 sentences).

### Critical Issues 🔴
**Must be fixed before merging:**
- **[File:Line]**: Issue description
  - **Impact**: Why this is critical
  - **Suggestion**: How to fix it
  ```language
  // Example fix if applicable
  ```

### Major Issues 🟡
**Should be addressed:**
- **[File:Line]**: Issue description
  - **Concern**: What could go wrong
  - **Recommendation**: Suggested improvement

### Minor Issues 🔵
**Nice-to-have improvements:**
- **[File:Line]**: Issue description
  - **Suggestion**: Optional improvement

### Positive Highlights ✅
**Things done well:**
- Well-implemented features
- Good practices observed
- Excellent design decisions

### Testing Recommendations 🧪
- Missing test coverage areas
- Additional test scenarios to consider
- Test quality improvements

### Performance Considerations ⚡
- Potential performance impacts
- Optimization opportunities
- Caching/async suggestions

### Security Review 🔒
- Security concerns if any
- Authentication/authorization verification
- Data sanitization checks

### Documentation 📚
- Missing documentation
- README updates needed
- API documentation requirements

### Final Verdict
- [ ] Approve ✅ - Ready to merge
- [ ] Approve with minor changes - Can merge after small fixes
- [ ] Request changes - Needs significant work before merging
- [ ] Needs discussion - Architecture/approach needs discussion

**Overall Score**: X/10

**Summary**: Brief final recommendation

## Best Practices for Code Reviews

### Be Constructive
- Focus on the code, not the person
- Explain **why** something is an issue, not just **what** is wrong
- Suggest concrete alternatives
- Acknowledge good practices and improvements

### Be Specific
- Reference exact file names and line numbers
- Provide code examples of suggested fixes
- Link to relevant documentation or standards
- Explain the impact of issues

### Prioritize Issues
- **Critical**: Security vulnerabilities, data loss risks, breaking changes
- **Major**: Performance issues, architectural violations, missing error handling
- **Minor**: Style inconsistencies, minor optimizations, documentation improvements

### Be Thorough
- Review all changed files systematically
- Check related files that might be affected
- Verify tests adequately cover changes
- Consider backward compatibility

### Be Balanced
- Highlight positive aspects, not just problems
- Consider the context and constraints
- Distinguish between preferences and requirements
- Suggest improvements without being nitpicky

## Common Code Smells to Watch For

### Structural Issues
- **God Objects**: Classes doing too much
- **Long Methods**: Functions over 50 lines
- **Long Parameter Lists**: More than 3-4 parameters
- **Deep Nesting**: More than 3 levels of indentation
- **Duplicate Code**: Copy-pasted logic
- **Magic Numbers**: Unexplained numeric constants

### Naming Issues
- **Unclear Names**: Variables like `data`, `temp`, `x`
- **Misleading Names**: Names that don't match behavior
- **Inconsistent Names**: Different names for same concept
- **Abbreviations**: Unnecessary abbreviations like `usr`, `ctx`

### Logic Issues
- **Complex Conditionals**: Multiple AND/OR conditions
- **Missing Null Checks**: Potential null pointer errors
- **Hardcoded Values**: Configuration in code
- **Unreachable Code**: Dead code that can't execute
- **Side Effects**: Functions that modify unexpected state

### Performance Issues
- **Inefficient Loops**: Nested loops over large datasets
- **Unnecessary Computation**: Recalculating same values
- **Memory Leaks**: Resources not properly cleaned up
- **Blocking Operations**: Synchronous I/O in async contexts

## Language-Specific Considerations

### Python
- Type hints on all functions
- Use of context managers for resources
- Proper exception hierarchy
- List/dict comprehensions vs loops
- Generator usage for large datasets

### JavaScript/TypeScript
- Proper async/await usage
- Avoid callback hell
- Type safety in TypeScript
- Proper error boundaries in React
- Memory leak prevention in closures

### Go
- Proper error handling (not ignoring errors)
- Context usage for cancellation
- Goroutine leak prevention
- Interface usage and design
- defer for cleanup

### Java
- Proper exception handling
- Resource management (try-with-resources)
- Stream API usage
- Concurrency considerations
- Null safety patterns

## Examples

### Example 1: Security Issue

**Issue Found:**
```python
query = f"SELECT * FROM users WHERE username = '{username}'"
cursor.execute(query)
```

**Review Comment:**
🔴 **Critical: SQL Injection Vulnerability**
- **File**: `auth/login.py:45`
- **Impact**: Attacker can inject malicious SQL and access/modify any data
- **Suggestion**: Use parameterized queries

```python
query = "SELECT * FROM users WHERE username = %s"
cursor.execute(query, (username,))
```

### Example 2: Performance Issue

**Issue Found:**
```python
for user in users:
    profile = db.get_profile(user.id)  # N+1 query
    user.profile = profile
```

**Review Comment:**
🟡 **Major: N+1 Query Problem**
- **File**: `users/service.py:78`
- **Concern**: This creates one query per user, causing performance issues with many users
- **Recommendation**: Fetch all profiles in one query

```python
user_ids = [user.id for user in users]
profiles = db.get_profiles_batch(user_ids)
profile_map = {p.user_id: p for p in profiles}
for user in users:
    user.profile = profile_map.get(user.id)
```

### Example 3: Code Quality

**Issue Found:**
```python
def process(data):
    if data is not None:
        if len(data) > 0:
            if validate(data):
                return transform(data)
    return None
```

**Review Comment:**
🔵 **Minor: Deep Nesting - Use Guard Clauses**
- **File**: `processing/handler.py:23`
- **Suggestion**: Improve readability with early returns

```python
def process(data):
    if data is None or len(data) == 0:
        return None

    if not validate(data):
        return None

    return transform(data)
```

## Integration with Project

This skill integrates with the repository's `.claude` structure:
- References standards from root `/CLAUDE.md`
- Uses output style from `.claude/output-styles/code-review.md`
- Complements `.claude/agents/code-reviewer.md` agent role
- Works with `.claude/commands/review-pr.md` command

## Checklist Template

Use this checklist when performing reviews:

- [ ] Understand change context and purpose
- [ ] Review code quality and readability
- [ ] Check error handling and edge cases
- [ ] Verify security best practices
- [ ] Assess performance implications
- [ ] Review test coverage and quality
- [ ] Check documentation completeness
- [ ] Verify adherence to project standards
- [ ] Provide constructive, specific feedback
- [ ] Highlight positive aspects
- [ ] Give clear final recommendation

## Resources

For additional reference, see:
- Project coding standards: `/CLAUDE.md`
- Output format: `.claude/output-styles/code-review.md`
- Code reviewer agent: `.claude/agents/code-reviewer.md`
- PR review command: `.claude/commands/review-pr.md`
