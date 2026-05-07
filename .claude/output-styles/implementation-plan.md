# Implementation Plan Output Style

## Format
Provide implementation plans in the following structured format:

---

# Implementation Plan: [Feature/Task Name]

## Overview
Brief description of what needs to be implemented and why.

## Prerequisites
- [ ] Requirement 1
- [ ] Requirement 2
- [ ] Dependency check
- [ ] Environment setup

## Implementation Steps

### Phase 1: [Phase Name] (Estimated: X hours)

#### Step 1.1: [Step Description]
**Files to modify/create:**
- `path/to/file.py` - What changes to make

**Code changes:**
```python
# Pseudocode or actual code example
```

**Verification:**
- How to verify this step is complete
- Expected output/behavior

---

#### Step 1.2: [Next Step]
**Files to modify/create:**
- List of files

**Code changes:**
```python
# Code example
```

**Verification:**
- Verification steps

---

### Phase 2: [Phase Name] (Estimated: X hours)

[Continue same pattern...]

## Testing Strategy

### Unit Tests
- [ ] Test case 1: Description
- [ ] Test case 2: Description

**Location:** `tests/unit/test_feature.py`

```python
# Example test structure
def test_feature():
    # Arrange
    # Act
    # Assert
    pass
```

### Integration Tests
- [ ] Integration scenario 1
- [ ] Integration scenario 2

### Manual Testing
1. Step-by-step manual test procedure
2. Expected results
3. Edge cases to verify

## Database Changes

### New Tables/Columns
```sql
-- Migration script example
ALTER TABLE ...
```

### Migration Script
**Location:** `src/migrations/scripts/XXX_description.py`

## API Changes

### New Endpoints
- `POST /api/v1/resource` - Description
  - Request schema
  - Response schema
  - Error codes

### Modified Endpoints
- Changes to existing endpoints
- Backward compatibility considerations

## Configuration Changes

**File:** `environments/env.default.toml`

```toml
[new_section]
setting = "value"
```

## Dependencies

### New Dependencies
- `package-name==version` - Why needed

**Update:** `requirements.txt`

## Rollout Plan

### Deployment Steps
1. Run migrations
2. Deploy new code
3. Verify health checks
4. Monitor logs

### Rollback Plan
1. How to rollback if issues occur
2. Data migration rollback (if applicable)

## Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Description | High/Med/Low | How to mitigate |

## Success Criteria
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] All tests passing
- [ ] Documentation updated
- [ ] Code review approved

## Timeline
- **Phase 1**: Start Date - End Date
- **Phase 2**: Start Date - End Date
- **Testing**: Start Date - End Date
- **Deployment**: Target Date

## Questions for Clarification
1. Question about requirement?
2. Technical decision needed?
3. Preference on approach?

---
