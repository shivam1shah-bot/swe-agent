# Code Review Output Style

## Format
Provide code review feedback in the following structured format:

### Summary
Brief overview of the changes and overall assessment.

### Critical Issues 🔴
Issues that must be addressed before merging:
- **[File:Line]**: Description of issue
  - Impact: Why this is critical
  - Suggestion: How to fix it
  ```python
  # Example of suggested fix (if applicable)
  ```

### Major Issues 🟡
Significant issues that should be addressed:
- **[File:Line]**: Description of issue
  - Concern: What could go wrong
  - Recommendation: Suggested improvement

### Minor Issues 🔵
Nice-to-have improvements:
- **[File:Line]**: Description
  - Suggestion: Optional improvement

### Positive Highlights ✅
Things done well:
- Good practices worth noting
- Excellent implementations
- Well-structured code

### Testing Recommendations 🧪
- Missing test coverage
- Additional test scenarios to consider
- Test quality improvements

### Performance Considerations ⚡
- Potential performance impacts
- Optimization opportunities
- Async/caching suggestions

### Security Review 🔒
- Security concerns if any
- Authentication/authorization checks
- Data sanitization verification

### Final Verdict
- [ ] Approve ✅
- [ ] Approve with minor changes
- [ ] Request changes
- [ ] Needs discussion

**Overall Score**: X/10
