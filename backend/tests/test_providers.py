from types import SimpleNamespace

import anthropic
import httpx2
import openai
import pytest

from app.config import Settings
from app.llm.anthropic_provider import FALLBACK_BETA, AnthropicProvider
from app.llm.base import (
    ChatTurn,
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMRateLimitError,
    LLMRefusalError,
    LLMUnavailableError,
    StructuredRequest,
    TokenUsage,
)
from app.llm.factory import build_provider, llm_status
from app.llm.openai_provider import OpenAIProvider
from app.review.schema import CHUNK_REVIEW_SCHEMA

REQUEST = StructuredRequest(
    system="SYSTEM",
    context="<pull_request>...</pull_request>",
    turns=[ChatTurn("user", "Review this chunk"), ChatTurn("assistant", "oops"), ChatTurn("user", "Fix it")],
    schema=CHUNK_REVIEW_SCHEMA,
    schema_name="chunk_review",
    max_tokens=32_000,
)


# --- Anthropic ---------------------------------------------------------------------------

class FakeStream:
    def __init__(self, message, error):
        self.message, self.error = message, error

    async def __aenter__(self):
        if self.error:
            raise self.error
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def get_final_message(self):
        return self.message


class FakeAnthropicClient:
    def __init__(self, message=None, error=None):
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))
        self._message, self._error = message, error

    def _stream(self, **kwargs):
        self.calls.append(kwargs)
        return FakeStream(self._message, self._error)

    async def close(self):
        pass


def claude_message(stop_reason="end_turn", text='{"summary": "ok", "findings": []}', **extra):
    return SimpleNamespace(
        stop_reason=stop_reason,
        stop_details=extra.get("stop_details"),
        model="claude-opus-5",
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=120, output_tokens=80, cache_creation_input_tokens=0, cache_read_input_tokens=2_400),
    )


async def test_anthropic_request_uses_structured_outputs_caching_and_fallbacks():
    client = FakeAnthropicClient(claude_message())
    provider = AnthropicProvider(api_key=None, client=client)

    result = await provider.generate_structured(REQUEST)

    [call] = client.calls
    assert call["model"] == "claude-opus-5"
    assert call["output_config"] == {"format": {"type": "json_schema", "schema": CHUNK_REVIEW_SCHEMA}, "effort": "high"}
    assert call["system"] == [{"type": "text", "text": "SYSTEM", "cache_control": {"type": "ephemeral"}}]
    first_message = call["messages"][0]
    assert first_message["content"][0] == {
        "type": "text", "text": "<pull_request>...</pull_request>", "cache_control": {"type": "ephemeral"}
    }
    assert [m["role"] for m in call["messages"]] == ["user", "assistant", "user"]
    assert call["fallbacks"] == "default" and call["betas"] == [FALLBACK_BETA]
    assert "temperature" not in call and "thinking" not in call

    assert result.text == '{"summary": "ok", "findings": []}'
    assert result.usage == TokenUsage(input_tokens=120, output_tokens=80, cache_read_input_tokens=2_400)


async def test_anthropic_omits_fallbacks_and_effort_where_not_applicable():
    client = FakeAnthropicClient(claude_message())
    provider = AnthropicProvider(api_key=None, model="claude-haiku-4-5", effort=None, client=client)

    await provider.generate_structured(REQUEST)

    [call] = client.calls
    assert "fallbacks" not in call and "betas" not in call
    assert "effort" not in call["output_config"]


async def test_anthropic_refusal_is_raised_not_parsed():
    message = claude_message(stop_reason="refusal", text="", stop_details=SimpleNamespace(category="cyber"))
    provider = AnthropicProvider(api_key=None, client=FakeAnthropicClient(message))

    with pytest.raises(LLMRefusalError) as caught:
        await provider.generate_structured(REQUEST)

    assert caught.value.category == "cyber"


async def test_anthropic_truncation_is_reported_via_stop_reason():
    provider = AnthropicProvider(api_key=None, client=FakeAnthropicClient(claude_message(stop_reason="max_tokens")))

    assert (await provider.generate_structured(REQUEST)).truncated


def _api_error(error_type, status):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return error_type("boom", response=httpx2.Response(status, request=request), body=None)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (_api_error(anthropic.AuthenticationError, 401), LLMAuthenticationError),
        (_api_error(anthropic.NotFoundError, 404), LLMConfigurationError),
        (_api_error(anthropic.RateLimitError, 429), LLMRateLimitError),
        (_api_error(anthropic.InternalServerError, 500), LLMUnavailableError),
        (anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com")), LLMUnavailableError),
    ],
)
async def test_anthropic_errors_map_to_provider_neutral_types(error, expected):
    provider = AnthropicProvider(api_key=None, client=FakeAnthropicClient(error=error))

    with pytest.raises(expected):
        await provider.generate_structured(REQUEST)


# --- OpenAI ------------------------------------------------------------------------------

class FakeOpenAIClient:
    def __init__(self, result):
        self.calls = []
        self.responses = SimpleNamespace(create=self._create)
        self._result = result

    async def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self._result

    async def close(self):
        pass


def openai_response(status="completed", reason=None, output=None):
    return SimpleNamespace(
        id="resp_1",
        model="gpt-test",
        status=status,
        incomplete_details=SimpleNamespace(reason=reason) if reason else None,
        output=output or [],
        output_text='{"summary": "ok", "findings": []}',
        usage=SimpleNamespace(input_tokens=1_000, output_tokens=150, input_tokens_details=SimpleNamespace(cached_tokens=600)),
    )


async def test_openai_request_uses_strict_json_schema():
    client = FakeOpenAIClient(openai_response())
    provider = OpenAIProvider(api_key=None, model="gpt-test", client=client)

    result = await provider.generate_structured(REQUEST)

    [call] = client.calls
    assert call["instructions"] == "SYSTEM"
    assert call["text"]["format"]["strict"] is True
    assert call["input"][0]["content"].startswith("<pull_request>")
    assert result.usage == TokenUsage(input_tokens=400, output_tokens=150, cache_read_input_tokens=600)


async def test_openai_incomplete_response_counts_as_truncated():
    provider = OpenAIProvider(api_key=None, model="gpt-test", client=FakeOpenAIClient(openai_response("incomplete", "max_output_tokens")))

    assert (await provider.generate_structured(REQUEST)).truncated


async def test_openai_refusal_is_raised():
    refusal = SimpleNamespace(content=[SimpleNamespace(type="refusal", refusal="can't help")])
    provider = OpenAIProvider(api_key=None, model="gpt-test", client=FakeOpenAIClient(openai_response(output=[refusal])))

    with pytest.raises(LLMRefusalError):
        await provider.generate_structured(REQUEST)


# --- Factory -----------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def no_ambient_keys(monkeypatch):
    for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)


def test_no_keys_means_not_configured():
    status = llm_status(Settings(_env_file=None))

    assert not status.configured
    assert "ANTHROPIC_API_KEY" in status.message
    with pytest.raises(LLMConfigurationError):
        build_provider(Settings(_env_file=None))


def test_anthropic_key_defaults_to_opus_5():
    settings = Settings(_env_file=None, anthropic_api_key="sk-ant-test")

    assert llm_status(settings).model == "claude-opus-5"
    assert isinstance(build_provider(settings), AnthropicProvider)


def test_openai_requires_an_explicit_model():
    assert not llm_status(Settings(_env_file=None, openai_api_key="sk-test")).configured
    settings = Settings(_env_file=None, openai_api_key="sk-test", llm_model="gpt-test")
    assert isinstance(build_provider(settings), OpenAIProvider)


def test_auto_prefers_anthropic_when_both_keys_exist():
    settings = Settings(_env_file=None, anthropic_api_key="a", openai_api_key="b", llm_model="claude-sonnet-5")

    status = llm_status(settings)
    assert (status.provider, status.model) == ("anthropic", "claude-sonnet-5")


def test_forced_provider_without_its_key_is_not_configured():
    assert not llm_status(Settings(_env_file=None, llm_provider="anthropic", openai_api_key="b")).configured
