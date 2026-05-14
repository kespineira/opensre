"""Token meters: stateless parsers extracting token counts from CLI output.

Cost calculation is deliberately separate — per-token rates change
per model and per counter (cache reads at 0.1×, cache writes at
1.25×), so binding cost to the parser would couple ``tokens/min``
to ``$/hr`` in a way that grows brittle.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class TokenSample:
    """A meter's read of a stdout chunk: tokens + optional model hint."""

    tokens: int
    model: str | None = None


class TokenMeter(Protocol):
    """A token-count parser over a CLI stdout chunk.

    Implementations must be safe to call with partial chunks — chunks
    coming from a streaming subprocess split at arbitrary byte offsets
    and may not align with line or JSON-document boundaries.
    """

    def parse_chunk(self, chunk: str, /) -> int:
        raise NotImplementedError

    def sample_chunk(self, chunk: str, /) -> TokenSample:
        raise NotImplementedError


class NullMeter:
    """Always returns 0 / ``None``."""

    def parse_chunk(self, _chunk: str, /) -> int:
        return 0

    def sample_chunk(self, _chunk: str, /) -> TokenSample:
        return TokenSample(tokens=0, model=None)


null_meter: TokenMeter = NullMeter()


def safe_int(value: object) -> int:
    """Coerce ``value`` to a non-negative int.

    ``bool`` is rejected explicitly because ``isinstance(True, int)``
    is ``True`` — a stray ``"input_tokens": true`` must not add 1.
    """
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value if value >= 0 else 0
    return 0


__all__ = ["NullMeter", "TokenMeter", "TokenSample", "null_meter", "safe_int"]
