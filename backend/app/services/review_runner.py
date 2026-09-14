"""Runs reviews in the background and turns engine progress into stored, streamed events.

Every step follows the same pattern: change rows and append a ReviewEvent in *one*
transaction, commit, then publish. A client that reads a review's status therefore always
finds the matching event in the log, and a reconnecting client never misses one.
"""

import asyncio
import contextlib
import logging
import time
from collections import Counter
from collections.abc import Callable, Sequence

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.diff.models import FileChunk, FileDiff, PullRequestDiff
from app.events import Event, EventBroker
from app.github.client import GitHubError
from app.github.urls import PRRef
from app.llm.base import LLMConfigurationError, LLMProvider
from app.llm.factory import price_override
from app.models import (
    LIVE_ISSUE_STATUSES,
    REVIEW_ACTIVE_STATUSES,
    Issue,
    LLMCall,
    Repository,
    Review,
    ReviewEvent,
    ReviewFile,
    new_id,
    utcnow,
)
from app.review.engine import FileReviewResult, LLMCallRecord, ReviewAborted, ReviewEngine
from app.review.schema import Finding
from app.review.scoring import ScoredIssue, health_score
from app.schemas import IssueOut
from app.security import TokenCipher
from app.services.pr_source import PRLoader
from app.services.views import file_fields, issue_stats, review_summary

logger = logging.getLogger("reviewmind.runner")


class ReviewRunner:
    def __init__(
        self,
        *,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        broker: EventBroker,
        cipher: TokenCipher,
        provider_factory: Callable[[Settings], LLMProvider],
        pr_loader: PRLoader,
    ):
        self.settings = settings
        self.session_factory = session_factory
        self.broker = broker
        self.cipher = cipher
        self.provider_factory = provider_factory
        self.pr_loader = pr_loader
        self._tasks: dict[str, asyncio.Task[None]] = {}

    def start(self, review_id: str) -> None:
        task = asyncio.create_task(self._run(review_id), name=f"review:{review_id}")
        self._tasks[review_id] = task
        task.add_done_callback(lambda _: self._tasks.pop(review_id, None))

    def is_running(self, review_id: str) -> bool:
        return review_id in self._tasks

    async def wait_idle(self) -> None:
        while self._tasks:
            await asyncio.gather(*list(self._tasks.values()), return_exceptions=True)

    async def shutdown(self) -> None:
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def record_event(self, session: AsyncSession, review_id: str, event_type: str, data: dict) -> Event:
        event = ReviewEvent(review_id=review_id, type=event_type, payload=data, created_at=utcnow())
        session.add(event)
        await session.flush()
        return {"id": event.id, "type": event_type, "data": data}

    async def _run(self, review_id: str) -> None:
        started = time.perf_counter()
        provider: LLMProvider | None = None
        try:
            ref, token = await self._begin(review_id)
            pr = await self.pr_loader(ref, token)
            file_ids = await self._store_pull_request(review_id, pr)

            if not pr.reviewable_files:
                await self._complete(review_id, started, [])
                return

            provider = self.provider_factory(self.settings)
            await self._mark_reviewing(review_id, provider, len(pr.reviewable_files))
            engine = ReviewEngine(
                provider,
                chunk_max_lines=self.settings.chunk_max_lines,
                concurrency=self.settings.llm_concurrency,
                max_attempts=self.settings.llm_max_attempts,
                max_output_tokens=self.settings.llm_max_output_tokens,
                price_override=price_override(self.settings),
            )
            results = await engine.review(pr, _PersistingListener(self, review_id, file_ids))
            await self._complete(review_id, started, results)
        except asyncio.CancelledError:
            await self._fail(review_id, started, "The API shut down while this review was running.")
            raise
        except (ReviewAborted, LLMConfigurationError) as exc:
            await self._fail(review_id, started, str(exc))
        except GitHubError as exc:
            await self._fail(review_id, started, f"GitHub: {exc}")
        except Exception:
            logger.exception("Review %s crashed", review_id)
            await self._fail(review_id, started, "Unexpected error while reviewing. Check the API logs for details.")
        finally:
            if provider is not None:
                with contextlib.suppress(Exception):
                    await provider.aclose()

    async def _begin(self, review_id: str) -> tuple[PRRef, str | None]:
        async with self.session_factory() as session:
            review = await session.get(Review, review_id)
            if review is None:
                raise RuntimeError(f"Review {review_id} disappeared before it started")
            token = await self._stored_token(session, review)
            review.status = "fetching"
            review.status_message = "Fetching the pull request from GitHub"
            review.started_at = utcnow()
            event = await self.record_event(
                session, review_id, "status", {"status": "fetching", "message": review.status_message}
            )
            await session.commit()
        self.broker.publish(review_id, event)
        return PRRef(review.owner, review.repo, review.pr_number), token or self.settings.github_token_value

    async def _stored_token(self, session: AsyncSession, review: Review) -> str | None:
        if review.repository_id is None:
            return None
        repository = await session.get(Repository, review.repository_id)
        if repository is None or not repository.encrypted_token:
            return None
        token = self.cipher.decrypt(repository.encrypted_token)
        if token is None:
            logger.warning("Stored token for %s could not be decrypted — was the secret key changed?", repository.full_name)
        return token

    async def _store_pull_request(self, review_id: str, pr: PullRequestDiff) -> dict[str, int]:
        meta = pr.metadata
        async with self.session_factory() as session:
            review = await session.get(Review, review_id)
            repository = await upsert_repository_from_pr(session, pr)
            review.repository_id = repository.id
            review.owner, review.repo = meta.owner, meta.repo
            review.pr_title = meta.title
            review.pr_body = meta.body
            review.pr_author = meta.author.login
            review.pr_author_avatar = meta.author.avatar_url
            review.pr_state = "merged" if meta.merged else meta.state
            review.pr_draft = meta.draft
            review.pr_merged = meta.merged
            review.base_ref, review.head_ref, review.head_sha = meta.base_ref, meta.head_ref, meta.head_sha
            review.pr_created_at = meta.created_at
            review.additions, review.deletions = meta.additions, meta.deletions
            review.changed_files, review.commits = meta.changed_files, meta.commits
            review.files_total = len(pr.reviewable_files)
            review.changed_lines_reviewed = sum(f.additions + f.deletions for f in pr.reviewable_files)

            rows = [
                ReviewFile(
                    review_id=review_id,
                    position=position,
                    filename=file.filename,
                    previous_filename=file.previous_filename,
                    git_status=str(file.status),
                    language=file.language,
                    additions=file.additions,
                    deletions=file.deletions,
                    skip_reason=str(file.skip_reason) if file.skip_reason else None,
                    state="pending" if file.reviewable else "skipped",
                    chunk_count=0,
                    hunks=[hunk.model_dump(mode="json") for hunk in file.hunks],
                )
                for position, file in enumerate(pr.files)
            ]
            session.add_all(rows)
            await session.flush()
            payload = {
                "review": review_summary(review).model_dump(mode="json"),
                "files": [file_fields(row) for row in rows],
            }
            event = await self.record_event(session, review_id, "pr", payload)
            await session.commit()
        self.broker.publish(review_id, event)
        return {row.filename: row.id for row in rows}

    async def _mark_reviewing(self, review_id: str, provider: LLMProvider, file_count: int) -> None:
        async with self.session_factory() as session:
            review = await session.get(Review, review_id)
            review.status = "reviewing"
            review.provider, review.model = provider.name, provider.model
            review.status_message = f"Reviewing {file_count} file{'s' if file_count != 1 else ''} with {provider.model}"
            event = await self.record_event(
                session, review_id, "status", {"status": "reviewing", "message": review.status_message, "model": provider.model}
            )
            await session.commit()
        self.broker.publish(review_id, event)

    async def _complete(self, review_id: str, started: float, results: Sequence[FileReviewResult]) -> None:
        failed = [result for result in results if result.error]
        if results and len(failed) == len(results):
            count = len(results)
            await self._fail(
                review_id,
                started,
                f"All {count} file{'s' if count != 1 else ''} failed to review. First error: {failed[0].error}",
            )
            return

        async with self.session_factory() as session:
            review = await session.get(Review, review_id)
            live = (
                await session.scalars(
                    select(Issue).where(Issue.review_id == review_id, Issue.status.in_(LIVE_ISSUE_STATUSES))
                )
            ).all()
            score = health_score(
                [ScoredIssue(issue.severity, issue.category, issue.confidence) for issue in live],
                review.changed_lines_reviewed,
            )
            review.health_score = review.initial_health_score = score
            review.summary = summarize(live, review.files_total, len(failed))
            review.status = "completed"
            review.status_message = None
            review.completed_at = utcnow()
            review.duration_ms = round((time.perf_counter() - started) * 1000)
            stats = (await issue_stats(session, [review_id]))[review_id]
            event = await self.record_event(
                session, review_id, "review.completed", {"review": review_summary(review, stats).model_dump(mode="json")}
            )
            await session.commit()
        self.broker.publish(review_id, event)

    async def _fail(self, review_id: str, started: float, message: str) -> None:
        try:
            async with self.session_factory() as session:
                review = await session.get(Review, review_id)
                if review is None:
                    return
                review.status = "failed"
                review.status_message = None
                review.error = message
                review.completed_at = utcnow()
                review.duration_ms = round((time.perf_counter() - started) * 1000)
                await session.execute(
                    update(ReviewFile)
                    .where(ReviewFile.review_id == review_id, ReviewFile.state.in_(("pending", "reviewing")))
                    .values(state="failed", error="The review stopped before this file finished.")
                )
                stats = (await issue_stats(session, [review_id]))[review_id]
                event = await self.record_event(
                    session,
                    review_id,
                    "review.failed",
                    {"error": message, "review": review_summary(review, stats).model_dump(mode="json")},
                )
                await session.commit()
            self.broker.publish(review_id, event)
        except Exception:
            logger.exception("Could not record the failure of review %s", review_id)


class _PersistingListener:
    def __init__(self, runner: ReviewRunner, review_id: str, file_ids: dict[str, int]):
        self.runner = runner
        self.review_id = review_id
        self.file_ids = file_ids

    async def on_file_started(self, file: FileDiff, chunk_count: int) -> None:
        file_id = self.file_ids[file.filename]
        async with self.runner.session_factory() as session:
            await session.execute(
                update(ReviewFile).where(ReviewFile.id == file_id).values(state="reviewing", chunk_count=chunk_count)
            )
            event = await self.runner.record_event(
                session, self.review_id, "file.started", {"file_id": file_id, "filename": file.filename, "chunks": chunk_count}
            )
            await session.commit()
        self.runner.broker.publish(self.review_id, event)

    async def on_chunk_findings(self, file: FileDiff, chunk: FileChunk, findings: list[Finding]) -> None:
        if not findings:
            return
        file_id = self.file_ids[file.filename]
        now = utcnow()
        issues = [
            Issue(
                id=new_id(),
                review_id=self.review_id,
                file_id=file_id,
                filename=file.filename,
                line_number=finding.line_number,
                end_line=finding.end_line,
                severity=finding.severity,
                category=finding.category,
                confidence=finding.confidence,
                title=finding.title,
                comment=finding.comment,
                suggested_fix=finding.suggested_fix,
                status="open",
                created_at=now,
                resolved_at=None,
            )
            for finding in findings
        ]
        async with self.runner.session_factory() as session:
            session.add_all(issues)
            await session.flush()
            event = await self.runner.record_event(
                session,
                self.review_id,
                "issues",
                {
                    "file_id": file_id,
                    "filename": file.filename,
                    "chunk": chunk.index + 1,
                    "issues": [IssueOut.model_validate(issue).model_dump(mode="json") for issue in issues],
                },
            )
            await session.commit()
        self.runner.broker.publish(self.review_id, event)

    async def on_file_finished(self, file: FileDiff, result: FileReviewResult) -> None:
        file_id = self.file_ids[file.filename]
        usage = result.usage
        async with self.runner.session_factory() as session:
            await session.execute(
                update(ReviewFile)
                .where(ReviewFile.id == file_id)
                .values(
                    state="failed" if result.error else "done",
                    summary=result.summary or None,
                    error=result.error,
                    input_tokens=usage.total_input_tokens,
                    output_tokens=usage.output_tokens,
                    cost_usd=result.cost_usd,
                )
            )
            # Files finish concurrently, so totals are incremented in SQL rather than read-modify-written.
            totals = {
                "files_done": Review.files_done + 1,
                "input_tokens": Review.input_tokens + usage.input_tokens,
                "output_tokens": Review.output_tokens + usage.output_tokens,
                "cache_creation_tokens": Review.cache_creation_tokens + usage.cache_creation_input_tokens,
                "cache_read_tokens": Review.cache_read_tokens + usage.cache_read_input_tokens,
            }
            if result.cost_usd is not None:
                totals["cost_usd"] = func.coalesce(Review.cost_usd, 0.0) + result.cost_usd
            await session.execute(update(Review).where(Review.id == self.review_id).values(**totals))
            review = await session.get(Review, self.review_id)
            event = await self.runner.record_event(
                session,
                self.review_id,
                "file.completed",
                {
                    "file_id": file_id,
                    "filename": file.filename,
                    "state": "failed" if result.error else "done",
                    "summary": result.summary or None,
                    "error": result.error,
                    "issue_count": len(result.findings),
                    "files_done": review.files_done,
                    "files_total": review.files_total,
                    "cost_usd": review.cost_usd,
                    "tokens": review.input_tokens + review.output_tokens + review.cache_read_tokens + review.cache_creation_tokens,
                },
            )
            await session.commit()
        self.runner.broker.publish(self.review_id, event)

    async def on_llm_call(self, record: LLMCallRecord) -> None:
        async with self.runner.session_factory() as session:
            session.add(
                LLMCall(
                    review_id=self.review_id,
                    filename=record.filename,
                    chunk_index=record.chunk_index,
                    attempt=record.attempt,
                    model=record.model,
                    input_tokens=record.usage.input_tokens,
                    output_tokens=record.usage.output_tokens,
                    cache_creation_tokens=record.usage.cache_creation_input_tokens,
                    cache_read_tokens=record.usage.cache_read_input_tokens,
                    cost_usd=record.cost_usd,
                    latency_ms=record.latency_ms,
                    outcome=record.outcome,
                    error=record.error,
                    created_at=utcnow(),
                )
            )
            counters = {"llm_calls": Review.llm_calls + 1}
            if record.outcome == "invalid":
                counters["invalid_outputs"] = Review.invalid_outputs + 1
            await session.execute(update(Review).where(Review.id == self.review_id).values(**counters))
            event = None
            if record.outcome == "invalid":
                event = await self.runner.record_event(
                    session,
                    self.review_id,
                    "file.retry",
                    {
                        "file_id": self.file_ids.get(record.filename),
                        "filename": record.filename,
                        "attempt": record.attempt,
                        "reason": record.error,
                    },
                )
            await session.commit()
        if event is not None:
            self.runner.broker.publish(self.review_id, event)


async def upsert_repository_from_pr(session: AsyncSession, pr: PullRequestDiff) -> Repository:
    meta = pr.metadata
    full_name = meta.repository.full_name if meta.repository else f"{meta.owner}/{meta.repo}"
    repository = await session.scalar(select(Repository).where(Repository.full_name_key == full_name.lower()))
    if repository is None:
        owner, _, name = full_name.partition("/")
        repository = Repository(
            owner=owner,
            name=name,
            full_name=full_name,
            full_name_key=full_name.lower(),
            html_url=f"https://github.com/{full_name}",
            created_at=utcnow(),
        )
        session.add(repository)
    if meta.repository is not None:
        info = meta.repository
        repository.html_url = info.html_url or repository.html_url
        repository.description = info.description
        repository.language = info.language
        repository.stars = info.stars
        repository.is_private = info.private
        repository.default_branch = info.default_branch
    await session.flush()
    return repository


async def mark_interrupted_reviews(session_factory: async_sessionmaker[AsyncSession]) -> int:
    """A review can't survive a restart (its task lived in the old process) — close it out honestly."""
    async with session_factory() as session:
        reviews = (await session.scalars(select(Review).where(Review.status.in_(REVIEW_ACTIVE_STATUSES)))).all()
        for review in reviews:
            review.status = "failed"
            review.status_message = None
            review.error = "Interrupted: the API restarted while this review was running."
            review.completed_at = utcnow()
            session.add(
                ReviewEvent(review_id=review.id, type="review.failed", payload={"error": review.error}, created_at=utcnow())
            )
        await session.commit()
        return len(reviews)


def summarize(issues: Sequence[Issue], files_reviewed: int, failed_files: int) -> str:
    if files_reviewed == 0:
        return "Nothing to review: every changed file was a lockfile, generated code, an asset, documentation or a deletion."
    reviewed = f"{files_reviewed} file{'s' if files_reviewed != 1 else ''}"
    counts = Counter(issue.severity for issue in issues)
    labels = [("critical", "critical issue", "critical issues"), ("warning", "warning", "warnings"), ("info", "suggestion", "suggestions")]
    parts = [f"{counts[key]} {one if counts[key] == 1 else many}" for key, one, many in labels if counts[key]]
    if not parts:
        text = f"No issues found across {reviewed}."
    elif len(parts) == 1:
        text = f"Found {parts[0]} across {reviewed}."
    else:
        text = f"Found {', '.join(parts[:-1])} and {parts[-1]} across {reviewed}."
    if failed_files:
        text += f" {failed_files} file{'s' if failed_files != 1 else ''} could not be reviewed."
    return text
