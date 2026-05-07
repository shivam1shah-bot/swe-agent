# GitHub CLI (gh) Tool

## Overview
GitHub CLI (`gh`) is used by SWE Agent for repository operations, PR creation, and issue management. It provides a command-line interface to GitHub's API.

## Installation
```bash
# macOS
brew install gh

# Linux
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update
sudo apt install gh

# Verify installation
gh --version
```

## Authentication
```bash
# Interactive authentication
gh auth login

# With token
gh auth login --with-token < token.txt

# Check authentication status
gh auth status
```

## Common Operations

### Repository Operations
```bash
# Clone repository
gh repo clone owner/repo

# View repository info
gh repo view owner/repo

# Create repository
gh repo create my-new-repo --public
```

### Pull Request Operations
```bash
# Create PR
gh pr create --title "Feature: Add authentication" \
  --body "Implements JWT authentication" \
  --base main \
  --head feature/auth

# List PRs
gh pr list

# View PR details
gh pr view 123

# Merge PR
gh pr merge 123 --squash

# Check PR status
gh pr status

# Checkout PR locally
gh pr checkout 123
```

### Issue Operations
```bash
# Create issue
gh issue create --title "Bug: Fix null pointer" \
  --body "Description of the bug"

# List issues
gh issue list

# View issue details
gh issue view 456

# Close issue
gh issue close 456
```

### Workflow Operations
```bash
# List workflows
gh workflow list

# View workflow runs
gh run list

# View specific run
gh run view 789

# Re-run workflow
gh run rerun 789
```

## SWE Agent Integration

### In Python Code
```python
import subprocess
import json

# Create PR via gh CLI
def create_pr(title: str, body: str, head: str, base: str = "main") -> dict:
    result = subprocess.run([
        "gh", "pr", "create",
        "--title", title,
        "--body", body,
        "--head", head,
        "--base", base,
        "--json", "url,number"
    ], capture_output=True, text=True, check=True)

    return json.loads(result.stdout)

# Usage
pr = create_pr(
    title="Feature: Add authentication",
    body="Implements JWT authentication middleware",
    head="feature/auth"
)
print(f"Created PR #{pr['number']}: {pr['url']}")
```

### List and Filter PRs
```python
# Get open PRs
result = subprocess.run([
    "gh", "pr", "list",
    "--state", "open",
    "--json", "number,title,author,url"
], capture_output=True, text=True, check=True)

prs = json.loads(result.stdout)
for pr in prs:
    print(f"PR #{pr['number']}: {pr['title']} by {pr['author']['login']}")
```

### Check PR Status
```python
# Get PR check status
result = subprocess.run([
    "gh", "pr", "view", "123",
    "--json", "statusCheckRollup"
], capture_output=True, text=True, check=True)

pr_status = json.loads(result.stdout)
checks = pr_status['statusCheckRollup']

all_passed = all(
    check['conclusion'] == 'SUCCESS'
    for check in checks
)
```

## GitHub Provider Integration

SWE Agent uses PyGithub for more complex operations:

```python
from github import Github

# Initialize
github = Github(token)

# Get repository
repo = github.get_repo("owner/repo")

# Create PR
pr = repo.create_pull(
    title="Feature: Add authentication",
    body="Implements JWT authentication",
    head="feature/auth",
    base="main"
)

# Add reviewers
pr.create_review_request(reviewers=["user1", "user2"])

# Add labels
pr.add_to_labels("enhancement", "authentication")
```

## Best Practices

1. **Use --json flag** for programmatic access
2. **Handle authentication** properly with tokens
3. **Check rate limits** to avoid API throttling
4. **Use draft PRs** for work-in-progress
5. **Add proper PR descriptions** with context and testing notes

## Common Use Cases in SWE Agent

### Automated PR Creation After Task
```bash
#!/bin/bash
# After implementing feature

# Create branch
git checkout -b feature/new-feature

# Make changes...
# ...

# Commit changes
git add .
git commit -m "feat: implement new feature"

# Push branch
git push -u origin feature/new-feature

# Create PR
gh pr create \
  --title "Feature: Implement new feature" \
  --body "$(cat << EOF
## Summary
Implements new feature X

## Changes
- Added feature implementation
- Updated tests
- Updated documentation

## Test Plan
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed
EOF
)" \
  --base main
```

### Check CI Status Before Merge
```python
async def can_merge_pr(pr_number: int) -> bool:
    """Check if PR is ready to merge"""

    # Get PR status
    result = subprocess.run([
        "gh", "pr", "view", str(pr_number),
        "--json", "mergeable,statusCheckRollup,reviewDecision"
    ], capture_output=True, text=True, check=True)

    pr_data = json.loads(result.stdout)

    # Check conditions
    is_mergeable = pr_data['mergeable'] == 'MERGEABLE'
    all_checks_pass = all(
        check['conclusion'] == 'SUCCESS'
        for check in pr_data.get('statusCheckRollup', [])
    )
    is_approved = pr_data.get('reviewDecision') == 'APPROVED'

    return is_mergeable and all_checks_pass and is_approved
```

## Environment Variables
```bash
# GitHub token
export GITHUB_TOKEN=ghp_your_token_here

# Default repository
export GH_REPO=owner/repo
```

## Troubleshooting

### Authentication Issues
```bash
# Re-authenticate
gh auth logout
gh auth login

# Check current authentication
gh auth status
```

### Rate Limiting
```bash
# Check rate limit status
gh api rate_limit

# Use authentication to increase rate limit
gh auth login
```

### Permission Issues
```bash
# Verify token has required scopes
gh auth status

# Required scopes:
# - repo (full control)
# - workflow (for GitHub Actions)
# - admin:org (for organization operations)
```

## Reference
- GitHub CLI documentation: https://cli.github.com/manual/
- GitHub API: https://docs.github.com/en/rest
- SWE Agent GitHub provider: `src/providers/github/global_auth.py`
- GitHub operations: `src/services/github_service.py`
