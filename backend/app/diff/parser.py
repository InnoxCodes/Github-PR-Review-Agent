import re

from app.diff.models import DiffLine, Hunk, LineType

# "@@ -12,7 +12,8 @@ def handler():"  — counts default to 1 when omitted ("@@ -3 +3 @@").
HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: (.*))?$")


class DiffParseError(ValueError):
    pass


def parse_patch(patch: str) -> list[Hunk]:
    """Parse one file's unified diff into hunks whose lines carry old/new line numbers.

    Lines are consumed by the counts in each hunk header rather than by sniffing prefixes,
    so a deleted SQL comment ("-- note" -> "--- note") or an added "++i" is never mistaken
    for a file header. Anything before the first hunk (diff --git, index, ---/+++) is ignored.
    """
    hunks: list[Hunk] = []
    hunk: Hunk | None = None
    old_line = new_line = old_left = new_left = 0

    for raw in _split_lines(patch):
        header = HUNK_HEADER.match(raw)
        if header:
            old_start, new_start = int(header[1]), int(header[3])
            old_left = int(header[2]) if header[2] is not None else 1
            new_left = int(header[4]) if header[4] is not None else 1
            hunk = Hunk(
                old_start=old_start,
                old_lines=old_left,
                new_start=new_start,
                new_lines=new_left,
                section=(header[5] or "").strip(),
            )
            hunks.append(hunk)
            old_line, new_line = old_start, new_start
            continue

        # "\ No newline at end of file" annotates the previous line; it isn't content.
        if hunk is None or raw.startswith("\\"):
            continue
        if old_left <= 0 and new_left <= 0:
            continue

        marker, content = raw[:1], raw[1:]
        if marker == "+":
            hunk.lines.append(DiffLine(type=LineType.ADD, content=content, new_line=new_line))
            new_line += 1
            new_left -= 1
        elif marker == "-":
            hunk.lines.append(DiffLine(type=LineType.DELETE, content=content, old_line=old_line))
            old_line += 1
            old_left -= 1
        elif marker in (" ", ""):
            # An empty string is a blank context line whose leading space was stripped.
            hunk.lines.append(
                DiffLine(type=LineType.CONTEXT, content=content, old_line=old_line, new_line=new_line)
            )
            old_line += 1
            new_line += 1
            old_left -= 1
            new_left -= 1
        else:
            raise DiffParseError(f"Unexpected line inside hunk near +{new_line}: {raw[:60]!r}")

    return hunks


def _split_lines(text: str) -> list[str]:
    # str.splitlines() would also split on \x0c,   etc. that can legitimately
    # appear inside source lines, so split on \n only and trim CRLF endings.
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return [line.removesuffix("\r") for line in lines]
