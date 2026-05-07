# On Task Start Hook

## Trigger
This hook is triggered when starting a new task or feature implementation.

## Instructions
When starting a new task:

1. **Understand Requirements**
   - Read and analyze the task description thoroughly
   - Check for any linked issues or documentation
   - Review related code or previous implementations

2. **Load Context**
   - Check if there's a project-specific CLAUDE.md in context/projects/
   - Review relevant memory from context/memory/
   - Load applicable skills from context/skills/
   - Check for relevant tools in context/tools/

3. **Create Implementation Plan**
   - Break down the task into specific steps
   - Identify files that need to be modified
   - Determine testing strategy
   - Estimate effort and identify risks

4. **Ask Clarifying Questions**
   - If requirements are unclear, ask specific questions
   - Confirm understanding of expected behavior
   - Verify assumptions about scope and approach
   - Get user approval before proceeding

5. **Set Up Environment**
   - Ensure development environment is ready
   - Verify dependencies are installed
   - Check that services are running if needed

6. **Create Feature Branch**
   - Create a descriptive branch name
   - Ensure working from latest master/main

## Output
Present an implementation plan to the user and wait for approval before proceeding.
