import asyncio

import pytest

from app.llm.base import (
    LLMAuthenticationError,
    LLMRefusalError,
    LLMUnavailableError,
    StructuredRequest,
    TokenUsage,
)
from app.review.engine import ReviewAborted, ReviewEngine
from tests.factories import (
    RETRY_PATCH,
    finding_json,
    make_file_payload,
    make_pr,
    requested_path,
    response,
    review_json,
)


class ScriptedProvider:
    """Stands in for an LLM: answers each request with a per-file script of responses."""

    name = "scripted"
    model = "claude-opus-5"

    def __init__(self, scripts, *, delay: float = 0.0):
        self.scripts = {path: list(items) for path, items in scripts.items()}
        self.requests: list[StructuredRequest] = []
        self.timeline: list[str] = []
        self.delay = delay

    async def generate_structured(self, request):
        path = requested_path(request)
        self.requests.append(request)
        self.timeline.append(f"start {path}")
        await asyncio.sleep(self.delay)
        self.timeline.append(f"end {path}")
        outcome = self.scripts[path].pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    async def aclose(self):
        pass


class RecordingListener:
    def __init__(self):
        self.events = []
        self.calls = []

    async def on_file_started(self, file, chunk_count):
        self.events.append(("started", file.filename, chunk_count))

    async def on_chunk_findings(self, file, chunk, findings):
        self.events.append(("findings", file.filename, [f.title for f in findings]))

    async def on_file_finished(self, file, result):
        self.events.append(("finished", file.filename, result.error))

    async def on_llm_call(self, record):
        self.calls.append(record)


CLEAN = response(review_json(summary="Adds a retry constant."))


async def run(provider, pr=None, **engine_options):
    listener = RecordingListener()
    engine = ReviewEngine(provider, **engine_options)
    results = await engine.review(pr or make_pr(), listener)
    return {r.filename: r for r in results}, listener


async def test_reviews_every_file_and_reports_progress():
    provider = ScriptedProvider(
        {"app/users.py": [response(review_json(finding_json()))], "app/client.py": [CLEAN]}
    )

    results, listener = await run(provider)

    assert [f.title for f in results["app/users.py"].findings] == ["SQL built with an f-string"]
    assert results["app/client.py"].findings == []
    assert results["app/client.py"].summary == "Adds a retry constant."
    for filename in ("app/users.py", "app/client.py"):
        events = [e[0] for e in listener.events if e[1] == filename]
        assert events == ["started", "findings", "finished"]
    assert [c.outcome for c in listener.calls] == ["ok", "ok"]


async def test_requests_carry_stable_system_prompt_pr_context_and_schema():
    provider = ScriptedProvider({"app/users.py": [CLEAN], "app/client.py": [CLEAN]})

    await run(provider)

    first, second = provider.requests
    assert first.system == second.system
    assert first.context == second.context
    assert "<title>Speed up user lookups</title>" in first.context
    assert first.schema["required"] == ["summary", "findings"]


async def test_invalid_output_is_retried_with_the_error_fed_back():
    provider = ScriptedProvider(
        {
            "app/users.py": [response("Sure! Here's my review: it has an injection."), response(review_json(finding_json()))],
            "app/client.py": [CLEAN],
        }
    )

    results, listener = await run(provider)

    retry = [r for r in provider.requests if requested_path(r) == "app/users.py"][1]
    assert [turn.role for turn in retry.turns] == ["user", "assistant", "user"]
    assert retry.turns[1].text == "Sure! Here's my review: it has an injection."
    assert "not valid JSON" in retry.turns[2].text
    assert len(results["app/users.py"].findings) == 1
    assert [c.outcome for c in listener.calls if c.filename == "app/users.py"] == ["invalid", "ok"]


async def test_truncated_output_is_retried():
    provider = ScriptedProvider(
        {
            "app/users.py": [
                response(review_json(finding_json()), stop_reason="max_tokens"),
                response(review_json(finding_json())),
            ],
            "app/client.py": [CLEAN],
        }
    )

    results, listener = await run(provider)

    assert results["app/users.py"].error is None
    assert "cut off" in listener.calls[0].error or "cut off" in listener.calls[1].error


async def test_file_fails_after_max_attempts_but_the_review_continues():
    provider = ScriptedProvider(
        {"app/users.py": [response("nope")] * 2, "app/client.py": [CLEAN]}
    )

    results, listener = await run(provider, max_attempts=2)

    assert "still invalid after 2 attempts" in results["app/users.py"].error
    assert results["app/client.py"].error is None
    assert ("finished", "app/users.py", results["app/users.py"].error) in listener.events


async def test_usage_and_cost_include_failed_attempts():
    usage = TokenUsage(input_tokens=1_000_000, output_tokens=0)
    provider = ScriptedProvider(
        {
            "app/users.py": [response("bad", usage=usage), response(review_json(), usage=usage)],
            "app/client.py": [response(review_json(), usage=usage)],
        }
    )

    results, _ = await run(provider)

    assert results["app/users.py"].usage.input_tokens == 2_000_000
    assert results["app/users.py"].cost_usd == pytest.approx(10.0)


async def test_refusal_marks_only_that_file_as_failed():
    provider = ScriptedProvider(
        {"app/users.py": [LLMRefusalError("Claude declined to review this chunk.", "cyber")], "app/client.py": [CLEAN]}
    )

    results, listener = await run(provider)

    assert results["app/users.py"].error == "Claude declined to review this chunk. (category: cyber)"
    assert results["app/client.py"].error is None
    assert listener.calls[0].outcome == "error"


async def test_provider_outage_fails_the_file_not_the_review():
    provider = ScriptedProvider(
        {"app/users.py": [LLMUnavailableError("Anthropic API is unavailable (529).")], "app/client.py": [CLEAN]}
    )

    results, _ = await run(provider)

    assert results["app/users.py"].error == "Anthropic API is unavailable (529)."


async def test_bad_credentials_abort_the_whole_review():
    provider = ScriptedProvider(
        {"app/users.py": [LLMAuthenticationError("Anthropic rejected the API key (401).")], "app/client.py": [CLEAN]}
    )

    with pytest.raises(ReviewAborted, match="rejected the API key"):
        await run(provider)


async def test_large_files_are_reviewed_chunk_by_chunk():
    patch = "@@ -0,0 +1,50 @@\n" + "\n".join(f"+value_{i} = {i}" for i in range(50))
    pr = make_pr([make_file_payload("app/constants.py", patch, status="added")])
    provider = ScriptedProvider(
        {
            "app/constants.py": [
                response(review_json(finding_json(line_number=5, title="first", category="style", severity="info"))),
                response(review_json(finding_json(line_number=30, title="second", category="style", severity="info"))),
                response(review_json()),
            ]
        }
    )

    results, listener = await run(provider, pr, chunk_max_lines=20)

    assert len(provider.requests) == 3
    assert 'chunk="2 of 3"' in provider.requests[1].turns[0].text
    assert [f.title for f in results["app/constants.py"].findings] == ["first", "second"]
    assert listener.events[0] == ("started", "app/constants.py", 3)


async def test_findings_outside_the_diff_are_dropped_and_recorded():
    provider = ScriptedProvider(
        {
            "app/users.py": [response(review_json(finding_json(), finding_json(line_number=900, title="ghost")))],
            "app/client.py": [CLEAN],
        }
    )

    results, _ = await run(provider)

    assert [f.title for f in results["app/users.py"].findings] == ["SQL built with an f-string"]
    assert "line 900 is not in this diff" in results["app/users.py"].dropped[0]


async def test_first_call_completes_before_the_rest_fan_out():
    files = [make_file_payload(f"app/m{i}.py", RETRY_PATCH) for i in range(4)]
    provider = ScriptedProvider({f"app/m{i}.py": [CLEAN] for i in range(4)}, delay=0.01)

    await run(provider, make_pr(files), concurrency=4)

    first_path = provider.timeline[0].split()[1]
    assert provider.timeline[1] == f"end {first_path}"
    later_starts = [event for event in provider.timeline[2:] if event.startswith("start")]
    assert len(later_starts) == 3


async def test_concurrency_limit_is_respected():
    files = [make_file_payload(f"app/m{i}.py", RETRY_PATCH) for i in range(6)]
    provider = ScriptedProvider({f"app/m{i}.py": [CLEAN] for i in range(6)}, delay=0.01)

    await run(provider, make_pr(files), concurrency=2)

    active = peak = 0
    for event in provider.timeline:
        active += 1 if event.startswith("start") else -1
        peak = max(peak, active)
    assert peak == 2


async def test_pr_without_reviewable_files_makes_no_calls():
    provider = ScriptedProvider({})
    pr = make_pr([make_file_payload("package-lock.json", RETRY_PATCH)])

    results, listener = await run(provider, pr)

    assert results == {} and provider.requests == [] and listener.events == []
