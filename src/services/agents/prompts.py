"""Prompt builders for Autonomous Agent service."""

from typing import Optional, Tuple, List, Dict, Any  # noqa: F401


def _extract_owner_repo_parts(repository_url: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract owner and repo parts from a GitHub URL (https or git@)."""
    url = (repository_url or "").strip()
    if url.startswith("https://github.com/"):
        path_part = url[len("https://github.com/"):]
    elif url.startswith("git@github.com:"):
        path_part = url[len("git@github.com:"):]
    else:
        path_part = url

    if path_part.endswith(".git"):
        path_part = path_part[:-4]

    parts = [p for p in path_part.split('/') if p]
    if len(parts) < 2:
        return None, None
    return parts[0], parts[1]


def build_combined_prompt(repository_url: str, branch: Optional[str], user_prompt: str, skills: Optional[List[str]] = None) -> str:
    """
    Build the full prompt for the autonomous agent, including:
    - gh clone instructions
    - branch requirements
    - mandatory commit/push/draft PR steps (prominent at the top)
    - appended user prompt
    """
    owner, repo = _extract_owner_repo_parts(repository_url)
    repo_dir_name = repo

    clone_lines = []
    if owner and repo:
        clone_lines.append(f"gh repo clone {owner}/{repo} -- --depth 1 --single-branch --branch master")
        if repo_dir_name:
            clone_lines.append(f"cd {repo_dir_name}")
    else:
        clone_lines.append(f"gh repo clone {repository_url} -- --depth 1 --single-branch --branch master")

    if branch:
        branch_instruction = (
            f"Use the feature branch '{branch}'. If it does not exist, create it from master. "
            "Never commit to main or master."
        )
    else:
        branch_instruction = "Create a new feature branch from master with a short, descriptive name (never use main or master)."

    setup_instructions = "\n".join([
        "Repository Setup (use gh CLI only):",
        *clone_lines,
        branch_instruction,
    ])

    post_change_instructions = "\n".join([
        "After implementing the requested changes:",
        "0. Verify the code builds/compiles before staging any changes:",
        "   - Detect the language from project files and run only if the tool is available:",
        "     go.mod → run: go build ./...",
        "     package.json with a 'build' script → run: npm run build",
        "     requirements.txt/setup.py → run: python -m py_compile <each changed .py file>",
        "     Java/Kotlin (pom.xml/build.gradle) → skip (build tools not available in this environment)",
        "   - If the build fails, fix ALL errors before proceeding.",
        "   - If none of the above apply, skip this step.",
        "1. Stage all changes: git add -A",
        "2. Commit with a clear message: git commit -m \"chore: apply requested changes via autonomous agent\"",
        f"3. Push the branch: git push -u origin {'<your-branch>' if not branch else branch}",
        "4. Open a DRAFT Pull Request using gh CLI with a meaningful title and body:",
        "   gh pr create --title \"chore: apply requested changes via autonomous agent\" --body \"Automated changes by autonomous agent.\" --draft",
    ])

    skills_section = ""
    if skills:
        skill_list = "\n".join(f"   - {s}" for s in skills)
        skills_section = (
            "\nAVAILABLE SKILLS:\n"
            "The following skills have been provided for this task:\n"
            f"{skill_list}\n\n"
            "Additional skills may also be present in the repository's own `.claude/skills/` directory.\n"
            "Use the Skill tool to invoke any skill when it is relevant to the task at hand.\n"
            "Each skill contains specific instructions, checklists, and guidance — follow them when you use a skill.\n"
        )

    combined_prompt = (
        f"{setup_instructions}\n\n"
        "MANDATORY: Ensure that all modifications are committed, pushed to the feature branch, and a DRAFT PR is created as described below.\n"
        f"{post_change_instructions}\n"
        f"{skills_section}\n"
        "User Task:\n"
        f"{user_prompt}"
    )

    return combined_prompt


def build_multi_repo_prompt(
    repositories: List[Dict[str, Any]],
    cloned_repo_names: List[str],
    prompt: str,
    task_id: str,
) -> str:
    """
    Build the prompt for multi-repo single-agent execution.

    All repositories are already cloned into the current working directory.
    Claude works across them as a single process — no agent teams, no spawning.

    Workspace layout:
      working_dir/
        .claude/skills/   <- skills already injected here
        scrooge/          <- cloned repo
        terminals/        <- cloned repo
    """
    group_tag = task_id[:8] if task_id else "multi-repo"

    repo_lines = []
    for i, name in enumerate(cloned_repo_names, start=1):
        repo = repositories[i - 1] if i - 1 < len(repositories) else {}
        branch = repo.get("branch", "")
        branch_info = f" (branch: {branch})" if branch else ""
        repo_lines.append(f"  - ./{name}/{branch_info}")

    repos_text = "\n".join(repo_lines)

    branch_instruction = (
        "For each repository, create a new feature branch from master with a short descriptive name "
        "(never commit to main or master)."
    )

    post_change_instructions = "\n".join([
        "After implementing changes in each repository:",
        "1. cd into the repository directory",
        "2. Verify the code builds/compiles before staging any changes:",
        "   - Detect the language from project files and run only if the tool is available:",
        "     go.mod → run: go build ./...",
        "     package.json with a 'build' script → run: npm run build",
        "     requirements.txt/setup.py → run: python -m py_compile <each changed .py file>",
        "     Java/Kotlin (pom.xml/build.gradle) → skip (build tools not available in this environment)",
        "   - If the build fails, fix ALL errors before proceeding.",
        "   - If none of the above apply, skip this step.",
        "3. Stage all changes: git add -A",
        "4. Commit: git commit -m \"chore: apply requested changes via autonomous agent\"",
        "5. Push the branch: git push -u origin <your-branch>",
        f"6. Open a DRAFT Pull Request. The PR body MUST include the tag: [group:{group_tag}]",
        f"   gh pr create --title \"chore: multi-repo change\" --body \"Automated changes by autonomous agent. [group:{group_tag}]\" --draft",
        "7. cd back to the workspace root and repeat for the next repository",
    ])

    return (
        "You are working in a shared workspace where all repositories have already been cloned.\n\n"
        f"Cloned repositories in this workspace:\n{repos_text}\n\n"
        f"{branch_instruction}\n\n"
        "MANDATORY: For every repository listed above, implement the task, commit, push, and open a DRAFT PR.\n"
        f"{post_change_instructions}\n\n"
        "User Task:\n"
        f"{prompt}"
    )


def build_clean_slate_prompt(user_prompt: str, skills: Optional[List[str]] = None, slack_channel: Optional[str] = None) -> str:
    """
    Build the prompt for clean slate (no repository) agent execution.

    Instructs the agent to work in a fresh temp directory, create files from
    scratch, and NOT attempt any git operations or remote pushes.
    """
    skills_section = ""
    if skills:
        skill_list = "\n".join(f"   - {s}" for s in skills)
        skills_section = (
            "\nAVAILABLE SKILLS:\n"
            "The following skills have been provided for this task. "
            "You MUST use the Skill tool to invoke the relevant skill(s) before proceeding:\n"
            f"{skill_list}\n\n"
            "Use the Skill tool to invoke each skill as needed for this task.\n"
        )

    output_note = ""
    if slack_channel:
        channel = slack_channel.lstrip('#')
        output_note = (
            f"\nNOTE: Your complete output will be automatically posted to #{channel} "
            f"when the task completes. Focus on producing the best possible output — "
            f"do NOT attempt to post to Slack yourself.\n"
        )

    return (
        "You are working in a fresh workspace. No repository has been provided.\n\n"
        "IMPORTANT RULES:\n"
        "1. Work only within the current working directory.\n"
        "2. Create any files and directories you need from scratch.\n"
        "3. Do NOT attempt to clone any repository.\n"
        "4. Do NOT run git push or attempt to connect to any remote git server.\n"
        "5. Your output artifacts will remain in the workspace directory.\n"
        f"{skills_section}"
        f"{output_note}\n"
        f"User Task:\n{user_prompt}"
    )
