import httpx
import pytest
import respx

from app.diff.models import FileStatus, SkipReason
from app.github.client import (
    GitHubAuthError,
    GitHubClient,
    GitHubError,
    GitHubNotFoundError,
    GitHubRateLimitError,
)
from app.github.urls import PRRef
from app.services.pr_loader import load_pull_request

API = "https://api.github.com"
REF = PRRef("octo", "widgets", 7)
PR_PATH = "/repos/octo/widgets/pulls/7"
CODE_PATCH = "@@ -1,3 +1,4 @@\n import os\n-x = 1\n+x = 2\n+y = 3\n print(x)"


def pr_payload(**overrides):
    payload = {
        "number": 7,
        "title": "Add widget cache",
        "body": None,
        "state": "open",
        "draft": False,
        "merged": False,
        "html_url": "https://github.com/octo/widgets/pull/7",
        "user": {"login": "mona", "avatar_url": "https://avatars.example/mona", "html_url": "https://github.com/mona"},
        "base": {"ref": "main", "sha": "a" * 40, "repo": {"name": "widgets", "owner": {"login": "octo"}}},
        "head": {"ref": "feature/cache", "sha": "b" * 40},
        "created_at": "2026-09-01T10:00:00Z",
        "updated_at": "2026-09-02T12:30:00Z",
        "additions": 2,
        "deletions": 1,
        "changed_files": 1,
        "commits": 2,
    }
    payload.update(overrides)
    return payload


def file_payload(filename, *, status="modified", patch=CODE_PATCH, additions=2, deletions=1):
    item = {
        "filename": filename,
        "status": status,
        "additions": additions,
        "deletions": deletions,
        "changes": additions + deletions,
    }
    if patch is not None:
        item["patch"] = patch
    return item


@pytest.fixture
def github_api():
    with respx.mock(base_url=API, assert_all_called=False) as mock:
        yield mock


def mock_pr(github_api, files, pr=None):
    github_api.get(PR_PATH).mock(return_value=httpx.Response(200, json=pr or pr_payload()))
    return github_api.get(f"{PR_PATH}/files").mock(return_value=httpx.Response(200, json=files))


async def load(settings, token=None):
    async with GitHubClient(token) as client:
        return await load_pull_request(client, REF, settings)


async def test_metadata_is_normalised(github_api, settings):
    mock_pr(github_api, [file_payload("src/cache.py")])

    pr = await load(settings)

    meta = pr.metadata
    assert (meta.owner, meta.repo, meta.number) == ("octo", "widgets", 7)
    assert meta.body == ""
    assert meta.author.login == "mona"
    assert (meta.base_ref, meta.head_ref) == ("main", "feature/cache")
    assert meta.created_at.year == 2026


async def test_files_are_parsed_or_skipped_with_a_reason(github_api, settings):
    big_patch = "@@ -0,0 +1,60 @@\n" + "\n".join(f"+line {i}" for i in range(60))
    mock_pr(
        github_api,
        [
            file_payload("src/cache.py"),
            file_payload("package-lock.json", additions=400, deletions=300),
            file_payload("public/logo.png", patch=None, additions=0, deletions=0),
            file_payload("src/legacy.py", status="removed", patch="@@ -1 +0,0 @@\n-x", additions=0),
            file_payload("docs/guide.md"),
            file_payload("src/renamed.py", status="renamed", patch=None, additions=0, deletions=0),
            file_payload("src/huge_blob.py", patch=None, additions=9000, deletions=0),
            file_payload("src/generated_table.py", patch=big_patch, additions=60, deletions=0),
            file_payload("src/weird.py", patch="not a diff at all"),
        ],
    )

    pr = await load(settings)

    reasons = {f.filename: f.skip_reason for f in pr.files}
    assert reasons == {
        "src/cache.py": None,
        "package-lock.json": SkipReason.LOCKFILE,
        "public/logo.png": SkipReason.ASSET,
        "src/legacy.py": SkipReason.DELETED,
        "docs/guide.md": SkipReason.DOCS,
        "src/renamed.py": SkipReason.NO_CHANGES,
        "src/huge_blob.py": SkipReason.NO_PATCH,
        "src/generated_table.py": SkipReason.TOO_LARGE,
        "src/weird.py": SkipReason.UNPARSEABLE,
    }

    [code] = pr.reviewable_files
    assert code.language == "python"
    assert code.status is FileStatus.MODIFIED
    assert [line.new_line for line in code.hunks[0].lines] == [1, None, 2, 3, 4]
    assert all(f.hunks == [] for f in pr.skipped_files)


async def test_reviewable_files_beyond_the_limit_are_marked(github_api, settings):
    files = [file_payload("README.md")] + [file_payload(f"src/m{i}.py") for i in range(5)]
    mock_pr(github_api, files)

    pr = await load(settings)

    assert [f.filename for f in pr.reviewable_files] == ["src/m0.py", "src/m1.py", "src/m2.py"]
    assert [f.skip_reason for f in pr.files[4:]] == [SkipReason.FILE_LIMIT, SkipReason.FILE_LIMIT]


async def test_file_listing_follows_pagination(github_api, settings):
    page_two = f"{API}/repositories/99/pulls/7/files?per_page=100&page=2"
    github_api.get(PR_PATH).mock(return_value=httpx.Response(200, json=pr_payload()))
    first = github_api.get(f"{PR_PATH}/files").mock(
        return_value=httpx.Response(
            200,
            json=[file_payload("a.py")],
            headers={"Link": f'<{page_two}>; rel="next", <{page_two}>; rel="last"'},
        )
    )
    github_api.get("/repositories/99/pulls/7/files").mock(
        return_value=httpx.Response(200, json=[file_payload("b.py")])
    )

    pr = await load(settings)

    assert [f.filename for f in pr.files] == ["a.py", "b.py"]
    assert first.calls.last.request.url.params["per_page"] == "100"


async def test_token_is_sent_only_when_configured(github_api, settings):
    route = mock_pr(github_api, [file_payload("a.py")])

    await load(settings)
    assert "authorization" not in route.calls.last.request.headers

    await load(settings, token="ghp_example")
    assert route.calls.last.request.headers["authorization"] == "Bearer ghp_example"


@pytest.mark.parametrize(
    ("response", "error_type"),
    [
        (httpx.Response(404, json={"message": "Not Found"}), GitHubNotFoundError),
        (httpx.Response(401, json={"message": "Bad credentials"}), GitHubAuthError),
        (
            httpx.Response(
                403,
                json={"message": "API rate limit exceeded"},
                headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1789000000"},
            ),
            GitHubRateLimitError,
        ),
        (httpx.Response(500, json={"message": "boom"}), GitHubError),
    ],
)
async def test_github_errors_are_translated(github_api, settings, response, error_type):
    github_api.get(PR_PATH).mock(return_value=response)
    github_api.get(f"{PR_PATH}/files").mock(return_value=response)

    with pytest.raises(error_type) as caught:
        await load(settings)

    assert caught.value.status_code == response.status_code


async def test_rate_limit_error_carries_reset_time_and_token_hint(github_api, settings):
    limited = httpx.Response(
        403, json={"message": "API rate limit exceeded"},
        headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1789000000"},
    )
    github_api.get(PR_PATH).mock(return_value=limited)
    github_api.get(f"{PR_PATH}/files").mock(return_value=limited)

    with pytest.raises(GitHubRateLimitError) as caught:
        await load(settings)

    assert caught.value.reset_at is not None
    assert "GITHUB_TOKEN" in str(caught.value)


async def test_network_failure_becomes_github_error(github_api, settings):
    github_api.get(PR_PATH).mock(side_effect=httpx.ConnectError("dns failure"))
    github_api.get(f"{PR_PATH}/files").mock(side_effect=httpx.ConnectError("dns failure"))

    with pytest.raises(GitHubError, match="Could not reach"):
        await load(settings)
