from app.diff.chunking import chunk_file
from app.diff.models import FileDiff, FileStatus, LineType
from app.diff.parser import parse_patch


def make_file(patch: str) -> FileDiff:
    return FileDiff(
        filename="src/app.py",
        status=FileStatus.MODIFIED,
        language="python",
        additions=0,
        deletions=0,
        hunks=parse_patch(patch),
    )


def added_hunk(start: int, count: int) -> str:
    body = "\n".join(f"+line {start + i}" for i in range(count))
    return f"@@ -{start - 1},0 +{start},{count} @@\n{body}"


def test_small_file_is_a_single_chunk():
    [chunk] = chunk_file(make_file(added_hunk(1, 5)), max_lines=20)

    assert (chunk.index, chunk.total, len(chunk.hunks)) == (0, 1, 1)
    assert chunk.language == "python"


def test_whole_hunks_are_packed_until_the_budget_is_reached():
    patch = "\n".join([added_hunk(1, 8), added_hunk(50, 8), added_hunk(100, 8)])

    chunks = chunk_file(make_file(patch), max_lines=20)

    assert [len(c.hunks) for c in chunks] == [2, 1]
    assert [c.total for c in chunks] == [2, 2]


def test_oversized_hunk_is_split_without_losing_line_numbers():
    file = make_file(added_hunk(1, 45))

    chunks = chunk_file(file, max_lines=20)

    assert len(chunks) == 3
    pieces = [hunk for chunk in chunks for hunk in chunk.hunks]
    assert [(p.new_start, p.new_lines) for p in pieces] == [(1, 20), (21, 20), (41, 5)]
    numbers = [line.new_line for p in pieces for line in p.lines]
    assert numbers == list(range(1, 46))


def test_split_hunk_tracks_both_sides():
    lines = "\n".join([" ctx"] * 15 + ["-old"] * 10 + ["+new"] * 5)
    file = make_file(f"@@ -1,25 +1,20 @@\n{lines}")

    pieces = [hunk for chunk in chunk_file(file, max_lines=20) for hunk in chunk.hunks]

    assert [(p.old_start, p.old_lines, p.new_start, p.new_lines) for p in pieces] == [
        (1, 20, 1, 15),
        (21, 5, 16, 5),
    ]
    assert pieces[1].lines[-1].type is LineType.ADD


def test_file_without_hunks_has_no_chunks():
    assert chunk_file(make_file(""), max_lines=20) == []
