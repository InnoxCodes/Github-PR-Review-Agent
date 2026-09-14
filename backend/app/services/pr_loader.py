import asyncio
from typing import Any

from app.config import Settings
from app.diff.classify import classify_path, detect_language
from app.diff.models import (
    FileDiff,
    FileStatus,
    Hunk,
    PRAuthor,
    PRMetadata,
    PRRepository,
    PullRequestDiff,
    SkipReason,
)
from app.diff.parser import DiffParseError, parse_patch
from app.github.client import GitHubClient
from app.github.urls import PRRef


async def load_pull_request(client: GitHubClient, ref: PRRef, settings: Settings) -> PullRequestDiff:
    pr_data, files_data = await asyncio.gather(
        client.get_pull_request(ref.owner, ref.repo, ref.number),
        client.list_pull_request_files(ref.owner, ref.repo, ref.number),
    )
    files = [build_file_diff(item, settings) for item in files_data]
    _enforce_file_limit(files, settings.max_reviewable_files)
    return PullRequestDiff(metadata=build_metadata(ref, pr_data), files=files)


def build_metadata(ref: PRRef, data: dict[str, Any]) -> PRMetadata:
    base_repo = data["base"].get("repo") or {}
    user = data.get("user") or {}
    owner = (base_repo.get("owner") or {}).get("login", ref.owner)
    repo = base_repo.get("name", ref.repo)
    return PRMetadata(
        owner=owner,
        repo=repo,
        repository=PRRepository(
            full_name=base_repo.get("full_name") or f"{owner}/{repo}",
            html_url=base_repo.get("html_url"),
            description=base_repo.get("description"),
            language=base_repo.get("language"),
            stars=base_repo.get("stargazers_count") or 0,
            private=bool(base_repo.get("private")),
            default_branch=base_repo.get("default_branch"),
        ),
        number=data["number"],
        title=data["title"],
        body=data.get("body") or "",
        author=PRAuthor(
            login=user.get("login", "ghost"),
            avatar_url=user.get("avatar_url"),
            html_url=user.get("html_url"),
        ),
        state=data["state"],
        draft=data.get("draft", False),
        merged=data.get("merged", False),
        base_ref=data["base"]["ref"],
        head_ref=data["head"]["ref"],
        base_sha=data["base"]["sha"],
        head_sha=data["head"]["sha"],
        html_url=data["html_url"],
        created_at=data["created_at"],
        updated_at=data["updated_at"],
        additions=data.get("additions", 0),
        deletions=data.get("deletions", 0),
        changed_files=data.get("changed_files", 0),
        commits=data.get("commits", 0),
    )


def build_file_diff(item: dict[str, Any], settings: Settings) -> FileDiff:
    filename = item["filename"]
    status = FileStatus(item["status"])
    skip_reason = _skip_reason(item, status, settings)

    hunks: list[Hunk] = []
    if skip_reason is None:
        try:
            hunks = parse_patch(item["patch"])
        except DiffParseError:
            skip_reason = SkipReason.UNPARSEABLE
        else:
            if not hunks:
                skip_reason = SkipReason.UNPARSEABLE

    return FileDiff(
        filename=filename,
        previous_filename=item.get("previous_filename"),
        status=status,
        language=detect_language(filename),
        additions=item.get("additions", 0),
        deletions=item.get("deletions", 0),
        hunks=hunks if skip_reason is None else [],
        skip_reason=skip_reason,
    )


def _skip_reason(item: dict[str, Any], status: FileStatus, settings: Settings) -> SkipReason | None:
    if reason := classify_path(item["filename"]):
        return reason
    # Review comments anchor to lines in the new version; a deleted file has none.
    if status is FileStatus.REMOVED:
        return SkipReason.DELETED

    patch = item.get("patch")
    if item.get("changes", 0) == 0 and not patch:
        return SkipReason.NO_CHANGES
    # GitHub omits "patch" for binary files and for diffs too large to render.
    if patch is None:
        return SkipReason.NO_PATCH
    if item.get("changes", 0) > settings.max_changed_lines_per_file:
        return SkipReason.TOO_LARGE
    return None


def _enforce_file_limit(files: list[FileDiff], limit: int) -> None:
    reviewable = 0
    for file in files:
        if not file.reviewable:
            continue
        reviewable += 1
        if reviewable > limit:
            file.skip_reason = SkipReason.FILE_LIMIT
            file.hunks = []
