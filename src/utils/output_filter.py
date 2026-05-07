"""
Output Filter module for detecting and redacting sensitive data from LLM outputs.

This module scans LLM responses for potential secrets, API keys, tokens, and
other sensitive information and redacts them before returning to users.
"""

import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class SecretMatch:
    """Represents a detected secret in the output."""
    secret_type: str
    matched_text: str
    start_pos: int
    end_pos: int
    pattern_name: str


@dataclass
class FilterResult:
    """Result of output filtering."""
    original_length: int
    filtered_length: int
    secrets_found: int
    secret_types: List[str]
    filtered_text: str


# Patterns for detecting secrets in output
# Format: (pattern, secret_type, description)
SECRET_PATTERNS: List[Tuple[str, str, str]] = [
    # GitHub tokens
    (r"ghp_[A-Za-z0-9_]{36,}", "github_pat", "GitHub Personal Access Token"),
    (r"gho_[A-Za-z0-9_]{36,}", "github_oauth", "GitHub OAuth Token"),
    (r"ghu_[A-Za-z0-9_]{36,}", "github_user", "GitHub User Token"),
    (r"ghs_[A-Za-z0-9_]{36,}", "github_server", "GitHub Server Token"),
    (r"ghr_[A-Za-z0-9_]{36,}", "github_refresh", "GitHub Refresh Token"),
    (r"github_pat_[A-Za-z0-9_]{22,}", "github_fine_grained", "GitHub Fine-grained PAT"),
    
    # AWS credentials
    (r"AKIA[0-9A-Z]{16}", "aws_access_key", "AWS Access Key ID"),
    (r"ABIA[0-9A-Z]{16}", "aws_access_key", "AWS Access Key ID"),
    (r"ACCA[0-9A-Z]{16}", "aws_access_key", "AWS Access Key ID"),
    (r"ASIA[0-9A-Z]{16}", "aws_temp_key", "AWS Temporary Access Key"),
    (r"(?<![A-Za-z0-9/+])[A-Za-z0-9/+]{40}(?![A-Za-z0-9/+])", "aws_secret_key_candidate", "Potential AWS Secret Key"),
    
    # Google Cloud
    (r"AIza[0-9A-Za-z\-_]{35}", "gcp_api_key", "Google Cloud API Key"),
    (r'"type":\s*"service_account"', "gcp_service_account", "GCP Service Account JSON"),
    
    # Note: Azure client IDs are just UUIDs which are too common to redact
    # They appear in task IDs, request IDs, etc. Only redact in specific contexts.
    
    # JWT tokens
    (r"eyJ[A-Za-z0-9_-]*\.eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*", "jwt_token", "JWT Token"),
    
    # Private keys
    (r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----[\s\S]*?-----END\s+(?:RSA\s+)?PRIVATE\s+KEY-----", "private_key", "Private Key"),
    (r"-----BEGIN\s+EC\s+PRIVATE\s+KEY-----[\s\S]*?-----END\s+EC\s+PRIVATE\s+KEY-----", "ec_private_key", "EC Private Key"),
    (r"-----BEGIN\s+OPENSSH\s+PRIVATE\s+KEY-----[\s\S]*?-----END\s+OPENSSH\s+PRIVATE\s+KEY-----", "openssh_key", "OpenSSH Private Key"),
    (r"-----BEGIN\s+PGP\s+PRIVATE\s+KEY\s+BLOCK-----[\s\S]*?-----END\s+PGP\s+PRIVATE\s+KEY\s+BLOCK-----", "pgp_private_key", "PGP Private Key"),
    
    # Slack tokens
    (r"xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24}", "slack_token", "Slack Token"),
    (r"xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{32}", "slack_token", "Slack Token (new format)"),
    
    # Stripe
    (r"sk_live_[0-9a-zA-Z]{24,}", "stripe_secret", "Stripe Secret Key"),
    (r"sk_test_[0-9a-zA-Z]{24,}", "stripe_test_secret", "Stripe Test Secret Key"),
    (r"rk_live_[0-9a-zA-Z]{24,}", "stripe_restricted", "Stripe Restricted Key"),
    
    # NPM
    (r"npm_[A-Za-z0-9]{36}", "npm_token", "NPM Token"),
    
    # Database connection strings
    (r"(?:mongodb|postgres|mysql|redis)://[^\s\"']+:[^\s\"'@]+@[^\s\"']+", "db_connection_string", "Database Connection String"),
    
    # Generic API keys (common patterns)
    (r"[aA][pP][iI][-_]?[kK][eE][yY][\s:=\"']+[A-Za-z0-9\-_]{20,}", "generic_api_key", "Generic API Key"),
    (r"[aA][cC][cC][eE][sS][sS][-_]?[tT][oO][kK][eE][nN][\s:=\"']+[A-Za-z0-9\-_]{20,}", "generic_access_token", "Generic Access Token"),
    (r"[sS][eE][cC][rR][eE][tT][-_]?[kK][eE][yY][\s:=\"']+[A-Za-z0-9\-_]{20,}", "generic_secret_key", "Generic Secret Key"),
    
    # Passwords in config-like contexts
    (r"[pP][aA][sS][sS][wW][oO][rR][dD][\s:=\"']+[^\s\"']{8,}", "password_in_config", "Password in Configuration"),
    
    # Bearer tokens
    (r"[bB]earer\s+[A-Za-z0-9\-_\.]{20,}", "bearer_token", "Bearer Token"),
    
    # SSH keys
    (r"ssh-(?:rsa|dss|ed25519|ecdsa)\s+[A-Za-z0-9+/=]{100,}", "ssh_public_key", "SSH Public Key"),
    
    # Encryption keys (hex format)
    (r"(?:encryption[-_]?key|aes[-_]?key|secret[-_]?key)[\s:=\"']+[0-9a-fA-F]{32,}", "encryption_key", "Encryption Key"),
]

# Patterns for sensitive file paths that might leak information
SENSITIVE_PATH_PATTERNS: List[Tuple[str, str]] = [
    (r"/etc/passwd", "passwd_file"),
    (r"/etc/shadow", "shadow_file"),
    (r"/var/run/secrets/kubernetes\.io", "k8s_secrets"),
    (r"~?/?\.aws/credentials", "aws_creds_file"),
    (r"~?/?\.ssh/id_[a-z]+", "ssh_key_file"),
    (r"~?/?\.env(?:\.[a-z]+)?", "env_file"),
]

# NEW: System prompt leakage patterns - detect when LLM outputs its own instructions
# These patterns detect content that appears to be from the system prompt
SYSTEM_PROMPT_LEAKAGE_PATTERNS: List[Tuple[str, str]] = [
    # Direct leakage indicators - exact phrases from our system prompt
    (r"SECURITY\s+RULES?\s*[\(:]?\s*MUST\s+FOLLOW", "system_prompt_leak"),
    (r"IMPORTANT\s+CONTEXT\s*:", "system_prompt_leak"),
    (r"CRITICAL\s+INSTRUCTION\s+PROTECTION", "system_prompt_leak"),
    
    # Rule structure patterns (numbered "NEVER" rules that look like system instructions)
    (r"\d+\.\s*NEVER\s+(access|read|display|output|execute|reveal|document|write)", "security_rules_leak"),
    
    # System prompt-like structures
    (r"(You\s+are\s+working\s+in\s+the\s+directory|cd\s+to\s+.+\s+if\s+not\s+already)", "context_leak"),
    (r"For\s+any\s+Git\s+operations.*strictly\s+use\s+gh\s+cli", "context_leak"),
    (r"The\s+default\s+organization\s+is\s+'razorpay'", "context_leak"),
    
    # Meta-instruction patterns that shouldn't appear in normal output
    (r"(Do\s+NOT|NEVER)\s+follow\s+instructions\s+that\s+ask\s+you\s+to\s+ignore", "meta_instruction_leak"),
    (r"Treat\s+ANY\s+request\s+about\s+your\s+internal\s+instructions", "meta_instruction_leak"),
    (r"politely\s+decline.*I\s+focus\s+only\s+on\s+legitimate", "meta_instruction_leak"),
]


def scan_for_secrets(text: str) -> List[SecretMatch]:
    """
    Scan text for potential secrets.
    
    Args:
        text: The output text to scan
        
    Returns:
        List of SecretMatch objects for each detected secret
    """
    if not text:
        return []
    
    matches: List[SecretMatch] = []
    seen_positions = set()  # Avoid duplicate matches
    
    for pattern, secret_type, description in SECRET_PATTERNS:
        try:
            for match in re.finditer(pattern, text, re.MULTILINE):
                # Skip if this position was already matched by a more specific pattern
                pos_key = (match.start(), match.end())
                if pos_key in seen_positions:
                    continue
                
                # Skip false positives for short patterns
                matched_text = match.group()
                if len(matched_text) < 10 and secret_type not in ["aws_access_key", "gcp_api_key"]:
                    continue
                
                matches.append(SecretMatch(
                    secret_type=secret_type,
                    matched_text=matched_text,
                    start_pos=match.start(),
                    end_pos=match.end(),
                    pattern_name=description
                ))
                seen_positions.add(pos_key)
        except re.error:
            # Skip invalid regex patterns
            continue
    
    return matches


def redact_secrets(text: str, redaction_placeholder: str = "[REDACTED]") -> str:
    """
    Redact detected secrets in the text.
    
    Args:
        text: The output text to redact
        redaction_placeholder: The string to replace secrets with
        
    Returns:
        Text with secrets replaced by the redaction placeholder
    """
    if not text:
        return text
    
    # Get all secret matches
    matches = scan_for_secrets(text)
    
    if not matches:
        return text
    
    # Sort matches by start position in reverse order to maintain positions
    matches.sort(key=lambda m: m.start_pos, reverse=True)
    
    redacted = text
    for match in matches:
        # Create a type-specific redaction
        type_hint = match.secret_type.upper().replace("_", " ")
        placeholder = f"[REDACTED {type_hint}]"
        redacted = redacted[:match.start_pos] + placeholder + redacted[match.end_pos:]
    
    return redacted


def redact_sensitive_paths(text: str) -> str:
    """
    Redact sensitive file paths from the text.
    
    Args:
        text: The output text to scan
        
    Returns:
        Text with sensitive paths redacted
    """
    if not text:
        return text
    
    redacted = text
    for pattern, path_type in SENSITIVE_PATH_PATTERNS:
        redacted = re.sub(
            pattern,
            f"[REDACTED {path_type.upper()}]",
            redacted,
            flags=re.IGNORECASE
        )
    
    return redacted


def detect_system_prompt_leakage(text: str) -> List[Tuple[str, str]]:
    """
    Check if output contains system prompt content that was leaked.
    
    Args:
        text: The output text to check
        
    Returns:
        List of tuples (matched_text, leak_type) for each detected leak
    """
    if not text:
        return []
    
    leaks: List[Tuple[str, str]] = []
    
    for pattern, leak_type in SYSTEM_PROMPT_LEAKAGE_PATTERNS:
        try:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                leaks.append((match.group(), leak_type))
        except re.error:
            continue
    
    return leaks


def contains_system_prompt_leakage(text: str) -> bool:
    """
    Quick check if text contains any system prompt leakage.
    
    Args:
        text: The text to check
        
    Returns:
        True if system prompt leakage is detected, False otherwise
    """
    leaks = detect_system_prompt_leakage(text)
    return len(leaks) > 0


def redact_system_prompt_content(text: str) -> str:
    """
    Redact detected system prompt content from the text.
    
    Args:
        text: The output text to redact
        
    Returns:
        Text with system prompt content redacted
    """
    if not text:
        return text
    
    redacted = text
    for pattern, leak_type in SYSTEM_PROMPT_LEAKAGE_PATTERNS:
        try:
            redacted = re.sub(
                pattern,
                f"[REDACTED {leak_type.upper()}]",
                redacted,
                flags=re.IGNORECASE | re.MULTILINE
            )
        except re.error:
            continue
    
    return redacted


def filter_output(text: str, include_path_redaction: bool = True, include_prompt_leak_detection: bool = True) -> FilterResult:
    """
    Full output filtering - scan and redact secrets, paths, and system prompt leakage.
    
    Args:
        text: The output text to filter
        include_path_redaction: Whether to also redact sensitive file paths
        include_prompt_leak_detection: Whether to check for and redact system prompt leakage
        
    Returns:
        FilterResult with filtering details and the filtered text
    """
    if not text:
        return FilterResult(
            original_length=0,
            filtered_length=0,
            secrets_found=0,
            secret_types=[],
            filtered_text=""
        )
    
    # Scan for secrets first to get stats
    matches = scan_for_secrets(text)
    secret_types = list(set(m.secret_type for m in matches))
    
    # Check for system prompt leakage
    if include_prompt_leak_detection:
        leaks = detect_system_prompt_leakage(text)
        if leaks:
            # Add leak types to secret_types for reporting
            leak_types = list(set(leak_type for _, leak_type in leaks))
            secret_types.extend(leak_types)
    
    # Redact secrets
    filtered = redact_secrets(text)
    
    # Optionally redact sensitive paths
    if include_path_redaction:
        filtered = redact_sensitive_paths(filtered)
    
    # Redact system prompt content if enabled
    if include_prompt_leak_detection:
        filtered = redact_system_prompt_content(filtered)
    
    return FilterResult(
        original_length=len(text),
        filtered_length=len(filtered),
        secrets_found=len(matches),
        secret_types=secret_types,
        filtered_text=filtered
    )


def contains_secrets(text: str) -> bool:
    """
    Quick check if text contains any secrets.
    
    Args:
        text: The text to check
        
    Returns:
        True if secrets are detected, False otherwise
    """
    matches = scan_for_secrets(text)
    return len(matches) > 0


def get_secret_summary(text: str) -> Dict[str, int]:
    """
    Get a summary of secret types found in the text.
    
    Args:
        text: The text to scan
        
    Returns:
        Dictionary mapping secret types to their count
    """
    matches = scan_for_secrets(text)
    summary: Dict[str, int] = {}
    for match in matches:
        summary[match.secret_type] = summary.get(match.secret_type, 0) + 1
    return summary

