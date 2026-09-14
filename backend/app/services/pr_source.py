from collections.abc import Awaitable, Callable

from app.config import Settings
from app.diff.models import PullRequestDiff
from app.github.client import GitHubClient
from app.github.urls import PRRef
from app.services.pr_loader import load_pull_request

PRLoader = Callable[[PRRef, str | None], Awaitable[PullRequestDiff]]


def github_pr_loader(settings: Settings) -> PRLoader:
    async def load(ref: PRRef, token: str | None) -> PullRequestDiff:
        async with GitHubClient(
            token, base_url=settings.github_api_url, timeout=settings.github_timeout_seconds
        ) as client:
            return await load_pull_request(client, ref, settings)

    return load
