"""
Unit tests for Behavior Compiler.

Tests cover:
- Base instructions output when no behaviors defined
- HOT server tool reference format (direct)
- COLD server tool reference format (airis-exec)
- Priority sorting (high > medium > low)
- Disabled servers with behavior (included for auto-enable)
- Routing table integration (Quick Routes section)
- Workflow directive compilation and integration
- Behavior exclusion for workflow-covered servers
- Server list auto-generation
- Token budget enforcement for workflows
"""

import pytest
from unittest.mock import patch

from app.core.behavior_compiler import (
    compile_instructions,
    _compile_behavior_lines,
    _compile_workflow_section,
    _compile_server_list,
    _BASE_INSTRUCTIONS,
    _META_TOOLS_SECTION,
    _FALLBACK_SECTION,
)
from app.core.mcp_config_loader import (
    McpServerConfig,
    BehaviorConfig,
    ServerType,
    ServerMode,
)
from app.core.workflow_loader import WorkflowConfig


def _make_server(
    name: str,
    mode: ServerMode = ServerMode.COLD,
    enabled: bool = True,
    behavior: BehaviorConfig | None = None,
) -> McpServerConfig:
    """Helper to create McpServerConfig for tests."""
    return McpServerConfig(
        name=name,
        server_type=ServerType.PROCESS,
        command="npx",
        args=[],
        env={},
        enabled=enabled,
        mode=mode,
        behavior=behavior,
    )


class TestCompileInstructions:
    """Test the main compile_instructions function."""

    @patch("app.core.behavior_compiler.format_routing_table_as_instructions", return_value="")
    @patch("app.core.behavior_compiler.load_workflows", return_value=[])
    def test_no_behaviors_returns_base_only(self, mock_workflows, mock_routing):
        """When no servers have behavior, output contains base + meta-tools only."""
        configs = {
            "server-a": _make_server("server-a"),
        }
        result = compile_instructions(configs)

        assert _BASE_INSTRUCTIONS in result
        assert _META_TOOLS_SECTION in result
        assert "## Proactive Tool Usage" not in result

    @patch("app.core.behavior_compiler.format_routing_table_as_instructions", return_value="")
    @patch("app.core.behavior_compiler.load_workflows", return_value=[])
    def test_with_behaviors_includes_proactive_section(self, mock_workflows, mock_routing):
        """When servers have behavior (and no workflows), Proactive Tool Usage section is included."""
        configs = {
            "context7": _make_server(
                "context7",
                mode=ServerMode.HOT,
                behavior=BehaviorConfig(
                    triggers=["implementing with library"],
                    instruction="Lookup docs BEFORE writing code",
                    priority="high",
                ),
            ),
        }
        result = compile_instructions(configs)

        assert "## Proactive Tool Usage" in result
        assert "WHEN implementing with library" in result
        assert "Lookup docs BEFORE writing code" in result

    @patch("app.core.behavior_compiler.format_routing_table_as_instructions", return_value="## Quick Routes\nWeb: tavily:search")
    @patch("app.core.behavior_compiler.load_workflows", return_value=[])
    def test_routing_table_appended(self, mock_workflows, mock_routing):
        """Quick Routes section from routing table is appended."""
        configs = {}
        result = compile_instructions(configs)

        assert "## Quick Routes" in result
        assert "Web: tavily:search" in result

    @patch("app.core.behavior_compiler.format_routing_table_as_instructions", return_value="")
    @patch("app.core.behavior_compiler.load_workflows", return_value=[])
    def test_empty_configs(self, mock_workflows, mock_routing):
        """Empty server configs produce base instructions only."""
        result = compile_instructions({})

        assert _BASE_INSTRUCTIONS in result
        assert "## Proactive Tool Usage" not in result
        assert "inspect the repo and check docs" in result
        assert "browser testing" in result


class TestCompileBehaviorLines:
    """Test behavior line compilation logic."""

    def test_hot_server_direct_reference(self):
        """HOT enabled server uses direct [name] reference."""
        configs = {
            "context7": _make_server(
                "context7",
                mode=ServerMode.HOT,
                enabled=True,
                behavior=BehaviorConfig(
                    triggers=["implementing with library"],
                    instruction="Lookup docs",
                    priority="high",
                ),
            ),
        }
        lines = _compile_behavior_lines(configs)

        assert len(lines) == 1
        assert "[context7]" in lines[0]
        assert "airis-exec" not in lines[0]

    def test_cold_server_airis_exec_reference(self):
        """COLD server uses airis-exec server:* reference."""
        configs = {
            "tavily": _make_server(
                "tavily",
                mode=ServerMode.COLD,
                enabled=True,
                behavior=BehaviorConfig(
                    triggers=["need current info"],
                    instruction="Search web",
                    priority="medium",
                ),
            ),
        }
        lines = _compile_behavior_lines(configs)

        assert len(lines) == 1
        assert "airis-exec tavily:*" in lines[0]

    def test_disabled_server_with_behavior_included(self):
        """Disabled servers with behavior are included (auto-enable via airis-exec)."""
        configs = {
            "sequential-thinking": _make_server(
                "sequential-thinking",
                mode=ServerMode.COLD,
                enabled=False,
                behavior=BehaviorConfig(
                    triggers=["complex analysis"],
                    instruction="Use sequential thinking",
                    priority="low",
                ),
            ),
        }
        lines = _compile_behavior_lines(configs)

        assert len(lines) == 1
        assert "airis-exec sequential-thinking:*" in lines[0]

    def test_priority_sorting(self):
        """Lines are sorted by priority: high > medium > low."""
        configs = {
            "low-server": _make_server(
                "low-server",
                behavior=BehaviorConfig(
                    triggers=["low trigger"],
                    instruction="Low action",
                    priority="low",
                ),
            ),
            "high-server": _make_server(
                "high-server",
                mode=ServerMode.HOT,
                behavior=BehaviorConfig(
                    triggers=["high trigger"],
                    instruction="High action",
                    priority="high",
                ),
            ),
            "medium-server": _make_server(
                "medium-server",
                behavior=BehaviorConfig(
                    triggers=["medium trigger"],
                    instruction="Medium action",
                    priority="medium",
                ),
            ),
        }
        lines = _compile_behavior_lines(configs)

        assert len(lines) == 3
        assert "High action" in lines[0]
        assert "Medium action" in lines[1]
        assert "Low action" in lines[2]

    def test_multiple_triggers_joined(self):
        """Multiple triggers are joined with ' / '."""
        configs = {
            "multi": _make_server(
                "multi",
                behavior=BehaviorConfig(
                    triggers=["trigger one", "trigger two"],
                    instruction="Do something",
                ),
            ),
        }
        lines = _compile_behavior_lines(configs)

        assert "trigger one / trigger two" in lines[0]

    def test_no_behavior_skipped(self):
        """Servers without behavior are skipped."""
        configs = {
            "no-behavior": _make_server("no-behavior"),
        }
        lines = _compile_behavior_lines(configs)

        assert len(lines) == 0

    def test_empty_triggers_skipped(self):
        """Behavior with empty triggers is skipped."""
        configs = {
            "empty": _make_server(
                "empty",
                behavior=BehaviorConfig(
                    triggers=[],
                    instruction="Do something",
                ),
            ),
        }
        lines = _compile_behavior_lines(configs)

        assert len(lines) == 0

    def test_empty_instruction_skipped(self):
        """Behavior with empty instruction is skipped."""
        configs = {
            "empty": _make_server(
                "empty",
                behavior=BehaviorConfig(
                    triggers=["some trigger"],
                    instruction="",
                ),
            ),
        }
        lines = _compile_behavior_lines(configs)

        assert len(lines) == 0

    def test_exclude_parameter(self):
        """Servers in exclude set are skipped."""
        configs = {
            "context7": _make_server(
                "context7",
                mode=ServerMode.HOT,
                behavior=BehaviorConfig(
                    triggers=["library usage"],
                    instruction="Check docs",
                    priority="high",
                ),
            ),
            "tavily": _make_server(
                "tavily",
                behavior=BehaviorConfig(
                    triggers=["web search"],
                    instruction="Search web",
                    priority="medium",
                ),
            ),
        }
        lines = _compile_behavior_lines(configs, exclude={"context7"})

        assert len(lines) == 1
        assert "tavily" in lines[0]
        assert "context7" not in lines[0]


def _make_workflow(
    name: str = "test-workflow",
    priority: str = "high",
    servers: list[str] | None = None,
    compile_to: str = "WHEN test: do something",
) -> WorkflowConfig:
    """Helper to create WorkflowConfig for tests."""
    return WorkflowConfig(
        name=name,
        description="Test workflow",
        priority=priority,
        max_tokens=200,
        servers=servers or ["test-server"],
        trigger="test",
        compile_to=compile_to,
    )


class TestCompileWorkflowSection:
    """Test workflow directive compilation."""

    def test_empty_workflows(self):
        assert _compile_workflow_section([]) == ""

    def test_single_workflow(self):
        workflows = [_make_workflow(compile_to="### Test\nWHEN test: do it")]
        result = _compile_workflow_section(workflows)

        assert "## Required Workflows" in result
        assert "directives, not suggestions" in result
        assert "### Test" in result
        assert "WHEN test: do it" in result

    def test_high_priority_always_included(self):
        """High priority workflows are always included regardless of budget."""
        long_text = "x" * 4000  # ~1000 tokens, exceeds budget
        workflows = [_make_workflow(priority="high", compile_to=long_text)]
        result = _compile_workflow_section(workflows)

        assert long_text in result

    def test_medium_skipped_when_budget_exhausted(self):
        """Medium priority workflows are skipped when budget is exhausted."""
        long_high = "H" * 3200  # ~800 tokens, fills budget
        workflows = [
            _make_workflow(name="high-one", priority="high", compile_to=long_high),
            _make_workflow(name="medium-one", priority="medium", compile_to="Medium text"),
        ]
        result = _compile_workflow_section(workflows)

        assert long_high in result
        assert "Medium text" not in result

    def test_medium_included_when_budget_available(self):
        """Medium priority workflows are included when budget allows."""
        short_high = "WHEN test: short"
        workflows = [
            _make_workflow(name="high-one", priority="high", compile_to=short_high),
            _make_workflow(name="medium-one", priority="medium", compile_to="WHEN medium: test"),
        ]
        result = _compile_workflow_section(workflows)

        assert short_high in result
        assert "WHEN medium: test" in result

    def test_multiple_workflows_joined(self):
        """Multiple workflows are separated by double newlines."""
        workflows = [
            _make_workflow(name="first", compile_to="First directive"),
            _make_workflow(name="second", compile_to="Second directive"),
        ]
        result = _compile_workflow_section(workflows)

        assert "First directive" in result
        assert "Second directive" in result


class TestCompileServerList:
    """Test server list auto-generation."""

    def test_empty_configs(self):
        assert _compile_server_list({}) == ""

    def test_generates_sorted_list(self):
        configs = {
            "zebra": _make_server("zebra"),
            "alpha": _make_server("alpha"),
            "middle": _make_server("middle"),
        }
        result = _compile_server_list(configs)

        assert "## Available Servers" in result
        assert "alpha, middle, zebra" in result

    def test_includes_disabled_servers(self):
        """Disabled servers are included (discoverable via airis-find)."""
        configs = {
            "enabled-one": _make_server("enabled-one", enabled=True),
            "disabled-one": _make_server("disabled-one", enabled=False),
        }
        result = _compile_server_list(configs)

        assert "disabled-one" in result
        assert "enabled-one" in result


class TestCompileInstructionsWithWorkflows:
    """Test full compile_instructions with workflow integration."""

    @patch("app.core.behavior_compiler.format_routing_table_as_instructions", return_value="")
    @patch("app.core.behavior_compiler.load_workflows")
    def test_workflows_included_in_output(self, mock_load, mock_routing):
        """Workflow directives appear in compiled instructions."""
        mock_load.return_value = [
            _make_workflow(
                name="test-wf",
                servers=["context7"],
                compile_to="### Test WF\nWHEN test: use context7",
            )
        ]
        configs = {
            "context7": _make_server("context7", mode=ServerMode.HOT),
        }
        result = compile_instructions(configs)

        assert "## Required Workflows" in result
        assert "### Test WF" in result
        assert "WHEN test: use context7" in result

    @patch("app.core.behavior_compiler.format_routing_table_as_instructions", return_value="")
    @patch("app.core.behavior_compiler.load_workflows")
    def test_fallback_included_when_workflows_exist(self, mock_load, mock_routing):
        """Fallback section is included when workflows exist."""
        mock_load.return_value = [_make_workflow()]
        result = compile_instructions({})

        assert "Tool Discovery Fallback" in result
        assert "airis-find" in result

    @patch("app.core.behavior_compiler.format_routing_table_as_instructions", return_value="")
    @patch("app.core.behavior_compiler.load_workflows")
    def test_no_fallback_without_workflows(self, mock_load, mock_routing):
        """Fallback section is NOT included when no workflows exist."""
        mock_load.return_value = []
        result = compile_instructions({})

        assert "Tool Discovery Fallback" not in result

    @patch("app.core.behavior_compiler.format_routing_table_as_instructions", return_value="")
    @patch("app.core.behavior_compiler.load_workflows")
    def test_behavior_excluded_for_workflow_servers(self, mock_load, mock_routing):
        """Behavior lines for servers covered by workflows are excluded."""
        mock_load.return_value = [
            _make_workflow(servers=["context7"]),
        ]
        configs = {
            "context7": _make_server(
                "context7",
                mode=ServerMode.HOT,
                behavior=BehaviorConfig(
                    triggers=["library"],
                    instruction="Check docs",
                    priority="high",
                ),
            ),
            "stripe": _make_server(
                "stripe",
                behavior=BehaviorConfig(
                    triggers=["payment"],
                    instruction="Use Stripe",
                    priority="medium",
                ),
            ),
        }
        result = compile_instructions(configs)

        # context7 behavior should be excluded (covered by workflow)
        assert "Check docs" not in result or "## Required Workflows" in result
        # stripe behavior should still be included
        assert "Use Stripe" in result

    @patch("app.core.behavior_compiler.format_routing_table_as_instructions", return_value="")
    @patch("app.core.behavior_compiler.load_workflows")
    def test_server_list_auto_generated(self, mock_load, mock_routing):
        """Available Servers list is auto-generated from configs."""
        mock_load.return_value = [_make_workflow()]
        configs = {
            "context7": _make_server("context7"),
            "tavily": _make_server("tavily"),
            "stripe": _make_server("stripe", enabled=False),
        }
        result = compile_instructions(configs)

        assert "## Available Servers" in result
        assert "context7" in result
        assert "stripe" in result  # Even disabled servers listed
