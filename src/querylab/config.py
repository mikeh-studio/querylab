"""Environment-backed configuration for replaceable external providers."""

from __future__ import annotations

import os
import shlex
from dataclasses import dataclass
from pathlib import Path


DEFAULT_CODEX_COMMAND = (
    "codex",
    "exec",
    "--ephemeral",
    "--sandbox",
    "read-only",
    "--skip-git-repo-check",
    "--color",
    "never",
)

DEFAULT_CLAUDE_COMMAND = (
    "claude",
    "--print",
    "--no-session-persistence",
    "--permission-mode",
    "dontAsk",
    "--tools",
    "",
)

PRIMARY_ENV_PREFIX = "QUERYLAB_"
LEGACY_ENV_PREFIXES = ("SQL_LAB_", "DATA_INTERVIEW_LAB_")


def _environment_value(name: str, default: str | None = None) -> str | None:
    """Prefer QueryLab settings, then the two historical prefixes."""
    for prefix in (PRIMARY_ENV_PREFIX, *LEGACY_ENV_PREFIXES):
        configured = os.getenv(name.replace(PRIMARY_ENV_PREFIX, prefix, 1))
        if configured is not None:
            return configured
    return default


def default_history_db_path() -> Path:
    configured = _environment_value("QUERYLAB_HISTORY_DB")
    if configured:
        return Path(configured).expanduser()
    paths = [
        Path.home() / folder / "history.db"
        for folder in (".querylab", ".sql-interview-lab", ".data-interview-lab")
    ]
    return next((path for path in paths if path.exists()), paths[0])


def history_limit_from_env() -> int:
    limit = int(_environment_value("QUERYLAB_HISTORY_LIMIT", "200"))
    if limit < 1:
        raise ValueError("QUERYLAB_HISTORY_LIMIT must be positive")
    return limit


def _command_from_env(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    configured = _environment_value(name)
    if configured is None:
        return default
    command = tuple(shlex.split(configured))
    if not command:
        raise ValueError(f"{name} cannot be empty")
    return command


@dataclass(frozen=True)
class Settings:
    llm_provider: str
    llm_timeout_seconds: float
    advanced_llm_timeout_seconds: float
    codex_command: tuple[str, ...]
    claude_command: tuple[str, ...]

    @classmethod
    def from_env(cls) -> "Settings":
        timeout = float(_environment_value("QUERYLAB_LLM_TIMEOUT", "600"))
        if timeout <= 0:
            raise ValueError("QUERYLAB_LLM_TIMEOUT must be positive")
        advanced_timeout = float(
            _environment_value("QUERYLAB_ADVANCED_LLM_TIMEOUT", "1200")
        )
        if advanced_timeout <= 0:
            raise ValueError("QUERYLAB_ADVANCED_LLM_TIMEOUT must be positive")
        return cls(
            llm_provider=_environment_value("QUERYLAB_LLM_PROVIDER", "codex"),
            llm_timeout_seconds=timeout,
            advanced_llm_timeout_seconds=advanced_timeout,
            codex_command=_command_from_env(
                "QUERYLAB_CODEX_COMMAND", DEFAULT_CODEX_COMMAND
            ),
            claude_command=_command_from_env(
                "QUERYLAB_CLAUDE_COMMAND", DEFAULT_CLAUDE_COMMAND
            ),
        )
