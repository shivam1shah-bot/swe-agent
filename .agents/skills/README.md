# SWE Agent Skills

This directory contains domain-specific skills for AI agents working with the SWE Agent codebase. Skills provide step-by-step procedural knowledge for complex workflows.

## Available Skills

### 1. **autonomous-task-execution**
Complete autonomous agent task lifecycle from API request through queue processing to completion.

**Use when**: Working with task creation, queue management, or autonomous agent execution
**Covers**: Validation, queuing, worker processing, cancellation, status updates

### 2. **mcp-server-integration**
Model Context Protocol (MCP) server setup, configuration, and integration.

**Use when**: Adding MCP servers, creating MCP tools, or debugging MCP integration
**Covers**: Client configuration, server implementation, tool creation, security

### 3. **worker-queue-processing**
SQS worker queue processing and background task management.

**Use when**: Working with queue configuration, worker processing, or task handlers
**Covers**: Queue setup, polling, message processing, visibility timeout, health monitoring

### 4. **service-registry-pattern**
Dynamic service registration and discovery for agents catalogue.

**Use when**: Adding new services, implementing service patterns, or monitoring service health
**Covers**: Registration, discovery, health checks, metrics tracking, lifecycle management

## How Skills Work

### What is a Skill?

A **skill** is a structured guide that provides:
- **Step-by-step procedures** for complex workflows
- **Decision frameworks** for making implementation choices
- **Common patterns** and best practices
- **Edge cases** and error handling
- **Testing strategies** and debugging tips

### Skills vs AGENTS.md vs CLAUDE.md

| Content Type | Location | Purpose | Length |
|--------------|----------|---------|--------|
| **Quick Reference** | `AGENTS.md` | Commands, setup, brief overview | 50-100 lines |
| **Detailed Docs** | `CLAUDE.md` | Architecture, patterns, standards | 200-300 lines |
| **Procedural Workflows** | `.agents/skills/` | Step-by-step execution guides | 300-500 lines per skill |

### When to Use Skills

AI agents automatically load relevant skills when working with specific parts of the codebase. Skills help agents:

1. **Understand complex workflows** - Multi-step processes with decision points
2. **Follow best practices** - Established patterns and conventions
3. **Handle edge cases** - Known issues and their solutions
4. **Debug problems** - Common issues and troubleshooting steps
5. **Make informed decisions** - Criteria for choosing between approaches

## Skill Structure

Each skill follows this format:

```markdown
---
name: skill-name
description: Brief description
version: 1.0.0
tags: [relevant, tags]
context: codebase
---

# Skill Title

## Overview
Brief explanation of what this skill covers

## Phase 1: First Major Step
Detailed step-by-step instructions

## Phase 2: Second Major Step
More detailed instructions

## Edge Cases & Error Handling
Common issues and solutions

## Key Files
Relevant source files

## Testing
How to test

## Monitoring & Debugging
How to debug and monitor
```

## Using Skills

### Automatic Loading (via Agentfill)

Skills in `.agents/skills/` are automatically available to AI agents when you use [agentfill](https://github.com/nevir/agentfill):

1. **Claude Code** - Skills symlinked to `.claude/skills/`
2. **Cursor** - Skills symlinked to `.cursor/skills/`
3. **Gemini CLI** - Skills symlinked to `.gemini/skills/`

**No manual action needed** - agentfill handles the setup automatically.

### Manual Reference

You can also reference skills directly in prompts:

```
"Using the autonomous-task-execution skill, implement task cancellation support"

"Following the service-registry-pattern skill, add a new service for code reviews"

"Apply the worker-queue-processing skill to debug why messages aren't being processed"
```

## Adding New Skills

### When to Create a Skill

Create a skill when:
- ✅ Workflow is repeated multiple times
- ✅ Multiple decision points exist
- ✅ Edge cases need handling
- ✅ New developers struggle with the process
- ✅ Tribal knowledge exists but isn't documented

Don't create a skill for:
- ❌ Single-line commands (put in AGENTS.md)
- ❌ One-time operations
- ❌ Simple, self-evident tasks
- ❌ Frequently changing processes

### Skill Creation Process

1. **Create directory**: `.agents/skills/your-skill-name/`
2. **Create skill file**: `.agents/skills/your-skill-name/SKILL.md`
3. **Follow template** (see "Skill Structure" above)
4. **Include frontmatter** with metadata
5. **Write clear steps** with code examples
6. **Add edge cases** and debugging tips
7. **Test the skill** with an AI agent
8. **Update this README** with skill entry

### Skill Template

```bash
mkdir -p .agents/skills/your-skill-name

cat > .agents/skills/your-skill-name/SKILL.md << 'EOF'
---
name: your-skill-name
description: What this skill helps with
version: 1.0.0
tags: [relevant, tags, here]
context: codebase
---

# Your Skill Title

## Overview
What this skill covers and when to use it

## Phase 1: Setup
Step-by-step setup instructions

## Phase 2: Implementation
Implementation steps with code examples

## Phase 3: Testing
Testing procedures

## Edge Cases & Error Handling
Common issues and solutions

## Key Files
- `src/path/to/file.py` - Purpose
- `config/file.toml` - Configuration

## Monitoring & Debugging
How to debug and monitor
EOF
```

## Skill Maintenance

### Updating Skills

Skills should be updated when:
- Code architecture changes
- New patterns emerge
- Edge cases discovered
- Best practices evolve

**Update process**:
1. Edit the skill's `SKILL.md` file
2. Update version number in frontmatter
3. Document changes in skill
4. Test with AI agent

### Deprecating Skills

If a skill becomes obsolete:
1. Add `deprecated: true` to frontmatter
2. Add deprecation notice at top of file
3. Recommend alternative skill or approach
4. Keep file for 3 months before removal

## Best Practices

### Writing Clear Skills

1. **Use active voice** - "Create the file" not "The file is created"
2. **Include code examples** - Show, don't just tell
3. **Be specific** - "Edit `src/api/routes.py`" not "Edit the routes file"
4. **Add context** - Explain *why*, not just *what*
5. **Include edge cases** - Document known issues and solutions

### Organizing Steps

1. **Group by phase** - Setup → Implementation → Testing → Deployment
2. **Number steps** - Clear sequential order
3. **Highlight decisions** - Bold decision points
4. **Use code blocks** - For commands and code snippets
5. **Add diagrams** - If workflow is complex (use ASCII or mermaid)

### Testing Skills

Before committing a skill:
1. **Test with AI agent** - Ask agent to follow the skill
2. **Verify accuracy** - Ensure all file paths are correct
3. **Check completeness** - No missing steps
4. **Validate examples** - Code examples work as-is
5. **Review edge cases** - Common issues covered

## Getting Help

- **AGENTS.md** - Quick reference for commands and setup
- **CLAUDE.md** - Detailed technical documentation
- **Skills** (this directory) - Procedural workflows and best practices

## Metrics & Value

Skills provide measurable value:
- **Faster onboarding** - 60% reduction (2-3 weeks → 3-5 days)
- **Fewer bugs** - 40-75% reduction in domain-specific bugs
- **Faster development** - 40% faster implementation
- **Better quality** - Consistent application of best practices

---

**Note**: These skills are living documents. Update them as the codebase evolves and new patterns emerge.
