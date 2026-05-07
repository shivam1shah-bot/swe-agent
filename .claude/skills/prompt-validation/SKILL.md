---
name: prompt-validation
description: Understanding prompt validation in autonomous agents. Use when working with prompt injection detection, validation rules, security patterns, or troubleshooting validation failures. Covers the 3-layer validation system (API, Service, Tool), pattern-based and LLM-based detection, output filtering, and how to modify validation rules.
---

# Prompt Validation

## Overview

Autonomous agents use a **3-layer defense-in-depth validation system** to prevent prompt injection attacks and ensure secure execution.

## Validation Flow

```
User Request
    ↓
Layer 1: API Router (tasks.py)
    → Pattern-based prompt injection scan
    ↓
Layer 2: Service (service.py)
    → Parameter validation
    → Repository access control (private repos only)
    ↓
Layer 3: Tool (autonomous_agent.py)
    → Pattern-based validation (prompt_guard.py)
    → LLM semantic validation (llm_prompt_validator.py)
    ↓
Execution → Output Filtering (output_filter.py)
    → Secret redaction
    → System prompt leakage detection
    ↓
Return to User
```

## Key Files

### Validation Components

**Pattern-Based Detection:**
- `src/utils/prompt_guard.py` - Regex pattern matching for injection attempts
  - Threat levels: SAFE, SUSPICIOUS, MALICIOUS
  - Pattern categories:
    - INJECTION_PATTERNS: System override, env extraction, sensitive files, credentials, SQL injection
    - BLOCKED_KEYWORDS: Jailbreak terms, reverse shell, credential theft (13 keywords)
    - INSTRUCTION_EXTRACTION_PATTERNS: System prompt extraction, k8s secrets, git credentials
    - OS_COMMAND_PATTERNS: Destructive commands, reverse shells, data exfiltration, network scanning
    - SUSPICIOUS_PATTERNS: curl, ps, docker (logged but allowed for debugging)

**LLM-Based Detection:**
- `src/utils/llm_prompt_validator.py` - Semantic analysis using Claude Haiku/Vertex AI
  - Detects sophisticated, obfuscated injection attempts
  - Temperature=0 for deterministic output
  - 20-second timeout (fail-closed on timeout)
  - Results: SAFE, INJECTION_DETECTED, VALIDATION_ERROR, DISABLED

**Output Filtering:**
- `src/utils/output_filter.py` - Post-execution filtering
  - Redacts secrets (GitHub tokens, AWS keys, JWT, private keys, etc.)
  - Detects system prompt leakage (numbered rules, meta-instructions)

**Service Validation:**
- `src/services/agents_catalogue/autonomous_agent/service.py` - Business logic validation
  - `_validate_parameters()` - Parameter presence and format
  - `_validate_repository_access()` - Private repository check

**API Validation:**
- `src/api/routers/tasks.py` - First-line defense
  - `_validate_task_parameters()` - Initial prompt scan

### Agent Integration

**Main Agent:**
- `src/agents/autonomous_agent.py` - Orchestrates validation in `_run_agent()`
  - Calls prompt_guard for pattern-based check
  - Calls llm_prompt_validator for semantic check
  - Blocks if either detects injection

## Common Tasks

### Modifying Pattern-Based Rules

Edit `src/utils/prompt_guard.py`:

```python
# Add new blocked command
BLOCKED_COMMANDS = [
    "existing_commands",
    "new_command_to_block",  # Add here
]

# Add new injection pattern
INJECTION_PATTERNS = {
    "new_category": [
        r"new_pattern_regex",
    ]
}
```

### Adjusting LLM Validation

Edit `src/utils/llm_prompt_validator.py`:

```python
# Change timeout (default: 20 seconds)
timeout = 30  # Increase for slower LLM responses

# Disable LLM validation (fallback to pattern-only)
# Check config: config["llm_validation"]["enabled"] = False
```

### Adding Output Filters

Edit `src/utils/output_filter.py`:

```python
# Add new secret pattern
SECRET_PATTERNS = [
    r"existing_patterns",
    r"new_secret_pattern",  # Add here
]

# Add new system prompt leakage pattern
SYSTEM_PROMPT_PATTERNS = [
    r"existing_patterns",
    r"new_leakage_pattern",  # Add here
]
```

### Configuring Repository Access

Edit `src/services/agents_catalogue/autonomous_agent/validations.py`:

```python
# Modify branch name validation
BRANCH_NAME_PATTERN = r"[A-Za-z0-9._/-]+"  # Current pattern

# Modify forbidden branches
if branch in ["main", "master", "new_forbidden_branch"]:
    raise ValueError(f"Cannot use branch: {branch}")
```

## Security Principles

**Fail-Closed Approach:**
- Validation errors → Block request (never allow-by-default)
- LLM timeout → Block request
- Repository access failure → Block request

**Validation Characteristics:**
- Multiple overlapping defense layers
- Pattern + semantic analysis
- Comprehensive logging for security audit
- Output filtering prevents data exfiltration

**Threat Levels:**
```python
SAFE         # No injection detected
SUSPICIOUS   # Low-priority patterns matched (logged, allowed)
MALICIOUS    # High-confidence injection (blocked, logged)
```

**What Gets BLOCKED (MALICIOUS):**
- Jailbreak attempts: "DAN mode", "ignore all safety", "bypass all filters"
- Reverse shells: nc -e, bash -i /dev/tcp, python socket
- Credential theft: "steal credentials", "exfiltrate secrets"
- System destruction: rm -rf /, shutdown, useradd, chmod /etc
- K8s exploitation: kubectl exec -it, kubectl get secret -o yaml
- Git abuse: git push --force main
- Data exfiltration: curl -d $SECRET, wget --post-data

**What Gets ALLOWED (SUSPICIOUS - logged for monitoring):**
- Debug commands: ps, top, htop, env, printenv
- Network tools: curl, wget, ssh (without malicious patterns)
- Container ops: docker exec, docker inspect
- File inspection: cat /, ls -la /

**What Gets ALLOWED (SAFE):**
- Normal development tasks
- Code analysis requests
- DevRev ticket work
- GitHub Actions optimization
- Repository exploration

## Troubleshooting

### False Positive (Legitimate Prompt Blocked)

**Symptom:** Valid development prompt rejected

**Check:**
1. Review logs for which layer blocked it
2. Pattern-based: Check `prompt_guard.py` patterns
3. LLM-based: Review LLM validation logic in `llm_prompt_validator.py`

**Fix:**
- Pattern-based: Adjust regex in `prompt_guard.py`
- LLM-based: Update validation prompt to better recognize legitimate use case

### Validation Not Triggering

**Symptom:** Injection attempts passing through

**Check:**
1. Verify all 3 layers are active
2. Check LLM validation enabled: `config["llm_validation"]["enabled"]`
3. Review logs for validation execution

**Fix:**
- Enable missing validation layer
- Add missing patterns to `prompt_guard.py`
- Update LLM validation prompt

### LLM Validation Timeout

**Symptom:** Requests blocked due to timeout

**Check:**
1. Review timeout setting (default: 20s)
2. Check LLM provider availability (Vertex AI → Anthropic fallback)

**Fix:**
- Increase timeout in `llm_prompt_validator.py`
- Check LLM provider credentials/connectivity

### Repository Access Denied

**Symptom:** "Private repository required" error

**Check:**
1. Repository visibility setting
2. GitHub authentication
3. User permissions

**Fix:**
- Ensure repository is private
- Verify GitHub token has correct permissions
- Check `GitHubAuthService` configuration

## File Locations Quick Reference

| Component | File | Line/Function |
|-----------|------|---------------|
| Pattern validation | `utils/prompt_guard.py` | `validate_prompt_or_raise()` |
| LLM validation | `utils/llm_prompt_validator.py` | `validate()` |
| Output filtering | `utils/output_filter.py` | `filter_output()` |
| Service validation | `services/.../service.py` | `_validate_parameters()` |
| API validation | `api/routers/tasks.py` | `_validate_task_parameters()` |
| Agent integration | `agents/autonomous_agent.py` | `_run_agent()` |
| Repository rules | `services/.../validations.py` | Multiple functions |
