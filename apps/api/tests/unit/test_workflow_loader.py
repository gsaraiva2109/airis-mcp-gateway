"""
Unit tests for Workflow Loader.

Tests cover:
- YAML parsing and WorkflowConfig creation
- Validation: required fields, token overflow, invalid priority, kebab-case
- Non-ASCII token estimation (Japanese text)
- Priority sorting (high > medium > low, then filename)
- Missing/empty workflows directory handling
"""

import pytest
from pathlib import Path
from unittest.mock import patch

from app.core.workflow_loader import (
    WorkflowConfig,
    estimate_tokens,
    load_workflows,
    validate_workflow,
)


class TestEstimateTokens:
    """Test token estimation logic."""

    def test_ascii_only(self):
        """ASCII text: ~4 chars per token."""
        text = "a" * 100
        assert estimate_tokens(text) == 25

    def test_non_ascii_only(self):
        """Non-ASCII text (Japanese): ~2 chars per token."""
        text = "あ" * 100
        assert estimate_tokens(text) == 50

    def test_mixed_content(self):
        """Mixed ASCII and non-ASCII."""
        # 40 ASCII + 10 Japanese
        text = "a" * 40 + "あ" * 10
        assert estimate_tokens(text) == 10 + 5  # 40//4 + 10//2

    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_realistic_compile_to(self):
        """Realistic compile_to text stays within typical budget."""
        text = (
            "### Implementing with Libraries/APIs\n"
            "WHEN writing code that uses ANY library:\n"
            "1. FIRST: Call context7:resolve-library-id\n"
            "2. THEN: Call context7:query-docs\n"
            "NEVER skip this workflow."
        )
        tokens = estimate_tokens(text)
        assert 30 < tokens < 100  # Should be well under 200


class TestValidateWorkflow:
    """Test workflow validation logic."""

    def _make_valid(self, **overrides) -> WorkflowConfig:
        defaults = {
            "name": "test-workflow",
            "description": "Test",
            "priority": "high",
            "max_tokens": 200,
            "servers": ["context7"],
            "trigger": "test trigger",
            "compile_to": "WHEN test: do something",
        }
        defaults.update(overrides)
        return WorkflowConfig(**defaults)

    def test_valid_workflow_no_errors(self):
        errors = validate_workflow(self._make_valid())
        assert errors == []

    def test_missing_name(self):
        errors = validate_workflow(self._make_valid(name=""))
        assert any("name" in e for e in errors)

    def test_invalid_name_not_kebab_case(self):
        errors = validate_workflow(self._make_valid(name="NotKebab"))
        assert any("kebab-case" in e for e in errors)

    def test_name_with_underscores_rejected(self):
        errors = validate_workflow(self._make_valid(name="my_workflow"))
        assert any("kebab-case" in e for e in errors)

    def test_invalid_priority(self):
        errors = validate_workflow(self._make_valid(priority="critical"))
        assert any("priority" in e for e in errors)

    def test_empty_compile_to(self):
        errors = validate_workflow(self._make_valid(compile_to=""))
        assert any("compile_to" in e for e in errors)

    def test_whitespace_only_compile_to(self):
        errors = validate_workflow(self._make_valid(compile_to="   \n  "))
        assert any("compile_to" in e for e in errors)

    def test_token_overflow(self):
        """compile_to exceeding max_tokens produces error."""
        long_text = "x" * 1000  # ~250 tokens
        errors = validate_workflow(self._make_valid(compile_to=long_text, max_tokens=100))
        assert any("exceeds max_tokens" in e for e in errors)

    def test_token_overflow_non_ascii(self):
        """Japanese text uses stricter token estimation."""
        jp_text = "あ" * 200  # ~100 tokens with non-ASCII estimation
        errors = validate_workflow(self._make_valid(compile_to=jp_text, max_tokens=50))
        assert any("exceeds max_tokens" in e for e in errors)

    def test_empty_servers(self):
        errors = validate_workflow(self._make_valid(servers=[]))
        assert any("servers" in e for e in errors)

    def test_multiple_errors_reported(self):
        """Multiple validation errors are all reported."""
        errors = validate_workflow(self._make_valid(
            name="",
            priority="invalid",
            compile_to="",
            servers=[],
        ))
        assert len(errors) >= 3


class TestLoadWorkflows:
    """Test workflow loading from directory."""

    def test_load_from_directory(self, tmp_path):
        """Valid YAML files are loaded and sorted."""
        (tmp_path / "b-second.yaml").write_text(
            "name: b-second\n"
            "description: Second\n"
            "priority: medium\n"
            "max_tokens: 200\n"
            "servers: [tavily]\n"
            "trigger: test\n"
            "compile_to: WHEN test B\n"
        )
        (tmp_path / "a-first.yaml").write_text(
            "name: a-first\n"
            "description: First\n"
            "priority: high\n"
            "max_tokens: 200\n"
            "servers: [context7]\n"
            "trigger: test\n"
            "compile_to: WHEN test A\n"
        )

        workflows = load_workflows(tmp_path)

        assert len(workflows) == 2
        assert workflows[0].name == "a-first"  # high priority first
        assert workflows[1].name == "b-second"  # medium after high

    def test_same_priority_sorted_by_filename(self, tmp_path):
        """Same priority workflows are sorted by filename."""
        (tmp_path / "z-last.yaml").write_text(
            "name: z-last\n"
            "description: Last\n"
            "priority: high\n"
            "max_tokens: 200\n"
            "servers: [s1]\n"
            "trigger: test\n"
            "compile_to: WHEN test Z\n"
        )
        (tmp_path / "a-first.yaml").write_text(
            "name: a-first\n"
            "description: First\n"
            "priority: high\n"
            "max_tokens: 200\n"
            "servers: [s2]\n"
            "trigger: test\n"
            "compile_to: WHEN test A\n"
        )

        workflows = load_workflows(tmp_path)

        assert len(workflows) == 2
        assert workflows[0].name == "a-first"
        assert workflows[1].name == "z-last"

    def test_invalid_yaml_skipped(self, tmp_path):
        """Invalid YAML files are skipped with error log."""
        (tmp_path / "bad.yaml").write_text("{{invalid yaml")
        (tmp_path / "good.yaml").write_text(
            "name: good\n"
            "description: Good\n"
            "priority: high\n"
            "max_tokens: 200\n"
            "servers: [s1]\n"
            "trigger: test\n"
            "compile_to: WHEN test\n"
        )

        workflows = load_workflows(tmp_path)

        assert len(workflows) == 1
        assert workflows[0].name == "good"

    def test_validation_error_skipped(self, tmp_path):
        """Workflow with validation errors is skipped."""
        (tmp_path / "bad.yaml").write_text(
            "name: BadName\n"  # Not kebab-case
            "description: Bad\n"
            "priority: high\n"
            "max_tokens: 200\n"
            "servers: [s1]\n"
            "trigger: test\n"
            "compile_to: WHEN test\n"
        )

        workflows = load_workflows(tmp_path)
        assert len(workflows) == 0

    def test_nonexistent_directory_returns_empty(self):
        """Non-existent directory returns empty list."""
        workflows = load_workflows(Path("/nonexistent/path"))
        assert workflows == []

    def test_empty_directory_returns_empty(self, tmp_path):
        """Empty directory returns empty list."""
        workflows = load_workflows(tmp_path)
        assert workflows == []

    def test_non_yaml_files_ignored(self, tmp_path):
        """Non-YAML files are ignored."""
        (tmp_path / "README.md").write_text("# Not a workflow")
        (tmp_path / "good.yaml").write_text(
            "name: good\n"
            "description: Good\n"
            "priority: high\n"
            "max_tokens: 200\n"
            "servers: [s1]\n"
            "trigger: test\n"
            "compile_to: WHEN test\n"
        )

        workflows = load_workflows(tmp_path)
        assert len(workflows) == 1
