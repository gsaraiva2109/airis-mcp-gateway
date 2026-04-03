"""Behavior Compiler — compiles workflows and behaviors into MCP instructions.

Reads workflow YAML recipes and server behavior configs, then produces
a ~1500 token instructions string for the MCP initialize response.
Workflows are directives (not suggestions) that force LLMs to use
the right MCP tools at the right time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .logging import get_logger
from .routing_engine import format_routing_table_as_instructions
from .workflow_loader import WorkflowConfig, estimate_tokens, load_workflows

if TYPE_CHECKING:
    from .mcp_config_loader import McpServerConfig

logger = get_logger(__name__)

# Priority sort order
_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}

# Token budget for the workflow directives section
_WORKFLOW_TOKEN_BUDGET = 800

# Base instructions (always included)
_BASE_INSTRUCTIONS = (
    "This is AIRIS MCP Gateway with Dynamic MCP. "
    "IMPORTANT: Do NOT call tools directly. Instead:\n"
    "1. Use 'airis-exec' to execute any tool — all available tool names are listed in its description\n"
    "2. If arguments are wrong, the schema will be returned automatically\n"
    "3. Before implementation, inspect the repo and check docs for unfamiliar libraries or APIs\n"
    "All 60+ tools are accessed through airis-exec. "
    "This provides 98% token reduction while maintaining full functionality."
)

_META_TOOLS_SECTION = (
    "## Additional Meta-Tools\n"
    "- 'airis-confidence': Pre-implementation confidence check. Use before starting complex tasks.\n"
    "- 'airis-repo-index': Generate repository structure overview for unfamiliar codebases.\n"
    "- 'airis-suggest': Get tool recommendations from natural language intent.\n\n"
    "When you need a capability, check airis-exec's description for available tools, "
    "or use airis-find to search by keyword."
)

_TOOL_ROUTING_GUIDE = (
    "## Tool Routing Guide\n"
    "Use Gateway (airis-exec) for API/service calls. Use host tools for everything else.\n\n"
    "Gateway (airis-exec): library docs → context7 | web search → tavily | "
    "database → supabase | payments → stripe | DNS/workers → cloudflare | design files → figma\n\n"
    "Host tools (NOT Gateway): browser automation → playwright-cli skill (needs host Chrome) | "
    "file generation (docx/xlsx/pdf) → claude-api plugin | "
    "TDD/debugging/planning → superpowers plugin | "
    "git operations → gh CLI or native git | "
    "simple code read/edit → native Read/Edit/Grep tools\n\n"
    "Rules: docs before code | API/service → Gateway | browser testing → Playwright CLI first | "
    "host-dependent → plugin/skill/CLI | simple file ops → native tools."
)

_FALLBACK_SECTION = (
    "## Tool Discovery Fallback\n"
    "If your task requires capabilities NOT covered by the Required Workflows above,\n"
    "you MUST call airis-find with keywords describing what you need before attempting the task.\n"
    "Do NOT proceed without checking available tools first."
)

def compile_instructions(server_configs: dict[str, McpServerConfig]) -> str:
    """Compile workflows and behavior specs into instructions string.

    Workflows take priority over behavior configs. Servers covered by
    workflows are excluded from the behavior lines section.

    Args:
        server_configs: Dict mapping server name to McpServerConfig

    Returns:
        Compiled instructions string for MCP initialize response
    """
    workflows = load_workflows()

    sections = [_BASE_INSTRUCTIONS, _META_TOOLS_SECTION, _TOOL_ROUTING_GUIDE]

    # Compile workflow directives
    workflow_section = _compile_workflow_section(workflows)
    if workflow_section:
        sections.append(workflow_section)

    # Add fallback directive (always, if we have workflows)
    if workflows:
        sections.append(_FALLBACK_SECTION)

    # Auto-generate server list for airis-find
    server_list = _compile_server_list(server_configs)
    if server_list:
        sections.append(server_list)

    # Servers covered by workflows are excluded from behavior lines
    workflow_servers = set()
    for wf in workflows:
        workflow_servers.update(wf.servers)

    behavior_lines = _compile_behavior_lines(server_configs, exclude=workflow_servers)
    if behavior_lines:
        sections.append("## Proactive Tool Usage\n" + "\n".join(behavior_lines))

    # Append routing table Quick Routes
    routing_instructions = format_routing_table_as_instructions()
    if routing_instructions:
        sections.append(routing_instructions)

    return "\n\n".join(sections)


def _compile_workflow_section(workflows: list[WorkflowConfig]) -> str:
    """Compile workflow directives into the Required Workflows section.

    Includes workflows in priority order until token budget is exhausted.
    High priority workflows are always included. Medium/low are included
    if budget permits.

    Returns:
        Compiled workflow section string, or empty string if no workflows.
    """
    if not workflows:
        return ""

    header = "## Required Workflows\nYou MUST follow these workflows. They are directives, not suggestions.\n"
    parts = [header]
    total_tokens = estimate_tokens(header)

    for wf in workflows:
        wf_tokens = estimate_tokens(wf.compile_to)

        if wf.priority == "high":
            # High priority: always include
            parts.append(wf.compile_to.strip())
            total_tokens += wf_tokens
        elif total_tokens + wf_tokens <= _WORKFLOW_TOKEN_BUDGET:
            # Medium/low: include if budget permits
            parts.append(wf.compile_to.strip())
            total_tokens += wf_tokens
        else:
            logger.warning(
                f"Workflow '{wf.name}' (priority={wf.priority}) skipped: "
                f"token budget exhausted ({total_tokens}/{_WORKFLOW_TOKEN_BUDGET})"
            )

    return "\n\n".join(parts)


def _compile_server_list(server_configs: dict[str, McpServerConfig]) -> str:
    """Generate available servers list from mcp-config.json.

    Includes all server names (including disabled) so LLMs know
    what's available via airis-find.
    """
    if not server_configs:
        return ""

    names = sorted(server_configs.keys())
    return "## Available Servers\n" + ", ".join(names)


def _compile_behavior_lines(
    server_configs: dict[str, McpServerConfig],
    exclude: set[str] | None = None,
) -> list[str]:
    """Extract and sort behavior lines from server configs.

    Args:
        server_configs: Server configurations with behavior definitions.
        exclude: Server names to skip (covered by workflow directives).

    Returns:
        List of "WHEN <trigger> -> <instruction> [server]" lines,
        sorted by priority (high > medium > low).
    """
    from .mcp_config_loader import ServerMode

    if exclude is None:
        exclude = set()

    entries: list[tuple[int, str]] = []  # (priority_order, line)

    for name, config in server_configs.items():
        if name in exclude:
            continue

        if config.behavior is None:
            continue

        behavior = config.behavior
        if not behavior.triggers or not behavior.instruction:
            continue

        priority_order = _PRIORITY_ORDER.get(behavior.priority, 1)

        # Determine tool reference format based on mode
        if config.enabled and config.mode == ServerMode.HOT:
            tool_ref = f"[{name}]"
        else:
            tool_ref = f"airis-exec {name}:* [{name}]"

        trigger_str = " / ".join(behavior.triggers)
        line = f"WHEN {trigger_str} → {behavior.instruction} {tool_ref}"
        entries.append((priority_order, line))

    # Sort by priority
    entries.sort(key=lambda x: x[0])

    return [line for _, line in entries]
