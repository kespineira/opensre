"""Resolve an ``AgentRecord`` to its canonical token-meter provider id."""

from __future__ import annotations

import shlex
from pathlib import Path

from app.agents.registry import AgentRecord

KNOWN_PROVIDERS: frozenset[str] = frozenset(
    {
        "claude-code",
        "codex",
        "cursor",
        "aider",
        "gemini-cli",
        "opencode",
        "kimi",
        "copilot",
    }
)

# ``cursor-claude-code`` is the Anthropic extension wrapping the real
# ``claude`` binary with ``--output-format stream-json``; same NDJSON,
# same meter. The other cursor flavors emit plain text.
_CURSOR_FAMILY_TO_PROVIDER: dict[str, str] = {
    "cursor-claude-code": "claude-code",
    "cursor-agent-exec": "cursor",
    "cursor-agent": "cursor",
}


def provider_for(record: AgentRecord) -> str | None:
    """Return the canonical provider id for ``record``, or ``None`` if unknown.

    Resolution order: persisted ``record.provider`` first, then the
    discovery-style name (``<provider>-<pid>``) stripped of its PID
    suffix, then the stored command line. ``None`` lets the dashboard
    render ``-``.
    """
    if record.provider is not None:
        return record.provider
    from_name = provider_from_classified_name(record.name)
    if from_name is not None:
        return from_name
    return provider_from_command(record.command)


def provider_from_classified_name(name: str) -> str | None:
    """Derive a canonical provider id from a discovery-style name."""
    base = _strip_pid_suffix(name)
    if base in _CURSOR_FAMILY_TO_PROVIDER:
        return _CURSOR_FAMILY_TO_PROVIDER[base]
    if base in KNOWN_PROVIDERS:
        return base
    return None


def provider_from_command(command: str) -> str | None:
    """Derive a canonical provider id from a stored process command."""
    cmdline = _split_command(command)
    if not cmdline:
        return None
    executable = _normalized_token(cmdline[0])
    tokens = {_normalized_token(part) for part in cmdline}
    lower = command.lower()

    if ".cursor/extensions/anthropic.claude-code" in lower:
        return "claude-code"
    if "extension-host (agent-exec)" in lower:
        return "cursor"
    if "cursor-agent" in lower or "cursor agent" in lower:
        return "cursor"
    if executable in {"claude", "claude-code"} or ("claude" in tokens and "code" in tokens):
        return "claude-code"
    if executable == "codex" or "codex" in tokens:
        return "codex"
    if executable == "aider" or "aider" in tokens:
        return "aider"
    if executable == "gemini" or "gemini" in tokens:
        return "gemini-cli"
    return None


def _strip_pid_suffix(name: str) -> str:
    if "-" not in name:
        return name
    base, _, tail = name.rpartition("-")
    if tail.isdigit():
        return base
    return name


def _split_command(command: str) -> list[str]:
    try:
        return shlex.split(command)
    except ValueError:
        return command.split()


def _normalized_token(value: str) -> str:
    return Path(value.strip("'\"")).name.lower()


__all__ = [
    "KNOWN_PROVIDERS",
    "provider_for",
    "provider_from_classified_name",
    "provider_from_command",
]
