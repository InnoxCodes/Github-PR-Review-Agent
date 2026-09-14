import pytest

from app.llm.base import TokenUsage
from app.llm.pricing import ModelPrice, estimate_cost, price_for


def test_opus_5_cost_includes_cache_multipliers():
    usage = TokenUsage(
        input_tokens=1_000_000,
        output_tokens=100_000,
        cache_creation_input_tokens=200_000,
        cache_read_input_tokens=1_000_000,
    )

    # 1M x $5 + 0.2M x $5 x 1.25 + 1M x $5 x 0.1 + 0.1M x $25
    assert estimate_cost("claude-opus-5", usage) == pytest.approx(5.0 + 1.25 + 0.5 + 2.5)


def test_suffixed_model_ids_match_the_longest_known_prefix():
    assert price_for("claude-sonnet-4-6-20260101") == price_for("claude-sonnet-4-6")


def test_unknown_model_has_unknown_cost():
    assert estimate_cost("some-other-model", TokenUsage(input_tokens=10)) is None


def test_override_prices_any_model():
    cost = estimate_cost("gpt-x", TokenUsage(input_tokens=2_000_000), ModelPrice(1.5, 6.0))

    assert cost == pytest.approx(3.0)


def test_usage_adds_up():
    total = TokenUsage(1, 2, 3, 4) + TokenUsage(10, 20, 30, 40)

    assert total == TokenUsage(11, 22, 33, 44)
    assert total.total_input_tokens == 11 + 33 + 44
