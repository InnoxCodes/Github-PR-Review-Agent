from app.demo.scenarios import DEMO_OWNER, SAMPLE_REVIEWS
from tests.test_api import PR_URL, api, api_settings, finished_review, parse_sse  # noqa: F401


async def test_sample_data_loads_complete_reviews(api):
    result = await api.client.post("/api/demo/sample-data")

    assert result.status_code == 200
    assert result.json() == {"reviews": len(SAMPLE_REVIEWS), "repositories": 3}
    reviews = (await api.client.get("/api/reviews")).json()
    assert len(reviews) == len(SAMPLE_REVIEWS)
    assert all(review["is_sample"] and review["status"] == "completed" for review in reviews)
    assert (await api.client.get("/api/health")).json()["sample_data_loaded"] is True


async def test_every_sample_finding_sits_on_a_real_diff_line(api):
    await api.client.post("/api/demo/sample-data")

    for summary in (await api.client.get("/api/reviews")).json():
        detail = (await api.client.get(f"/api/reviews/{summary['id']}")).json()
        new_lines = {
            file["id"]: {line["new_line"] for hunk in file["hunks"] for line in hunk["lines"] if line["new_line"]}
            for file in detail["files"]
        }
        for issue in detail["issues"]:
            assert issue["line_number"] in new_lines[issue["file_id"]], issue["title"]
        assert detail["health_score"] is not None
        assert detail["cost_usd"] > 0 and detail["llm_calls"] >= detail["files_total"]


async def test_sample_reviews_replay_through_the_stream(api):
    await api.client.post("/api/demo/sample-data")
    [review] = [r for r in (await api.client.get("/api/reviews")).json() if r["repo"] == "edge-cache" and r["pr_number"] == 322]

    events = parse_sse((await api.client.get(f"/api/reviews/{review['id']}/stream")).text)

    types = [event["event"] for event in events]
    assert types[:3] == ["status", "pr", "status"]
    assert "file.retry" in types
    assert types[-1] == "review.completed"


async def test_loading_twice_replaces_samples_and_clearing_keeps_real_reviews(api):
    await finished_review(api, PR_URL)
    await api.client.post("/api/demo/sample-data")
    await api.client.post("/api/demo/sample-data")
    assert len((await api.client.get("/api/reviews")).json()) == len(SAMPLE_REVIEWS) + 1

    assert (await api.client.delete("/api/demo/sample-data")).status_code == 204

    remaining = (await api.client.get("/api/reviews")).json()
    assert [review["is_sample"] for review in remaining] == [False]
    repos = (await api.client.get("/api/repos")).json()
    assert all(repo["owner"] != DEMO_OWNER for repo in repos)


async def test_stream_ends_cleanly_when_nothing_is_left_to_send(api):
    detail = await finished_review(api)
    events = parse_sse((await api.client.get(f"/api/reviews/{detail['id']}/stream")).text)

    result = await api.client.get(
        f"/api/reviews/{detail['id']}/stream", headers={"Last-Event-ID": str(events[-1]["id"])}
    )

    assert result.text == "event: stream.end\ndata: {}\n\n"
