"""
Prompt Guard module for detecting and preventing prompt injection attacks.

This module provides utilities for scanning user inputs for potential
injection patterns and sanitizing inputs before they reach the LLM.
"""

import re
from enum import Enum
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


class ThreatLevel(Enum):
    """Threat level classification for detected patterns."""
    SAFE = "safe"
    SUSPICIOUS = "suspicious"
    MALICIOUS = "malicious"


class PromptInjectionError(Exception):
    """Exception raised when a malicious prompt injection is detected."""
    
    def __init__(self, message: str, threat_level: ThreatLevel, matched_patterns: List[str]):
        self.message = message
        self.threat_level = threat_level
        self.matched_patterns = matched_patterns
        super().__init__(self.message)


@dataclass
class ScanResult:
    """Result of a prompt injection scan."""
    threat_level: ThreatLevel
    matched_patterns: List[str]
    is_safe: bool
    details: Dict[str, List[str]]


# Patterns that indicate prompt injection attempts - MALICIOUS level
INJECTION_PATTERNS: List[Tuple[str, str]] = [
    # System prompt override attempts
    (r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions?|context|prompts?)", "system_override"),
    (r"disregard\s+(all\s+)?(previous|prior|your)\s+(instructions?|rules?|guidelines?)", "system_override"),
    (r"forget\s+(everything|all|your)\s+(you\s+know|instructions?|rules?)", "system_override"),
    (r"you\s+are\s+now\s+(in\s+)?(a\s+)?(new|different|jailbreak|dan)\s+mode", "jailbreak"),
    (r"pretend\s+(you\s+are|to\s+be|you're)\s+(a\s+)?(different|new|evil|unrestricted)", "jailbreak"),
    (r"act\s+as\s+(if|though)\s+you\s+(have\s+no|don't\s+have)\s+(restrictions?|limits?|rules?)", "jailbreak"),
    (r"\[\[system\]\]|\[system\]|<\s*system\s*>|<<\s*system\s*>>", "system_tag_injection"),
    
    # Environment/secret extraction attempts - only when combined with extraction commands
    (r"(print|echo|show|display|reveal|output|dump)\s+(os\.)?environ", "env_extraction"),
    (r"os\.(environ|getenv)\s*[\[\(]", "env_extraction"),
    (r"process\.env\s*[\.\[]", "env_extraction"),
    (r"getenv\s*\(", "env_extraction"),
    (r"(echo|print|cat|printf)\s+\$[A-Z_]+", "shell_variable_extraction"),
    
    # Sensitive file access attempts
    (r"cat\s+/etc/(passwd|shadow|hosts|group)", "sensitive_file_access"),
    (r"cat\s+~?/?\.(ssh|aws|config|bashrc|zshrc|profile|env)", "sensitive_file_access"),
    (r"(read|open|cat|less|more|head|tail)\s+.*\.(pem|key|crt|cer|p12|pfx)", "key_file_access"),
    (r"/var/run/secrets", "k8s_secrets_access"),
    (r"/proc/(self|[0-9]+)/(environ|cmdline|fd)", "proc_access"),
    (r"~?/?\.aws/(credentials|config)", "cloud_credentials_access"),
    (r"~?/?\.kube/config", "cloud_credentials_access"),
    (r"~?/?\.gcloud", "cloud_credentials_access"),

    # Token/credential pattern extraction
    (r"(ghp_|gho_|github_pat_)[A-Za-z0-9_]{30,}", "github_token_exposure"),
    (r"AKIA[0-9A-Z]{16}", "aws_access_key_exposure"),
    (r"(xox[baprs]-[0-9]{10,13}-[0-9]{10,13}[a-zA-Z0-9-]*)", "slack_token_exposure"),
    (r"sk-[a-zA-Z0-9]{32,}", "api_key_exposure"),

    # Explicit token extraction requests
    (r"(extract|steal|get|find|show)\s+.{0,30}(api[_\s]?key|access[_\s]?token|secret[_\s]?key|password|credential)", "credential_extraction"),
    (r"(send|post|upload|exfil)\s+.{0,30}(token|secret|credential|password|key)\s+to", "credential_exfiltration"),
    
    # Command injection attempts - destructive commands
    (r";\s*(rm|dd|mkfs|shutdown|reboot|halt|init)\s+", "destructive_command"),
    (r"\|\s*(rm|dd|mkfs|shutdown|reboot|halt)\s+", "destructive_command"),
    (r"&&\s*(rm|dd|mkfs|shutdown|reboot|halt)\s+", "destructive_command"),
    
    # SQL injection attempts
    (r";\s*(drop|delete|truncate|alter)\s+(table|database)", "sql_injection"),
    (r"union\s+(all\s+)?select", "sql_injection"),
    (r"'\s*or\s*'?\d*'?\s*=\s*'?\d*'?", "sql_injection"),
    
    # Prompt delimiter manipulation - only dangerous system-level delimiters
    (r"<\|endoftext\|>", "token_manipulation"),
    (r"<\|im_start\|>|<\|im_end\|>", "token_manipulation"),
]

# Exact-match blocked keywords - MALICIOUS level
# RELAXED for internal users - block explicit jailbreak and dangerous terms
BLOCKED_KEYWORDS: List[str] = [
    # Explicit jailbreak/bypass attempts
    "jailbreak mode",
    "DAN mode",
    "ignore all safety",
    "disable all safety",
    "override all security",
    "bypass all filters",
    "disable content filter",
    "unrestricted mode",
    # Reverse shell / remote access
    "reverse shell",
    "bind shell",
    "connect back",
    # Credential theft explicit requests
    "steal credentials",
    "exfiltrate secrets",
    "dump all secrets",
]

# NEW: System prompt/instruction extraction attempts - MALICIOUS level
# These patterns detect attempts to extract system prompts, internal rules, or meta-information
# RELAXED for internal users - only catch explicit extraction attempts
INSTRUCTION_EXTRACTION_PATTERNS: List[Tuple[str, str]] = [
    # Direct system prompt extraction (very explicit)
    (r"(reveal|show|display|print|dump|output)\s+(the\s+)?(system\s*prompt|hidden\s*instructions?|internal\s*rules?|secret\s*instructions?)", "meta_extraction"),
    (r"(system\s*prompt|hidden\s*instructions?).{0,30}(reveal|show|display|print|dump)", "meta_extraction"),

    # Generic attack detection patterns (keep these)
    (r"(bypass|circumvent|evade|avoid)\s+(all\s+)?(security|filter|detection|restriction|protection)", "attack_evasion"),
    (r"(exploit|attack|hack|compromise)\s+(this|the|system|service|application)", "attack_intent"),
    (r"(malicious|harmful|dangerous)\s+(code|script|payload|command)", "malicious_intent"),

    # Kubernetes secrets/sensitive access
    (r"/var/run/secrets/kubernetes", "k8s_secrets_path"),
    (r"kubectl\s+(get|describe)\s+(secret|configmap)\s+.{0,30}(-o\s+yaml|-o\s+json|--output)", "k8s_secret_extraction"),
    (r"kubectl\s+exec\s+.{0,50}(-it?|--stdin|--tty)", "k8s_exec_shell"),
    (r"kubectl\s+cp\s+.{0,30}:/", "k8s_copy_from_pod"),

    # Git credential/config extraction
    (r"git\s+config\s+.{0,20}(credential|password|token|secret)", "git_credential_access"),
    (r"cat\s+.{0,20}\.git/(config|credentials)", "git_credential_access"),

    # Force push to protected branches
    (r"git\s+push\s+.{0,30}(--force|-f)\s+.{0,20}(main|master|prod)", "git_force_push_protected"),
]

# ============================================================================
# OS COMMAND REQUEST PATTERNS - MALICIOUS level
# RELAXED for internal development use - only block truly dangerous commands
# ============================================================================
OS_COMMAND_PATTERNS: List[Tuple[str, str]] = [
    # Shutdown/reboot/power commands
    (r"\b(shutdown|reboot|halt|poweroff)\s+(the\s+)?(server|system|machine|host)?", "os_command_destructive"),
    (r"\binit\s+[0-6]\b", "os_command_destructive"),

    # User management (dangerous operations)
    (r"\b(useradd|userdel|usermod|groupadd|groupdel)\s+", "os_command_user_mgmt"),
    (r"\bpasswd\s+\w+", "os_command_user_mgmt"),

    # Permission changes on system paths
    (r"\b(chmod|chown|chgrp)\s+.{0,30}(/etc|/usr|/bin|/sbin|/var|/sys|/boot|/root)", "os_command_permission"),

    # Package management (installation/removal)
    (r"\b(apt|apt-get|yum|dnf|pacman)\s+(install|remove|purge|erase)\s+", "os_command_package"),

    # Service management (start/stop/restart)
    (r"\b(systemctl|service)\s+(start|stop|restart|enable|disable)\s+", "os_command_service"),

    # Reverse shell patterns (critical security)
    (r"\bnc\s+.{0,30}(-e|exec)\s+", "reverse_shell"),
    (r"\bbash\s+-i\s+.{0,20}>/dev/tcp/", "reverse_shell"),
    (r"\bpython.{0,10}-c.{0,30}socket", "reverse_shell"),
    (r"\bperl\s+-e.{0,30}socket", "reverse_shell"),
    (r"\bmkfifo\s+.{0,30}nc\s+", "reverse_shell"),

    # Data exfiltration patterns
    (r"\bcurl\s+.{0,50}(-d|--data|--data-binary)\s+.{0,30}(secret|password|token|key|credential)", "data_exfiltration"),
    (r"\bwget\s+.{0,30}--post-data", "data_exfiltration"),

    # Disk/filesystem destructive operations
    (r"\brm\s+(-rf?|--recursive).{0,20}(/|/home|/etc|/var|/usr)", "os_command_destructive"),
    (r"\bdd\s+.{0,30}of=/dev/", "os_command_destructive"),
    (r"\bmkfs\s+", "os_command_destructive"),

    # Cron/scheduled task manipulation
    (r"\bcrontab\s+(-r|--remove)", "os_command_cron"),
    (r"\bcrontab\s+-e", "os_command_cron"),

    # Network scanning/reconnaissance (explicit attacks only)
    (r"\bnmap\s+.{0,30}(-sS|-sT|-sU|-sV|-O|--script)", "network_scan"),
    (r"\bmasscan\s+", "network_scan"),
]

# Patterns that are suspicious but not necessarily malicious
# These are logged but not blocked - useful for security monitoring
SUSPICIOUS_PATTERNS: List[Tuple[str, str]] = [
    (r"base64\s+(encode|decode)", "encoding_operation"),
    (r"eval\s*\(", "eval_call"),
    (r"exec\s*\(", "exec_call"),

    # Network operations (allowed but logged)
    (r"\bcurl\s+", "network_request"),
    (r"\bwget\s+", "network_request"),
    (r"\bssh\s+", "ssh_connection"),

    # Process inspection (allowed for debugging)
    (r"\bps\s+(aux|ef)", "process_inspection"),
    (r"\btop\b", "process_inspection"),
    (r"\bhtop\b", "process_inspection"),

    # File operations outside repo
    (r"\bcat\s+/", "system_file_read"),
    (r"\bls\s+-la\s+/", "system_dir_listing"),

    # Docker/container operations
    (r"\bdocker\s+(exec|run)", "container_operation"),
    (r"\bdocker\s+inspect", "container_inspection"),

    # Environment inspection (non-extraction)
    (r"\benv\b", "env_listing"),
    (r"\bprintenv\b", "env_listing"),
]


def scan_for_injection(text: str) -> ScanResult:
    """
    Scan text for potential prompt injection attempts.
    
    Args:
        text: The input text to scan
        
    Returns:
        ScanResult with threat level and matched patterns
    """
    if not text:
        return ScanResult(
            threat_level=ThreatLevel.SAFE,
            matched_patterns=[],
            is_safe=True,
            details={}
        )
    
    text_lower = text.lower()
    matched_patterns: List[str] = []
    details: Dict[str, List[str]] = {
        "malicious": [],
        "suspicious": []
    }
    
    # Check for exact-match blocked keywords (case-insensitive)
    for keyword in BLOCKED_KEYWORDS:
        if keyword.lower() in text_lower:
            matched_patterns.append(f"blocked_keyword:{keyword}")
            details["malicious"].append(keyword)
    
    # Check for injection patterns (MALICIOUS)
    for pattern, category in INJECTION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            matched_patterns.append(f"{category}:{pattern[:30]}")
            details["malicious"].append(category)
    
    # Check for instruction extraction patterns (MALICIOUS)
    for pattern, category in INSTRUCTION_EXTRACTION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            matched_patterns.append(f"{category}:{pattern[:30]}")
            details["malicious"].append(category)
    
    # Check for OS command request patterns (MALICIOUS)
    for pattern, category in OS_COMMAND_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            matched_patterns.append(f"{category}:{pattern[:30]}")
            details["malicious"].append(category)
    
    # Check for suspicious patterns
    for pattern, category in SUSPICIOUS_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            if category not in [p.split(":")[0] for p in matched_patterns]:
                details["suspicious"].append(category)
    
    # Determine threat level
    if details["malicious"]:
        threat_level = ThreatLevel.MALICIOUS
    elif details["suspicious"]:
        threat_level = ThreatLevel.SUSPICIOUS
    else:
        threat_level = ThreatLevel.SAFE
    
    return ScanResult(
        threat_level=threat_level,
        matched_patterns=matched_patterns,
        is_safe=threat_level == ThreatLevel.SAFE,
        details=details
    )


def validate_prompt_or_raise(text: str) -> None:
    """
    Validate a prompt and raise PromptInjectionError if malicious.
    
    Args:
        text: The input text to validate
        
    Raises:
        PromptInjectionError: If malicious patterns are detected
    """
    result = scan_for_injection(text)
    
    if result.threat_level == ThreatLevel.MALICIOUS:
        raise PromptInjectionError(
            message="Potential prompt injection detected. Request blocked for security.",
            threat_level=result.threat_level,
            matched_patterns=result.matched_patterns
        )


def sanitize_for_prompt(text: str) -> str:
    """
    Sanitize input text by removing potentially dangerous delimiters and patterns.
    
    Args:
        text: The input text to sanitize
        
    Returns:
        Sanitized text with dangerous delimiters removed/escaped
    """
    if not text:
        return text
    
    sanitized = text
    
    # Remove or escape dangerous delimiters
    dangerous_delimiters = [
        ("[[system]]", "[[sys-blocked]]"),
        ("[system]", "[sys-blocked]"),
        ("<system>", "<sys-blocked>"),
        ("<<system>>", "<<sys-blocked>>"),
        ("<|endoftext|>", "[end-blocked]"),
        ("<|im_start|>", "[im-blocked]"),
        ("<|im_end|>", "[im-blocked]"),
    ]
    
    for pattern, replacement in dangerous_delimiters:
        sanitized = sanitized.replace(pattern, replacement)
        sanitized = sanitized.replace(pattern.upper(), replacement)
        sanitized = sanitized.replace(pattern.lower(), replacement)
    
    return sanitized


def is_safe_prompt(text: str) -> bool:
    """
    Quick check if a prompt appears safe.
    
    Args:
        text: The input text to check
        
    Returns:
        True if the prompt appears safe, False otherwise
    """
    result = scan_for_injection(text)
    return result.is_safe
