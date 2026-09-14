import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

REVIEW_ACTIVE_STATUSES = ("queued", "fetching", "reviewing")
LIVE_ISSUE_STATUSES = ("open", "accepted")


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return uuid.uuid4().hex


class UTCDateTime(TypeDecorator):
    """Store naive UTC; always return timezone-aware UTC (SQLite has no timezone type)."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None or value.tzinfo is None:
            return value
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        return value.replace(tzinfo=UTC) if value is not None else None


class Base(DeclarativeBase):
    type_annotation_map = {datetime: UTCDateTime(), dict[str, Any]: JSON, list[Any]: JSON}


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(100))
    full_name: Mapped[str] = mapped_column(String(201))
    full_name_key: Mapped[str] = mapped_column(String(201), unique=True, index=True)
    html_url: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(60))
    stars: Mapped[int] = mapped_column(default=0)
    is_private: Mapped[bool] = mapped_column(default=False)
    default_branch: Mapped[str | None] = mapped_column(String(200))
    # Fernet ciphertext only. The plaintext token is never persisted or returned by the API.
    encrypted_token: Mapped[str | None] = mapped_column(Text)
    token_hint: Mapped[str | None] = mapped_column(String(8))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    reviews: Mapped[list["Review"]] = relationship(back_populates="repository", passive_deletes=True)


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    repository_id: Mapped[int | None] = mapped_column(ForeignKey("repositories.id", ondelete="SET NULL"), index=True)
    owner: Mapped[str] = mapped_column(String(100))
    repo: Mapped[str] = mapped_column(String(100))
    pr_number: Mapped[int]
    pr_url: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    status_message: Mapped[str | None] = mapped_column(Text)

    pr_title: Mapped[str | None] = mapped_column(Text)
    pr_body: Mapped[str | None] = mapped_column(Text)
    pr_author: Mapped[str | None] = mapped_column(String(100))
    pr_author_avatar: Mapped[str | None] = mapped_column(String(300))
    pr_state: Mapped[str | None] = mapped_column(String(20))
    pr_draft: Mapped[bool] = mapped_column(default=False)
    pr_merged: Mapped[bool] = mapped_column(default=False)
    base_ref: Mapped[str | None] = mapped_column(String(250))
    head_ref: Mapped[str | None] = mapped_column(String(250))
    head_sha: Mapped[str | None] = mapped_column(String(40))
    pr_created_at: Mapped[datetime | None]
    additions: Mapped[int] = mapped_column(default=0)
    deletions: Mapped[int] = mapped_column(default=0)
    changed_files: Mapped[int] = mapped_column(default=0)
    commits: Mapped[int] = mapped_column(default=0)

    files_total: Mapped[int] = mapped_column(default=0)
    files_done: Mapped[int] = mapped_column(default=0)
    changed_lines_reviewed: Mapped[int] = mapped_column(default=0)
    health_score: Mapped[int | None]
    initial_health_score: Mapped[int | None]
    summary: Mapped[str | None] = mapped_column(Text)

    provider: Mapped[str | None] = mapped_column(String(30))
    model: Mapped[str | None] = mapped_column(String(80))
    input_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
    cache_creation_tokens: Mapped[int] = mapped_column(default=0)
    cache_read_tokens: Mapped[int] = mapped_column(default=0)
    cost_usd: Mapped[float | None]
    llm_calls: Mapped[int] = mapped_column(default=0)
    invalid_outputs: Mapped[int] = mapped_column(default=0)

    error: Mapped[str | None] = mapped_column(Text)
    is_sample: Mapped[bool] = mapped_column(default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    started_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]
    duration_ms: Mapped[int | None]

    repository: Mapped[Repository | None] = relationship(back_populates="reviews")
    files: Mapped[list["ReviewFile"]] = relationship(
        back_populates="review", cascade="all, delete-orphan", passive_deletes=True, order_by="ReviewFile.position"
    )
    issues: Mapped[list["Issue"]] = relationship(back_populates="review", cascade="all, delete-orphan", passive_deletes=True)


class ReviewFile(Base):
    __tablename__ = "review_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    review_id: Mapped[str] = mapped_column(ForeignKey("reviews.id", ondelete="CASCADE"), index=True)
    position: Mapped[int]
    filename: Mapped[str] = mapped_column(Text)
    previous_filename: Mapped[str | None] = mapped_column(Text)
    git_status: Mapped[str] = mapped_column(String(20))
    language: Mapped[str] = mapped_column(String(40))
    additions: Mapped[int] = mapped_column(default=0)
    deletions: Mapped[int] = mapped_column(default=0)
    skip_reason: Mapped[str | None] = mapped_column(String(30))
    # pending -> reviewing -> done | failed; skipped files never leave "skipped".
    state: Mapped[str] = mapped_column(String(20), default="pending")
    chunk_count: Mapped[int] = mapped_column(default=0)
    summary: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    hunks: Mapped[list[Any]] = mapped_column(default=list)
    input_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
    cost_usd: Mapped[float | None]

    review: Mapped[Review] = relationship(back_populates="files")


class Issue(Base):
    __tablename__ = "issues"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    review_id: Mapped[str] = mapped_column(ForeignKey("reviews.id", ondelete="CASCADE"), index=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("review_files.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(Text)
    line_number: Mapped[int]
    end_line: Mapped[int | None]
    severity: Mapped[str] = mapped_column(String(10), index=True)
    category: Mapped[str] = mapped_column(String(20), index=True)
    confidence: Mapped[str] = mapped_column(String(10), default="medium")
    title: Mapped[str] = mapped_column(Text)
    comment: Mapped[str] = mapped_column(Text)
    suggested_fix: Mapped[str | None] = mapped_column(Text)
    # open | accepted | dismissed | false_positive — the feedback signal for improving the reviewer.
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    resolved_at: Mapped[datetime | None]

    review: Mapped[Review] = relationship(back_populates="issues")


class ReviewEvent(Base):
    """Append-only log of everything streamed for a review; its id doubles as the SSE event id."""

    __tablename__ = "review_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    review_id: Mapped[str] = mapped_column(ForeignKey("reviews.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict[str, Any]] = mapped_column(default=dict)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class LLMCall(Base):
    __tablename__ = "llm_calls"

    id: Mapped[int] = mapped_column(primary_key=True)
    review_id: Mapped[str] = mapped_column(ForeignKey("reviews.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(Text)
    chunk_index: Mapped[int]
    attempt: Mapped[int]
    model: Mapped[str] = mapped_column(String(80))
    input_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
    cache_creation_tokens: Mapped[int] = mapped_column(default=0)
    cache_read_tokens: Mapped[int] = mapped_column(default=0)
    cost_usd: Mapped[float | None]
    latency_ms: Mapped[int] = mapped_column(default=0)
    outcome: Mapped[str] = mapped_column(String(10))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
