import pytest

from app.review.scoring import ScoredIssue, grade, health_score


def issues(*specs):
    return [ScoredIssue(*spec) for spec in specs]


def test_clean_pr_scores_100():
    assert health_score([], changed_lines=250) == 100


def test_critical_findings_cost_the_same_regardless_of_pr_size():
    critical = issues(("critical", "bug", "high"))

    assert health_score(critical, changed_lines=10) == health_score(critical, changed_lines=10_000)


def test_non_critical_findings_are_diluted_by_pr_size():
    warnings = issues(*[("warning", "bug", "high")] * 4)

    assert health_score(warnings, changed_lines=2_000) > health_score(warnings, changed_lines=40)


def test_security_outweighs_style_at_equal_severity():
    security = health_score(issues(("warning", "security", "high")), changed_lines=100)
    style = health_score(issues(("warning", "style", "high")), changed_lines=100)

    assert security < style


def test_low_confidence_findings_count_less():
    confident = health_score(issues(("warning", "bug", "high")), changed_lines=100)
    unsure = health_score(issues(("warning", "bug", "low")), changed_lines=100)

    assert unsure > confident


def test_score_never_goes_below_zero():
    assert health_score(issues(*[("critical", "security", "high")] * 20), changed_lines=50) == 0


@pytest.mark.parametrize(
    ("score", "expected"),
    [(100, "healthy"), (80, "healthy"), (79, "needs_attention"), (50, "needs_attention"), (49, "at_risk"), (None, None)],
)
def test_grade_thresholds(score, expected):
    assert grade(score) == expected
