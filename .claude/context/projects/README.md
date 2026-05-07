# Projects

This directory contains project-specific context and configuration for active projects.

## Purpose
Organize context by project, allowing Claude to load specific knowledge and instructions for different initiatives.

## Structure
Each project should have its own directory with:
- `CLAUDE.md` - Project-specific instructions (overrides root CLAUDE.md)
- `context.md` - Project background and goals
- `tasks.md` - Active tasks and progress
- `notes.md` - Important notes and decisions

## Project Hierarchy
More specific CLAUDE.md files override broader ones:
1. Root `/CLAUDE.md` - Global instructions
2. `.claude/CLAUDE.md` - Claude-specific context
3. `.claude/context/projects/PROJECT_NAME/CLAUDE.md` - Project-specific instructions

## Example Structure
```
projects/
├── README.md (this file)
├── example-feature/
│   ├── CLAUDE.md (project instructions)
│   ├── context.md (background)
│   ├── tasks.md (tasks list)
│   └── notes.md (important notes)
└── another-project/
    ├── CLAUDE.md
    └── ...
```

## Usage
When working on a specific project, Claude will:
1. Load root CLAUDE.md for global context
2. Load project-specific CLAUDE.md for specialized instructions
3. Follow project-specific guidelines that override global ones

## Creating New Projects
To create a new project context:
1. Create a directory: `.claude/context/projects/project-name/`
2. Add a CLAUDE.md with project-specific instructions
3. Optionally add context.md, tasks.md, notes.md
4. Reference the project when starting work on it
