from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, computed_field


class LineType(StrEnum):
    ADD = "add"
    DELETE = "delete"
    CONTEXT = "context"


class DiffLine(BaseModel):
    type: LineType
    content: str
    # Exactly one side is None for adds/deletes; context lines carry both numbers.
    # Review comments anchor to new_line, which is what GitHub's review API uses too.
    old_line: int | None = None
    new_line: int | None = None


class Hunk(BaseModel):
    old_start: int
    old_lines: int
    new_start: int
    new_lines: int
    section: str = ""
    lines: list[DiffLine] = Field(default_factory=list)

    @property
    def header(self) -> str:
        section = f" {self.section}" if self.section else ""
        return f"@@ -{self.old_start},{self.old_lines} +{self.new_start},{self.new_lines} @@{section}"


class FileStatus(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    RENAMED = "renamed"
    COPIED = "copied"
    CHANGED = "changed"
    UNCHANGED = "unchanged"


class SkipReason(StrEnum):
    LOCKFILE = "lockfile"
    GENERATED = "generated"
    VENDORED = "vendored"
    ASSET = "asset"
    DOCS = "docs"
    DELETED = "deleted"
    NO_CHANGES = "no_changes"
    NO_PATCH = "no_patch"
    TOO_LARGE = "too_large"
    UNPARSEABLE = "unparseable"
    FILE_LIMIT = "file_limit"


class FileDiff(BaseModel):
    filename: str
    previous_filename: str | None = None
    status: FileStatus
    language: str
    additions: int
    deletions: int
    hunks: list[Hunk] = Field(default_factory=list)
    skip_reason: SkipReason | None = None

    @computed_field
    @property
    def reviewable(self) -> bool:
        return self.skip_reason is None


class FileChunk(BaseModel):
    filename: str
    language: str
    index: int
    total: int
    hunks: list[Hunk]


class PRAuthor(BaseModel):
    login: str
    avatar_url: str | None = None
    html_url: str | None = None


class PRMetadata(BaseModel):
    owner: str
    repo: str
    number: int
    title: str
    body: str
    author: PRAuthor
    state: str
    draft: bool
    merged: bool
    base_ref: str
    head_ref: str
    base_sha: str
    head_sha: str
    html_url: str
    created_at: datetime
    updated_at: datetime
    additions: int
    deletions: int
    changed_files: int
    commits: int


class PullRequestDiff(BaseModel):
    metadata: PRMetadata
    files: list[FileDiff]

    @property
    def reviewable_files(self) -> list[FileDiff]:
        return [f for f in self.files if f.reviewable]

    @property
    def skipped_files(self) -> list[FileDiff]:
        return [f for f in self.files if not f.reviewable]
