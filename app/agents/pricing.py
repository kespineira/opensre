"""Per-model token pricing for the dashboard's ``$/hr`` column.

``$/hr`` is a *projected hourly burn rate* derived from the trailing
60 s ``tokens/min`` window, not the actual spend over the last hour.
The formula projects the current ritmo to a one-hour horizon::

    $/hr = tokens_per_min × 60 × usd_per_token(model)

Reads as "if the agent sustains this ritmo for one hour, it will
cost this much". Same operational signal as ``cpu%``: tracks the
current state, reacts when the agent goes idle or switches model,
and stays memory-bounded.

``usd_per_token`` is a 70/30 input/output blend: today's meters sum
input + output into one int, so the tracker can't apply rates per
direction without a meter refactor. A follow-up that emits a
structured ``(input_tokens, output_tokens)`` count can replace the
blend with exact rate application.

Unknown models return ``None`` from every API in this module — the
dashboard renders ``-`` rather than inventing a rate.

Rates in :data:`MODEL_PRICES` are USD per single token. They are
public-pricing-page snapshots last verified at the date in
:data:`RATES_VERIFIED_AT` and need a refresh whenever providers
publish new rates. For ad-hoc overrides without a code change, users
can set per-agent prices in ``agents.yaml`` (see :class:`PriceOverride`
and the dashboard docs).

Excluded today: ``cache_read_input_tokens`` (~0.10×) and
``cache_creation_input_tokens`` (~1.25×) for Anthropic;
``cached_input_tokens`` (~0.10×) and ``reasoning_output_tokens``
for Codex. The meters skip those counters so ``$/hr`` undercounts
cache-heavy or reasoning-heavy sessions slightly.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Public pricing pages last cross-checked. Refresh when bumping rates.
RATES_VERIFIED_AT = "2026-05-14"

_USD_PER_M = 1_000_000


@dataclass(frozen=True)
class ModelPrice:
    usd_per_input_token: float
    usd_per_output_token: float


@dataclass(frozen=True)
class PriceOverride:
    """Per-agent rate override loaded from ``agents.yaml``.

    Lets users update pricing without a code change when providers
    bump rates between releases. Set either or both; missing values
    fall back to :data:`MODEL_PRICES`.
    """

    input_usd_per_million: float | None = None
    output_usd_per_million: float | None = None


MODEL_PRICES: dict[str, ModelPrice] = {
    "claude-3-5-sonnet-20241022": ModelPrice(3.00 / _USD_PER_M, 15.00 / _USD_PER_M),
    "claude-3-5-haiku-20241022": ModelPrice(0.80 / _USD_PER_M, 4.00 / _USD_PER_M),
    "claude-sonnet-4": ModelPrice(3.00 / _USD_PER_M, 15.00 / _USD_PER_M),
    "claude-sonnet-4-5": ModelPrice(3.00 / _USD_PER_M, 15.00 / _USD_PER_M),
    "claude-opus-4": ModelPrice(15.00 / _USD_PER_M, 75.00 / _USD_PER_M),
    "claude-opus-4-1": ModelPrice(15.00 / _USD_PER_M, 75.00 / _USD_PER_M),
    "gpt-5": ModelPrice(1.25 / _USD_PER_M, 10.00 / _USD_PER_M),
    "gpt-5.5": ModelPrice(1.25 / _USD_PER_M, 10.00 / _USD_PER_M),
    "gpt-5-codex": ModelPrice(1.25 / _USD_PER_M, 10.00 / _USD_PER_M),
    "gpt-5-mini": ModelPrice(0.25 / _USD_PER_M, 2.00 / _USD_PER_M),
    "gpt-4o": ModelPrice(2.50 / _USD_PER_M, 10.00 / _USD_PER_M),
    "gpt-4o-mini": ModelPrice(0.15 / _USD_PER_M, 0.60 / _USD_PER_M),
    "o3": ModelPrice(2.00 / _USD_PER_M, 8.00 / _USD_PER_M),
    "o3-mini": ModelPrice(1.10 / _USD_PER_M, 4.40 / _USD_PER_M),
}

# Longest-prefix-first so ``claude-opus-4-1`` is matched before
# ``claude-opus-4``. A date-suffixed model id (e.g.
# ``claude-sonnet-4-5-20260714``) resolves to its family.
_FAMILY_FALLBACKS: tuple[tuple[str, str], ...] = (
    ("claude-3-5-sonnet", "claude-3-5-sonnet-20241022"),
    ("claude-3-5-haiku", "claude-3-5-haiku-20241022"),
    ("claude-sonnet-4-5", "claude-sonnet-4-5"),
    ("claude-sonnet-4", "claude-sonnet-4"),
    ("claude-opus-4-1", "claude-opus-4-1"),
    ("claude-opus-4", "claude-opus-4"),
    ("gpt-5-codex", "gpt-5-codex"),
    ("gpt-5-mini", "gpt-5-mini"),
    ("gpt-5.5", "gpt-5.5"),
    ("gpt-5", "gpt-5"),
    ("gpt-4o-mini", "gpt-4o-mini"),
    ("gpt-4o", "gpt-4o"),
    ("o3-mini", "o3-mini"),
    ("o3", "o3"),
)


def usd_per_token_blended(model: str | None, override: PriceOverride | None = None) -> float | None:
    price = _resolve_price(model, override)
    if price is None:
        return None
    return 0.7 * price.usd_per_input_token + 0.3 * price.usd_per_output_token


def usd_per_hour(
    tokens_per_min: float,
    model: str | None,
    override: PriceOverride | None = None,
) -> float | None:
    rate = usd_per_token_blended(model, override)
    if rate is None:
        return None
    return tokens_per_min * 60.0 * rate


def _resolve_price(model: str | None, override: PriceOverride | None) -> ModelPrice | None:
    base = _lookup_price(model) if model is not None else None
    if override is None:
        return base
    # Merge: yaml fields override the table; missing yaml fields keep
    # the table's value. If the model is unknown AND the override is
    # incomplete, we still return ``None`` (never invent half a rate).
    input_rate = (
        override.input_usd_per_million / _USD_PER_M
        if override.input_usd_per_million is not None
        else (base.usd_per_input_token if base is not None else None)
    )
    output_rate = (
        override.output_usd_per_million / _USD_PER_M
        if override.output_usd_per_million is not None
        else (base.usd_per_output_token if base is not None else None)
    )
    if input_rate is None or output_rate is None:
        return None
    return ModelPrice(input_rate, output_rate)


def _lookup_price(model: str) -> ModelPrice | None:
    direct = MODEL_PRICES.get(model)
    if direct is not None:
        return direct
    # Continue past prefixes whose canonical id is missing from
    # MODEL_PRICES — a shorter family prefix may still match.
    for prefix, canonical_id in _FAMILY_FALLBACKS:
        if model.startswith(prefix):
            resolved = MODEL_PRICES.get(canonical_id)
            if resolved is not None:
                return resolved
    return None


__all__ = [
    "MODEL_PRICES",
    "ModelPrice",
    "PriceOverride",
    "RATES_VERIFIED_AT",
    "usd_per_hour",
    "usd_per_token_blended",
]
