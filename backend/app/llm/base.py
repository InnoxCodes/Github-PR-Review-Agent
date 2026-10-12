"""Provider-neutral contract between the review engine and an LLM vendor.

The engine only ever asks for one thing: "given these instructions and this diff, return
JSON matching this schema". Keeping the interface that narrow is what makes Claude and
OpenAI swappable, each provider maps it onto its own structured-output feature.
"""

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_creation_input_tokens=self.cache_creation_input_tokens + other.cache_creation_input_tokens,
            cache_read_input_tokens=self.cache_read_input_tokens + other.cache_read_input_tokens,
        )

    @property
    def total_input_tokens(self) -> int:
        return self.input_tokens + self.cache_creation_input_tokens + self.cache_read_input_tokens


@dataclass(frozen=True)
class ChatTurn:
    role: Literal["user", "assistant"]
    text: str


@dataclass(frozen=True)
class StructuredRequest:
    # Byte-identical across every call in every review, so providers can cache it.
    system: str
    # Identical for every chunk of one pull request (title, description, file list):
    # the second cache breakpoint.
    context: str
    # The chunk prompt, plus assistant/user pairs appended by validation retries.
    turns: list[ChatTurn]
    schema: dict[str, Any]
    schema_name: str
    max_tokens: int = 32_000


@dataclass(frozen=True)
class StructuredResponse:
    text: str
    model: str
    usage: TokenUsage
    stop_reason: str | None = None
    request_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def truncated(self) -> bool:
        return self.stop_reason in {"max_tokens", "length", "max_output_tokens"}


class LLMError(Exception):
    """Base for provider failures that are not about the *content* of the output."""


class LLMConfigurationError(LLMError):
    pass


class LLMAuthenticationError(LLMError):
    pass


class LLMRateLimitError(LLMError):
    pass


class LLMUnavailableError(LLMError):
    pass


class LLMRefusalError(LLMError):
    def __init__(self, message: str, category: str | None = None):
        super().__init__(message)
        self.category = category


class LLMProvider(Protocol):
    name: str
    model: str

    async def generate_structured(self, request: StructuredRequest) -> StructuredResponse: ...

    async def aclose(self) -> None: ...
