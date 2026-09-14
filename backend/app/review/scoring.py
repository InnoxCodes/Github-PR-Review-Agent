"""PR health score: one 0-100 number summarising how much the review found.

Design, so it can be defended:

* **Critical findings are absolute.** A SQL injection is disqualifying whether it sits in a
  5-line PR or a 5,000-line one, so each critical costs a fixed number of points.
* **Everything else is density-based.** Ten style nits across 2,000 changed lines is a tidy
  PR; ten in 20 lines is not. Non-critical penalties are divided by a size factor that grows
  with the square root of changed lines, so big PRs aren't punished merely for being big.
* **Category and confidence shift the weight.** A security warning matters more than a style
  warning; a low-confidence finding counts half, since it is more likely a false positive.
* **Only live findings count.** Dismissed and false-positive findings are excluded, so the
  score reacts as the developer triages.
"""

import math
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

SEVERITY_POINTS = {"critical": 18.0, "warning": 6.0, "info": 1.5}
CATEGORY_WEIGHT = {
    "security": 1.5,
    "bug": 1.25,
    "performance": 1.0,
    "missing-test": 0.8,
    "complexity": 0.8,
    "style": 0.5,
}
CONFIDENCE_WEIGHT = {"high": 1.0, "medium": 0.8, "low": 0.5}

Grade = Literal["healthy", "needs_attention", "at_risk"]


@dataclass(frozen=True)
class ScoredIssue:
    severity: str
    category: str
    confidence: str = "medium"


def health_score(issues: Iterable[ScoredIssue], changed_lines: int) -> int:
    size_factor = max(1.0, math.sqrt(max(changed_lines, 0) / 100))
    absolute = 0.0
    density = 0.0
    for issue in issues:
        points = (
            SEVERITY_POINTS.get(issue.severity, 0.0)
            * CATEGORY_WEIGHT.get(issue.category, 1.0)
            * CONFIDENCE_WEIGHT.get(issue.confidence, 1.0)
        )
        if issue.severity == "critical":
            absolute += points
        else:
            density += points
    score = 100.0 - absolute - density / size_factor
    return round(min(100.0, max(0.0, score)))


def grade(score: int | None) -> Grade | None:
    if score is None:
        return None
    if score >= 80:
        return "healthy"
    if score >= 50:
        return "needs_attention"
    return "at_risk"
