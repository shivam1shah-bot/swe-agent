# Task Execution Report Output Style

## Format

Use this format for reporting autonomous task execution results.

```markdown
# Task Execution Report

**Task ID**: {task_id}
**Task Type**: {task_type}
**Status**: {✅ COMPLETED | ❌ FAILED | ⚠️ PARTIAL}
**Duration**: {duration}
**Started**: {start_timestamp}
**Completed**: {end_timestamp}

## Summary

{2-3 sentence summary of what was accomplished or what failed}

## Execution Steps

### Phase 1: Analysis
- ✅ Analyzed requirements
- ✅ Identified affected files: {count}
- ✅ Determined complexity: {complexity_level}

### Phase 2: Planning
- ✅ Created implementation plan
- ✅ Designed test strategy
- ✅ Identified dependencies

### Phase 3: Implementation
- ✅ Implemented changes in {file_count} files
- ✅ Added {test_count} tests
- ⚠️ Encountered {warning_count} warnings

### Phase 4: Verification
- ✅ All tests passed ({passed}/{total})
- ✅ Code review checks passed
- ✅ No security issues detected

## Changes Made

### Files Modified ({count})
```
src/api/routes/auth.py          (+45, -12)
src/models/user.py               (+23, -5)
src/services/auth_service.py     (+67, -8)
tests/test_auth.py               (+120, -0)
```

### Files Created ({count})
```
src/middleware/auth_middleware.py  (+85 lines)
tests/integration/test_auth_flow.py (+145 lines)
```

### Files Deleted ({count})
```
src/legacy/old_auth.py
```

## Test Results

### Unit Tests
- **Total**: {total}
- **Passed**: {passed} ✅
- **Failed**: {failed} ❌
- **Skipped**: {skipped}
- **Coverage**: {coverage}%

### Integration Tests
- **Total**: {total}
- **Passed**: {passed} ✅
- **Failed**: {failed} ❌

### Test Output Sample
```
test_user_authentication ... PASSED
test_token_generation ... PASSED
test_invalid_credentials ... PASSED
test_token_expiration ... PASSED
```

## Code Quality Metrics

- **Lines Added**: {lines_added}
- **Lines Removed**: {lines_removed}
- **Net Change**: {net_change}
- **Complexity Score**: {complexity}/10
- **Code Smells**: {code_smells_count}
- **Security Issues**: {security_issues_count}

## Pull Request

{IF pr_created}
✅ **Pull Request Created**

- **URL**: {pr_url}
- **Title**: {pr_title}
- **Branch**: {branch_name} → {base_branch}
- **Status**: {draft/ready_for_review}
- **Reviewers**: {reviewers}

{END IF}

## Agent Execution Log

<details>
<summary>View detailed agent execution log</summary>

```
[10:23:45] Starting task execution...
[10:23:47] Analyzing requirements: "Add authentication middleware"
[10:24:15] Identified 4 files requiring changes
[10:24:30] Creating implementation plan...
[10:25:00] Implementing auth_middleware.py...
[10:27:30] Implementing auth_service.py...
[10:30:15] Writing tests...
[10:33:45] Running test suite...
[10:35:20] All tests passed ✅
[10:35:30] Creating pull request...
[10:36:00] Task completed successfully ✅
```

</details>

## Errors and Warnings

{IF has_errors_or_warnings}

### Errors ({count})
1. **DatabaseConnectionError** (resolved)
   - Occurred at: 10:28:30
   - Resolution: Retry successful
   - Impact: 15 second delay

### Warnings ({count})
1. **Slow test execution**
   - Test: test_auth_integration_flow
   - Duration: 3.2 seconds
   - Recommendation: Consider mocking external dependencies

{ELSE}
✅ No errors or warnings
{END IF}

## Performance Metrics

- **Average Response Time**: {avg_response_time}ms
- **Database Queries**: {query_count}
- **Cache Hit Rate**: {cache_hit_rate}%
- **Memory Usage**: {memory_usage}MB

## Security Analysis

✅ **No security vulnerabilities detected**

Checks performed:
- ✅ No hardcoded secrets
- ✅ Input validation present
- ✅ Authentication checks in place
- ✅ SQL injection prevention via ORM
- ✅ XSS prevention in outputs

## Recommendations

{IF has_recommendations}
1. **Performance**: Consider adding database index on `users.email`
2. **Testing**: Add E2E tests for complete authentication flow
3. **Documentation**: Update API documentation with new endpoints
{ELSE}
✅ No recommendations at this time
{END IF}

## Next Steps

{IF status == COMPLETED}
1. ✅ Review pull request: {pr_url}
2. ✅ Run manual testing if needed
3. ✅ Merge after approval
4. ✅ Deploy to staging
{ELSE IF status == FAILED}
1. ❌ Review error logs above
2. ❌ Fix identified issues
3. ❌ Retry task with corrections
{END IF}

## Artifacts

- **Branch**: {branch_name}
- **Commit**: {commit_hash}
- **Logs**: `tmp/logs/task-{task_id}.log`
- **Test Report**: `tmp/reports/test-{task_id}.html`

---

**Generated**: {timestamp}
**Report ID**: {report_id}
```

## Usage

Use this format when:
- Reporting task execution results
- Summarizing autonomous agent operations
- Documenting task outcomes

## Variables

- `{task_id}`: Unique task identifier
- `{task_type}`: Type of task (feature, bugfix, etc.)
- `{status}`: Final task status
- `{duration}`: Total execution time
- `{file_count}`: Number of files modified
- `{test_count}`: Number of tests added/modified
- `{pr_url}`: Pull request URL if created
- `{complexity}`: Code complexity score
- `{coverage}`: Test coverage percentage

## Color Coding

- ✅ Success/Completed
- ❌ Failed/Error
- ⚠️ Warning/Partial Success
- 🔄 In Progress
- ℹ️ Information
