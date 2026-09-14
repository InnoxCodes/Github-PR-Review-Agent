"""Read-side helpers that turn ORM rows into API response models."""

from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.diff.models import Hunk
from app.models import LIVE_ISSUE_STATUSES, Issue, Repository, Review, ReviewFile
from app.review.scoring import grade
from app.schemas import (
    IssueOut,
    RepositoryOut,
    ReviewDetail,
    ReviewFileDetail,
    ReviewSummary,
    SeverityCounts,
    TokenTotals,
)


@dataclass
class IssueStats:
    counts: SeverityCounts = field(default_factory=SeverityCounts)
    total: int = 0
    open: int = 0


async def issue_stats(session: AsyncSession, review_ids: list[str]) -> dict[str, IssueStats]:
    stats = {review_id: IssueStats() for review_id in review_ids}
    if not review_ids:
        return stats
    rows = await session.execute(
        select(Issue.review_id, Issue.severity, Issue.status, func.count())
        .where(Issue.review_id.in_(review_ids))
        .group_by(Issue.review_id, Issue.severity, Issue.status)
    )
    for review_id, severity, status, count in rows:
        entry = stats[review_id]
        entry.total += count
        if status in LIVE_ISSUE_STATUSES and hasattr(entry.counts, severity):
            setattr(entry.counts, severity, getattr(entry.counts, severity) + count)
        if status == "open":
            entry.open += count
    return stats


def review_summary(review: Review, stats: IssueStats | None = None) -> ReviewSummary:
    stats = stats or IssueStats()
    return ReviewSummary(**_summary_fields(review, stats))


async def review_detail(session: AsyncSession, review: Review) -> ReviewDetail:
    files = (
        await session.scalars(select(ReviewFile).where(ReviewFile.review_id == review.id).order_by(ReviewFile.position))
    ).all()
    issues = (await session.scalars(select(Issue).where(Issue.review_id == review.id))).all()
    stats = (await issue_stats(session, [review.id]))[review.id]

    position = {file.id: file.position for file in files}
    issues = sorted(issues, key=lambda issue: (position.get(issue.file_id, 0), issue.line_number))
    per_file: dict[int, int] = defaultdict(int)
    for issue in issues:
        per_file[issue.file_id] += 1

    return ReviewDetail(
        **_summary_fields(review, stats),
        pr_body=review.pr_body,
        pr_state=review.pr_state,
        pr_draft=review.pr_draft,
        pr_merged=review.pr_merged,
        head_sha=review.head_sha,
        changed_files=review.changed_files,
        commits=review.commits,
        summary=review.summary,
        provider=review.provider,
        initial_health_score=review.initial_health_score,
        tokens=TokenTotals(
            input_tokens=review.input_tokens,
            output_tokens=review.output_tokens,
            cache_creation_tokens=review.cache_creation_tokens,
            cache_read_tokens=review.cache_read_tokens,
        ),
        llm_calls=review.llm_calls,
        invalid_outputs=review.invalid_outputs,
        files=[
            ReviewFileDetail(**file_fields(file), issue_count=per_file[file.id], hunks=[Hunk.model_validate(h) for h in file.hunks])
            for file in files
        ],
        issues=[IssueOut.model_validate(issue) for issue in issues],
    )


def file_fields(file: ReviewFile) -> dict:
    return {
        "id": file.id,
        "filename": file.filename,
        "previous_filename": file.previous_filename,
        "git_status": file.git_status,
        "language": file.language,
        "additions": file.additions,
        "deletions": file.deletions,
        "skip_reason": file.skip_reason,
        "state": file.state,
        "chunk_count": file.chunk_count,
        "summary": file.summary,
        "error": file.error,
        "cost_usd": file.cost_usd,
    }


async def repositories_with_stats(session: AsyncSession, repositories: list[Repository]) -> list[RepositoryOut]:
    ids = [repo.id for repo in repositories]
    reviews = []
    if ids:
        reviews = (
            await session.scalars(
                select(Review)
                .where(Review.repository_id.in_(ids), Review.status == "completed")
                .order_by(Review.created_at)
            )
        ).all()
    stats = await issue_stats(session, [review.id for review in reviews])
    grouped: dict[int, list[Review]] = defaultdict(list)
    for review in reviews:
        grouped[review.repository_id].append(review)

    results = []
    for repo in repositories:
        history = grouped[repo.id]
        scores = [review.health_score for review in history if review.health_score is not None]
        results.append(
            RepositoryOut(
                id=repo.id,
                owner=repo.owner,
                name=repo.name,
                full_name=repo.full_name,
                html_url=repo.html_url,
                description=repo.description,
                language=repo.language,
                stars=repo.stars,
                is_private=repo.is_private,
                default_branch=repo.default_branch,
                has_token=repo.encrypted_token is not None,
                token_hint=repo.token_hint,
                created_at=repo.created_at,
                review_count=len(history),
                last_reviewed_at=history[-1].created_at if history else None,
                average_health_score=round(sum(scores) / len(scores), 1) if scores else None,
                open_issues=sum(stats[review.id].open for review in history),
                score_history=scores[-12:],
                issue_history=[stats[review.id].total for review in history][-12:],
            )
        )
    return results


def _summary_fields(review: Review, stats: IssueStats) -> dict:
    return {
        "id": review.id,
        "status": review.status,
        "status_message": review.status_message,
        "pr_url": review.pr_url,
        "owner": review.owner,
        "repo": review.repo,
        "pr_number": review.pr_number,
        "pr_title": review.pr_title,
        "pr_author": review.pr_author,
        "pr_author_avatar": review.pr_author_avatar,
        "base_ref": review.base_ref,
        "head_ref": review.head_ref,
        "health_score": review.health_score,
        "grade": grade(review.health_score),
        "issue_counts": stats.counts,
        "issues_total": stats.total,
        "open_issues": stats.open,
        "files_total": review.files_total,
        "files_done": review.files_done,
        "additions": review.additions,
        "deletions": review.deletions,
        "model": review.model,
        "cost_usd": review.cost_usd,
        "is_sample": review.is_sample,
        "error": review.error,
        "created_at": review.created_at,
        "completed_at": review.completed_at,
        "duration_ms": review.duration_ms,
    }
