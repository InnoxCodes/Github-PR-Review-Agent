"""Developer CLI: see exactly how ReviewMind fetches and structures a real pull request.

    python -m app.cli inspect https://github.com/owner/repo/pull/123
    python -m app.cli inspect owner/repo#123 --show path/to/file.py
    python -m app.cli inspect owner/repo#123 --json > pr.json
"""

import argparse
import asyncio
import sys
from collections import Counter

from app.config import Settings, get_settings
from app.diff.chunking import chunk_file
from app.diff.models import FileDiff, LineType, PullRequestDiff
from app.github.client import GitHubClient, GitHubError
from app.github.urls import InvalidPRReference, PRRef, parse_pr_reference
from app.services.pr_loader import load_pull_request


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect", help="fetch a PR and print its parsed structure")
    inspect.add_argument("pr", help="PR URL or owner/repo#number")
    inspect.add_argument("--show", metavar="FILENAME", help="print the parsed diff lines of one file")
    inspect.add_argument("--json", action="store_true", help="dump the full parsed structure as JSON")
    args = parser.parse_args(argv)

    try:
        ref = parse_pr_reference(args.pr)
    except InvalidPRReference as exc:
        print(exc, file=sys.stderr)
        return 2

    settings = get_settings()
    try:
        pr = asyncio.run(_load(ref, settings))
    except GitHubError as exc:
        print(f"GitHub error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(pr.model_dump_json(indent=2))
        return 0

    _print_summary(pr, settings)
    if args.show:
        match = next((f for f in pr.files if f.filename == args.show), None)
        if match is None:
            print(f"\nNo file named {args.show!r} in this PR.", file=sys.stderr)
            return 1
        _print_file(match)
    return 0


async def _load(ref: PRRef, settings: Settings) -> PullRequestDiff:
    async with GitHubClient(
        settings.github_token_value,
        base_url=settings.github_api_url,
        timeout=settings.github_timeout_seconds,
    ) as client:
        return await load_pull_request(client, ref, settings)


def _print_summary(pr: PullRequestDiff, settings: Settings) -> None:
    meta = pr.metadata
    state = "merged" if meta.merged else ("draft" if meta.draft else meta.state)
    print(f"\n{meta.owner}/{meta.repo}#{meta.number}  {meta.title}")
    print(
        f"by {meta.author.login} · {meta.base_ref} <- {meta.head_ref} · {state} · "
        f"{meta.changed_files} files (+{meta.additions} -{meta.deletions}) · {meta.commits} commits\n"
    )

    rows = [("STATUS", "LANGUAGE", "+", "-", "HUNKS", "REVIEW", "FILE")]
    total_chunks = 0
    for file in pr.files:
        if file.reviewable:
            chunks = len(chunk_file(file, settings.chunk_max_lines))
            total_chunks += chunks
            review = f"yes ({chunks} chunk{'s' if chunks != 1 else ''})"
        else:
            review = f"skip: {file.skip_reason}"
        rows.append(
            (file.status, file.language, str(file.additions), str(file.deletions),
             str(len(file.hunks)), review, file.filename)
        )

    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]) - 1)]
    for row in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row[:-1])) + "  " + row[-1])

    skipped = Counter(str(f.skip_reason) for f in pr.skipped_files)
    skipped_text = ", ".join(f"{count} {reason}" for reason, count in skipped.items()) or "none"
    print(
        f"\n{len(pr.reviewable_files)} of {len(pr.files)} files will be reviewed "
        f"in {total_chunks} chunk{'s' if total_chunks != 1 else ''} · skipped: {skipped_text}"
    )


def _print_file(file: FileDiff) -> None:
    print(f"\n{file.filename}")
    markers = {LineType.ADD: "+", LineType.DELETE: "-", LineType.CONTEXT: " "}
    for hunk in file.hunks:
        print(hunk.header)
        for line in hunk.lines:
            old = str(line.old_line) if line.old_line is not None else ""
            new = str(line.new_line) if line.new_line is not None else ""
            print(f"{old:>5} {new:>5} {markers[line.type]} {line.content}")


if __name__ == "__main__":
    raise SystemExit(main())
