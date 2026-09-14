"""Runs a pull request through the LLM: chunk -> prompt -> structured output -> validation.

Retry policy, in one place:

* Transport failures (429, 5xx, timeouts) are retried by the vendor SDK with backoff.
  If they still fail, the file is marked failed and the rest of the review continues.
* Invalid *output* (bad JSON, truncated, nothing usable) is retried here, up to
  ``max_attempts``, with the validation error fed back to the model as a correction turn.
* Credential/configuration errors abort the whole review — every file would fail the same way.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Literal, Protocol

from app.diff.chunking import chunk_file
from app.diff.models import FileChunk, FileDiff, PullRequestDiff
from app.llm.base import (
    ChatTurn,
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMError,
    LLMProvider,
    LLMRefusalError,
    StructuredRequest,
    StructuredResponse,
    TokenUsage,
)
from app.llm.pricing import ModelPrice, estimate_cost
from app.review.prompts import SYSTEM_PROMPT, render_chunk_prompt, render_pr_context
from app.review.schema import CHUNK_REVIEW_SCHEMA, Finding
from app.review.validation import InvalidReviewOutput, ValidatedReview, correction_prompt, validate_chunk_review


class ReviewAborted(Exception):
    pass


@dataclass(frozen=True)
class LLMCallRecord:
    filename: str
    chunk_index: int
    attempt: int
    model: str
    usage: TokenUsage
    cost_usd: float | None
    latency_ms: int
    outcome: Literal["ok", "invalid", "error"]
    error: str | None = None


@dataclass
class FileReviewResult:
    filename: str
    summary: str = ""
    findings: list[Finding] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=TokenUsage)
    cost_usd: float | None = None
    error: str | None = None
    dropped: list[str] = field(default_factory=list)
    adjusted: list[str] = field(default_factory=list)

    def add_cost(self, cost: float | None) -> None:
        if cost is not None:
            self.cost_usd = (self.cost_usd or 0.0) + cost


class ReviewListener(Protocol):
    async def on_file_started(self, file: FileDiff, chunk_count: int) -> None: ...

    async def on_chunk_findings(self, file: FileDiff, chunk: FileChunk, findings: list[Finding]) -> None: ...

    async def on_file_finished(self, file: FileDiff, result: FileReviewResult) -> None: ...

    async def on_llm_call(self, record: LLMCallRecord) -> None: ...


class ReviewEngine:
    def __init__(
        self,
        provider: LLMProvider,
        *,
        chunk_max_lines: int = 400,
        concurrency: int = 4,
        max_attempts: int = 3,
        max_output_tokens: int = 32_000,
        price_override: ModelPrice | None = None,
    ):
        self.provider = provider
        self.chunk_max_lines = chunk_max_lines
        self.concurrency = concurrency
        self.max_attempts = max_attempts
        self.max_output_tokens = max_output_tokens
        self.price_override = price_override

    async def review(self, pr: PullRequestDiff, listener: ReviewListener) -> list[FileReviewResult]:
        files = pr.reviewable_files
        if not files:
            return []

        run = _Run(self.provider.generate_structured, asyncio.Semaphore(self.concurrency))
        context = render_pr_context(pr)
        try:
            async with asyncio.TaskGroup() as group:
                tasks = [group.create_task(self._review_file(run, file, context, listener)) for file in files]
        except* (LLMAuthenticationError, LLMConfigurationError) as errors:
            raise ReviewAborted(str(errors.exceptions[0])) from errors.exceptions[0]
        return [task.result() for task in tasks]

    async def _review_file(self, run: "_Run", file: FileDiff, context: str, listener: ReviewListener) -> FileReviewResult:
        chunks = chunk_file(file, self.chunk_max_lines)
        await listener.on_file_started(file, len(chunks))
        result = FileReviewResult(filename=file.filename)
        summaries: list[str] = []

        try:
            for chunk in chunks:
                validated = await self._review_chunk(run, file, chunk, context, listener, result)
                summaries.append(validated.summary)
                result.findings.extend(validated.findings)
                result.dropped.extend(validated.dropped)
                result.adjusted.extend(validated.adjusted)
                await listener.on_chunk_findings(file, chunk, validated.findings)
        except (LLMAuthenticationError, LLMConfigurationError):
            raise
        except LLMRefusalError as exc:
            suffix = f" (category: {exc.category})" if exc.category else ""
            result.error = f"{exc}{suffix}"
        except (LLMError, _ChunkFailed) as exc:
            result.error = str(exc)

        result.summary = " ".join(summary for summary in summaries if summary)
        await listener.on_file_finished(file, result)
        return result

    async def _review_chunk(
        self,
        run: "_Run",
        file: FileDiff,
        chunk: FileChunk,
        context: str,
        listener: ReviewListener,
        result: FileReviewResult,
    ) -> ValidatedReview:
        turns = [ChatTurn("user", render_chunk_prompt(file, chunk))]
        last_error: InvalidReviewOutput | None = None

        for attempt in range(1, self.max_attempts + 1):
            request = StructuredRequest(
                system=SYSTEM_PROMPT,
                context=context,
                turns=list(turns),
                schema=CHUNK_REVIEW_SCHEMA,
                schema_name="chunk_review",
                max_tokens=self.max_output_tokens,
            )
            started = time.perf_counter()
            try:
                response = await run.generate(request)
            except LLMError as exc:
                await listener.on_llm_call(
                    LLMCallRecord(file.filename, chunk.index, attempt, self.provider.model, TokenUsage(),
                                  None, _elapsed_ms(started), "error", str(exc))
                )
                raise

            cost = estimate_cost(response.model, response.usage, self.price_override)
            result.usage += response.usage
            result.add_cost(cost)

            try:
                validated = validate_chunk_review(response.text, chunk, truncated=response.truncated)
            except InvalidReviewOutput as exc:
                last_error = exc
                await listener.on_llm_call(_record(file, chunk, attempt, response, cost, started, "invalid", str(exc)))
                # Show the model its own output and exactly what was wrong with it.
                turns += [ChatTurn("assistant", response.text), ChatTurn("user", correction_prompt(exc))]
                continue

            await listener.on_llm_call(_record(file, chunk, attempt, response, cost, started, "ok"))
            return validated

        raise _ChunkFailed(
            f"The model's output was still invalid after {self.max_attempts} attempts "
            f"(chunk {chunk.index + 1} of {chunk.total}): {last_error}"
        )


class _ChunkFailed(Exception):
    pass


class _Run:
    """Per-review call gate: bounded concurrency plus a prompt-cache warm-up.

    A cache entry only becomes readable once the request writing it starts responding, so
    N identical-prefix requests fired at once would all pay to write N copies. The first
    call of a review goes alone; once it returns, the system prompt and PR context are
    cached and every other chunk runs concurrently while reading them at ~10% of the price.
    """

    def __init__(self, generate: Callable[[StructuredRequest], Awaitable[StructuredResponse]], semaphore: asyncio.Semaphore):
        self._generate = generate
        self._semaphore = semaphore
        self._warm = asyncio.Event()
        self._warming_task: asyncio.Task | None = None

    async def generate(self, request: StructuredRequest) -> StructuredResponse:
        current = asyncio.current_task()
        if self._warming_task is None:
            self._warming_task = current
        elif current is not self._warming_task and not self._warm.is_set():
            await self._warm.wait()

        async with self._semaphore:
            try:
                return await self._generate(request)
            finally:
                if current is self._warming_task:
                    self._warm.set()


def _record(
    file: FileDiff,
    chunk: FileChunk,
    attempt: int,
    response: StructuredResponse,
    cost: float | None,
    started: float,
    outcome: Literal["ok", "invalid"],
    error: str | None = None,
) -> LLMCallRecord:
    return LLMCallRecord(
        file.filename, chunk.index, attempt, response.model, response.usage, cost, _elapsed_ms(started), outcome, error
    )


def _elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)
