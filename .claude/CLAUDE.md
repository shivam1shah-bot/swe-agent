# Claude Operating Instructions

Welcome! This file defines how Claude Code operates within this repository's `.claude` directory structure.

## Core Principles

### 1. Context-Aware Operation
Claude's behavior is defined by the files in the `.claude` directory:
- **agents/** - Different personalities or roles to adopt
- **commands/** - Custom commands that can be invoked
- **output-styles/** - Format templates for responses
- **hooks/** - Triggers for specific actions or events
- **context/** - Knowledge base and project information

### 2. Hierarchical Instructions
Claude follows a hierarchy of instruction files:
1. **Root `/CLAUDE.md`** - Global project guidelines (highest priority for project rules)
2. **`.claude/CLAUDE.md`** (this file) - Claude-specific operating instructions
3. **Project-specific `CLAUDE.md`** - Instructions for specific projects in `context/projects/`

**IMPORTANT**: Instructions in more specific contexts override broader ones. When working on a project in `context/projects/PROJECT_NAME/`, the instructions in that project's `CLAUDE.md` take precedence.

## Directory Structure

### `.claude/` Root
The brain of Claude's operation in this repository.

### `agents/` - Personalities & Roles
Contains different roles Claude can adopt:
- **code-reviewer.md** - Meticulous code review specialist
- **architect.md** - System architecture and design expert
- **debugger.md** - Debugging and troubleshooting specialist

**Usage**: When asked to act as a specific agent (e.g., "act as code reviewer"), load that agent's definition and follow its guidelines.

### `commands/` - Custom Commands
Defines specialized commands for common tasks:
- **analyze-architecture.md** - Analyze codebase architecture
- **review-pr.md** - Comprehensive PR review
- **setup-dev-env.md** - Guide environment setup

**Usage**: When a command is invoked (e.g., "/analyze-architecture"), load the command definition and execute its instructions.

### `output-styles/` - Response Formats
Templates for formatting responses:
- **code-review.md** - Structured code review format
- **architectural-report.md** - Architecture analysis format
- **implementation-plan.md** - Detailed implementation plan format

**Usage**: When asked to use a specific output style or when a command specifies one, format the response according to that template.

### `hooks/` - Event Triggers
Instructions triggered by specific events:
- **pre-commit.md** - Run before committing code
- **on-task-start.md** - Run when starting a new task
- **on-error.md** - Run when an error occurs

**Usage**: Automatically trigger these hooks at the appropriate times in the workflow.

### `context/` - Knowledge Base

#### `context/memory/`
Persistent memory and learned information:
- **project-facts.md** - Key facts about the project
- **user-preferences.md** - User preferences and working style
- **known-issues.md** - Known issues and workarounds
- **patterns.md** - Common patterns and solutions

**Usage**: Reference these files for context. Update as new patterns emerge or important facts are discovered.

#### `context/tools/`
Definitions of available external tools and how to use them.

**Usage**: Consult when needing to use external tools or integrations.

#### `context/skills/`
Descriptions of complex, multi-step skills Claude possesses.

**Usage**: Apply these skills when tasks require specialized capabilities.

#### `context/projects/`
Project-specific contexts and instructions.

**Structure**: Each project has its own directory with:
- `CLAUDE.md` - Project-specific instructions (overrides this file)
- `context.md` - Project background and goals
- `tasks.md` - Active tasks and progress
- `notes.md` - Important decisions and notes

**Usage**: When working on a specific project, load its context and follow its specific instructions.

## Operational Guidelines

### Task Start Workflow
1. **Load Context**
   - Read root `/CLAUDE.md` for project standards
   - Check if working on specific project in `context/projects/`
   - Load project-specific `CLAUDE.md` if available
   - Review relevant memory from `context/memory/`

2. **Trigger Hook**
   - Execute `hooks/on-task-start.md` instructions
   - Understand requirements
   - Ask clarifying questions
   - Create implementation plan

3. **Get Approval**
   - Present plan to user
   - Wait for explicit approval before proceeding

### During Task Execution
1. **Follow Standards**
   - Adhere to root `/CLAUDE.md` coding standards
   - Apply project-specific guidelines if in a project context
   - Use appropriate design patterns
   - Maintain code quality

2. **Apply Skills**
   - Use skills from `context/skills/` as needed
   - Follow agent guidelines if operating in a specific agent role
   - Use defined tools from `context/tools/`

3. **Handle Errors**
   - Trigger `hooks/on-error.md` when errors occur
   - Systematically debug and resolve
   - Document solutions in `context/memory/`

### Before Committing
1. **Trigger Hook**
   - Execute `hooks/pre-commit.md` instructions
   - Verify code quality
   - Ensure tests pass
   - Check for security issues

2. **Get Confirmation**
   - Review changes with user
   - Confirm all requirements met
   - Verify tests passing

### Command Invocation
When a command is invoked (e.g., `/review-pr`, `/analyze-architecture`):
1. Load the command definition from `commands/`
2. Execute the command's instructions
3. Use specified output style if defined
4. Return results to user

### Agent Role Adoption
When asked to act as a specific agent:
1. Load the agent definition from `agents/`
2. Adopt that agent's personality and focus areas
3. Follow agent-specific guidelines
4. Maintain agent role throughout interaction

### Output Formatting
When asked to use a specific output style or when a command specifies one:
1. Load the style template from `output-styles/`
2. Format response according to template
3. Ensure all sections are included
4. Provide structured, organized output

## Priority Rules

### Instruction Hierarchy
When conflicts arise, follow this priority order:
1. **Explicit user instructions** (always highest priority)
2. **Project-specific CLAUDE.md** (in `context/projects/PROJECT_NAME/`)
3. **Root `/CLAUDE.md`** (global project standards)
4. **`.claude/CLAUDE.md`** (this file - operational guidelines)
5. **Agent/Command/Hook specific instructions**

### File Creation Rules
- **NEVER create files unless absolutely necessary**
- **ALWAYS prefer editing existing files**
- **NEVER proactively create documentation files** unless explicitly requested
- Follow root `/CLAUDE.md` guidelines on file creation

### Code Quality
- Follow all coding standards from root `/CLAUDE.md`
- Use early error handling with guard clauses
- Include type hints on all functions
- Use async/await for I/O operations
- Maintain proper session cleanup

## Memory Management

### Updating Memory
As you work, update files in `context/memory/` when:
- New patterns emerge
- Important decisions are made
- Issues and solutions are discovered
- User preferences are learned

### Project Context
When working on a project:
- Keep `tasks.md` updated with progress
- Document decisions in `notes.md`
- Update context as requirements evolve

## Integration with Root CLAUDE.md

The root `/CLAUDE.md` contains project-specific technical guidelines:
- Development commands and workflows
- Architecture overview and patterns
- Testing strategy
- Code quality standards
- Service URLs and configuration

**Always reference root `/CLAUDE.md` for**:
- Project architecture and structure
- Coding standards and patterns
- Development workflows
- Service configuration
- Testing requirements

**Use `.claude/` structure for**:
- Behavioral guidelines (how Claude operates)
- Context and memory management
- Custom commands and agents
- Project-specific contexts
- Event-driven workflows (hooks)

## Examples

### Starting a New Task
```
User: "I need to add a new feature to handle user notifications"

Claude:
1. Triggers hooks/on-task-start.md
2. Loads root /CLAUDE.md for architecture patterns
3. Checks if this is part of a specific project
4. Asks clarifying questions about requirements
5. Creates implementation plan using output-styles/implementation-plan.md
6. Waits for user approval before proceeding
```

### Using a Command
```
User: "/review-pr 123"

Claude:
1. Loads commands/review-pr.md
2. Follows the command's instructions
3. Uses output-styles/code-review.md for formatting
4. References root /CLAUDE.md for code standards
5. Provides structured review feedback
```

### Adopting an Agent Role
```
User: "Act as the architect agent and analyze the current system"

Claude:
1. Loads agents/architect.md
2. Adopts architect personality and focus
3. May use commands/analyze-architecture.md
4. Uses output-styles/architectural-report.md
5. Provides architecture analysis from architect perspective
```

## Best Practices

1. **Always start by understanding context**
   - What task is being requested?
   - Is this part of a specific project?
   - What are the requirements and constraints?

2. **Plan before executing**
   - Create detailed implementation plans
   - Get user approval
   - Break down complex tasks

3. **Maintain quality standards**
   - Follow root `/CLAUDE.md` coding standards
   - Ensure proper testing
   - Document important decisions

4. **Be proactive but not presumptuous**
   - Suggest improvements
   - Ask clarifying questions
   - Don't make assumptions about requirements

5. **Learn and adapt**
   - Update memory with new patterns
   - Document solutions to problems
   - Improve efficiency over time

---

**Remember**: This `.claude` directory structure exists to make Claude more helpful, context-aware, and consistent. Always prioritize the user's explicit instructions while leveraging this structure to provide better assistance.
