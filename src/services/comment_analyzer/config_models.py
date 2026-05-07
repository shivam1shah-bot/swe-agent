#!/usr/bin/env python3
"""
Configuration module for rCore Comment Analyzer
Handles loading and validation of configuration
"""

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class AnalysisType(Enum):
    """Analysis strategy types."""
    LLM = "llm"
    RULES = "rules"
    HYBRID = "hybrid"


class SeverityLevel(Enum):
    """Severity levels for issues."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class FilterConfig:
    """Configuration for comment filtering."""

    # Sub-agent identification
    sub_agent_identifier: str = "rcore-v2"

    # Filter by reactions
    filter_thumbs_down: bool = True  # Exclude comments with thumbs down (false positives)
    filter_thumbs_up: bool = False   # Only include comments with thumbs up

    # Filter by status
    include_open: bool = True
    include_outdated: bool = True
    include_resolved: bool = False

    # Filter by author
    bot_usernames: List[str] = field(default_factory=lambda: ["rcore-v2", "sharma0vineet"])

    # Deduplication
    deduplicate: bool = True

    # Advanced filters
    exclude_patterns: List[str] = field(default_factory=list)  # Regex patterns to exclude
    min_comment_length: int = 10  # Minimum comment body length


@dataclass
class ImportanceRules:
    """Importance scoring rules per category."""

    # i18n categories (1-10 scale)
    missing_translation_keys: int = 9
    hardcoded_strings: int = 8
    inconsistent_patterns: int = 6
    naming_conventions: int = 3
    other: int = 5

    def get_score(self, category: str) -> int:
        """Get importance score for a category."""
        return getattr(self, category, self.other)


@dataclass
class SeverityMapping:
    """Maps importance scores to severity levels."""

    critical: str = "9-10"
    high: str = "7-8"
    medium: str = "4-6"
    low: str = "1-3"

    def get_severity(self, importance: int) -> SeverityLevel:
        """Get severity level from importance score."""
        if 9 <= importance <= 10:
            return SeverityLevel.CRITICAL
        elif 7 <= importance <= 8:
            return SeverityLevel.HIGH
        elif 4 <= importance <= 6:
            return SeverityLevel.MEDIUM
        else:
            return SeverityLevel.LOW


@dataclass
class ThresholdConfig:
    """Blocking thresholds configuration."""

    fail_on_critical_count: int = 1
    fail_on_high_count: int = 5
    fail_on_medium_count: int = 15
    fail_on_low_count: int = 999  # Effectively disabled

    blocking: bool = False  # Whether this sub-agent can block PRs

    def should_block(self, counts: Dict[str, int]) -> bool:
        """Determine if PR should be blocked based on issue counts."""
        if not self.blocking:
            return False

        critical = counts.get("critical", 0)
        high = counts.get("high", 0)
        medium = counts.get("medium", 0)
        low = counts.get("low", 0)

        if critical >= self.fail_on_critical_count:
            return True
        if high >= self.fail_on_high_count:
            return True
        if medium >= self.fail_on_medium_count:
            return True
        if low >= self.fail_on_low_count:
            return True

        return False


@dataclass
class CategoryConfig:
    """Category-specific configuration."""

    name: str
    keywords: List[str]
    importance: int
    description: str = ""


@dataclass
class AnalysisConfig:
    """Configuration for comment analysis."""

    type: AnalysisType = AnalysisType.RULES

    # Severity extraction patterns
    severity_patterns: List[str] = field(default_factory=lambda: [
        r'severity[:\s]+(\d+)',
        r'\[severity[:\s]+(\d+)\]',
        r'\*\*severity\*\*[:\s]+(\d+)',
    ])

    # Default severity if not found
    default_severity: int = 5

    # Categories for i18n
    categories: List[CategoryConfig] = field(default_factory=lambda: [
        CategoryConfig(
            name="hardcoded_strings",
            keywords=["hardcoded", "hard-coded", "string literal"],
            importance=8,
            description="Hardcoded strings that should use i18n"
        ),
        CategoryConfig(
            name="inconsistent_patterns",
            keywords=["inconsistent", "pattern"],
            importance=6,
            description="Inconsistent i18n patterns"
        ),
        CategoryConfig(
            name="naming_conventions",
            keywords=["naming", "convention"],
            importance=3,
            description="Translation key naming conventions"
        ),
        CategoryConfig(
            name="missing_translation_keys",
            keywords=["missing translation", "translation key", "translate"],
            importance=9,
            description="Missing translation keys"
        ),
    ])

    # LLM configuration (for future use)
    llm_provider: str = "claude"
    llm_model: str = "claude-sonnet-4.5"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 1000


@dataclass
class SubAgentConfig:
    """Complete sub-agent configuration."""

    # Metadata
    name: str = "i18n"
    identifier: str = "rcore-v2"
    enabled: bool = True
    description: str = "Internationalization (i18n) analysis sub-agent"

    # Component configurations
    filter: FilterConfig = field(default_factory=FilterConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    importance_rules: ImportanceRules = field(default_factory=ImportanceRules)
    severity_mapping: SeverityMapping = field(default_factory=SeverityMapping)
    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SubAgentConfig":
        """Create configuration from dictionary."""
        config = cls()

        if "name" in data:
            config.name = data["name"]
        if "identifier" in data:
            config.identifier = data["identifier"]
        if "enabled" in data:
            config.enabled = data["enabled"]

        # Load filter config
        if "filter" in data:
            config.filter = FilterConfig(**data["filter"])

        # Load analysis config
        if "analysis" in data:
            analysis_data = data["analysis"]
            if "type" in analysis_data:
                analysis_data["type"] = AnalysisType(analysis_data["type"])
            config.analysis = AnalysisConfig(**analysis_data)

        # Load thresholds
        if "thresholds" in data:
            config.thresholds = ThresholdConfig(**data["thresholds"])

        return config

    @classmethod
    def from_json_file(cls, file_path: str) -> "SubAgentConfig":
        """Load configuration from JSON file."""
        with open(file_path, "r") as f:
            data = json.load(f)
        return cls.from_dict(data)

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "name": self.name,
            "identifier": self.identifier,
            "enabled": self.enabled,
            "description": self.description,
            "filter": {
                "sub_agent_identifier": self.filter.sub_agent_identifier,
                "filter_thumbs_down": self.filter.filter_thumbs_down,
                "filter_thumbs_up": self.filter.filter_thumbs_up,
                "include_open": self.filter.include_open,
                "include_outdated": self.filter.include_outdated,
                "include_resolved": self.filter.include_resolved,
                "bot_usernames": self.filter.bot_usernames,
                "deduplicate": self.filter.deduplicate,
            },
            "analysis": {
                "type": self.analysis.type.value,
                "default_severity": self.analysis.default_severity,
            },
            "thresholds": {
                "fail_on_critical_count": self.thresholds.fail_on_critical_count,
                "fail_on_high_count": self.thresholds.fail_on_high_count,
                "fail_on_medium_count": self.thresholds.fail_on_medium_count,
                "blocking": self.thresholds.blocking,
            }
        }

    def to_json_file(self, file_path: str):
        """Save configuration to JSON file."""
        with open(file_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)


# Default configurations for different sub-agents
DEFAULT_I18N_CONFIG = SubAgentConfig(
    name="i18n",
    identifier="rcore-v2",
    enabled=True,
    description="Internationalization (i18n) analysis sub-agent",
    thresholds=ThresholdConfig(
        fail_on_critical_count=1,
        fail_on_high_count=5,
        fail_on_medium_count=15,
        blocking=False
    )
)

DEFAULT_SECURITY_CONFIG = SubAgentConfig(
    name="security",
    identifier="security-bot",
    enabled=True,
    description="Security vulnerability analysis sub-agent",
    thresholds=ThresholdConfig(
        fail_on_critical_count=1,
        fail_on_high_count=1,
        fail_on_medium_count=5,
        blocking=True  # Security BLOCKS by default
    )
)
