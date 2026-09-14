import json
import re

from app.config import Settings
from app.diff.models import PRAuthor, PRMetadata, PullRequestDiff
from app.llm.base import StructuredRequest, StructuredResponse, TokenUsage
from app.services.pr_loader import build_file_diff

SQL_PATCH = (
    "@@ -10,3 +10,4 @@ def load(user_id):\n"
    "     conn = get_conn()\n"
    "-    row = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,))\n"
    "+    query = f\"SELECT * FROM users WHERE id = {user_id}\"\n"
    "+    row = conn.execute(query)\n"
    "     return row"
)

RETRY_PATCH = "@@ -1,2 +1,3 @@\n import time\n+RETRIES = 3\n def fetch():"


def make_metadata(**overrides) -> PRMetadata:
    data = {
        "owner": "octo",
        "repo": "widgets",
        "number": 7,
        "title": "Speed up user lookups",
        "body": "Switches the lookup to a raw query.",
        "author": PRAuthor(login="mona"),
        "state": "open",
        "draft": False,
        "merged": False,
        "base_ref": "main",
        "head_ref": "feature/fast-lookup",
        "base_sha": "a" * 40,
        "head_sha": "b" * 40,
        "html_url": "https://github.com/octo/widgets/pull/7",
        "created_at": "2026-09-01T10:00:00Z",
        "updated_at": "2026-09-02T10:00:00Z",
        "additions": 3,
        "deletions": 1,
        "changed_files": 2,
        "commits": 1,
    }
    data.update(overrides)
    return PRMetadata(**data)


def make_file_payload(filename: str, patch: str, status: str = "modified") -> dict:
    additions = sum(1 for line in patch.split("\n") if line.startswith("+"))
    deletions = sum(1 for line in patch.split("\n") if line.startswith("-"))
    return {
        "filename": filename,
        "status": status,
        "patch": patch,
        "additions": additions,
        "deletions": deletions,
        "changes": additions + deletions,
    }


def make_pr(files: list[dict] | None = None, settings: Settings | None = None, **metadata) -> PullRequestDiff:
    settings = settings or Settings(_env_file=None)
    files = files if files is not None else [
        make_file_payload("app/users.py", SQL_PATCH),
        make_file_payload("app/client.py", RETRY_PATCH),
    ]
    return PullRequestDiff(
        metadata=make_metadata(**metadata),
        files=[build_file_diff(item, settings) for item in files],
    )


def finding_json(**overrides) -> dict:
    data = {
        "line_number": 11,
        "end_line": None,
        "category": "security",
        "title": "SQL built with an f-string",
        "comment": "`user_id` is interpolated into the query, allowing SQL injection.",
        "suggested_fix": "row = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,))",
        "severity": "critical",
        "confidence": "high",
    }
    data.update(overrides)
    return data


def review_json(*findings: dict, summary: str = "Looks at the change.") -> str:
    return json.dumps({"summary": summary, "findings": list(findings)})


def response(text: str, *, model: str = "claude-opus-5", stop_reason: str = "end_turn", usage: TokenUsage | None = None) -> StructuredResponse:
    return StructuredResponse(
        text=text,
        model=model,
        usage=usage or TokenUsage(input_tokens=1_000, output_tokens=200, cache_read_input_tokens=3_000),
        stop_reason=stop_reason,
    )


_PATH = re.compile(r'<file path="([^"]+)"')


def requested_path(request: StructuredRequest) -> str:
    match = _PATH.search(request.turns[0].text)
    assert match, "chunk prompt should name the file"
    return match.group(1)
