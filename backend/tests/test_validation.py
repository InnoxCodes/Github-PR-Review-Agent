import json

import pytest

from app.diff.chunking import chunk_file
from app.diff.models import FileDiff, FileStatus
from app.diff.parser import parse_patch
from app.review.validation import (
    MAX_FINDINGS_PER_CHUNK,
    InvalidReviewOutput,
    correction_prompt,
    extract_json_object,
    validate_chunk_review,
)

# New-file lines present in this diff: 10, 11, 12, 13 (context/added). Old line 11 was deleted.
PATCH = (
    "@@ -10,3 +10,4 @@ def load(user_id):\n"
    "     conn = get_conn()\n"
    "-    row = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,))\n"
    "+    query = f\"SELECT * FROM users WHERE id = {user_id}\"\n"
    "+    row = conn.execute(query)\n"
    "     return row"
)


@pytest.fixture
def chunk():
    file = FileDiff(
        filename="app/users.py",
        status=FileStatus.MODIFIED,
        language="python",
        additions=2,
        deletions=1,
        hunks=parse_patch(PATCH),
    )
    [only] = chunk_file(file, max_lines=400)
    return only


def finding(**overrides):
    base = {
        "line_number": 11,
        "end_line": None,
        "category": "security",
        "title": "SQL built with an f-string",
        "comment": "user_id is interpolated into the query, which allows SQL injection.",
        "suggested_fix": "row = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,))",
        "severity": "critical",
        "confidence": "high",
    }
    base.update(overrides)
    return base


def payload(*findings, summary="Switches the user lookup to an f-string query."):
    return json.dumps({"summary": summary, "findings": list(findings)})


class TestExtractJson:
    def test_plain_object(self):
        assert extract_json_object('{"summary": "ok", "findings": []}') == {"summary": "ok", "findings": []}

    def test_markdown_fenced_object(self):
        text = 'Here is the review:\n```json\n{"summary": "ok", "findings": []}\n```'
        assert extract_json_object(text)["summary"] == "ok"

    def test_object_surrounded_by_prose(self):
        text = 'Sure! {"summary": "ok", "findings": []} Let me know if you need more.'
        assert extract_json_object(text)["findings"] == []

    def test_malformed_json_explains_where_it_broke(self):
        with pytest.raises(InvalidReviewOutput, match="not valid JSON .*line 1"):
            extract_json_object('{"summary": "ok", "findings": [}')

    def test_empty_response(self):
        with pytest.raises(InvalidReviewOutput, match="empty"):
            extract_json_object("   ")

    def test_top_level_array_is_rejected(self):
        with pytest.raises(InvalidReviewOutput, match="must be an object"):
            extract_json_object("[1, 2, 3]")


class TestValidateChunkReview:
    def test_valid_findings_pass_through(self, chunk):
        review = validate_chunk_review(payload(finding()), chunk)

        assert review.summary.startswith("Switches")
        [only] = review.findings
        assert (only.line_number, only.severity, only.category) == (11, "critical", "security")
        assert review.dropped == [] and review.adjusted == []

    def test_no_findings_is_a_valid_review(self, chunk):
        assert validate_chunk_review(payload(), chunk).findings == []

    def test_line_slightly_outside_the_diff_is_snapped_to_the_nearest_line(self, chunk):
        review = validate_chunk_review(payload(finding(line_number=15)), chunk)

        assert review.findings[0].line_number == 13
        assert review.adjusted == ["'SQL built with an f-string': moved from line 15 to 13"]

    def test_line_far_from_the_diff_is_dropped_but_others_survive(self, chunk):
        review = validate_chunk_review(
            payload(finding(line_number=400, title="Hallucinated"), finding(line_number=12, title="Real")),
            chunk,
        )

        assert [f.title for f in review.findings] == ["Real"]
        assert "line 400 is not in this diff" in review.dropped[0]

    def test_malformed_finding_is_dropped_individually(self, chunk):
        review = validate_chunk_review(
            payload(finding(severity="blocker"), finding(title="Kept", line_number=12)), chunk
        )

        assert [f.title for f in review.findings] == ["Kept"]
        assert review.dropped[0].startswith("finding 0: severity")

    def test_all_findings_invalid_is_fatal_so_the_engine_retries(self, chunk):
        with pytest.raises(InvalidReviewOutput, match="None of the findings were valid"):
            validate_chunk_review(payload(finding(category="naming"), finding(line_number=999)), chunk)

    def test_missing_findings_array_is_fatal(self, chunk):
        with pytest.raises(InvalidReviewOutput, match="'findings' must be an array"):
            validate_chunk_review('{"summary": "no findings key"}', chunk)

    def test_truncated_output_is_fatal_even_if_it_parses(self, chunk):
        with pytest.raises(InvalidReviewOutput, match="cut off"):
            validate_chunk_review(payload(finding()), chunk, truncated=True)

    def test_duplicate_findings_are_collapsed(self, chunk):
        review = validate_chunk_review(payload(finding(), finding(title="sql built with an F-string")), chunk)

        assert len(review.findings) == 1

    def test_invalid_end_line_is_cleared(self, chunk):
        review = validate_chunk_review(payload(finding(line_number=12, end_line=11)), chunk)

        assert review.findings[0].end_line is None

    def test_markdown_fence_is_stripped_from_suggested_fix(self, chunk):
        review = validate_chunk_review(payload(finding(suggested_fix="```python\nx = 1\n```")), chunk)

        assert review.findings[0].suggested_fix == "x = 1"

    def test_blank_suggested_fix_becomes_none(self, chunk):
        review = validate_chunk_review(payload(finding(suggested_fix="   ")), chunk)

        assert review.findings[0].suggested_fix is None

    def test_overlong_title_is_clipped(self, chunk):
        review = validate_chunk_review(payload(finding(title="x" * 500)), chunk)

        assert len(review.findings[0].title) == 120

    def test_excess_findings_keep_the_most_severe(self, chunk):
        many = [finding(title=f"nit {i}", severity="info", category="style", line_number=12) for i in range(30)]
        many.append(finding(title="the real bug", severity="critical", line_number=13))

        review = validate_chunk_review(payload(*many), chunk)

        assert len(review.findings) == MAX_FINDINGS_PER_CHUNK
        assert any(f.title == "the real bug" for f in review.findings)
        assert [f.line_number for f in review.findings] == sorted(f.line_number for f in review.findings)


def test_correction_prompt_quotes_the_error():
    message = correction_prompt(InvalidReviewOutput("The response was not valid JSON."))

    assert "not valid JSON" in message
    assert "single JSON object" in message
