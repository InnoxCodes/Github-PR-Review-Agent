from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.events import EventBroker
from app.github.client import GitHubClient
from app.llm.factory import LLMStatus
from app.security import TokenCipher
from app.services.review_runner import ReviewRunner


@dataclass
class Services:
    settings: Settings
    session_factory: async_sessionmaker[AsyncSession]
    broker: EventBroker
    cipher: TokenCipher
    runner: ReviewRunner
    llm_status: Callable[[], LLMStatus]
    github: Callable[[str | None], GitHubClient]
