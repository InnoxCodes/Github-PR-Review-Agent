"""Loads the hand-written sample reviews into the database, shaped exactly like real ones.

Diffs are generated with difflib from before/after file contents and then run through the
real parser, classifier and chunker, and findings are anchored by locating their text in the
new file — so a sample finding that doesn't land on a real diff line fails loudly here.
Token counts and costs are estimates of what the review would plausibly have used.
"""

import difflib
import hashlib
from collections.abc import Sequence
from datetime import timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.demo.scenarios import DEMO_OWNER, SAMPLE_REPOS, SAMPLE_REVIEWS, SampleFile, SampleReview
from app.diff.chunking import chunk_file
from app.diff.models import FileDiff, LineType
from app.llm.base import TokenUsage
from app.llm.pricing import estimate_cost
from app.models import (
    LIVE_ISSUE_STATUSES,
    Issue,
    LLMCall,
    Repository,
    Review,
    ReviewEvent,
    ReviewFile,
    new_id,
    utcnow,
)
from app.review.scoring import ScoredIssue, health_score
from app.schemas import IssueOut
from app.services.pr_loader import build_file_diff
from app.services.review_runner import summarize
from app.services.views import file_fields, issue_stats, review_summary

SAMPLE_MODEL = "claude-opus-5"
SYSTEM_AND_CONTEXT_TOKENS = 2_350


class SampleDataError(ValueError):
    pass


async def load_sample_data(session_factory: async_sessionmaker[AsyncSession], settings: Settings) -> tuple[int, int]:
    await clear_sample_data(session_factory)
    async with session_factory() as session:
        repositories = {key: await _repository(session, key) for key in SAMPLE_REPOS}
        for scenario in SAMPLE_REVIEWS:
            await _create_review(session, scenario, repositories[scenario.repo], settings)
        await session.commit()
    return len(SAMPLE_REVIEWS), len(repositories)


async def clear_sample_data(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        await session.execute(delete(Review).where(Review.is_sample.is_(True)))
        demo_repos = (await session.scalars(select(Repository).where(Repository.owner == DEMO_OWNER))).all()
        for repository in demo_repos:
            remaining = await session.scalar(
                select(func.count()).select_from(Review).where(Review.repository_id == repository.id)
            )
            if not remaining:
                await session.delete(repository)
        await session.commit()


async def _repository(session: AsyncSession, key: str) -> Repository:
    full_name = f"{DEMO_OWNER}/{key}"
    repository = await session.scalar(select(Repository).where(Repository.full_name_key == full_name.lower()))
    if repository is None:
        info = SAMPLE_REPOS[key]
        repository = Repository(
            owner=DEMO_OWNER,
            name=key,
            full_name=full_name,
            full_name_key=full_name.lower(),
            html_url=f"https://github.com/{full_name}",
            description=info["description"],
            language=info["language"],
            stars=info["stars"],
            default_branch="main",
            created_at=utcnow() - timedelta(days=60),
        )
        session.add(repository)
        await session.flush()
    return repository


async def _create_review(session: AsyncSession, scenario: SampleReview, repository: Repository, settings: Settings) -> None:
    created = utcnow() - timedelta(days=scenario.days_ago)
    diffs = [(sample, build_file_diff(_file_payload(sample), settings)) for sample in scenario.files]
    reviewable = [(sample, diff) for sample, diff in diffs if diff.reviewable]
    changed_lines = sum(diff.additions + diff.deletions for _, diff in reviewable)

    review = Review(
        id=new_id(),
        repository_id=repository.id,
        owner=DEMO_OWNER,
        repo=scenario.repo,
        pr_number=scenario.number,
        pr_url=f"https://github.com/{DEMO_OWNER}/{scenario.repo}/pull/{scenario.number}",
        status="completed",
        pr_title=scenario.title,
        pr_body=scenario.body,
        pr_author=scenario.author,
        pr_state="merged" if scenario.merged else "open",
        pr_merged=scenario.merged,
        base_ref="main",
        head_ref=scenario.head_ref,
        head_sha=hashlib.sha1(f"{scenario.repo}{scenario.number}{scenario.days_ago}".encode()).hexdigest(),
        pr_created_at=created - timedelta(hours=5),
        additions=sum(diff.additions for _, diff in diffs),
        deletions=sum(diff.deletions for _, diff in diffs),
        changed_files=len(diffs),
        commits=scenario.commits,
        files_total=len(reviewable),
        files_done=len(reviewable),
        changed_lines_reviewed=changed_lines,
        provider="anthropic",
        model=SAMPLE_MODEL,
        is_sample=True,
        created_at=created,
        started_at=created,
    )
    session.add(review)

    file_rows: list[tuple[SampleFile, FileDiff, ReviewFile]] = []
    for position, (sample, diff) in enumerate(diffs):
        row = ReviewFile(
            review_id=review.id,
            position=position,
            filename=diff.filename,
            git_status=str(diff.status),
            language=diff.language,
            additions=diff.additions,
            deletions=diff.deletions,
            skip_reason=str(diff.skip_reason) if diff.skip_reason else None,
            state="done" if diff.reviewable else "skipped",
            chunk_count=len(chunk_file(diff, settings.chunk_max_lines)) if diff.reviewable else 0,
            summary=sample.summary or None if diff.reviewable else None,
            hunks=[hunk.model_dump(mode="json") for hunk in diff.hunks],
        )
        session.add(row)
        file_rows.append((sample, diff, row))
    await session.flush()

    clock = _Clock(created)
    events: list[tuple[str, dict]] = [
        ("status", {"status": "fetching", "message": "Fetching the pull request from GitHub"}),
    ]
    events.append(("pr", {"review": review_summary(review).model_dump(mode="json"), "files": [file_fields(r) for _, _, r in file_rows]}))
    events.append(
        (
            "status",
            {
                "status": "reviewing",
                "message": f"Reviewing {len(reviewable)} file{'s' if len(reviewable) != 1 else ''} with {SAMPLE_MODEL}",
                "model": SAMPLE_MODEL,
            },
        )
    )

    all_issues: list[Issue] = []
    totals = TokenUsage()
    total_cost = 0.0
    llm_calls = invalid = files_done = 0
    first_call = True

    for sample, diff, row in file_rows:
        if not diff.reviewable:
            continue
        events.append(("file.started", {"file_id": row.id, "filename": diff.filename, "chunks": row.chunk_count}))
        attempts = 2 if scenario.retry_file == diff.filename else 1
        file_usage = TokenUsage()
        for attempt in range(1, attempts + 1):
            usage = _estimated_usage(diff, len(sample.findings), cache_write=first_call)
            first_call = False
            cost = estimate_cost(SAMPLE_MODEL, usage) or 0.0
            outcome = "invalid" if attempt < attempts else "ok"
            error = (
                "The response was not valid JSON (Expecting ',' delimiter at line 14, column 3). Return only the JSON object."
                if outcome == "invalid"
                else None
            )
            session.add(
                LLMCall(
                    review_id=review.id,
                    filename=diff.filename,
                    chunk_index=0,
                    attempt=attempt,
                    model=SAMPLE_MODEL,
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    cache_creation_tokens=usage.cache_creation_input_tokens,
                    cache_read_tokens=usage.cache_read_input_tokens,
                    cost_usd=cost,
                    latency_ms=4_200 + 90 * len(sample.findings) + diff.additions * 11,
                    outcome=outcome,
                    error=error,
                    created_at=clock.tick(4),
                )
            )
            llm_calls += 1
            file_usage += usage
            total_cost += cost
            if outcome == "invalid":
                invalid += 1
                events.append(
                    ("file.retry", {"file_id": row.id, "filename": diff.filename, "attempt": attempt, "reason": error})
                )
        totals += file_usage

        issues = [_issue(review.id, row, sample, diff, index, clock) for index, _ in enumerate(sample.findings)]
        session.add_all(issues)
        await session.flush()
        all_issues.extend(issues)
        if issues:
            # Stored as they were first reported: open. Triage happened afterwards.
            payload = [IssueOut.model_validate(issue).model_dump(mode="json") | {"status": "open", "resolved_at": None} for issue in issues]
            events.append(("issues", {"file_id": row.id, "filename": diff.filename, "chunk": 1, "issues": payload}))

        files_done += 1
        row.input_tokens = file_usage.total_input_tokens
        row.output_tokens = file_usage.output_tokens
        row.cost_usd = estimate_cost(SAMPLE_MODEL, file_usage)
        events.append(
            (
                "file.completed",
                {
                    "file_id": row.id,
                    "filename": diff.filename,
                    "state": "done",
                    "summary": row.summary,
                    "error": None,
                    "issue_count": len(issues),
                    "files_done": files_done,
                    "files_total": len(reviewable),
                    "cost_usd": round(total_cost, 6),
                    "tokens": totals.total_input_tokens + totals.output_tokens,
                },
            )
        )

    scored_all = [ScoredIssue(i.severity, i.category, i.confidence) for i in all_issues]
    live = [ScoredIssue(i.severity, i.category, i.confidence) for i in all_issues if i.status in LIVE_ISSUE_STATUSES]
    review.initial_health_score = health_score(scored_all, changed_lines)
    review.health_score = health_score(live, changed_lines)
    review.summary = summarize(all_issues, len(reviewable), 0)
    review.input_tokens = totals.input_tokens
    review.output_tokens = totals.output_tokens
    review.cache_creation_tokens = totals.cache_creation_input_tokens
    review.cache_read_tokens = totals.cache_read_input_tokens
    review.cost_usd = round(total_cost, 6)
    review.llm_calls = llm_calls
    review.invalid_outputs = invalid
    review.duration_ms = int((clock.now - created).total_seconds() * 1000) + 1_800
    review.completed_at = created + timedelta(milliseconds=review.duration_ms)
    await session.flush()

    stats = (await issue_stats(session, [review.id]))[review.id]
    completed = review_summary(review, stats).model_dump(mode="json")
    completed["health_score"] = review.initial_health_score
    events.append(("review.completed", {"review": completed}))

    for event_type, payload in events:
        session.add(ReviewEvent(review_id=review.id, type=event_type, payload=payload, created_at=clock.tick(1)))


def _file_payload(sample: SampleFile) -> dict:
    if sample.skipped_size is not None:
        additions, deletions = sample.skipped_size
        patch = "@@ -1,1 +1,1 @@\n-placeholder\n+placeholder"
        return {
            "filename": sample.filename,
            "status": sample.status,
            "patch": patch,
            "additions": additions,
            "deletions": deletions,
            "changes": additions + deletions,
        }

    if sample.status == "added":
        lines = sample.after.rstrip("\n").split("\n")
        patch = f"@@ -0,0 +1,{len(lines)} @@\n" + "\n".join(f"+{line}" for line in lines)
    else:
        diff = difflib.unified_diff(
            sample.before.rstrip("\n").split("\n"), sample.after.rstrip("\n").split("\n"), lineterm="", n=3
        )
        patch = "\n".join(list(diff)[2:])

    additions = sum(1 for line in patch.split("\n") if line.startswith("+"))
    deletions = sum(1 for line in patch.split("\n") if line.startswith("-"))
    return {
        "filename": sample.filename,
        "status": sample.status,
        "patch": patch,
        "additions": additions,
        "deletions": deletions,
        "changes": additions + deletions,
    }


def _issue(review_id: str, row: ReviewFile, sample: SampleFile, diff: FileDiff, index: int, clock: "_Clock") -> Issue:
    finding = sample.findings[index]
    line_number = _locate(sample, diff, finding.anchor)
    end_line = line_number + finding.span if finding.span else None
    created = clock.tick(2)
    return Issue(
        id=new_id(),
        review_id=review_id,
        file_id=row.id,
        filename=diff.filename,
        line_number=line_number,
        end_line=end_line,
        severity=finding.severity,
        category=finding.category,
        confidence=finding.confidence,
        title=finding.title,
        comment=finding.comment,
        suggested_fix=finding.suggested_fix or None,
        status=finding.status,
        created_at=created,
        resolved_at=None if finding.status == "open" else created + timedelta(hours=3),
    )


def _locate(sample: SampleFile, diff: FileDiff, anchor: str) -> int:
    lines = sample.after.split("\n")
    matches = [number for number, text in enumerate(lines, start=1) if anchor in text]
    if not matches:
        raise SampleDataError(f"{sample.filename}: anchor {anchor!r} not found")
    anchorable = {
        line.new_line
        for hunk in diff.hunks
        for line in hunk.lines
        if line.type is not LineType.DELETE and line.new_line is not None
    }
    if matches[0] not in anchorable:
        raise SampleDataError(f"{sample.filename}: line {matches[0]} ({anchor!r}) is not part of the diff")
    return matches[0]


def _estimated_usage(diff: FileDiff, finding_count: int, *, cache_write: bool) -> TokenUsage:
    diff_lines = sum(len(hunk.lines) for hunk in diff.hunks)
    return TokenUsage(
        input_tokens=180 + diff_lines * 12,
        output_tokens=900 + finding_count * 210,
        cache_creation_input_tokens=SYSTEM_AND_CONTEXT_TOKENS if cache_write else 0,
        cache_read_input_tokens=0 if cache_write else SYSTEM_AND_CONTEXT_TOKENS,
    )


class _Clock:
    def __init__(self, start):
        self.now = start

    def tick(self, seconds: float):
        self.now = self.now + timedelta(seconds=seconds)
        return self.now


def sample_file_names() -> Sequence[str]:
    return [sample.filename for scenario in SAMPLE_REVIEWS for sample in scenario.files]
