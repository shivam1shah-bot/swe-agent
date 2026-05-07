# Troubleshooting Guide

## Common Issues

### 1. Public Repository Error

**Error**: "Repository must be private"

**Cause**: Batch autonomous agents only work with private Razorpay repositories

**Solution**:
- Verify the repository is set to private in GitHub
- Ensure you're targeting a Razorpay organization repository
- Check that the repository URL is correctly formatted

### 2. Access Denied

**Error**: "User does not have access to repository"

**Cause**: User lacks proper GitHub permissions for the target repository

**Solution**:
- Verify user has read/write access to the repository
- Check GitHub authentication token is valid
- Ensure user is a member of the Razorpay organization
- Verify repository permissions in GitHub settings

### 3. Branch Restrictions

**Error**: "Cannot use main/master branch"

**Cause**: Direct commits to main/master branches are blocked for safety

**Solution**:
- Specify a different branch: `repo-name@feature-branch`
- Let the system auto-generate a new branch (omit @branch)
- Use an existing feature or development branch

### 4. Validation Mismatch

**Error**: Frontend allows N repositories but backend rejects them

**Cause**: Frontend and backend limits are out of sync

**Solution**:
- Check both validation limits match
- See limits-guide.md for proper configuration
- Ensure both files are updated when changing limits
- Verify deployed versions include both changes

### 5. Child Tasks Not Created

**Symptom**: Parent task shows COMPLETED but no child tasks exist

**Cause**: Error during child task creation after parent was created

**Debug Steps**:
1. Check backend logs for errors during task submission
2. Verify queue integration is working
3. Check database for parent task metadata
4. Ensure autonomous-agent service is registered correctly

**Solution**:
- Review error logs for specific failure
- Verify SQS queue is accessible
- Check worker is running and processing tasks
- Ensure all repositories passed validation

### 6. Partial Batch Failure

**Symptom**: Some child tasks created but not all

**Cause**: Batch operations should be atomic but partial failure occurred

**Debug Steps**:
1. Check parent task metadata for child_task_ids count
2. Review logs for which repositories failed
3. Verify validation ran on all repositories

**Solution**:
- This shouldn't happen - report as bug if it does
- Expected behavior: all succeed or all fail
- Review batch_service.py for atomic operation handling

## Debugging Tips

### Check Parent Task Metadata

Query the parent task to see:
- Which repositories were requested
- How many child tasks were created
- Timestamps of creation

### Verify Repository URLs

Common issues with repository input:
- Missing organization prefix (should auto-add "razorpay/")
- Invalid branch names
- Typos in repository names

### Monitor System Resources

When running large batches:
- Check database connection pool
- Monitor worker queue length
- Watch for GitHub API rate limits
- Verify sufficient memory/CPU
