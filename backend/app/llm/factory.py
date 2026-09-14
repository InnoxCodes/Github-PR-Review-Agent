import os
from dataclasses import dataclass

from app.config import Settings
from app.llm.base import LLMConfigurationError, LLMProvider
from app.llm.pricing import ModelPrice


@dataclass(frozen=True)
class LLMStatus:
    configured: bool
    provider: str | None
    model: str | None
    message: str


def llm_status(settings: Settings) -> LLMStatus:
    provider = _resolve_provider(settings)
    if provider is None:
        return LLMStatus(
            configured=False,
            provider=None,
            model=None,
            message="No LLM API key found. Add ANTHROPIC_API_KEY (or OPENAI_API_KEY) to backend/.env and restart the API.",
        )
    if provider == "openai" and not settings.llm_model:
        return LLMStatus(False, "openai", None, "Set LLM_MODEL to the OpenAI model ReviewMind should use.")
    model = settings.llm_model or ("claude-opus-5" if provider == "anthropic" else None)
    return LLMStatus(True, provider, model, f"Reviews run on {model}.")


def build_provider(settings: Settings) -> LLMProvider:
    status = llm_status(settings)
    if not status.configured:
        raise LLMConfigurationError(status.message)

    if status.provider == "anthropic":
        from app.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider(
            api_key=_anthropic_key(settings),
            model=status.model,
            effort=settings.llm_effort,
        )

    from app.llm.openai_provider import OpenAIProvider

    return OpenAIProvider(api_key=_openai_key(settings), model=status.model)


def price_override(settings: Settings) -> ModelPrice | None:
    if settings.llm_price_input_per_mtok is None or settings.llm_price_output_per_mtok is None:
        return None
    return ModelPrice(settings.llm_price_input_per_mtok, settings.llm_price_output_per_mtok)


def _resolve_provider(settings: Settings) -> str | None:
    has_anthropic = bool(_anthropic_key(settings) or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
    has_openai = bool(_openai_key(settings))
    if settings.llm_provider == "anthropic":
        return "anthropic" if has_anthropic else None
    if settings.llm_provider == "openai":
        return "openai" if has_openai else None
    if has_anthropic:
        return "anthropic"
    if has_openai:
        return "openai"
    return None


def _anthropic_key(settings: Settings) -> str | None:
    return settings.anthropic_api_key_value or os.environ.get("ANTHROPIC_API_KEY") or None


def _openai_key(settings: Settings) -> str | None:
    return settings.openai_api_key_value or os.environ.get("OPENAI_API_KEY") or None
