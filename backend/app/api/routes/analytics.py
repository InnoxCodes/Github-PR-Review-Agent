from collections import Counter
from datetime import date, datetime, timedelta
from statistics import mean
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import ServicesDep, SessionDep
from app.models import Issue, Review, ReviewFile, utcnow
from app.review.schema import CATEGORIES
from app.schemas import (
    AnalyticsSummary,
    AnalyticsTotals,
    CategoryBreakdown,
    ScorePoint,
    SeverityCounts,
    WeeklyIssues,
)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

MAX_WEEKS = 26


@router.get("/summary", response_model=AnalyticsSummary, summary="Aggregate statistics across completed reviews")
async def analytics_summary(
    services: ServicesDep,
    session: SessionDep,
    days: Annotated[int, Query(ge=1, le=3650, description="Look-back window in days")] = 90,
) -> AnalyticsSummary:
    """Totals, health-score trend, findings by category and week, and the triage feedback
    that measures precision: the false-positive rate is false positives over all findings
    a developer has triaged (accepted, dismissed or flagged)."""
    since = utcnow() - timedelta(days=days)
    reviews = (
        await session.scalars(
            select(Review).where(Review.status == "completed", Review.created_at >= since).order_by(Review.created_at)
        )
    ).all()
    review_ids = [review.id for review in reviews]
    issues = []
    files_reviewed = 0
    if review_ids:
        issues = (await session.scalars(select(Issue).where(Issue.review_id.in_(review_ids)))).all()
        files_reviewed = await session.scalar(
            select(func.count())
            .select_from(ReviewFile)
            .where(ReviewFile.review_id.in_(review_ids), ReviewFile.state == "done")
        ) or 0

    by_status = Counter(issue.status for issue in issues)
    by_severity = Counter(issue.severity for issue in issues)
    triaged = by_status["accepted"] + by_status["dismissed"] + by_status["false_positive"]

    categories = []
    for category in CATEGORIES:
        subset = [issue for issue in issues if issue.category == category]
        severity = Counter(issue.severity for issue in subset)
        status = Counter(issue.status for issue in subset)
        categories.append(
            CategoryBreakdown(
                category=category,
                total=len(subset),
                critical=severity["critical"],
                warning=severity["warning"],
                info=severity["info"],
                open=status["open"],
                accepted=status["accepted"],
                dismissed=status["dismissed"],
                false_positive=status["false_positive"],
            )
        )

    weeks = _week_range([review.created_at for review in reviews])
    weekly = {week: WeeklyIssues(week_start=week, reviews=0, counts={c: 0 for c in CATEGORIES}) for week in weeks}
    review_week = {review.id: _week_start(review.created_at) for review in reviews}
    for review in reviews:
        if bucket := weekly.get(review_week[review.id]):
            bucket.reviews += 1
    for issue in issues:
        bucket = weekly.get(review_week[issue.review_id])
        if bucket is not None and issue.category in bucket.counts:
            bucket.counts[issue.category] += 1

    scores = [review.health_score for review in reviews if review.health_score is not None]
    costs = [review.cost_usd for review in reviews if review.cost_usd is not None]
    durations = [review.duration_ms for review in reviews if review.duration_ms]
    minutes_per_file = services.settings.minutes_per_file_manual_review

    return AnalyticsSummary(
        days=days,
        totals=AnalyticsTotals(
            prs_reviewed=len(reviews),
            files_reviewed=files_reviewed,
            issues_found=len(issues),
            open_issues=by_status["open"],
            accepted=by_status["accepted"],
            dismissed=by_status["dismissed"],
            false_positives=by_status["false_positive"],
        ),
        severity_counts=SeverityCounts(
            critical=by_severity["critical"], warning=by_severity["warning"], info=by_severity["info"]
        ),
        false_positive_rate=round(by_status["false_positive"] / triaged, 4) if triaged else None,
        acceptance_rate=round(by_status["accepted"] / triaged, 4) if triaged else None,
        average_health_score=round(mean(scores), 1) if scores else None,
        minutes_saved=round(files_reviewed * minutes_per_file, 1),
        minutes_per_file=minutes_per_file,
        total_cost_usd=round(sum(costs), 4) if costs else None,
        total_tokens=sum(
            review.input_tokens + review.output_tokens + review.cache_read_tokens + review.cache_creation_tokens
            for review in reviews
        ),
        average_review_seconds=round(mean(durations) / 1000, 1) if durations else None,
        score_trend=[
            ScorePoint(
                review_id=review.id,
                label=f"{review.repo}#{review.pr_number}",
                title=review.pr_title,
                date=review.created_at,
                score=review.health_score,
            )
            for review in reviews
            if review.health_score is not None
        ],
        categories=categories,
        weekly=[weekly[week] for week in weeks],
    )


def _week_start(moment: datetime) -> date:
    day = moment.date()
    return day - timedelta(days=day.weekday())


def _week_range(moments: list[datetime]) -> list[date]:
    if not moments:
        return []
    current, end = _week_start(min(moments)), _week_start(utcnow())
    weeks = []
    while current <= end:
        weeks.append(current)
        current += timedelta(days=7)
    return weeks[-MAX_WEEKS:]
