"""Resolve an ``AgentRecord`` to its canonical token-meter provider id."""

from __future__ import annotations

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
    suffix, then a backfill via the shared strict command classifier
    in :mod:`app.agents.discovery` (covers legacy ``agents.jsonl``
    rows from before the ``provider`` field existed). ``None`` lets
    the dashboard render ``-``.
    """
    if record.provider is not None:
        return record.provider
    from_name = provider_from_classified_name(record.name)
    if from_name is not None:
        return from_name
    # Function-scope import: ``discovery`` imports
    # ``provider_from_classified_name`` from this module, so the
    # reverse direction must stay out of module load.
    from app.agents.discovery import classify_command_provider

    return classify_command_provider(record.command)


def provider_from_classified_name(name: str) -> str | None:
    """Derive a canonical provider id from a discovery-style name."""
    base = _strip_pid_suffix(name)
    if base in _CURSOR_FAMILY_TO_PROVIDER:
        return _CURSOR_FAMILY_TO_PROVIDER[base]
    if base in KNOWN_PROVIDERS:
        return base
    return None


def provider_from_command(command: str) -> str | None:
    """Legacy alias for :func:`app.agents.discovery.classify_command_provider`.

    Kept for tests and external callers; the classification engine
    now lives in ``discovery`` so register-time wiring and the
    on-read backfill share one implementation.
    """
    from app.agents.discovery import classify_command_provider

    return classify_command_provider(command)


def _strip_pid_suffix(name: str) -> str:
    if "-" not in name:
        return name
    base, _, tail = name.rpartition("-")
    if tail.isdigit():
        return base
    return name


__all__ = [
    "KNOWN_PROVIDERS",
    "provider_for",
    "provider_from_classified_name",
    "provider_from_command",
]
