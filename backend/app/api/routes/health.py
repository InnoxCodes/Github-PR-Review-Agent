from dataclasses import asdict

from fastapi import APIRouter
from sqlalchemy import func, select

from app import __version__
from app.api.deps import ServicesDep, SessionDep
from app.models import Review
from app.schemas import HealthOut, LLMStatusOut

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health", response_model=HealthOut, summary="Service status and configuration")
async def health(services: ServicesDep, session: SessionDep) -> HealthOut:
    """Whether an LLM provider and GitHub token are configured — the dashboard uses this to
    explain what's missing instead of failing on the first review."""
    samples = await session.scalar(select(func.count()).select_from(Review).where(Review.is_sample.is_(True)))
    return HealthOut(
        status="ok",
        version=__version__,
        llm=LLMStatusOut(**asdict(services.llm_status())),
        github_token_configured=services.settings.github_token_value is not None,
        sample_data_loaded=bool(samples),
    )
