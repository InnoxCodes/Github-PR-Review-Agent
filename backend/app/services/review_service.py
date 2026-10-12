from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.github.urls import PRRef
from app.models import REVIEW_ACTIVE_STATUSES, Repository, Review, new_id, utcnow
from app.services.container import Services


async def start_review(session: AsyncSession, services: Services, ref: PRRef) -> tuple[Review, bool]:
    """Create and launch a review, or return the one already running for this PR, so a
    double-click or a webhook redelivery never pays for the same review twice."""
    running = await session.scalar(
        select(Review)
        .where(
            func.lower(Review.owner) == ref.owner.lower(),
            func.lower(Review.repo) == ref.repo.lower(),
            Review.pr_number == ref.number,
            Review.status.in_(REVIEW_ACTIVE_STATUSES),
        )
        .order_by(Review.created_at.desc())
        .limit(1)
    )
    if running is not None:
        return running, False

    status = services.llm_status()
    repository = await session.scalar(select(Repository).where(Repository.full_name_key == ref.full_name.lower()))
    review = Review(
        id=new_id(),
        owner=ref.owner,
        repo=ref.repo,
        pr_number=ref.number,
        pr_url=ref.html_url,
        repository_id=repository.id if repository else None,
        status="queued",
        status_message="Queued",
        provider=status.provider,
        model=status.model,
        created_at=utcnow(),
    )
    session.add(review)
    await session.commit()
    await session.refresh(review)
    services.runner.start(review.id)
    return review, True
