# Batch Autonomous Agents Architecture

## Core Components

### 1. Backend Service
**File**: `src/services/agents_catalogue/autonomous_agent/batch_service.py`

Responsibilities:
- Handles batch execution logic
- Creates parent task to track the batch
- Spawns individual child tasks for each repository
- Validates all repositories before execution

### 2. Frontend UI
**File**: `ui/src/pages/AutonomousAgentPage.tsx`

Responsibilities:
- Provides tabbed interface (Single vs Batch)
- Validates repository input format
- Parses comma-separated repository list
- Enforces UI-level validation rules

### 3. API Client
**File**: `ui/src/lib/api.ts`

Responsibilities:
- Defines `triggerAutonomousAgentBatch` method
- Sends batch requests to backend API endpoint

## Data Flow

```
User Input (UI)
    ↓
Parse & Validate Repositories (Frontend)
    ↓
API Call to /api/v1/agents-catalogue/api/autonomous-agent-batch
    ↓
AutonomousAgentBatchService.execute()
    ↓
├─ Validate Batch Parameters (max limit check)
├─ Parse Repositories
├─ Validate Individual Repositories (access, visibility)
├─ Create Parent Task (tracking)
└─ Submit Child Tasks
    ↓
    For each repository:
    ├─ Create child task parameters
    ├─ Submit to autonomous-agent service
    └─ Link child to parent task
    ↓
Update Parent Task with Child IDs
    ↓
Return Response to User
```

## Task Hierarchy

### Parent Task
Tracks the overall batch execution:
- Contains metadata about all repositories
- Stores child task IDs
- Status set to COMPLETED after child tasks are created

### Child Tasks
Individual autonomous agent tasks:
- Each executes against one repository
- Contains batch metadata (parent_task_id, repository_index)
- Runs independently using the single autonomous-agent service

## Metadata Structure

### Parent Task Metadata
```json
{
  "batch": {
    "is_parent": true,
    "repositories": [
      {
        "repository_url": "https://github.com/razorpay/repo1",
        "branch": "feature-branch"
      }
    ],
    "child_task_ids": ["task-id-1", "task-id-2"],
    "prompt": "Task description",
    "created_at": "2026-02-12T15:12:54.439Z",
    "updated_at": "2026-02-12T15:12:55.388Z"
  }
}
```

### Child Task Metadata
```json
{
  "batch": {
    "is_child": true,
    "parent_task_id": "parent-task-id",
    "repository_url": "https://github.com/razorpay/repo1",
    "branch": "feature-branch",
    "repository_index": 1
  },
  "service_type": "autonomous_agent",
  "execution_mode": "async",
  "priority": "normal"
}
```

## Key Files Reference

### Backend Files
- `src/services/agents_catalogue/autonomous_agent/batch_service.py` - Main batch service
- `src/services/agents_catalogue/autonomous_agent/validations.py` - Validation utilities
- `src/services/agents_catalogue/autonomous_agent/__init__.py` - Single agent service
- `src/services/agents_catalogue/registry.py` - Service registry

### Frontend Files
- `ui/src/pages/AutonomousAgentPage.tsx` - UI component
- `ui/src/lib/api.ts` - API client methods

### Configuration
- Service registered as "autonomous-agent-batch" in registry
- Uses queue_integration for task submission
- Leverages existing autonomous-agent service for execution

## API Endpoints

- **Single Agent**: `POST /api/v1/agents-catalogue/api/autonomous-agent`
- **Batch Agent**: `POST /api/v1/agents-catalogue/api/autonomous-agent-batch`

## Performance Considerations

- Each child task runs independently in parallel
- Parent task completes immediately after child tasks are queued
- Monitor system resources when increasing limits
- Consider rate limiting for GitHub API calls
- Database connections may increase with more simultaneous tasks

## Security Considerations

- Only Razorpay private repositories allowed
- GitHub authentication required for all operations
- Branch protection prevents direct commits to main/master
- Repository visibility checked before task creation
