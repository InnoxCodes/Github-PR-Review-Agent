import asyncio
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ServicesDep, SessionDep
from app.events import TERMINAL_EVENTS, format_sse
from app.github.urls import InvalidPRReference, InvalidRepoReference, parse_pr_reference, parse_repo_reference
from app.models import LIVE_ISSUE_STATUSES, REVIEW_ACTIVE_STATUSES, Issue, Review, ReviewEvent, utcnow
from app.review.scoring import ScoredIssue, grade, health_score
from app.schemas import (
    IssueOut,
    IssueUpdate,
    IssueUpdateResult,
    ReviewCreate,
    ReviewDetail,
    ReviewStatus,
    ReviewSummary,
)
from app.services.review_service import start_review
from app.services.views import issue_stats, review_detail, review_summary

router = APIRouter(prefix="/api/reviews", tags=["reviews"])

KEEPALIVE_SECONDS = 15.0
# Pacing for ?replay=true, so a finished review can be watched building up again.
REPLAY_DELAYS = {
    "status": 0.4,
    "pr": 0.7,
    "file.started": 0.35,
    "file.retry": 0.6,
    "issues": 0.6,
    "file.completed": 0.4,
    "review.completed": 0.6,
    "review.failed": 0.6,
}


@router.post(
    "",
    status_code=202,
    response_model=ReviewSummary,
    summary="Start reviewing a pull request",
    responses={422: {"description": "Not a pull request reference"}, 503: {"description": "No LLM provider configured"}},
)
async def create_review(body: ReviewCreate, services: ServicesDep, session: SessionDep) -> ReviewSummary:
    """Queues a review and returns at once; follow it on `GET /api/reviews/{id}/stream`.
    If this PR is already being reviewed, the running review is returned instead."""
    try:
        ref = parse_pr_reference(body.pr_url)
    except InvalidPRReference as exc:
        raise HTTPException(422, str(exc)) from exc

    llm = services.llm_status()
    if not llm.configured:
        raise HTTPException(503, llm.message)

    review, _ = await start_review(session, services, ref)
    stats = await issue_stats(session, [review.id])
    return review_summary(review, stats[review.id])


@router.get("", response_model=list[ReviewSummary], summary="List reviews, newest first")
async def list_reviews(
    session: SessionDep,
    repository: Annotated[str | None, Query(description="Only reviews of this owner/name")] = None,
    status: Annotated[ReviewStatus | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[ReviewSummary]:
    query = select(Review).order_by(Review.created_at.desc()).limit(limit)
    if repository:
        try:
            owner, name = parse_repo_reference(repository)
        except InvalidRepoReference as exc:
            raise HTTPException(422, str(exc)) from exc
        query = query.where(func.lower(Review.owner) == owner.lower(), func.lower(Review.repo) == name.lower())
    if status:
        query = query.where(Review.status == status)

    reviews = (await session.scalars(query)).all()
    stats = await issue_stats(session, [review.id for review in reviews])
    return [review_summary(review, stats[review.id]) for review in reviews]


@router.get("/{review_id}", response_model=ReviewDetail, summary="Full review: file diffs, findings, score and cost")
async def get_review(review_id: str, session: SessionDep) -> ReviewDetail:
    return await review_detail(session, await _review_or_404(session, review_id))


@router.delete("/{review_id}", status_code=204, summary="Delete a review and its findings")
async def delete_review(review_id: str, services: ServicesDep, session: SessionDep) -> Response:
    review = await _review_or_404(session, review_id)
    if services.runner.is_running(review_id):
        raise HTTPException(409, "This review is still running.")
    await session.delete(review)
    await session.commit()
    return Response(status_code=204)


@router.get(
    "/{review_id}/stream",
    summary="Stream review progress as Server-Sent Events",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}, "description": "An SSE stream"}},
)
async def stream_review(
    review_id: str,
    request: Request,
    services: ServicesDep,
    replay: Annotated[bool, Query(description="Re-play a finished review at a watchable pace")] = False,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    """Event types, in order: `status`, `pr`, then per file `file.started`, `issues`
    (possibly several), `file.retry` (when output failed validation), `file.completed`, and
    finally `review.completed` or `review.failed`.

    Every event is stored before it is sent, so a client that connects late — or reconnects
    with `Last-Event-ID`, which browsers' EventSource does automatically — first receives
    everything it missed, then live events."""
    async with services.session_factory() as session:
        await _review_or_404(session, review_id)

    after = int(last_event_id) if last_event_id and last_event_id.isdigit() else 0
    # Subscribe before reading the log: anything published in between is queued, not lost.
    queue = None if replay else services.broker.subscribe(review_id)

    async def events():
        try:
            last_id = after
            async with services.session_factory() as session:
                stored = (
                    await session.scalars(
                        select(ReviewEvent)
                        .where(ReviewEvent.review_id == review_id, ReviewEvent.id > after)
                        .order_by(ReviewEvent.id)
                    )
                ).all()
                current_status = await session.scalar(select(Review.status).where(Review.id == review_id))

            for event in stored:
                if replay:
                    await asyncio.sleep(REPLAY_DELAYS.get(event.type, 0.35))
                yield format_sse(event.id, event.type, event.payload)
                last_id = event.id
                if event.type in TERMINAL_EVENTS:
                    return

            if queue is None or current_status not in REVIEW_ACTIVE_STATUSES:
                return

            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_SECONDS)
                except TimeoutError:
                    if await request.is_disconnected():
                        return
                    yield ": keep-alive\n\n"
                    continue
                if event["id"] <= last_id:
                    continue
                yield format_sse(event["id"], event["type"], event["data"])
                last_id = event["id"]
                if event["type"] in TERMINAL_EVENTS:
                    return
        finally:
            if queue is not None:
                services.broker.unsubscribe(review_id, queue)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.patch(
    "/{review_id}/issues/{issue_id}",
    response_model=IssueUpdateResult,
    summary="Accept, dismiss or flag a finding as a false positive",
)
async def update_issue(review_id: str, issue_id: str, body: IssueUpdate, session: SessionDep) -> IssueUpdateResult:
    """Records the developer's verdict and recomputes the health score from findings that
    are still live (open or accepted). These verdicts are the labelled data you would use
    to measure and tune the reviewer's precision over time."""
    issue = await session.get(Issue, issue_id)
    if issue is None or issue.review_id != review_id:
        raise HTTPException(404, "Issue not found.")
    review = await _review_or_404(session, review_id)

    issue.status = body.status
    issue.resolved_at = None if body.status == "open" else utcnow()
    await session.flush()

    if review.health_score is not None:
        live = (
            await session.scalars(
                select(Issue).where(Issue.review_id == review_id, Issue.status.in_(LIVE_ISSUE_STATUSES))
            )
        ).all()
        review.health_score = health_score(
            [ScoredIssue(item.severity, item.category, item.confidence) for item in live],
            review.changed_lines_reviewed,
        )
    await session.commit()

    stats = (await issue_stats(session, [review_id]))[review_id]
    return IssueUpdateResult(
        issue=IssueOut.model_validate(issue),
        health_score=review.health_score,
        grade=grade(review.health_score),
        issue_counts=stats.counts,
        open_issues=stats.open,
    )


async def _review_or_404(session: AsyncSession, review_id: str) -> Review:
    review = await session.get(Review, review_id)
    if review is None:
        raise HTTPException(404, "Review not found.")
    return review
