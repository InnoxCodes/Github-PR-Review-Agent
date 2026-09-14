import asyncio
import hashlib
import hmac
import inspect
import json
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import select

from app.config import Settings
from app.github.client import GitHubClient, GitHubNotFoundError
from app.llm.factory import LLMStatus
from app.main import create_app
from app.models import Repository, Review, utcnow
from tests.factories import finding_json, make_pr, requested_path, response, review_json

WEBHOOK_SECRET = "webhook-test-secret"
PR_URL = "https://github.com/octo/widgets/pull/7"
TOKEN = "ghp_supersecrettoken1234"

REPO_JSON = {
    "full_name": "octo/widgets",
    "name": "widgets",
    "owner": {"login": "octo"},
    "html_url": "https://github.com/octo/widgets",
    "description": "Widgets, but faster.",
    "language": "Python",
    "stargazers_count": 42,
    "private": False,
    "default_branch": "main",
}


def default_behaviour(path, request):
    if path == "app/users.py":
        return response(review_json(finding_json(), summary="Builds SQL with an f-string."))
    return response(review_json(summary="Adds a retry constant."))


class FakeProvider:
    name = "anthropic"
    model = "claude-opus-5"

    def __init__(self, state):
        self.state = state

    async def generate_structured(self, request):
        result = self.state.behaviour(requested_path(request), request)
        return await result if inspect.isawaitable(result) else result

    async def aclose(self):
        pass


def github_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/repos/octo/widgets":
        return httpx.Response(200, json=REPO_JSON)
    return httpx.Response(404, json={"message": "Not Found"})


@pytest.fixture
def api_settings(tmp_path):
    return Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'reviewmind.db'}",
        secret_key_file=tmp_path / "secret.key",
        github_token=None,
        github_webhook_secret=WEBHOOK_SECRET,
    )


def build_app(settings, state):
    async def loader(ref, token):
        state.loader_calls.append((ref, token))
        if state.loader_error is not None:
            raise state.loader_error
        return state.pr

    return create_app(
        settings,
        provider_factory=lambda _settings: FakeProvider(state),
        pr_loader=loader,
        llm_status_fn=lambda: LLMStatus(
            state.configured, "anthropic", "claude-opus-5", "ok" if state.configured else "No LLM API key found."
        ),
        github_factory=lambda token: GitHubClient(token, transport=httpx.MockTransport(github_handler)),
    )


@pytest.fixture
async def api(api_settings):
    state = SimpleNamespace(behaviour=default_behaviour, pr=make_pr(), loader_error=None, configured=True, loader_calls=[])
    app = build_app(api_settings, state)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            yield SimpleNamespace(client=client, services=app.state.services, state=state)


async def finished_review(api, url=PR_URL) -> dict:
    created = await api.client.post("/api/reviews", json={"pr_url": url})
    assert created.status_code == 202, created.text
    await api.services.runner.wait_idle()
    return (await api.client.get(f"/api/reviews/{created.json()['id']}")).json()


def parse_sse(text: str) -> list[dict]:
    events = []
    for block in text.strip().split("\n\n"):
        if not block or block.startswith(":"):
            continue
        fields = dict(line.split(": ", 1) for line in block.split("\n"))
        fields["id"] = int(fields["id"])
        fields["data"] = json.loads(fields["data"])
        events.append(fields)
    return events


def sign(body: bytes) -> str:
    return "sha256=" + hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()


# --- Reviews -----------------------------------------------------------------------------

async def test_health_reports_configuration(api):
    body = (await api.client.get("/api/health")).json()

    assert body["status"] == "ok"
    assert body["llm"] == {"configured": True, "provider": "anthropic", "model": "claude-opus-5", "message": "ok"}
    assert body["github_token_configured"] is False


async def test_openapi_docs_are_generated(api):
    schema = (await api.client.get("/openapi.json")).json()

    assert schema["info"]["title"] == "ReviewMind API"
    assert "/api/reviews/{review_id}/stream" in schema["paths"]


async def test_rejects_references_that_are_not_pull_requests(api):
    result = await api.client.post("/api/reviews", json={"pr_url": "https://github.com/octo/widgets"})

    assert result.status_code == 422
    assert "Not a GitHub pull request reference" in result.json()["detail"]


async def test_refuses_to_start_without_an_llm_provider(api):
    api.state.configured = False

    result = await api.client.post("/api/reviews", json={"pr_url": PR_URL})

    assert result.status_code == 503
    assert "No LLM API key" in result.json()["detail"]


async def test_review_lifecycle_end_to_end(api):
    detail = await finished_review(api)

    assert detail["status"] == "completed"
    assert detail["pr_title"] == "Speed up user lookups"
    assert detail["files_total"] == detail["files_done"] == 2
    [issue] = detail["issues"]
    assert (issue["filename"], issue["line_number"], issue["severity"], issue["status"]) == ("app/users.py", 11, "critical", "open")
    assert detail["health_score"] < 100 and detail["grade"] is not None
    assert detail["issue_counts"] == {"critical": 1, "warning": 0, "info": 0}
    assert detail["summary"] == "Found 1 critical issue across 2 files."

    users = next(f for f in detail["files"] if f["filename"] == "app/users.py")
    assert users["state"] == "done" and users["issue_count"] == 1
    assert users["summary"] == "Builds SQL with an f-string."
    assert [line["new_line"] for line in users["hunks"][0]["lines"]] == [10, None, 11, 12, 13]

    assert detail["llm_calls"] == 2 and detail["invalid_outputs"] == 0
    assert detail["tokens"]["cache_read_tokens"] == 6_000
    assert detail["cost_usd"] > 0
    assert detail["model"] == "claude-opus-5"


async def test_stream_replays_the_stored_event_log(api):
    detail = await finished_review(api)

    result = await api.client.get(f"/api/reviews/{detail['id']}/stream")

    assert result.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(result.text)
    types = [event["event"] for event in events]
    assert types[:2] == ["status", "pr"]
    assert types[-1] == "review.completed"
    assert types.count("file.started") == types.count("file.completed") == 2
    assert types.count("issues") == 1
    assert [e["id"] for e in events] == sorted({e["id"] for e in events})
    assert events[-1]["data"]["review"]["health_score"] == detail["health_score"]


async def test_stream_resumes_after_last_event_id(api):
    detail = await finished_review(api)
    everything = parse_sse((await api.client.get(f"/api/reviews/{detail['id']}/stream")).text)

    resumed = await api.client.get(
        f"/api/reviews/{detail['id']}/stream", headers={"Last-Event-ID": str(everything[2]["id"])}
    )

    assert [e["id"] for e in parse_sse(resumed.text)] == [e["id"] for e in everything[3:]]


async def test_live_stream_switches_from_the_log_to_live_events(api):
    gate = asyncio.Event()

    async def held(path, request):
        await gate.wait()
        return default_behaviour(path, request)

    api.state.behaviour = held
    created = (await api.client.post("/api/reviews", json={"pr_url": PR_URL})).json()
    stream = asyncio.create_task(api.client.get(f"/api/reviews/{created['id']}/stream"))
    for _ in range(200):
        if api.services.broker.subscriber_count(created["id"]):
            break
        await asyncio.sleep(0.01)
    assert api.services.broker.subscriber_count(created["id"]) == 1

    gate.set()
    events = parse_sse((await asyncio.wait_for(stream, timeout=10)).text)

    assert events[-1]["event"] == "review.completed"
    assert len({e["id"] for e in events}) == len(events)
    assert api.services.broker.subscriber_count(created["id"]) == 0


async def test_submitting_a_running_pr_again_returns_the_same_review(api):
    gate = asyncio.Event()

    async def held(path, request):
        await gate.wait()
        return default_behaviour(path, request)

    api.state.behaviour = held
    first = (await api.client.post("/api/reviews", json={"pr_url": PR_URL})).json()
    second = (await api.client.post("/api/reviews", json={"pr_url": "octo/widgets#7"})).json()
    gate.set()
    await api.services.runner.wait_idle()

    assert first["id"] == second["id"]
    assert len((await api.client.get("/api/reviews")).json()) == 1


async def test_invalid_model_output_is_retried_and_counted(api):
    attempts = {"app/users.py": 0}

    def flaky(path, request):
        if path == "app/users.py" and attempts[path] == 0:
            attempts[path] += 1
            return response("I found one issue: SQL injection.")
        return default_behaviour(path, request)

    api.state.behaviour = flaky
    detail = await finished_review(api)

    assert detail["status"] == "completed"
    assert detail["invalid_outputs"] == 1 and detail["llm_calls"] == 3
    events = parse_sse((await api.client.get(f"/api/reviews/{detail['id']}/stream")).text)
    [retry] = [e for e in events if e["event"] == "file.retry"]
    assert retry["data"]["filename"] == "app/users.py" and "not valid JSON" in retry["data"]["reason"]


async def test_review_fails_when_every_file_fails(api):
    api.state.behaviour = lambda path, request: response("still not json")

    detail = await finished_review(api)

    assert detail["status"] == "failed"
    assert detail["error"].startswith("All 2 files failed to review.")
    assert {f["state"] for f in detail["files"]} == {"failed"}


async def test_github_errors_fail_the_review_with_a_readable_message(api):
    api.state.loader_error = GitHubNotFoundError("Not found on GitHub.", 404)

    detail = await finished_review(api)

    assert detail["status"] == "failed"
    assert detail["error"] == "GitHub: Not found on GitHub."
    events = parse_sse((await api.client.get(f"/api/reviews/{detail['id']}/stream")).text)
    assert events[-1]["event"] == "review.failed"


async def test_pr_with_nothing_reviewable_completes_without_llm_calls(api):
    from tests.factories import SQL_PATCH, make_file_payload

    api.state.pr = make_pr([make_file_payload("package-lock.json", SQL_PATCH)])

    detail = await finished_review(api)

    assert detail["status"] == "completed" and detail["health_score"] == 100
    assert detail["llm_calls"] == 0
    assert detail["summary"].startswith("Nothing to review")


async def test_listing_and_filtering_reviews(api):
    await finished_review(api)

    reviews = (await api.client.get("/api/reviews")).json()
    assert [r["issue_counts"]["critical"] for r in reviews] == [1]
    assert (await api.client.get("/api/reviews", params={"repository": "octo/widgets"})).json() != []
    assert (await api.client.get("/api/reviews", params={"repository": "someone/else"})).json() == []
    assert (await api.client.get("/api/reviews", params={"status": "failed"})).json() == []


async def test_deleting_a_review(api):
    detail = await finished_review(api)

    assert (await api.client.delete(f"/api/reviews/{detail['id']}")).status_code == 204
    assert (await api.client.get(f"/api/reviews/{detail['id']}")).status_code == 404


# --- Issue triage --------------------------------------------------------------------------

async def test_triaging_a_finding_recomputes_the_health_score(api):
    detail = await finished_review(api)
    issue = detail["issues"][0]
    url = f"/api/reviews/{detail['id']}/issues/{issue['id']}"

    dismissed = (await api.client.patch(url, json={"status": "dismissed"})).json()
    assert dismissed["issue"]["status"] == "dismissed" and dismissed["issue"]["resolved_at"]
    assert dismissed["health_score"] == 100 and dismissed["grade"] == "healthy"
    assert dismissed["issue_counts"]["critical"] == 0 and dismissed["open_issues"] == 0

    reopened = (await api.client.patch(url, json={"status": "open"})).json()
    assert reopened["health_score"] == detail["health_score"]
    assert reopened["issue"]["resolved_at"] is None

    accepted = (await api.client.patch(url, json={"status": "accepted"})).json()
    assert accepted["health_score"] == detail["health_score"] and accepted["open_issues"] == 0


async def test_triage_validation(api):
    detail = await finished_review(api)
    issue_id = detail["issues"][0]["id"]

    assert (await api.client.patch(f"/api/reviews/{detail['id']}/issues/{issue_id}", json={"status": "wontfix"})).status_code == 422
    assert (await api.client.patch(f"/api/reviews/other/issues/{issue_id}", json={"status": "accepted"})).status_code == 404


# --- Repositories ------------------------------------------------------------------------

async def test_tracking_a_repository_encrypts_its_token(api):
    created = await api.client.post("/api/repos", json={"repository": "https://github.com/octo/widgets", "github_token": TOKEN})

    assert created.status_code == 201
    body = created.json()
    assert (body["full_name"], body["stars"], body["has_token"], body["token_hint"]) == ("octo/widgets", 42, True, "1234")
    assert TOKEN not in created.text

    async with api.services.session_factory() as session:
        stored = await session.scalar(select(Repository))
    assert TOKEN not in stored.encrypted_token
    assert api.services.cipher.decrypt(stored.encrypted_token) == TOKEN

    again = await api.client.post("/api/repos", json={"repository": "octo/widgets"})
    assert again.status_code == 200 and again.json()["has_token"] is True


async def test_reviews_of_tracked_repositories_use_the_stored_token(api):
    await api.client.post("/api/repos", json={"repository": "octo/widgets", "github_token": TOKEN})

    await finished_review(api)

    [(ref, token)] = api.state.loader_calls
    assert (str(ref), token) == ("octo/widgets#7", TOKEN)
    [repo] = (await api.client.get("/api/repos")).json()
    assert repo["review_count"] == 1 and len(repo["score_history"]) == 1 and repo["issue_history"] == [1]


async def test_unknown_repository_is_rejected(api):
    result = await api.client.post("/api/repos", json={"repository": "octo/missing"})

    assert result.status_code == 404


async def test_untracking_keeps_past_reviews(api):
    detail = await finished_review(api)
    [repo] = (await api.client.get("/api/repos")).json()

    assert (await api.client.delete(f"/api/repos/{repo['id']}")).status_code == 204
    assert (await api.client.get(f"/api/reviews/{detail['id']}")).status_code == 200


# --- Analytics ---------------------------------------------------------------------------

async def test_analytics_summarise_reviews_and_feedback(api):
    detail = await finished_review(api)
    await api.client.patch(f"/api/reviews/{detail['id']}/issues/{detail['issues'][0]['id']}", json={"status": "false_positive"})

    body = (await api.client.get("/api/analytics/summary")).json()

    assert body["totals"] == {
        "prs_reviewed": 1, "files_reviewed": 2, "issues_found": 1, "open_issues": 0,
        "accepted": 0, "dismissed": 0, "false_positives": 1,
    }
    assert body["false_positive_rate"] == 1.0
    assert body["minutes_saved"] == 12.0 and body["minutes_per_file"] == 6.0
    security = next(c for c in body["categories"] if c["category"] == "security")
    assert (security["total"], security["critical"], security["false_positive"]) == (1, 1, 1)
    assert [point["label"] for point in body["score_trend"]] == ["widgets#7"]
    assert sum(sum(week["counts"].values()) for week in body["weekly"]) == 1


async def test_analytics_on_an_empty_database(api):
    body = (await api.client.get("/api/analytics/summary")).json()

    assert body["totals"]["prs_reviewed"] == 0
    assert body["false_positive_rate"] is None and body["weekly"] == []


# --- Webhooks ----------------------------------------------------------------------------

def webhook_body(action="opened", repository="octo/widgets", draft=False) -> bytes:
    return json.dumps(
        {"action": action, "pull_request": {"number": 7, "draft": draft}, "repository": {"full_name": repository}}
    ).encode()


async def post_webhook(api, body: bytes, event="pull_request", signature=None):
    return await api.client.post(
        "/api/github/webhook",
        content=body,
        headers={"X-GitHub-Event": event, "X-Hub-Signature-256": signature or sign(body), "Content-Type": "application/json"},
    )


async def test_webhook_rejects_bad_signatures(api):
    result = await post_webhook(api, webhook_body(), signature="sha256=" + "0" * 64)

    assert result.status_code == 401


async def test_webhook_reviews_prs_on_tracked_repositories_only(api):
    assert (await post_webhook(api, webhook_body())).json()["status"] == "ignored"

    await api.client.post("/api/repos", json={"repository": "octo/widgets"})
    queued = await post_webhook(api, webhook_body())
    await api.services.runner.wait_idle()

    assert queued.status_code == 202 and queued.json()["status"] == "queued"
    assert (await api.client.get(f"/api/reviews/{queued.json()['review_id']}")).json()["status"] == "completed"
    assert (await post_webhook(api, webhook_body(draft=True))).json()["reason"] == "draft pull requests are not reviewed"
    assert (await post_webhook(api, webhook_body(action="closed"))).json()["status"] == "ignored"
    assert (await post_webhook(api, b"{}", event="ping")).json() == {"status": "pong"}


# --- Restarts ----------------------------------------------------------------------------

async def test_reviews_interrupted_by_a_restart_are_marked_failed(api_settings):
    state = SimpleNamespace(behaviour=default_behaviour, pr=make_pr(), loader_error=None, configured=True, loader_calls=[])
    first = build_app(api_settings, state)
    async with first.router.lifespan_context(first):
        async with first.state.services.session_factory() as session:
            session.add(Review(id="stuck", owner="octo", repo="widgets", pr_number=7, pr_url=PR_URL, status="reviewing", created_at=utcnow()))
            await session.commit()

    second = build_app(api_settings, state)
    async with second.router.lifespan_context(second):
        async with second.state.services.session_factory() as session:
            review = await session.get(Review, "stuck")

    assert review.status == "failed"
    assert review.error.startswith("Interrupted")
