# Code Review Skill

A comprehensive skill for performing professional code reviews.

## Overview

This skill enables Claude to perform thorough, systematic code reviews following industry best practices. It provides structured guidance for reviewing code quality, security, performance, and maintainability.

## Files

### Skill.md
The main skill definition following Claude's official Skill format. Contains:
- Metadata (name, description, version)
- Complete code review process
- Review categories and checklists
- Output format template
- Best practices and examples

### Resources

#### SECURITY_CHECKLIST.md
Comprehensive security review checklist covering:
- Authentication & Authorization
- Input Validation & Sanitization
- SQL/XSS/Injection Prevention
- Data Protection & Encryption
- Session Management
- CSRF Protection
- API Security
- Cryptography
- File Operations
- OWASP Top 10

#### PERFORMANCE_CHECKLIST.md
Performance review guidelines including:
- Database Query Optimization
- N+1 Query Detection
- Indexing Strategy
- Async/Await Patterns
- Caching Strategies
- Algorithm Efficiency
- Memory Management
- Network Performance
- Language-Specific Optimizations

#### CODE_SMELLS.md
Reference guide for identifying code smells:
- Bloaters (Long Methods, God Objects)
- Object-Orientation Abusers
- Change Preventers
- Dispensables (Dead Code, Comments)
- Couplers (Feature Envy, Message Chains)
- Naming Issues
- Complexity Smells
- Language-Specific Smells
- Refactoring Techniques

## Usage

### Invoking the Skill

Claude will automatically use this skill when:
- Reviewing pull requests
- Analyzing code changes
- Performing quality assurance
- Checking code submissions
- When explicitly asked to review code

### Example Prompts

```
"Review this pull request"
"Perform a code review on these changes"
"Check this code for security issues"
"Analyze the performance of this code"
"Review for code quality and best practices"
```

### Review Categories

The skill performs comprehensive reviews across:

1. **Code Quality**
   - Readability & Maintainability
   - Architecture & Design
   - Error Handling
   - Code Smells

2. **Security**
   - Input Validation
   - Injection Prevention
   - Authentication/Authorization
   - Data Protection

3. **Performance**
   - Database Optimization
   - Algorithm Efficiency
   - Caching Strategy
   - Memory Management

4. **Testing**
   - Test Coverage
   - Test Quality
   - Edge Cases
   - Test Best Practices

5. **Documentation**
   - Code Comments
   - API Documentation
   - README Updates

## Output Format

Reviews follow a structured format:

```markdown
### Summary
Brief overview and assessment

### Critical Issues 🔴
Must-fix items before merging

### Major Issues 🟡
Should be addressed

### Minor Issues 🔵
Nice-to-have improvements

### Positive Highlights ✅
Well-implemented aspects

### Testing Recommendations 🧪
Test coverage suggestions

### Performance Considerations ⚡
Optimization opportunities

### Security Review 🔒
Security concerns

### Documentation 📚
Documentation needs

### Final Verdict
- [ ] Approve ✅
- [ ] Approve with minor changes
- [ ] Request changes
- [ ] Needs discussion

Overall Score: X/10
```

## Integration

This skill integrates with the repository's `.claude` structure:
- References: `/CLAUDE.md` for project standards
- Uses: `.claude/output-styles/code-review.md` for formatting
- Complements: `.claude/agents/code-reviewer.md` agent
- Works with: `.claude/commands/review-pr.md` command

## Best Practices

### Be Constructive
- Focus on code, not person
- Explain why, not just what
- Suggest alternatives
- Acknowledge good practices

### Be Specific
- Reference file:line numbers
- Provide code examples
- Link to documentation
- Explain impact

### Be Thorough
- Review all changed files
- Check related files
- Verify test coverage
- Consider compatibility

### Be Balanced
- Highlight positives
- Consider context
- Distinguish preferences from requirements
- Avoid being nitpicky

## Priority Levels

**Critical 🔴**: Security vulnerabilities, data loss risks, breaking changes
**Major 🟡**: Performance issues, architectural violations, missing error handling
**Minor 🔵**: Style inconsistencies, minor optimizations, documentation

## Language Support

The skill provides specific guidance for:
- Python
- JavaScript/TypeScript
- Go
- Java
- And other common languages

## Updates

**Version**: 1.0.0
**Last Updated**: 2024
**Maintained By**: SWE Agent Team

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Clean Code by Robert C. Martin](https://www.amazon.com/Clean-Code-Handbook-Software-Craftsmanship/dp/0132350882)
- [Refactoring by Martin Fowler](https://refactoring.com/)
- [Code Review Best Practices](https://google.github.io/eng-practices/review/)
