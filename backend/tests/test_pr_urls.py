import pytest

from app.github.urls import InvalidPRReference, PRRef, parse_pr_reference


@pytest.mark.parametrize(
    "value",
    [
        "https://github.com/octo-org/my.repo/pull/42",
        "http://github.com/octo-org/my.repo/pull/42",
        "https://www.github.com/octo-org/my.repo/pull/42",
        "github.com/octo-org/my.repo/pull/42",
        "https://github.com/octo-org/my.repo/pull/42/",
        "https://github.com/octo-org/my.repo/pull/42/files",
        "https://github.com/octo-org/my.repo/pull/42/files#diff-abc123",
        "https://github.com/octo-org/my.repo/pull/42?w=1",
        "  https://github.com/octo-org/my.repo/pull/42  ",
        "https://api.github.com/repos/octo-org/my.repo/pulls/42",
        "octo-org/my.repo#42",
        "octo-org/my.repo/pull/42",
    ],
)
def test_supported_reference_formats(value):
    assert parse_pr_reference(value) == PRRef("octo-org", "my.repo", 42)


def test_git_suffix_is_dropped():
    assert parse_pr_reference("https://github.com/o/r.git/pull/1").repo == "r"


def test_ref_helpers():
    ref = PRRef("octo", "widgets", 7)

    assert ref.full_name == "octo/widgets"
    assert ref.html_url == "https://github.com/octo/widgets/pull/7"
    assert str(ref) == "octo/widgets#7"


@pytest.mark.parametrize(
    "value",
    [
        "",
        "not a url",
        "https://github.com/octo/widgets",
        "https://github.com/octo/widgets/issues/42",
        "https://github.com/octo/widgets/pull/0",
        "https://github.com/octo/widgets/pull/abc",
        "https://gitlab.com/octo/widgets/pull/42",
        "https://github.com.evil.io/octo/widgets/pull/42",
        "octo/widgets",
    ],
)
def test_invalid_references_raise(value):
    with pytest.raises(InvalidPRReference):
        parse_pr_reference(value)
