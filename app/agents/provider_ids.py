"""Canonical provider-id constants and discovery-style name resolution.

Lives in its own module so :mod:`app.agents.discovery` (which
classifies commands and produces canonical provider names) and
:mod:`app.agents.providers` (which resolves an ``AgentRecord`` to a
provider id, calling back into discovery for the strict command
classifier) can both depend on it without forming an import cycle.
"""

from __future__ import annotations

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


def provider_from_classified_name(name: str) -> str | None:
    """Derive a canonical provider id from a discovery-style name."""
    base = _strip_pid_suffix(name)
    if base in _CURSOR_FAMILY_TO_PROVIDER:
        return _CURSOR_FAMILY_TO_PROVIDER[base]
    if base in KNOWN_PROVIDERS:
        return base
    return None


def _strip_pid_suffix(name: str) -> str:
    if "-" not in name:
        return name
    base, _, tail = name.rpartition("-")
    if tail.isdigit():
        return base
    return name


__all__ = ["KNOWN_PROVIDERS", "provider_from_classified_name"]
