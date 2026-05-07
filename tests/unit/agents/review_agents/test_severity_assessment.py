"""
Unit tests for SeverityAssessmentLayer._parse_response auto_approve extraction.

Tests the parser's handling of the auto_approve field from LLM YAML output,
including type coercion, rule_source guards, and missing field defaults.
"""

import logging
from unittest.mock import Mock

import pytest

from src.agents.review_agents.severity_assessment import SeverityAssessmentLayer


@pytest.fixture
def layer():
    """Create a SeverityAssessmentLayer with a mock ClaudeCodeTool."""
    layer = object.__new__(SeverityAssessmentLayer)
    layer._working_directory = "/tmp/test"
    layer._logger = logging.getLogger("test")
    return layer


class TestParseAutoApprove:
    """Tests for auto_approve extraction in _parse_response."""

    def _make_response(self, yaml_text: str) -> dict:
        return {"result": yaml_text}

    def test_auto_approve_true_with_repo_skill(self, layer):
        """auto_approve: true + risk-assessment skill → auto_approve=True."""
        response = self._make_response(
            'severity: LOW\n'
            'confidence: 0.9\n'
            'rule_source: "risk-assessment skill"\n'
            'reasoning: "Test PR"\n'
            'auto_approve: true\n'
        )
        result = layer._parse_response(response, {})
        assert result.auto_approve is True
        assert result.rule_source == "repo_skill"

    def test_auto_approve_false(self, layer):
        """auto_approve: false → auto_approve=False."""
        response = self._make_response(
            'severity: LOW\n'
            'confidence: 0.9\n'
            'rule_source: "risk-assessment skill"\n'
            'reasoning: "Test PR"\n'
            'auto_approve: false\n'
        )
        result = layer._parse_response(response, {})
        assert result.auto_approve is False

    def test_auto_approve_missing_defaults_false(self, layer):
        """Missing auto_approve field → defaults to False."""
        response = self._make_response(
            'severity: LOW\n'
            'confidence: 0.9\n'
            'rule_source: "standard_rules"\n'
            'reasoning: "Test PR"\n'
        )
        result = layer._parse_response(response, {})
        assert result.auto_approve is False

    def test_auto_approve_forced_false_without_repo_skill(self, layer):
        """auto_approve: true but rule_source=standard_rules → forced to False."""
        response = self._make_response(
            'severity: LOW\n'
            'confidence: 0.9\n'
            'rule_source: "standard_rules"\n'
            'reasoning: "Test PR"\n'
            'auto_approve: true\n'
        )
        result = layer._parse_response(response, {})
        assert result.auto_approve is False
        assert result.rule_source == "standard_rules"

    def test_auto_approve_string_true(self, layer):
        """auto_approve: "true" (string) → coerced to True."""
        response = self._make_response(
            'severity: LOW\n'
            'confidence: 0.9\n'
            'rule_source: "risk-assessment skill"\n'
            'reasoning: "Test PR"\n'
            'auto_approve: "true"\n'
        )
        result = layer._parse_response(response, {})
        assert result.auto_approve is True

    def test_auto_approve_string_false(self, layer):
        """auto_approve: "false" (string) → coerced to False."""
        response = self._make_response(
            'severity: LOW\n'
            'confidence: 0.9\n'
            'rule_source: "risk-assessment skill"\n'
            'reasoning: "Test PR"\n'
            'auto_approve: "false"\n'
        )
        result = layer._parse_response(response, {})
        assert result.auto_approve is False

    def test_auto_approve_true_with_code_review_skill(self, layer):
        """auto_approve: true + code-review skill → auto_approve=True."""
        response = self._make_response(
            'severity: LOW\n'
            'confidence: 0.9\n'
            'rule_source: "code-review skill"\n'
            'reasoning: "Test PR"\n'
            'auto_approve: true\n'
        )
        result = layer._parse_response(response, {})
        assert result.auto_approve is True
        assert result.rule_source == "repo_skill"
        assert result.repo_skill_name == "code-review"

    def test_generated_context_rule_source(self, layer):
        """Auto-generated risk-assessment skill → rule_source=generated_context."""
        response = self._make_response(
            'severity: MEDIUM\n'
            'confidence: 0.75\n'
            'rule_source: "auto-generated risk-assessment skill"\n'
            'reasoning: "Used auto-generated context"\n'
            'auto_approve: false\n'
        )
        result = layer._parse_response(response, {})
        assert result.rule_source == "generated_context"
        assert result.repo_skill_name == "risk-assessment"
        assert result.auto_approve is False

    def test_generated_context_blocks_auto_approve(self, layer):
        """Auto-generated skill must never auto-approve even if LLM says true."""
        response = self._make_response(
            'severity: LOW\n'
            'confidence: 0.9\n'
            'rule_source: "generated context"\n'
            'reasoning: "Simple test change"\n'
            'auto_approve: true\n'
        )
        result = layer._parse_response(response, {})
        assert result.rule_source == "generated_context"
        assert result.auto_approve is False

    def test_hallucination_guard_overrides_fake_skill(self, layer):
        """LLM claims code-review skill but it doesn't exist → override to standard_rules."""
        response = self._make_response(
            'severity: MEDIUM\n'
            'confidence: 0.8\n'
            'rule_source: "code-review skill"\n'
            'reasoning: "Used repo skill"\n'
            'auto_approve: false\n'
        )
        result = layer._parse_response(response, {}, available_skills=[])
        assert result.rule_source == "standard_rules"
        assert result.repo_skill_name is None

    def test_hallucination_guard_passes_when_skill_exists(self, layer):
        """LLM claims code-review skill and it exists → keep repo_skill."""
        response = self._make_response(
            'severity: MEDIUM\n'
            'confidence: 0.85\n'
            'rule_source: "code-review skill"\n'
            'reasoning: "Used repo skill"\n'
            'auto_approve: false\n'
        )
        result = layer._parse_response(
            response, {}, available_skills=["code-review", "pre-mortem"]
        )
        assert result.rule_source == "repo_skill"
        assert result.repo_skill_name == "code-review"

    def test_hallucination_guard_skipped_when_no_available_skills_info(self, layer):
        """When available_skills is None (not passed), skip verification."""
        response = self._make_response(
            'severity: LOW\n'
            'confidence: 0.9\n'
            'rule_source: "risk-assessment skill"\n'
            'reasoning: "Test"\n'
            'auto_approve: true\n'
        )
        # available_skills=None means we don't know → trust LLM (backward compat)
        result = layer._parse_response(response, {}, available_skills=None)
        assert result.rule_source == "repo_skill"
        assert result.auto_approve is True

    def test_auto_generated_skill_overrides_to_generated_context(self, layer):
        """LLM claims risk-assessment skill, but it was auto-generated → generated_context."""
        response = self._make_response(
            'severity: LOW\n'
            'confidence: 0.9\n'
            'rule_source: "risk-assessment skill"\n'
            'reasoning: "Test"\n'
            'auto_approve: false\n'
        )
        result = layer._parse_response(
            response, {},
            available_skills=["risk-assessment", "code-review"],
            auto_generated_skills=["risk-assessment"],
        )
        assert result.rule_source == "generated_context"
        assert result.repo_skill_name == "risk-assessment"
        assert result.auto_approve is False

    def test_hand_crafted_skill_stays_repo_skill(self, layer):
        """LLM claims risk-assessment skill, hand-crafted → stays repo_skill."""
        response = self._make_response(
            'severity: MEDIUM\n'
            'confidence: 0.85\n'
            'rule_source: "risk-assessment skill"\n'
            'reasoning: "Test"\n'
            'auto_approve: false\n'
        )
        result = layer._parse_response(
            response, {},
            available_skills=["risk-assessment"],
            auto_generated_skills=[],  # not auto-generated
        )
        assert result.rule_source == "repo_skill"
        assert result.repo_skill_name == "risk-assessment"
