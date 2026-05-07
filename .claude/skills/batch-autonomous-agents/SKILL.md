---
name: batch-autonomous-agents
description: Comprehensive guide for working with the Batch Autonomous Agents feature in swe-agent. Use when Claude needs to understand, modify, troubleshoot, or configure batch execution of autonomous agent tasks across multiple repositories. Covers architecture, validation rules, limit configuration, and common issues. Trigger when user asks about batch agents, changing batch limits, batch validation, or troubleshooting batch autonomous agent features.
---

# Batch Autonomous Agents

## Overview

Batch Autonomous Agents allows executing autonomous agent tasks across multiple repositories simultaneously. This skill provides the knowledge needed to understand the architecture, make configuration changes, troubleshoot issues, and work with the batch execution system.

## When to Use This Skill

Use this skill when working with:
- Understanding how batch autonomous agents work
- Changing batch repository limits (e.g., from 10 to 50)
- Troubleshooting batch execution issues
- Modifying validation rules
- Understanding task hierarchy and metadata

## Quick Reference

### Key Files

**Backend:**
- `src/services/agents_catalogue/autonomous_agent/batch_service.py` - Main batch service (limit: line 181)
- `src/services/agents_catalogue/autonomous_agent/validations.py` - Validation utilities

**Frontend:**
- `ui/src/pages/AutonomousAgentPage.tsx` - Batch UI (limit: line 75, slice: line 79, docs: line 336)
- `ui/src/lib/api.ts` - API client

### Current Configuration

- **Max repositories**: 10 (both frontend and backend)
- **Repository format**: `repo-name` or `repo-name@branch-name`
- **Organization**: Razorpay only
- **Visibility**: Private repositories only
- **Branch restrictions**: Cannot use 'main' or 'master'

## Common Tasks

### Changing Repository Limits

To change from 10 to 50 repositories (or any limit):

1. **Backend** (`batch_service.py:181`): Update max check
2. **Frontend** (`AutonomousAgentPage.tsx`):
   - Line 75: Update validation message
   - Line 79: Update slice limit
   - Line 336: Update user documentation

See [limits-guide.md](references/limits-guide.md) for detailed steps and testing requirements.

### Understanding Architecture

Read [architecture.md](references/architecture.md) for:
- Core components and their responsibilities
- Data flow through the system
- Task hierarchy (parent/child relationship)
- Metadata structure

### Validation Rules

Read [validation.md](references/validation.md) for:
- Repository input format and syntax
- Individual repository validation requirements
- Batch-level validation rules
- Best practices

### Troubleshooting

Read [troubleshooting.md](references/troubleshooting.md) for:
- Common error messages and solutions
- Debugging tips
- Known issues and workarounds

## Reference Files

All detailed documentation is in the `references/` directory:

- **[architecture.md](references/architecture.md)** - System architecture, components, data flow, and metadata structures
- **[limits-guide.md](references/limits-guide.md)** - How to change repository limits and testing requirements
- **[validation.md](references/validation.md)** - All validation rules and repository format specifications
- **[troubleshooting.md](references/troubleshooting.md)** - Common issues, error messages, and debugging tips

Load these files as needed based on the specific task at hand.
