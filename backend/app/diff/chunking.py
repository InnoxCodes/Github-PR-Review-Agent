from app.diff.models import FileChunk, FileDiff, Hunk, LineType


def chunk_file(file: FileDiff, max_lines: int) -> list[FileChunk]:
    """Group a file's hunks into chunks of at most ``max_lines`` diff lines.

    Hunks are kept whole whenever they fit, because a hunk is the smallest unit that still
    reads coherently to a reviewer. Only a single hunk larger than the budget is split.
    """
    pieces = [piece for hunk in file.hunks for piece in _split_hunk(hunk, max_lines)]

    groups: list[list[Hunk]] = []
    current: list[Hunk] = []
    size = 0
    for piece in pieces:
        if current and size + len(piece.lines) > max_lines:
            groups.append(current)
            current, size = [], 0
        current.append(piece)
        size += len(piece.lines)
    if current:
        groups.append(current)

    return [
        FileChunk(filename=file.filename, language=file.language, index=i, total=len(groups), hunks=group)
        for i, group in enumerate(groups)
    ]


def _split_hunk(hunk: Hunk, max_lines: int) -> list[Hunk]:
    if len(hunk.lines) <= max_lines:
        return [hunk]

    pieces: list[Hunk] = []
    old_start, new_start = hunk.old_start, hunk.new_start
    for offset in range(0, len(hunk.lines), max_lines):
        lines = hunk.lines[offset : offset + max_lines]
        old_count = sum(1 for line in lines if line.type is not LineType.ADD)
        new_count = sum(1 for line in lines if line.type is not LineType.DELETE)
        pieces.append(
            Hunk(
                old_start=old_start,
                old_lines=old_count,
                new_start=new_start,
                new_lines=new_count,
                section=hunk.section,
                lines=lines,
            )
        )
        old_start += old_count
        new_start += new_count
    return pieces
