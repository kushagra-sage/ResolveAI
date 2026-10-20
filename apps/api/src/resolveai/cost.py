from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True, slots=True)
class Price:
    provider: str
    model: str
    version: str
    effective_from: datetime
    effective_to: datetime | None
    input_usd_per_million: Decimal
    output_usd_per_million: Decimal
    cached_usd_per_million: Decimal


@dataclass(frozen=True, slots=True)
class Usage:
    input_tokens: int
    output_tokens: int
    cached_tokens: int = 0


def select_price(
    prices: list[Price], provider: str, model: str, occurred_at: datetime
) -> Price | None:
    matching = [
        price
        for price in prices
        if price.provider == provider
        and price.model == model
        and price.effective_from <= occurred_at
        and (price.effective_to is None or occurred_at < price.effective_to)
    ]
    return max(matching, key=lambda item: item.effective_from) if matching else None


def calculate_cost_micros(usage: Usage, price: Price | None) -> int | None:
    if min(usage.input_tokens, usage.output_tokens, usage.cached_tokens) < 0:
        raise ValueError("token usage cannot be negative")
    if usage.cached_tokens > usage.input_tokens:
        raise ValueError("cached tokens cannot exceed input tokens")
    if price is None:
        return None
    uncached = usage.input_tokens - usage.cached_tokens
    usd = (
        Decimal(uncached) * price.input_usd_per_million
        + Decimal(usage.cached_tokens) * price.cached_usd_per_million
        + Decimal(usage.output_tokens) * price.output_usd_per_million
    ) / Decimal(1_000_000)
    return int((usd * Decimal(1_000_000)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
