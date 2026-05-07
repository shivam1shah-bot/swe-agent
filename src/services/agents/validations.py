"""Parameter validations for Autonomous Agent service."""

from typing import Dict, Tuple, List
import re


def extract_owner_repo(repository_url: str) -> Tuple[str, str]:
    """Extract owner and repo from GitHub URL; raises ValueError on failure."""
    if not repository_url:
        raise ValueError("Repository URL is required")
    url = repository_url.strip()
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
        raise ValueError("Repository URL must include owner and repo name, e.g. https://github.com/razorpay/<repo>")
    return parts[0], parts[1]


def validate_repository_url(repository_url: str) -> str:
    """Validate repo URL belongs to razorpay org and repo name pattern is safe."""
    if not (repository_url.startswith("https://github.com/") or repository_url.startswith("git@github.com:")):
        raise ValueError(f"Invalid repository URL: {repository_url}. Must be a GitHub repository URL.")
    owner, repo_name = extract_owner_repo(repository_url)
    if owner != "razorpay":
        raise ValueError("Repository must belong to the 'razorpay' organization")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", repo_name):
        raise ValueError(f"Invalid repository name: {repo_name}")
    return repository_url


def validate_branch_name(branch: str) -> str:
    """Validate feature branch name; disallow main/master and unsafe patterns."""
    branch_normalized = branch.strip()
    if branch_normalized.lower() in {"main", "master"}:
        raise ValueError(f"Branch '{branch}' is not allowed. Please use a feature branch.")
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", branch_normalized):
        raise ValueError(f"Invalid branch name: {branch}")
    if branch_normalized.startswith('/') or branch_normalized.endswith('/'):
        raise ValueError(f"Invalid branch name (cannot start/end with '/'): {branch}")
    if ' ' in branch_normalized or '..' in branch_normalized or '@' in branch_normalized:
        raise ValueError(f"Invalid branch name: {branch}")
    return branch_normalized


def validate_parameters(parameters: Dict[str, str]) -> None:
    """Top-level parameter validation for autonomous agent service."""
    prompt_val = parameters.get("prompt", None)
    if not isinstance(prompt_val, str) or not prompt_val.strip():
        raise ValueError("Missing required parameter: prompt")

    repo_val = parameters.get("repository_url", None)
    if not isinstance(repo_val, str) or not repo_val.strip():
        raise ValueError("Missing required parameter: repository_url")
    validate_repository_url(repo_val.strip())

    branch = parameters.get("branch", None)
    if isinstance(branch, str) and branch:
        validate_branch_name(branch)


# Expose required parameters for validator discovery to enforce presence
REQUIRED_PARAMETERS: List[str] = ["prompt", "repository_url"]

def required_parameters() -> List[str]:
    return REQUIRED_PARAMETERS


