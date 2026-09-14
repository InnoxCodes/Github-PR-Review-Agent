"""Request and response models for the HTTP API (these drive the Swagger docs)."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.diff.models import Hunk

IssueStatus = Literal["open", "accepted", "dismissed", "false_positive"]
ReviewStatus = Literal["queued", "fetching", "reviewing", "completed", "failed"]
FileState = Literal["pending", "reviewing", "done", "failed", "skipped"]
Grade = Literal["healthy", "needs_attention", "at_risk"]


class ReviewCreate(BaseModel):
    pr_url: str = Field(
        description="A pull request URL, or the owner/repo#number shorthand.",
        examples=["https://github.com/sindresorhus/ky/pull/880"],
    )


class RepositoryCreate(BaseModel):
    repository: str = Field(description="owner/name or a github.com repository URL.", examples=["encode/httpx"])
    github_token: SecretStr | None = Field(
        default=None,
        description="Optional token for private repositories. Encrypted at rest and never returned by the API.",
    )


class IssueUpdate(BaseModel):
    status: IssueStatus = Field(description="The developer's verdict on this finding.")


class SeverityCounts(BaseModel):
    critical: int = 0
    warning: int = 0
    info: int = 0


class IssueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    review_id: str
    file_id: int
    filename: str
    line_number: int
    end_line: int | None
    severity: Literal["critical", "warning", "info"]
    category: str
    confidence: str
    title: str
    comment: str
    suggested_fix: str | None
    status: IssueStatus
    created_at: datetime
    resolved_at: datetime | None


class ReviewFileOut(BaseModel):
    id: int
    filename: str
    previous_filename: str | None
    git_status: str
    language: str
    additions: int
    deletions: int
    skip_reason: str | None
    state: FileState
    chunk_count: int
    summary: str | None
    error: str | None
    issue_count: int = 0
    cost_usd: float | None = None


class ReviewFileDetail(ReviewFileOut):
    hunks: list[Hunk]


class ReviewSummary(BaseModel):
    id: str
    status: ReviewStatus
    status_message: str | None
    pr_url: str
    owner: str
    repo: str
    pr_number: int
    pr_title: str | None
    pr_author: str | None
    pr_author_avatar: str | None
    base_ref: str | None
    head_ref: str | None
    health_score: int | None
    grade: Grade | None
    issue_counts: SeverityCounts = Field(description="Live findings (open or accepted) by severity.")
    issues_total: int
    open_issues: int
    files_total: int
    files_done: int
    additions: int
    deletions: int
    model: str | None
    cost_usd: float | None
    is_sample: bool
    error: str | None
    created_at: datetime
    completed_at: datetime | None
    duration_ms: int | None


class TokenTotals(BaseModel):
    input_tokens: int
    output_tokens: int
    cache_creation_tokens: int
    cache_read_tokens: int


class ReviewDetail(ReviewSummary):
    pr_body: str | None
    pr_state: str | None
    pr_draft: bool
    pr_merged: bool
    head_sha: str | None
    changed_files: int
    commits: int
    summary: str | None
    provider: str | None
    initial_health_score: int | None
    tokens: TokenTotals
    llm_calls: int
    invalid_outputs: int = Field(description="LLM responses rejected by validation and retried.")
    files: list[ReviewFileDetail]
    issues: list[IssueOut]


class IssueUpdateResult(BaseModel):
    issue: IssueOut
    health_score: int | None
    grade: Grade | None
    issue_counts: SeverityCounts
    open_issues: int


class RepositoryOut(BaseModel):
    id: int
    owner: str
    name: str
    full_name: str
    html_url: str
    description: str | None
    language: str | None
    stars: int
    is_private: bool
    default_branch: str | None
    has_token: bool
    token_hint: str | None = Field(description="Last four characters of the stored token, if any.")
    created_at: datetime
    review_count: int
    last_reviewed_at: datetime | None
    average_health_score: float | None
    open_issues: int
    score_history: list[int] = Field(description="Health scores of the most recent reviews, oldest first.")
    issue_history: list[int] = Field(description="Findings per review for the same reviews, oldest first.")


class LLMStatusOut(BaseModel):
    configured: bool
    provider: str | None
    model: str | None
    message: str


class HealthOut(BaseModel):
    status: Literal["ok"]
    version: str
    llm: LLMStatusOut
    github_token_configured: bool
    sample_data_loaded: bool


class ScorePoint(BaseModel):
    review_id: str
    label: str
    title: str | None
    date: datetime
    score: int


class CategoryBreakdown(BaseModel):
    category: str
    total: int
    critical: int
    warning: int
    info: int
    open: int
    accepted: int
    dismissed: int
    false_positive: int


class WeeklyIssues(BaseModel):
    week_start: date
    reviews: int
    counts: dict[str, int]


class AnalyticsTotals(BaseModel):
    prs_reviewed: int
    files_reviewed: int
    issues_found: int
    open_issues: int
    accepted: int
    dismissed: int
    false_positives: int


class AnalyticsSummary(BaseModel):
    days: int
    totals: AnalyticsTotals
    severity_counts: SeverityCounts
    false_positive_rate: float | None = Field(description="False positives / all triaged findings.")
    acceptance_rate: float | None
    average_health_score: float | None
    minutes_saved: float
    minutes_per_file: float = Field(description="The manual-review assumption behind minutes_saved.")
    total_cost_usd: float | None
    total_tokens: int
    average_review_seconds: float | None
    score_trend: list[ScorePoint]
    categories: list[CategoryBreakdown]
    weekly: list[WeeklyIssues]


class SampleDataResult(BaseModel):
    reviews: int
    repositories: int
