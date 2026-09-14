import openai

from app.llm.base import (
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


class OpenAIProvider:
    """OpenAI via the Responses API with a strict JSON-schema text format."""

    name = "openai"

    def __init__(self, *, api_key: str | None, model: str, max_retries: int = 3, client: openai.AsyncOpenAI | None = None):
        self.model = model
        self._client = client or openai.AsyncOpenAI(api_key=api_key, max_retries=max_retries)

    async def generate_structured(self, request: StructuredRequest) -> StructuredResponse:
        first, *rest = request.turns
        items = [{"role": "user", "content": f"{request.context}\n\n{first.text}"}]
        items.extend({"role": turn.role, "content": turn.text or "(empty response)"} for turn in rest)

        try:
            response = await self._client.responses.create(
                model=self.model,
                instructions=request.system,
                input=items,
                max_output_tokens=request.max_tokens,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": request.schema_name,
                        "schema": request.schema,
                        "strict": True,
                    }
                },
            )
        except openai.AuthenticationError as exc:
            raise LLMAuthenticationError("OpenAI rejected the API key (401). Check OPENAI_API_KEY.") from exc
        except openai.PermissionDeniedError as exc:
            raise LLMAuthenticationError(f"This API key is not allowed to use {self.model}.") from exc
        except openai.NotFoundError as exc:
            raise LLMConfigurationError(f"Model {self.model!r} was not found for this API key.") from exc
        except openai.RateLimitError as exc:
            raise LLMRateLimitError("OpenAI rate limit reached and retries were exhausted.") from exc
        except openai.BadRequestError as exc:
            raise LLMError(f"OpenAI rejected the request: {exc.message}") from exc
        except openai.APIStatusError as exc:
            if exc.status_code >= 500:
                raise LLMUnavailableError(f"OpenAI API is unavailable ({exc.status_code}).") from exc
            raise LLMError(f"OpenAI API error {exc.status_code}: {exc.message}") from exc
        except openai.APIConnectionError as exc:
            raise LLMUnavailableError("Could not reach the OpenAI API (connection error or timeout).") from exc

        for item in response.output or []:
            for part in getattr(item, "content", None) or []:
                if getattr(part, "type", None) == "refusal":
                    raise LLMRefusalError(f"The model declined to review this chunk: {part.refusal}")

        stop_reason = None
        if response.status == "incomplete" and response.incomplete_details is not None:
            stop_reason = response.incomplete_details.reason

        usage = response.usage
        cached = 0
        if usage is not None and usage.input_tokens_details is not None:
            cached = usage.input_tokens_details.cached_tokens or 0
        return StructuredResponse(
            text=response.output_text or "",
            model=response.model,
            usage=TokenUsage(
                # OpenAI reports cached tokens as a subset of input_tokens.
                input_tokens=(usage.input_tokens - cached) if usage else 0,
                output_tokens=usage.output_tokens if usage else 0,
                cache_read_input_tokens=cached,
            ),
            stop_reason=stop_reason,
            request_id=response.id,
        )

    async def aclose(self) -> None:
        await self._client.close()
