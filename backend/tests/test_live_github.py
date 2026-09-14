"""Checks the parser against real, merged public PRs (which never change).

Opt-in because it needs network access and spends GitHub API quota:
    RUN_LIVE_TESTS=1 pytest tests/test_live_github.py
"""

import os

import pytest

from app.config import Settings
from app.diff.chunking import chunk_file
from app.diff.models import LineType, SkipReason
from app.github.client import GitHubClient
from app.github.urls import parse_pr_reference
from app.services.pr_loader import load_pull_request

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_TESTS") != "1", reason="set RUN_LIVE_TESTS=1 to call the real GitHub API"
)


async def load(reference: str):
    settings = Settings()
    async with GitHubClient(settings.github_token_value) as client:
        return await load_pull_request(client, parse_pr_reference(reference), settings), settings


@pytest.mark.parametrize(
    "reference",
    [
        "https://github.com/sindresorhus/ky/pull/880",
        "https://github.com/sindresorhus/ky/pull/874",
        "https://github.com/encode/httpx/pull/3690",
    ],
)
async def test_parsed_lines_agree_with_githubs_own_counts(reference):
    pr, settings = await load(reference)

    assert pr.reviewable_files, "expected at least one reviewable file"
    for file in pr.reviewable_files:
        lines = [line for hunk in file.hunks for line in hunk.lines]
        assert sum(line.type is LineType.ADD for line in lines) == file.additions, file.filename
        assert sum(line.type is LineType.DELETE for line in lines) == file.deletions, file.filename

        for hunk in file.hunks:
            assert sum(line.type is not LineType.ADD for line in hunk.lines) == hunk.old_lines
            assert sum(line.type is not LineType.DELETE for line in hunk.lines) == hunk.new_lines

        chunked = [line for chunk in chunk_file(file, settings.chunk_max_lines) for h in chunk.hunks for line in h.lines]
        assert chunked == lines, f"chunking dropped or reordered lines in {file.filename}"


async def test_dependency_bump_skips_the_lockfile():
    pr, _ = await load("fastapi/typer#1948")

    reasons = {f.filename: f.skip_reason for f in pr.files}
    assert reasons["uv.lock"] is SkipReason.LOCKFILE
    assert reasons["typer/_click/_compat.py"] is None
