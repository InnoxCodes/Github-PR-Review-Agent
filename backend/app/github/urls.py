import re
from dataclasses import dataclass

_OWNER = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})"
_REPO = r"[A-Za-z0-9._-]+"

_WEB_URL = re.compile(
    rf"^(?:https?://)?(?:www\.)?github\.com/(?P<owner>{_OWNER})/(?P<repo>{_REPO})"
    r"/pull/(?P<number>\d+)(?:[/?#].*)?$",
    re.IGNORECASE,
)
_API_URL = re.compile(
    rf"^https?://api\.github\.com/repos/(?P<owner>{_OWNER})/(?P<repo>{_REPO})"
    r"/pulls/(?P<number>\d+)/?$",
    re.IGNORECASE,
)
_SHORTHAND = re.compile(rf"^(?P<owner>{_OWNER})/(?P<repo>{_REPO})(?:#|/pull/)(?P<number>\d+)$")


_REPO_URL = re.compile(
    rf"^(?:https?://)?(?:www\.)?github\.com/(?P<owner>{_OWNER})/(?P<repo>{_REPO})(?:[/?#].*)?$",
    re.IGNORECASE,
)
_REPO_SHORTHAND = re.compile(rf"^(?P<owner>{_OWNER})/(?P<repo>{_REPO})$")


class InvalidPRReference(ValueError):
    pass


class InvalidRepoReference(ValueError):
    pass


def parse_repo_reference(value: str) -> tuple[str, str]:
    """Accept owner/name or any github.com URL inside a repository."""
    text = value.strip()
    for pattern in (_REPO_URL, _REPO_SHORTHAND):
        match = pattern.match(text)
        if match:
            repo = match["repo"].removesuffix(".git")
            if repo not in {"", ".", ".."}:
                return match["owner"], repo
    raise InvalidRepoReference(
        f"Not a GitHub repository: {value!r}. Expected owner/name or https://github.com/owner/name."
    )


@dataclass(frozen=True)
class PRRef:
    owner: str
    repo: str
    number: int

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.repo}"

    @property
    def html_url(self) -> str:
        return f"https://github.com/{self.full_name}/pull/{self.number}"

    def __str__(self) -> str:
        return f"{self.full_name}#{self.number}"


def parse_pr_reference(value: str) -> PRRef:
    """Accept a PR web URL (incl. /files, query, anchors), an API URL, or owner/repo#123."""
    text = value.strip()
    for pattern in (_WEB_URL, _API_URL, _SHORTHAND):
        match = pattern.match(text)
        if not match:
            continue
        repo = match["repo"].removesuffix(".git")
        number = int(match["number"])
        if number < 1 or repo in {"", ".", ".."}:
            break
        return PRRef(owner=match["owner"], repo=repo, number=number)

    raise InvalidPRReference(
        f"Not a GitHub pull request reference: {value!r}. "
        "Expected something like https://github.com/owner/repo/pull/123 or owner/repo#123."
    )
