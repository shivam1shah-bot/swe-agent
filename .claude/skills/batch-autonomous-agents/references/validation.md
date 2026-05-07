# Validation Rules

## Repository Input Format

### Syntax
- Comma or newline separated list
- Format: `repo-name` or `repo-name@branch-name`
- Organization prefix automatically added (razorpay/)

### Examples
```
scrooge
pg-router@feature-branch
api-service, payment-gateway
database-service@develop
```

### Restrictions
- Only private Razorpay repositories allowed
- Branches 'main' and 'master' are forbidden
- If no branch specified, auto-generates new branch

## Repository Validation

Each repository must pass these checks:

1. **URL Format**: Must be valid GitHub URL
2. **Organization**: Must belong to Razorpay
3. **Visibility**: Must be private repository
4. **Access**: User must have read/write access
5. **Branch**: Cannot be 'main' or 'master'

## Batch Validation

The batch request must satisfy:

1. **Prompt**: Required, non-empty string
2. **Repositories**: Required, must be a list
3. **Count**: Between 1 and current limit (see limits-guide.md)
4. **Individual**: Each repository must pass repository validation

## Best Practices

1. **Validation First**: Always validate all repositories before creating any tasks
2. **Atomic Operations**: Either all child tasks are created or none
3. **Error Handling**: Collect and report all validation errors together
4. **Logging**: Log parent/child task relationships for debugging
5. **Status Tracking**: Parent task stores child IDs for monitoring
