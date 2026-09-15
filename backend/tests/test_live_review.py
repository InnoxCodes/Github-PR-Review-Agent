"""End to end: a real public pull request through GitHub, the real LLM, the database and the API.

Opt-in, because it calls the GitHub API and spends LLM tokens (a few cents per run):
    RUN_LIVE_TESTS=1 pytest tests/test_live_review.py
The LLM key is read from backend/.env or the environment, like the running app.
"""

import os

import httpx
import pytest

from app.config import Settings
from app.llm.factory import llm_status
from app.main import create_app

# Small, merged (so it never changes), three reviewable TypeScript files plus a readme.
PR_URL = "https://github.com/sindresorhus/ky/pull/880"

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_TESTS") != "1",
    reason="set RUN_LIVE_TESTS=1 (with an LLM API key configured) to run the real pipeline",
)


async def test_real_pull_request_end_to_end(tmp_path):
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'live.db'}",
        secret_key_file=tmp_path / "secret.key",
    )
    status = llm_status(settings)
    if not status.configured:
        pytest.skip(status.message)

    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            created = await client.post("/api/reviews", json={"pr_url": PR_URL})
            assert created.status_code == 202, created.text
            await app.state.services.runner.wait_idle()

            review = (await client.get(f"/api/reviews/{created.json()['id']}")).json()
            stream = (await client.get(f"/api/reviews/{review['id']}/stream")).text

    assert review["status"] == "completed", review["error"]
    assert review["pr_title"] == "Fix `signal` replacement when extending instances"

    files = {file["filename"]: file for file in review["files"]}
    assert files["readme.md"]["skip_reason"] == "docs"
    reviewed = [file for file in review["files"] if file["state"] != "skipped"]
    assert len(reviewed) == 3
    assert all(file["state"] == "done" for file in reviewed), [file["error"] for file in reviewed]

    # Every finding the model produced must survive validation onto a real line of its file's diff.
    new_lines = {
        file["id"]: {line["new_line"] for hunk in file["hunks"] for line in hunk["lines"] if line["new_line"]}
        for file in review["files"]
    }
    for issue in review["issues"]:
        assert issue["line_number"] in new_lines[issue["file_id"]], issue
        assert issue["severity"] in {"critical", "warning", "info"}
        assert issue["title"] and issue["comment"]

    assert 0 <= review["health_score"] <= 100
    assert review["llm_calls"] >= len(reviewed)
    assert review["tokens"]["output_tokens"] > 0
    if status.provider == "anthropic":
        assert review["cost_usd"] > 0

    assert stream.count("event: file.completed") == 3
    assert "event: review.completed" in stream
