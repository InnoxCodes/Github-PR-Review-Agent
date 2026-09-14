import anthropic

from app.llm.base import (
    ChatTurn,
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMError,
    LLMRateLimitError,
    LLMRefusalError,
    LLMUnavailableError,
    StructuredRequest,
    StructuredResponse,
    TokenUsage,
)

DEFAULT_MODEL = "claude-opus-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
# Models whose safety classifiers can decline a request, and that accept fallbacks="default".
MODELS_WITH_REFUSAL_FALLBACK = frozenset({"claude-opus-5", "claude-fable-5-1"})


class AnthropicProvider:
    """Claude via structured outputs: the JSON schema is enforced during decoding."""

    name = "anthropic"

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str = DEFAULT_MODEL,
        effort: str | None = "high",
        max_retries: int = 3,
        client: anthropic.AsyncAnthropic | None = None,
    ):
        self.model = model
        self.effort = effort
        # The SDK already retries 408/409/429/5xx and connection errors with backoff, so
        # transport-level retries live there; the engine only retries on *invalid output*.
        self._client = client or anthropic.AsyncAnthropic(api_key=api_key, max_retries=max_retries)

    async def generate_structured(self, request: StructuredRequest) -> StructuredResponse:
        output_config: dict = {"format": {"type": "json_schema", "schema": request.schema}}
        if self.effort:
            output_config["effort"] = self.effort

        extra: dict = {}
        if self.model in MODELS_WITH_REFUSAL_FALLBACK:
            # Safety classifiers occasionally decline benign security-adjacent code (reviewing
            # an auth or crypto change, say). "default" re-runs a declined request server-side
            # on Anthropic's recommended fallback model instead of failing the whole file.
            extra = {"fallbacks": "default", "betas": [FALLBACK_BETA]}

        try:
            # Streaming keeps long adaptive-thinking generations clear of HTTP timeouts.
            async with self._client.beta.messages.stream(
                model=self.model,
                max_tokens=request.max_tokens,
                system=[{"type": "text", "text": request.system, "cache_control": {"type": "ephemeral"}}],
                messages=_to_messages(request),
                output_config=output_config,
                **extra,
            ) as stream:
                message = await stream.get_final_message()
        except anthropic.AuthenticationError as exc:
            raise LLMAuthenticationError("Anthropic rejected the API key (401). Check ANTHROPIC_API_KEY.") from exc
        except anthropic.PermissionDeniedError as exc:
            raise LLMAuthenticationError(f"This API key is not allowed to use {self.model}: {exc.message}") from exc
        except anthropic.NotFoundError as exc:
            raise LLMConfigurationError(
                f"Model {self.model!r} was not found or is not available to this API key."
            ) from exc
        except anthropic.RateLimitError as exc:
            raise LLMRateLimitError("Anthropic rate limit reached and retries were exhausted.") from exc
        except anthropic.BadRequestError as exc:
            raise LLMError(f"Anthropic rejected the request: {exc.message}") from exc
        except anthropic.APIStatusError as exc:
            if exc.status_code >= 500:
                raise LLMUnavailableError(f"Anthropic API is unavailable ({exc.status_code}).") from exc
            raise LLMError(f"Anthropic API error {exc.status_code}: {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMUnavailableError("Could not reach the Anthropic API (connection error or timeout).") from exc

        # A refusal is an HTTP 200 whose content is empty or partial — never read it as a review.
        if message.stop_reason == "refusal":
            details = getattr(message, "stop_details", None)
            category = getattr(details, "category", None)
            raise LLMRefusalError("Claude declined to review this chunk.", category)

        usage = message.usage
        return StructuredResponse(
            text="".join(block.text for block in message.content if block.type == "text"),
            model=message.model,
            usage=TokenUsage(
                input_tokens=usage.input_tokens or 0,
                output_tokens=usage.output_tokens or 0,
                cache_creation_input_tokens=usage.cache_creation_input_tokens or 0,
                cache_read_input_tokens=usage.cache_read_input_tokens or 0,
            ),
            stop_reason=message.stop_reason,
            request_id=getattr(message, "_request_id", None),
        )

    async def aclose(self) -> None:
        await self._client.close()


def _to_messages(request: StructuredRequest) -> list[dict]:
    first, *rest = request.turns
    messages: list[dict] = [
        {
            "role": "user",
            "content": [
                # Second cache breakpoint: the PR context is shared by every chunk of this review.
                {"type": "text", "text": request.context, "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": first.text},
            ],
        }
    ]
    messages.extend(_turn(turn) for turn in rest)
    return messages


def _turn(turn: ChatTurn) -> dict:
    return {"role": turn.role, "content": [{"type": "text", "text": turn.text or "(empty response)"}]}
