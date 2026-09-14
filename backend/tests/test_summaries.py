from types import SimpleNamespace

from app.events import format_sse
from app.services.review_runner import summarize


def issues(*severities):
    return [SimpleNamespace(severity=severity) for severity in severities]


def test_summary_counts_findings_by_severity():
    assert summarize(issues("critical", "warning", "warning", "info"), 3, 0) == (
        "Found 1 critical issue, 2 warnings and 1 suggestion across 3 files."
    )


def test_summary_for_a_clean_review():
    assert summarize([], 1, 0) == "No issues found across 1 file."


def test_summary_mentions_files_that_could_not_be_reviewed():
    assert summarize(issues("warning"), 4, 1) == "Found 1 warning across 4 files. 1 file could not be reviewed."


def test_summary_when_nothing_was_reviewable():
    assert summarize([], 0, 0).startswith("Nothing to review")


def test_sse_frames_carry_id_event_and_compact_json():
    assert format_sse(12, "issues", {"a": [1, 2]}) == 'id: 12\nevent: issues\ndata: {"a":[1,2]}\n\n'
