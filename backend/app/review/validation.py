"""Turn a raw model response into trusted findings, or a precise reason to retry.

Failures are split into two tiers, because they deserve different reactions:

* **Fatal** (``InvalidReviewOutput``): the response as a whole is unusable, not JSON,
  wrong top-level shape, cut off by the token limit, or every finding malformed. The
  engine retries, feeding this error message back to the model so it can correct itself.
* **Per-finding**: one finding is broken (bad enum value, a line that isn't in the diff).
  It is dropped and recorded, and the rest are kept. Throwing away five good findings
  because a sixth pointed at a deleted line would make the reviewer worse, not safer.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from app.diff.models import FileChunk, LineType
from app.review.schema import SEVERITIES, ChunkReview, Finding

# How far (in lines) a finding may be moved to land on a line that exists in the diff.
LINE_SNAP_DISTANCE = 3
MAX_FINDINGS_PER_CHUNK = 25

_FENCED_JSON = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)


class InvalidReviewOutput(ValueError):
    pass


@dataclass
class ValidatedReview:
    summary: str
    findings: list[Finding]
    dropped: list[str] = field(default_factory=list)
    adjusted: list[str] = field(default_factory=list)


def extract_json_object(text: str) -> dict[str, Any]:
    """Parse the model's JSON, tolerating wrapper noise that some providers/modes add."""
    stripped = text.strip()
    if not stripped:
        raise InvalidReviewOutput("The response was empty. Return a JSON object with 'summary' and 'findings'.")

    candidates = [stripped]
    if fenced := _FENCED_JSON.search(stripped):
        candidates.append(fenced.group(1))
    start, end = stripped.find("{"), stripped.rfind("}")
    if 0 <= start < end:
        candidates.append(stripped[start : end + 1])

    last_error: json.JSONDecodeError | None = None
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc
            continue
        if not isinstance(data, dict):
            raise InvalidReviewOutput("The top-level JSON value must be an object with 'summary' and 'findings'.")
        return data

    detail = f" ({last_error.msg} at line {last_error.lineno}, column {last_error.colno})" if last_error else ""
    raise InvalidReviewOutput(f"The response was not valid JSON{detail}. Return only the JSON object.")


def validate_chunk_review(text: str, chunk: FileChunk, *, truncated: bool = False) -> ValidatedReview:
    if truncated:
        raise InvalidReviewOutput(
            "The response was cut off by the output token limit. Report fewer, higher-value "
            "findings with shorter comments so the JSON is complete."
        )

    data = extract_json_object(text)
    raw_findings = data.get("findings")
    if not isinstance(raw_findings, list):
        raise InvalidReviewOutput("'findings' must be an array (use [] when there are no issues).")

    summary = data.get("summary")
    summary = summary.strip() if isinstance(summary, str) else ""

    anchorable = _anchorable_lines(chunk)
    result = ValidatedReview(summary=summary, findings=[])
    seen: set[tuple[int, str, str]] = set()

    for index, raw in enumerate(raw_findings):
        try:
            finding = Finding.model_validate(raw)
        except ValidationError as exc:
            result.dropped.append(f"finding {index}: {_first_error(exc)}")
            continue

        anchored = _anchor(finding, anchorable)
        if anchored is None:
            result.dropped.append(
                f"finding {index} ('{finding.title}'): line {finding.line_number} is not in this diff"
            )
            continue
        if anchored.line_number != finding.line_number:
            result.adjusted.append(
                f"'{finding.title}': moved from line {finding.line_number} to {anchored.line_number}"
            )

        key = (anchored.line_number, anchored.category, anchored.title.lower())
        if key in seen:
            continue
        seen.add(key)
        result.findings.append(anchored)

    if raw_findings and not result.findings and len(result.dropped) == len(raw_findings):
        problems = "; ".join(result.dropped[:5])
        raise InvalidReviewOutput(f"None of the findings were valid: {problems}.")

    if len(result.findings) > MAX_FINDINGS_PER_CHUNK:
        rank = {severity: i for i, severity in enumerate(SEVERITIES)}
        result.findings.sort(key=lambda f: (rank[f.severity], f.line_number))
        result.dropped.extend(f"'{f.title}': over the per-chunk limit" for f in result.findings[MAX_FINDINGS_PER_CHUNK:])
        result.findings = sorted(result.findings[:MAX_FINDINGS_PER_CHUNK], key=lambda f: f.line_number)

    return result


def correction_prompt(error: InvalidReviewOutput) -> str:
    return (
        f"Your previous response could not be used: {error} "
        "Respond again with the complete review as a single JSON object that follows the schema exactly."
    )


def _anchorable_lines(chunk: FileChunk) -> list[int]:
    return sorted(
        {
            line.new_line
            for hunk in chunk.hunks
            for line in hunk.lines
            if line.type is not LineType.DELETE and line.new_line is not None
        }
    )


def _anchor(finding: Finding, anchorable: list[int]) -> Finding | None:
    """Snap a finding onto a line that exists in the diff, or reject it.

    Models reliably get *near* the right line but occasionally land one or two off, or on a
    deleted line (which has no new-file number). A short snap keeps those comments; anything
    further away is more likely a hallucinated location than an off-by-one.
    """
    if not anchorable:
        return None
    line = _nearest(finding.line_number, anchorable)
    if line is None:
        return None

    end_line = finding.end_line
    if end_line is not None:
        end_line = _nearest(end_line, anchorable)
        if end_line is None or end_line <= line:
            end_line = None

    if line == finding.line_number and end_line == finding.end_line:
        return finding
    return finding.model_copy(update={"line_number": line, "end_line": end_line})


def _nearest(target: int, anchorable: list[int]) -> int | None:
    best = min(anchorable, key=lambda candidate: (abs(candidate - target), candidate))
    return best if abs(best - target) <= LINE_SNAP_DISTANCE else None


def _first_error(exc: ValidationError) -> str:
    error = exc.errors()[0]
    location = ".".join(str(part) for part in error["loc"]) or "value"
    return f"{location}: {error['msg']}"
