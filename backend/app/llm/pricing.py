from dataclasses import dataclass

from app.llm.base import TokenUsage


@dataclass(frozen=True)
class ModelPrice:
    input_per_mtok: float
    output_per_mtok: float
    # 5-minute cache writes bill at 1.25x input; cache reads at 0.1x.
    cache_write_multiplier: float = 1.25
    cache_read_multiplier: float = 0.10


# USD per million tokens — Anthropic first-party API list prices (cached 2026-06-24).
# Other vendors' prices change often and aren't hardcoded: set LLM_PRICE_INPUT_PER_MTOK /
# LLM_PRICE_OUTPUT_PER_MTOK to track them, otherwise cost is reported as unknown.
ANTHROPIC_PRICES: dict[str, ModelPrice] = {
    "claude-fable-5-1": ModelPrice(10.0, 50.0, cache_read_multiplier=0.025),
    "claude-fable-5": ModelPrice(10.0, 50.0),
    "claude-opus-5": ModelPrice(5.0, 25.0),
    "claude-opus-4-8": ModelPrice(5.0, 25.0),
    "claude-opus-4-7": ModelPrice(5.0, 25.0),
    "claude-opus-4-6": ModelPrice(5.0, 25.0),
    "claude-sonnet-5": ModelPrice(2.0, 10.0),
    "claude-sonnet-4-6": ModelPrice(3.0, 15.0),
    "claude-haiku-4-5": ModelPrice(1.0, 5.0),
}


def price_for(model: str, override: ModelPrice | None = None) -> ModelPrice | None:
    if override is not None:
        return override
    if model in ANTHROPIC_PRICES:
        return ANTHROPIC_PRICES[model]
    # Tolerate dated or suffixed IDs by matching the longest known prefix.
    matches = [known for known in ANTHROPIC_PRICES if model.startswith(known)]
    return ANTHROPIC_PRICES[max(matches, key=len)] if matches else None


def estimate_cost(model: str, usage: TokenUsage, override: ModelPrice | None = None) -> float | None:
    price = price_for(model, override)
    if price is None:
        return None
    per_token_in = price.input_per_mtok / 1_000_000
    per_token_out = price.output_per_mtok / 1_000_000
    return (
        usage.input_tokens * per_token_in
        + usage.cache_creation_input_tokens * per_token_in * price.cache_write_multiplier
        + usage.cache_read_input_tokens * per_token_in * price.cache_read_multiplier
        + usage.output_tokens * per_token_out
    )
