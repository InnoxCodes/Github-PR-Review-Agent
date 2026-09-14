import logging
from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import analytics, demo, health, repos, reviews, webhooks
from app.config import Settings, get_settings
from app.db import create_db_engine, create_session_factory, init_db
from app.events import EventBroker
from app.github.client import GitHubClient
from app.llm.base import LLMProvider
from app.llm.factory import LLMStatus, build_provider, llm_status
from app.security import TokenCipher, load_or_create_key
from app.services.container import Services
from app.services.pr_source import PRLoader, github_pr_loader
from app.services.review_runner import ReviewRunner, mark_interrupted_reviews

logger = logging.getLogger("reviewmind")

DESCRIPTION = """
AI pull-request reviewer. ReviewMind fetches a PR's diff from GitHub, reviews it chunk by
chunk with an LLM constrained to structured output, and streams line-anchored findings
to the dashboard as they're produced.

**Typical flow**

1. `POST /api/reviews` with a PR URL — returns the review id immediately.
2. `GET /api/reviews/{id}/stream` — Server-Sent Events while the review runs.
3. `GET /api/reviews/{id}` — files, diffs, findings, health score and cost.
4. `PATCH /api/reviews/{id}/issues/{issue_id}` — accept, dismiss or flag findings.
"""

TAGS = [
    {"name": "reviews", "description": "Start reviews, stream progress and triage findings."},
    {"name": "repositories", "description": "Tracked repositories, with optional encrypted access tokens."},
    {"name": "analytics", "description": "Aggregate statistics and triage feedback across reviews."},
    {"name": "github", "description": "Webhook receiver for automatic reviews."},
    {"name": "system", "description": "Health and configuration."},
]


def create_app(
    settings: Settings | None = None,
    *,
    provider_factory: Callable[[Settings], LLMProvider] | None = None,
    pr_loader: PRLoader | None = None,
    llm_status_fn: Callable[[], LLMStatus] | None = None,
    github_factory: Callable[[str | None], GitHubClient] | None = None,
) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = create_db_engine(settings.database_url)
        await init_db(engine)
        session_factory = create_session_factory(engine)
        if interrupted := await mark_interrupted_reviews(session_factory):
            logger.warning("Marked %d review(s) interrupted by a restart as failed", interrupted)

        broker = EventBroker()
        cipher = TokenCipher(load_or_create_key(settings))
        runner = ReviewRunner(
            settings=settings,
            session_factory=session_factory,
            broker=broker,
            cipher=cipher,
            provider_factory=provider_factory or build_provider,
            pr_loader=pr_loader or github_pr_loader(settings),
        )
        app.state.services = Services(
            settings=settings,
            session_factory=session_factory,
            broker=broker,
            cipher=cipher,
            runner=runner,
            llm_status=llm_status_fn or (lambda: llm_status(settings)),
            github=github_factory
            or (lambda token: GitHubClient(token, base_url=settings.github_api_url, timeout=settings.github_timeout_seconds)),
        )
        try:
            yield
        finally:
            await runner.shutdown()
            await engine.dispose()

    app = FastAPI(
        title="ReviewMind API",
        version=__version__,
        description=DESCRIPTION,
        openapi_tags=TAGS,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["*"],
    )
    for module in (reviews, repos, analytics, webhooks, health, demo):
        app.include_router(module.router)
    return app


app = create_app()
