"""Workflow Loader — loads and validates workflow YAML recipes.

Reads workflow definitions from workflows/ directory and produces
validated WorkflowConfig objects for behavior_compiler to compile
into MCP instructions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from .logging import get_logger

logger = get_logger(__name__)

_PRIORITY_VALUES = {"high", "medium", "low"}
_KEBAB_CASE_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


@dataclass
class WorkflowConfig:
    """Parsed workflow recipe configuration."""

    name: str
    description: str
    priority: str  # "high" | "medium" | "low"
    max_tokens: int
    servers: list[str]
    trigger: str
    compile_to: str


def estimate_tokens(text: str) -> int:
    """Estimate token count for a text string.

    ASCII characters: ~4 chars per token.
    Non-ASCII characters (Japanese, etc.): ~2 chars per token.
    """
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    non_ascii_chars = len(text) - ascii_chars
    return (ascii_chars // 4) + (non_ascii_chars // 2)


def load_workflows(workflows_dir: Optional[Path] = None) -> list[WorkflowConfig]:
    """Load all workflow YAML files, validate, and return sorted by priority.

    Args:
        workflows_dir: Path to workflows/ directory. Defaults to
            /app/workflows (container) or ./workflows (development).

    Returns:
        List of WorkflowConfig sorted by priority (high > medium > low),
        then by filename within same priority.
    """
    if workflows_dir is None:
        candidates = [
            Path("/app/workflows"),
            Path("./workflows"),
            Path("../workflows"),
            Path("../../workflows"),
        ]
        for candidate in candidates:
            if candidate.is_dir():
                workflows_dir = candidate
                break

    if workflows_dir is None or not workflows_dir.is_dir():
        logger.debug("No workflows/ directory found, skipping workflow loading")
        return []

    priority_order = {"high": 0, "medium": 1, "low": 2}
    workflows: list[tuple[int, str, WorkflowConfig]] = []

    for yaml_path in sorted(workflows_dir.glob("*.yaml")):
        try:
            with open(yaml_path) as f:
                raw = yaml.safe_load(f)
        except Exception:
            logger.exception(f"Failed to parse {yaml_path}")
            continue

        if not isinstance(raw, dict):
            logger.warning(f"Invalid workflow file (not a mapping): {yaml_path}")
            continue

        config = WorkflowConfig(
            name=raw.get("name", ""),
            description=raw.get("description", ""),
            priority=raw.get("priority", "medium"),
            max_tokens=raw.get("max_tokens", 200),
            servers=raw.get("servers", []),
            trigger=raw.get("trigger", ""),
            compile_to=raw.get("compile_to", ""),
        )

        errors = validate_workflow(config)
        if errors:
            for error in errors:
                logger.error(f"Workflow '{yaml_path.name}': {error}")
            continue

        order = priority_order.get(config.priority, 1)
        workflows.append((order, yaml_path.name, config))

    workflows.sort(key=lambda x: (x[0], x[1]))
    loaded = [wf for _, _, wf in workflows]

    logger.info(f"Loaded {len(loaded)} workflows from {workflows_dir}")
    return loaded


def validate_workflow(config: WorkflowConfig) -> list[str]:
    """Validate a workflow configuration.

    Returns:
        List of validation error messages. Empty list means valid.
    """
    errors: list[str] = []

    if not config.name:
        errors.append("'name' is required")
    elif not _KEBAB_CASE_RE.match(config.name):
        errors.append(f"'name' must be kebab-case, got '{config.name}'")

    if config.priority not in _PRIORITY_VALUES:
        errors.append(f"'priority' must be high/medium/low, got '{config.priority}'")

    if not config.compile_to or not config.compile_to.strip():
        errors.append("'compile_to' is required and must not be empty")
    else:
        token_estimate = estimate_tokens(config.compile_to)
        if token_estimate > config.max_tokens:
            errors.append(
                f"'compile_to' exceeds max_tokens: estimated {token_estimate} > limit {config.max_tokens}"
            )

    if not config.servers:
        errors.append("'servers' is required and must not be empty")

    return errors
