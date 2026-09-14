from datetime import UTC, datetime
from typing import Any

import httpx

DEFAULT_API_URL = "https://api.github.com"
# GitHub's own ceiling for the PR files endpoint.
MAX_PR_FILES = 3000


class GitHubError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class GitHubNotFoundError(GitHubError):
    pass


class GitHubAuthError(GitHubError):
    pass


class GitHubRateLimitError(GitHubError):
    def __init__(self, message: str, status_code: int, reset_at: datetime | None):
        super().__init__(message, status_code)
        self.reset_at = reset_at


class GitHubClient:
    """Thin async wrapper over the few GitHub REST endpoints ReviewMind needs (read-only)."""

    def __init__(
        self,
        token: str | None = None,
        *,
        base_url: str = DEFAULT_API_URL,
        timeout: float = 20.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "ReviewMind",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self.authenticated = bool(token)
        self._http = httpx.AsyncClient(
            base_url=base_url,
            headers=headers,
            timeout=timeout,
            transport=transport,
            follow_redirects=True,
        )

    async def __aenter__(self) -> "GitHubClient":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()

    async def get_pull_request(self, owner: str, repo: str, number: int) -> dict[str, Any]:
        response = await self._get(f"/repos/{owner}/{repo}/pulls/{number}")
        return response.json()

    async def list_pull_request_files(
        self, owner: str, repo: str, number: int, *, max_files: int = MAX_PR_FILES
    ) -> list[dict[str, Any]]:
        url: str | None = f"/repos/{owner}/{repo}/pulls/{number}/files"
        params: dict[str, Any] | None = {"per_page": 100}
        files: list[dict[str, Any]] = []

        while url and len(files) < max_files:
            response = await self._get(url, params=params)
            files.extend(response.json())
            url = response.links.get("next", {}).get("url")
            # GitHub's "next" link already carries per_page/page in its query string.
            params = None

        return files[:max_files]

    async def get_repository(self, owner: str, repo: str) -> dict[str, Any]:
        response = await self._get(f"/repos/{owner}/{repo}")
        return response.json()

    async def _get(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        try:
            response = await self._http.get(url, params=params)
        except httpx.TimeoutException as exc:
            raise GitHubError("GitHub API request timed out.") from exc
        except httpx.HTTPError as exc:
            raise GitHubError(f"Could not reach the GitHub API: {exc}") from exc

        if response.is_success:
            return response
        raise self._error_for(response)

    def _error_for(self, response: httpx.Response) -> GitHubError:
        status = response.status_code
        detail = _error_message(response)

        if status == 401:
            return GitHubAuthError(
                "GitHub rejected the access token (401). Check it is valid and not expired.", status
            )

        rate_limited = status == 429 or (
            status == 403
            and (response.headers.get("x-ratelimit-remaining") == "0" or "rate limit" in detail.lower())
        )
        if rate_limited:
            reset = response.headers.get("x-ratelimit-reset", "")
            reset_at = datetime.fromtimestamp(int(reset), tz=UTC) if reset.isdigit() else None
            hint = "" if self.authenticated else " Add a GITHUB_TOKEN to raise the limit to 5,000/hour."
            return GitHubRateLimitError(f"GitHub API rate limit exceeded.{hint}", status, reset_at)

        if status == 404:
            return GitHubNotFoundError(
                "Not found on GitHub. Check the URL — if the repository is private, "
                "the token needs read access to it.",
                status,
            )

        return GitHubError(f"GitHub API error {status}: {detail}", status)


def _error_message(response: httpx.Response) -> str:
    try:
        return str(response.json().get("message", response.text))
    except ValueError:
        return response.text
