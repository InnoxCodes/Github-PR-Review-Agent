import pytest

from app.diff.models import LineType
from app.diff.parser import DiffParseError, parse_patch


def triples(hunk):
    return [(line.type, line.old_line, line.new_line, line.content) for line in hunk.lines]


def test_modification_numbers_each_side_independently():
    patch = (
        "@@ -10,4 +10,5 @@ def total(items):\n"
        "     result = 0\n"
        "-    for item in items:\n"
        "+    for item in items or []:\n"
        "+        # skip missing prices\n"
        "         result += item.price\n"
        "     return result"
    )

    [hunk] = parse_patch(patch)

    assert (hunk.old_start, hunk.old_lines, hunk.new_start, hunk.new_lines) == (10, 4, 10, 5)
    assert hunk.section == "def total(items):"
    assert triples(hunk) == [
        (LineType.CONTEXT, 10, 10, "    result = 0"),
        (LineType.DELETE, 11, None, "    for item in items:"),
        (LineType.ADD, None, 11, "    for item in items or []:"),
        (LineType.ADD, None, 12, "        # skip missing prices"),
        (LineType.CONTEXT, 12, 13, "        result += item.price"),
        (LineType.CONTEXT, 13, 14, "    return result"),
    ]


def test_multiple_hunks_restart_numbering_from_their_headers():
    patch = "@@ -1,2 +1,2 @@\n-a\n+b\n ctx\n@@ -40,1 +40,2 @@ class Thing:\n ctx\n+new"

    first, second = parse_patch(patch)

    assert [line.new_line for line in first.lines] == [None, 1, 2]
    assert second.section == "class Thing:"
    assert triples(second) == [
        (LineType.CONTEXT, 40, 40, "ctx"),
        (LineType.ADD, None, 41, "new"),
    ]


def test_header_counts_default_to_one_when_omitted():
    [hunk] = parse_patch("@@ -3 +3 @@\n-old\n+new")

    assert (hunk.old_lines, hunk.new_lines) == (1, 1)
    assert triples(hunk) == [(LineType.DELETE, 3, None, "old"), (LineType.ADD, None, 3, "new")]


def test_new_file_has_only_additions_from_line_one():
    [hunk] = parse_patch("@@ -0,0 +1,3 @@\n+import os\n+\n+print(os.getcwd())")

    assert [(line.type, line.old_line, line.new_line) for line in hunk.lines] == [
        (LineType.ADD, None, 1),
        (LineType.ADD, None, 2),
        (LineType.ADD, None, 3),
    ]


def test_deletion_only_hunk():
    [hunk] = parse_patch("@@ -5,2 +4,0 @@\n-gone = True\n-also_gone = True")

    assert [(line.type, line.old_line) for line in hunk.lines] == [
        (LineType.DELETE, 5),
        (LineType.DELETE, 6),
    ]


def test_no_newline_marker_is_not_treated_as_content():
    patch = "@@ -1 +1 @@\n-x = 1\n\\ No newline at end of file\n+x = 2\n\\ No newline at end of file"

    [hunk] = parse_patch(patch)

    assert [line.content for line in hunk.lines] == ["x = 1", "x = 2"]


def test_blank_context_line_with_stripped_leading_space():
    [hunk] = parse_patch("@@ -1,3 +1,3 @@\n a\n\n-b\n+c")

    assert triples(hunk)[1] == (LineType.CONTEXT, 2, 2, "")
    assert triples(hunk)[3] == (LineType.ADD, None, 3, "c")


def test_crlf_line_endings_are_trimmed():
    [hunk] = parse_patch("@@ -1 +1 @@\r\n-old\r\n+new\r\n")

    assert [line.content for line in hunk.lines] == ["old", "new"]


def test_lines_that_look_like_file_headers_are_parsed_as_content():
    # A deleted SQL comment "-- x" becomes "--- x"; an added "++ y" becomes "+++ y".
    patch = "@@ -1,2 +1,2 @@\n--- drop the old index\n+++ counter\n select 1;"

    [hunk] = parse_patch(patch)

    assert triples(hunk) == [
        (LineType.DELETE, 1, None, "-- drop the old index"),
        (LineType.ADD, None, 1, "++ counter"),
        (LineType.CONTEXT, 2, 2, "select 1;"),
    ]


def test_git_file_headers_before_first_hunk_are_ignored():
    patch = (
        "diff --git a/app.py b/app.py\n"
        "index 83db48f..bf269f4 100644\n"
        "--- a/app.py\n"
        "+++ b/app.py\n"
        "@@ -1 +1 @@\n"
        "-DEBUG = True\n"
        "+DEBUG = False\n"
    )

    [hunk] = parse_patch(patch)

    assert [line.content for line in hunk.lines] == ["DEBUG = True", "DEBUG = False"]


def test_unexpected_marker_inside_hunk_raises():
    with pytest.raises(DiffParseError):
        parse_patch("@@ -1,2 +1,2 @@\n context\n?garbage")


def test_empty_patch_has_no_hunks():
    assert parse_patch("") == []


def test_hunk_header_round_trips():
    [hunk] = parse_patch("@@ -7,3 +7,4 @@ fn main() {\n a\n+b\n c\n d")

    assert hunk.header == "@@ -7,3 +7,4 @@ fn main() {"
