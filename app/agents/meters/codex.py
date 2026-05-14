"""Token meter for OpenAI Codex CLI rollout NDJSON.

Verified empirically against codex-cli 0.130 rollouts. Event types
in ``$CODEX_HOME/sessions/YYYY/MM/DD/rollout-*.jsonl``:

- ``session_meta`` — once per session; carries cwd and
  ``model_provider`` but not a specific model.
- ``turn_context`` — once per turn; carries ``payload.model``.
- ``response_item`` — agent messages and tool calls; no usage.
- ``event_msg`` with ``payload.type == "token_count"`` — emitted
  after every turn; carries ``payload.info.last_token_usage`` with
  per-turn ``input_tokens``, ``cached_input_tokens``,
  ``output_tokens``, ``reasoning_output_tokens``. The first such
  event in a session carries ``info: null`` (rate-limit handshake).

This differs from ``codex exec --json`` stdout which uses
``turn.completed`` events. The on-disk rollout is the source of
truth because the wiring layer tails files, not stdout.

``cached_input_tokens`` (10× cheaper than input) and
``reasoning_output_tokens`` (priced as regular output but only
emitted by reasoning models) are excluded from the sum.
``total_token_usage`` is cumulative and would double-count.
"""

from __future__ import annotations

import json
from typing import Any

from app.agents.meters import TokenSample, safe_int


class CodexMeter:
    """Sums per-turn input + output from ``event_msg.token_count`` records."""

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
    if not isinstance(event, dict) or event.get("type") != "event_msg":
        return 0
    payload = event.get("payload")
    if not isinstance(payload, dict) or payload.get("type") != "token_count":
        return 0
    info = payload.get("info")
    if not isinstance(info, dict):
        return 0
    last = info.get("last_token_usage")
    if not isinstance(last, dict):
        return 0
    return safe_int(last.get("input_tokens")) + safe_int(last.get("output_tokens"))


def _model_from_event(event: object) -> str | None:
    if not isinstance(event, dict) or event.get("type") != "turn_context":
        return None
    payload = event.get("payload")
    if not isinstance(payload, dict):
        return None
    model = payload.get("model")
    if isinstance(model, str) and model:
        return model
    return None
