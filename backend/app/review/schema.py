"""The contract between ReviewMind and the model: what one chunk review must look like.

Two representations of the same contract live here on purpose:

* ``CHUNK_REVIEW_SCHEMA`` — the JSON Schema sent to the provider's structured-output
  feature. It is constrained decoding, so the model *cannot* emit a different shape.
  It deliberately avoids keywords structured outputs don't support (minLength, minimum…).
* ``ChunkReview`` / ``Finding`` — Pydantic models that re-validate whatever comes back.
  Constrained decoding removes malformed JSON, but not truncated output, refusals,
  providers without schema enforcement, or values that are well-typed yet wrong
  (a line number that isn't in the diff). Defence in depth, not redundancy.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Severity = Literal["critical", "warning", "info"]
Category = Literal["bug", "security", "performance", "missing-test", "complexity", "style"]
Confidence = Literal["high", "medium", "low"]

SEVERITIES: tuple[Severity, ...] = ("critical", "warning", "info")
CATEGORIES: tuple[Category, ...] = ("bug", "security", "performance", "missing-test", "complexity", "style")

MAX_TITLE_CHARS = 120
MAX_COMMENT_CHARS = 2000
MAX_FIX_CHARS = 4000


def _nullable(schema: dict) -> dict:
    return {"anyOf": [schema, {"type": "null"}]}


# Property order matters: the model writes the explanation before it commits to a
# severity and confidence, so the verdict is conditioned on its own reasoning.
FINDING_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "line_number": {
            "type": "integer",
            "description": "Line in the NEW version of the file this comment anchors to. Must be a numbered line shown in the diff.",
        },
        "end_line": _nullable(
            {"type": "integer", "description": "Last line of a multi-line range, or null for a single line."}
        ),
        "category": {"type": "string", "enum": list(CATEGORIES)},
        "title": {"type": "string", "description": "Headline under 80 characters, e.g. 'SQL query built from user input'."},
        "comment": {
            "type": "string",
            "description": "2-4 sentences: what is wrong, why it matters, and when it would fail.",
        },
        "suggested_fix": _nullable(
            {
                "type": "string",
                "description": "Drop-in replacement code for line_number..end_line, without markdown fences. Null if no concrete fix.",
            }
        ),
        "severity": {"type": "string", "enum": list(SEVERITIES)},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    },
    "required": ["line_number", "end_line", "category", "title", "comment", "suggested_fix", "severity", "confidence"],
}

CHUNK_REVIEW_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {
            "type": "string",
            "description": "One or two sentences describing what this change does and its overall risk.",
        },
        "findings": {"type": "array", "items": FINDING_SCHEMA},
    },
    "required": ["summary", "findings"],
}


class Finding(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    line_number: int
    end_line: int | None = None
    category: Category
    title: str = Field(min_length=1)
    comment: str = Field(min_length=1)
    suggested_fix: str | None = None
    severity: Severity
    confidence: Confidence = "medium"

    @field_validator("title")
    @classmethod
    def _clip_title(cls, value: str) -> str:
        return value[:MAX_TITLE_CHARS]

    @field_validator("comment")
    @classmethod
    def _clip_comment(cls, value: str) -> str:
        return value[:MAX_COMMENT_CHARS]

    @field_validator("suggested_fix")
    @classmethod
    def _clean_fix(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = _strip_markdown_fence(value)
        return value[:MAX_FIX_CHARS] if value.strip() else None


class ChunkReview(BaseModel):
    summary: str
    findings: list[Finding]


def _strip_markdown_fence(code: str) -> str:
    # Even with the schema saying "no fences", models occasionally wrap fixes in ```lang.
    lines = code.strip("\n").split("\n")
    if len(lines) >= 2 and lines[0].lstrip().startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1])
    return code.strip("\n")
