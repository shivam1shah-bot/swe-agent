# Batch Limits Configuration Guide

## Current Limits

### Backend Validation
**File**: `src/services/agents_catalogue/autonomous_agent/batch_service.py`
**Line**: 181-182

```python
if len(repositories) > 10:
    raise ValueError(f"Too many repositories: {len(repositories)}. Maximum allowed: 10")
```

- Maximum repositories: 10
- Minimum repositories: 1

### Frontend Validation
**File**: `ui/src/pages/AutonomousAgentPage.tsx`
**Line**: 75-77

```typescript
if (lines.length > 10) {
    errors.push(`Maximum 10 repositories allowed; you entered ${lines.length}. Only the first 10 will be considered.`)
}
```

- Maximum repositories: 10
- Displays error when exceeded
- Slices to first 10 repositories

## Increasing the Limit

To increase the batch limit from 10 to 50 (or any other value):

### Step 1: Backend Changes

Update `src/services/agents_catalogue/autonomous_agent/batch_service.py` line 181:

```python
if len(repositories) > 50:
    raise ValueError(f"Too many repositories: {len(repositories)}. Maximum allowed: 50")
```

### Step 2: Frontend Changes

**File**: `ui/src/pages/AutonomousAgentPage.tsx`

1. Update line 75 (validation check):
   ```typescript
   if (lines.length > 50) {
       errors.push(`Maximum 50 repositories allowed; you entered ${lines.length}. Only the first 50 will be considered.`)
   }
   ```

2. Update line 79 (slice to first N):
   ```typescript
   lines.slice(0, 50).forEach((line, idx) => {
   ```

3. Update line 336 (user documentation):
   ```typescript
   Up to 50 entries. Use <code>repo</code> or <code>repo@branch</code>, comma separated.
   ```

### Step 3: Testing

After making changes, verify:

- Validation works for exactly N repositories (boundary condition)
- Test N-1, N, and N+1 repositories
- Error messages display correctly
- All N child tasks are created successfully
- System performance remains acceptable

### Important Notes

- **Keep frontend and backend limits synchronized** - mismatched limits cause user confusion
- **Consider system resources** - higher limits increase:
  - Database connections
  - Worker load
  - GitHub API rate limits
  - Memory usage
- **Test thoroughly** - batch operations are critical workflows
