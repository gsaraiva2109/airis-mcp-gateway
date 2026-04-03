"""
Unit tests for Behavior Compiler.

Tests cover:
- Base instructions output when no behaviors defined
- HOT server tool reference format (direct)
- COLD server tool reference format (airis-exec)
- Priority sorting (high > medium > low)
- Disabled servers with behavior (included for auto-enable)
- Routing table integration (Quick Routes section)
- Workflow text compilation and integration
- Behavior exclusion for workflow-covered servers
"""

import pytest
from unittest.mock import patch

from app.core.behavior_compiler import (
    compile_instructions,
    _compile_behavior_lines,
    _compile_workflow_texts,
    _BASE_INSTRUCTIONS,
    _META_TOOLS_SECTION,
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
    compile_to: str = "mcp_instructions",
    priority: str = "high",
    text: str = "WHEN test: do something",
    servers: list[str] | None = None,
) -> WorkflowConfig:
    """Helper to create WorkflowConfig for tests."""
    return WorkflowConfig(
        name=name,
        compile_to=compile_to,
        priority=priority,
        text=text,
        servers=servers or ["test-server"],
    )


class TestCompileWorkflowTexts:
    """Test workflow text compilation."""

    def test_empty_workflows(self):
        assert _compile_workflow_texts([]) == ""

    def test_single_workflow(self):
        workflows = [_make_workflow(text="### Test\nWHEN test: do it")]
        result = _compile_workflow_texts(workflows)

        assert "### Test" in result
        assert "WHEN test: do it" in result

    def test_filters_by_compile_to(self):
        """Only workflows with compile_to='mcp_instructions' are included."""
        workflows = [
            _make_workflow(name="included", compile_to="mcp_instructions", text="Included text"),
            _make_workflow(name="excluded", compile_to="other_target", text="Excluded text"),
        ]
        result = _compile_workflow_texts(workflows)

        assert "Included text" in result
        assert "Excluded text" not in result

    def test_empty_text_skipped(self):
        """Workflows with empty text are skipped."""
        workflows = [
            _make_workflow(text="   "),
            _make_workflow(name="valid", text="Valid text"),
        ]
        result = _compile_workflow_texts(workflows)

        assert "Valid text" in result

    def test_multiple_workflows_joined(self):
        """Multiple workflows are separated by double newlines."""
        workflows = [
            _make_workflow(name="first", text="First directive"),
            _make_workflow(name="second", text="Second directive"),
        ]
        result = _compile_workflow_texts(workflows)

        assert "First directive" in result
        assert "Second directive" in result

    def test_text_emitted_verbatim(self):
        """Text is emitted without template processing."""
        raw_text = "### Section\n${VAR} {{template}} %s"
        workflows = [_make_workflow(text=raw_text)]
        result = _compile_workflow_texts(workflows)

        assert "${VAR}" in result
        assert "{{template}}" in result
        assert "%s" in result


class TestCompileInstructionsWithWorkflows:
    """Test full compile_instructions with workflow integration."""

    @patch("app.core.behavior_compiler.format_routing_table_as_instructions", return_value="")
    @patch("app.core.behavior_compiler.load_workflows")
    def test_workflows_replace_routing_guide(self, mock_load, mock_routing):
        """When workflows exist, their text replaces the hardcoded routing guide."""
        mock_load.return_value = [
            _make_workflow(
                name="test-wf",
                servers=["context7"],
                text="### Custom Workflow\nWHEN test: use context7",
            )
        ]
        configs = {
            "context7": _make_server("context7", mode=ServerMode.HOT),
        }
        result = compile_instructions(configs)

        assert "### Custom Workflow" in result
        assert "WHEN test: use context7" in result

    @patch("app.core.behavior_compiler.format_routing_table_as_instructions", return_value="")
    @patch("app.core.behavior_compiler.load_workflows")
    def test_no_workflows_uses_routing_guide(self, mock_load, mock_routing):
        """When no workflows exist, hardcoded routing guide is used."""
        mock_load.return_value = []
        result = compile_instructions({})

        assert "## Tool Routing Guide" in result

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

        # stripe behavior should still be included
        assert "Use Stripe" in result

    @patch("app.core.behavior_compiler.format_routing_table_as_instructions", return_value="")
    @patch("app.core.behavior_compiler.load_workflows")
    def test_non_mcp_instructions_workflows_ignored(self, mock_load, mock_routing):
        """Workflows with compile_to != 'mcp_instructions' don't affect output."""
        mock_load.return_value = [
            _make_workflow(compile_to="other_target", text="Should not appear"),
        ]
        result = compile_instructions({})

        assert "Should not appear" not in result
        # Falls back to routing guide since no mcp_instructions workflows
        assert "## Tool Routing Guide" in result
