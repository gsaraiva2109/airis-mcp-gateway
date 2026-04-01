import os
from pydantic_settings import BaseSettings
from pathlib import Path

DEFAULT_PROJECT_ROOT = Path(
    os.getenv(
        "CONTAINER_PROJECT_ROOT",
        os.getenv("PROJECT_ROOT", "/workspace/project")
    )
)
DEFAULT_MCP_GATEWAY_URL = os.getenv("MCP_GATEWAY_URL", "http://mcp-gateway:9390")
DEFAULT_MCP_CONFIG = Path(
    os.getenv("MCP_CONFIG_PATH", str(DEFAULT_PROJECT_ROOT / "mcp-config.json"))
)


class Settings(BaseSettings):
    """Application settings"""

    # Mode: lite (no DB) or full (with DB)
    GATEWAY_MODE: str = os.getenv("GATEWAY_MODE", "lite")

    # Database (optional - only used in "full" mode)
    DATABASE_URL: str | None = os.getenv("DATABASE_URL", None)

    # Simple auth for single-user mode
    AIRIS_API_KEY: str | None = os.getenv("AIRIS_API_KEY", None)

    @property
    def is_lite_mode(self) -> bool:
        """Check if running in lite (stateless) mode"""
        return self.GATEWAY_MODE == "lite" or not self.DATABASE_URL

    # MCP Gateway
    PROJECT_ROOT: Path = DEFAULT_PROJECT_ROOT
    MCP_CONFIG_PATH: Path = DEFAULT_MCP_CONFIG
    MCP_GATEWAY_URL: str = DEFAULT_MCP_GATEWAY_URL
    MCP_STREAM_GATEWAY_URL: str = os.getenv(
        "MCP_STREAM_GATEWAY_URL",
        f"{DEFAULT_MCP_GATEWAY_URL.rstrip('/')}/mcp",
    )
    GATEWAY_PUBLIC_URL: str = os.getenv("GATEWAY_PUBLIC_URL", "http://gateway.localhost:9390")
    GATEWAY_API_URL: str = os.getenv("GATEWAY_API_URL", "http://localhost:9400/api")
    UI_PUBLIC_URL: str = os.getenv("UI_PUBLIC_URL", "http://ui.gateway.localhost:5273")
    MASTER_KEY_HEX: str | None = None

    # API
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "AIRIS MCP Gateway API"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

    # Schema Partitioning
    # Description mode: "full", "summary" (160 chars), "brief" (60 chars), "none"
    DESCRIPTION_MODE: str = os.getenv("DESCRIPTION_MODE", "brief")

    # Dynamic MCP Mode
    # When enabled, tools/list returns only meta-tools (airis-find, airis-exec)
    # instead of all available tools. This dramatically reduces context usage.
    DYNAMIC_MCP: bool = os.getenv("DYNAMIC_MCP", "true").lower() in ("true", "1", "yes")

    # Meta-Tools Mode: "core" (3 tools: find/exec/schema) or "full" (all 7 including confidence/suggest/route)
    META_TOOLS_MODE: str = os.getenv("META_TOOLS_MODE", "core")

    # Tool Listing Mode: "full" (all tool names) or "compact" (top 3 per server + count)
    TOOL_LISTING_MODE: str = os.getenv("TOOL_LISTING_MODE", "compact")

    # Tool Call Timeout (seconds)
    # Fail-safe timeout for MCP tool calls to prevent Claude Code from hanging indefinitely.
    # Applies to ProcessManager tool calls and Docker Gateway proxy requests.
    TOOL_CALL_TIMEOUT: float = float(os.getenv("TOOL_CALL_TIMEOUT", "90"))

    # CORS
    CORS_ORIGINS: list[str] = []

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "allow"


settings = Settings()

if not settings.CORS_ORIGINS:
    settings.CORS_ORIGINS = [
        settings.UI_PUBLIC_URL,
        settings.GATEWAY_PUBLIC_URL,
    ]


def validate_environment() -> list[str]:
    """
    Validate environment configuration at startup.

    Returns list of warnings for non-critical issues.
    Raises ValueError for critical misconfigurations.
    """
    warnings = []

    # Check ALLOWED_ORIGINS in production
    allowed_origins = os.getenv("ALLOWED_ORIGINS", "")
    if not allowed_origins or allowed_origins == "*":
        warnings.append(
            "ALLOWED_ORIGINS not set or set to '*'. "
            "Set explicit origins in production (e.g., ALLOWED_ORIGINS=https://app.example.com)"
        )

    # Check API key in production (optional but recommended)
    if not settings.AIRIS_API_KEY:
        warnings.append(
            "AIRIS_API_KEY not set. API authentication is disabled. "
            "Set AIRIS_API_KEY for public-facing deployments."
        )

    # Validate TOOL_CALL_TIMEOUT range
    if settings.TOOL_CALL_TIMEOUT < 10:
        warnings.append(
            f"TOOL_CALL_TIMEOUT={settings.TOOL_CALL_TIMEOUT}s is very low. "
            "Some MCP tools may timeout. Recommended minimum: 30s"
        )
    elif settings.TOOL_CALL_TIMEOUT > 300:
        warnings.append(
            f"TOOL_CALL_TIMEOUT={settings.TOOL_CALL_TIMEOUT}s is very high. "
            "Consider lowering to prevent hung requests."
        )

    # Validate rate limits
    rate_limit_ip = int(os.getenv("RATE_LIMIT_PER_IP", "100"))
    rate_limit_key = int(os.getenv("RATE_LIMIT_PER_API_KEY", "1000"))
    if rate_limit_ip > rate_limit_key:
        warnings.append(
            f"RATE_LIMIT_PER_IP ({rate_limit_ip}) > RATE_LIMIT_PER_API_KEY ({rate_limit_key}). "
            "API key users should have higher limits than anonymous users."
        )

    return warnings


def log_startup_warnings() -> None:
    """Log configuration warnings at startup."""
    import logging
    logger = logging.getLogger("airis.config")

    warnings = validate_environment()
    for warning in warnings:
        logger.warning(f"[Config] {warning}")
