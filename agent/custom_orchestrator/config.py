"""Configuration for the custom orchestrator agent"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

# agent/custom_orchestrator/config.py -> repo root is two parents up.
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DUCKDB = REPO_ROOT / "dbt_project" / "olist.duckdb"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "agent_outputs"


@dataclass
class AgentConfig:
    """Everything the agent needs to run. Swap the model here or in config.yaml."""

    model: str = "anthropic:claude-haiku-4-5"
    duckdb_path: Path = DEFAULT_DUCKDB
    output_dir: Path = DEFAULT_OUTPUT
    mcp_command: str = "uvx"
    # Guardrail against runaway tool loops (maps to Pydantic AI request_limit).
    max_requests: int = 12
    # Retries allowed when a tool call (e.g. bad SQL) errors, so the model can
    # self-correct its query before the run fails.
    max_sql_retries: int = 2

    def duckdb_mcp_args(self) -> list[str]:
        """Args for the DuckDB MCP server (mcp-server-motherduck)"""
        return [
            "mcp-server-motherduck",
            "--db-path",
            str(self.duckdb_path),
        ]


def load_config(config_path: str | Path | None = None) -> AgentConfig:
    """Build config from defaults, an optional YAML file, and the root .env"""
    load_dotenv(REPO_ROOT / ".env")

    cfg = AgentConfig()

    if config_path is None:
        default_yaml = Path(__file__).resolve().parent / "config.yaml"
        config_path = default_yaml if default_yaml.exists() else None

    if config_path is not None:
        data = yaml.safe_load(Path(config_path).read_text()) or {}
        if "model" in data:
            cfg.model = data["model"]
        if "duckdb_path" in data:
            cfg.duckdb_path = Path(data["duckdb_path"]).expanduser()
        if "output_dir" in data:
            cfg.output_dir = Path(data["output_dir"]).expanduser()
        if "mcp_command" in data:
            cfg.mcp_command = data["mcp_command"]
        if "max_requests" in data:
            cfg.max_requests = int(data["max_requests"])
        if "max_sql_retries" in data:
            cfg.max_sql_retries = int(data["max_sql_retries"])

    return cfg
