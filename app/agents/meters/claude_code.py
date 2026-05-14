"""Token meter for Anthropic Claude Code stream-json stdout.

Claude Code with ``--output-format stream-json`` emits NDJSON where
each ``assistant`` event carries an Anthropic-shape ``usage`` block
under ``message.usage``. The ``result`` event at session end carries
cumulative totals — counting it would overcount by ~50% in any
multi-turn session.

Cache counters (``cache_creation_input_tokens``,
``cache_read_input_tokens``) bill at 1.25× and 0.10× of input
respectively, so a flat sum with ``input_tokens`` would mis-price.
A future split per counter requires extending the meter return shape.
"""

from __future__ import annotations

import json
from typing import Any

from app.agents.meters import TokenSample, safe_int


class ClaudeCodeMeter:
    """Sums ``input_tokens`` + ``output_tokens`` from ``assistant`` events."""

    def parse_chunk(self, chunk: str) -> int:
        return self.sample_chunk(chunk).tokens

    def sample_chunk(self, chunk: str) -> TokenSample:
        total = 0
        latest_model: str | None = None
        for line in chunk.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                event: Any = json.loads(stripped)
            except (json.JSONDecodeError, ValueError):
                continue
            total += _tokens_from_event(event)
            event_model = _model_from_event(event)
            if event_model is not None:
                latest_model = event_model
        return TokenSample(tokens=total, model=latest_model)


def _tokens_from_event(event: object) -> int:
    if not isinstance(event, dict) or event.get("type") != "assistant":
        return 0
    message = event.get("message")
    if not isinstance(message, dict):
        return 0
    usage = message.get("usage")
    if not isinstance(usage, dict):
        return 0
    return safe_int(usage.get("input_tokens")) + safe_int(usage.get("output_tokens"))


def _model_from_event(event: object) -> str | None:
    if not isinstance(event, dict) or event.get("type") != "assistant":
        return None
    message = event.get("message")
    if not isinstance(message, dict):
        return None
    model = message.get("model")
    if isinstance(model, str) and model:
        return model
    return None
