"""MCP-specific configuration loading."""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MCPConfig:
    """Immutable MCP-specific configuration."""

    allowed_directories: list[Path]
    max_file_size_bytes: int = 100_000_000
    request_timeout_seconds: int = 60
    max_images_per_extraction: int = 100
    max_extraction_depth: int = 3
    resource_storage_dir: Path = field(default_factory=lambda: Path("./mcp_resources"))
    output_dir: Path | None = None
    # 2026-06-18 round 16 Phase A3: explicit host/port so the server
    # doesn't default to FastMCP's 0.0.0.0:8000 (binds to all
    # interfaces, no auth). Default 127.0.0.1:8766 (loopback only,
    # different port from ORF's 8765 so both can run simultaneously).
    host: str = "127.0.0.1"
    port: int = 8766


def _parse_allowed_dirs(value: str) -> list[Path]:
    """Parse colon/semicolon separated paths into a list of Path objects.

    Single paths (no separator) are returned as a one-element list.
    Fix for the same bug ORF patched in round 12
    (commit 6741143): a single-path env var was returning [].
    """
    if not value or not value.strip():
        return []
    separators = [":", ";"]
    for sep in separators:
        if sep in value:
            paths = [Path(p.strip()) for p in value.split(sep) if p.strip()]
            if paths:
                return paths
            break
    # 2026-06-18 round 16 A3: single path without separator
    return [Path(value.strip())]


def _load_from_yaml(config_path: Path) -> dict | None:
    """Load configuration from a YAML file."""
    if not config_path.exists():
        return None
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning(f"Failed to load MCP config from {config_path}: {e}")
        return None


def _load_from_env() -> dict:
    """Load configuration from environment variables."""
    config = {}

    allowed_dirs = os.environ.get("OPP_MCP_ALLOWED_DIRS", "")
    if allowed_dirs:
        config["allowed_directories"] = _parse_allowed_dirs(allowed_dirs)

    max_file_size = os.environ.get("OPP_MCP_MAX_FILE_SIZE")
    if max_file_size:
        try:
            config["max_file_size_bytes"] = int(max_file_size)
        except ValueError:
            logger.warning(
                "Invalid OPP_MCP_MAX_FILE_SIZE=%r; falling back to default", max_file_size
            )

    timeout = os.environ.get("OPP_MCP_TIMEOUT")
    if timeout:
        try:
            config["request_timeout_seconds"] = int(timeout)
        except ValueError:
            logger.warning(
                "Invalid OPP_MCP_TIMEOUT=%r; falling back to default", timeout
            )

    # 2026-06-18 round 16 Phase A3: host/port env vars. Without
    # these, the MCP server defaults to FastMCP's 0.0.0.0:8000
    # which binds to all interfaces with no auth.
    host = os.environ.get("OPP_MCP_HOST")
    if host:
        config["host"] = host

    port = os.environ.get("OPP_MCP_PORT")
    if port:
        try:
            config["port"] = int(port)
        except ValueError:
            logger.warning(
                "Invalid OPP_MCP_PORT=%r; falling back to default", port
            )

    return config


def load_config(config_path: Path | None = None) -> MCPConfig:
    """Load MCP configuration from YAML file or environment variables.

    Args:
        config_path: Optional path to YAML configuration file.

    Returns:
        MCPConfig instance with loaded configuration.

    Raises:
        ValueError: If allowed_directories is empty or not provided.
    """
    config_data = {}

    # Try loading from YAML file if provided
    if config_path:
        yaml_data = _load_from_yaml(config_path)
        if yaml_data:
            config_data.update(yaml_data)

    # Merge with environment variables (env vars take precedence)
    env_data = _load_from_env()
    config_data.update(env_data)

    # Apply defaults
    if "max_file_size_bytes" not in config_data:
        config_data["max_file_size_bytes"] = 100_000_000
    if "request_timeout_seconds" not in config_data:
        config_data["request_timeout_seconds"] = 60
    if "max_images_per_extraction" not in config_data:
        config_data["max_images_per_extraction"] = 100
    if "max_extraction_depth" not in config_data:
        config_data["max_extraction_depth"] = 3
    if "resource_storage_dir" not in config_data:
        config_data["resource_storage_dir"] = Path("./mcp_resources")
    if "output_dir" not in config_data:
        config_data["output_dir"] = None
    if "host" not in config_data:
        config_data["host"] = "127.0.0.1"
    if "port" not in config_data:
        config_data["port"] = 8766

    # Validate required field
    allowed_dirs = config_data.get("allowed_directories")
    if not allowed_dirs:
        raise ValueError("allowed_directories cannot be empty")

    return MCPConfig(
        allowed_directories=allowed_dirs,
        max_file_size_bytes=config_data["max_file_size_bytes"],
        request_timeout_seconds=config_data["request_timeout_seconds"],
        max_images_per_extraction=config_data["max_images_per_extraction"],
        max_extraction_depth=config_data["max_extraction_depth"],
        resource_storage_dir=config_data["resource_storage_dir"],
        output_dir=config_data["output_dir"],
        host=config_data["host"],
        port=config_data["port"],
    )