from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ServicesDep, SessionDep
from app.github.client import GitHubAuthError, GitHubError, GitHubNotFoundError, GitHubRateLimitError
from app.github.urls import InvalidRepoReference, parse_repo_reference
from app.models import Repository, utcnow
from app.schemas import RepositoryCreate, RepositoryOut
from app.security import token_hint
from app.services.views import repositories_with_stats

router = APIRouter(prefix="/api/repos", tags=["repositories"])


@router.post(
    "",
    response_model=RepositoryOut,
    status_code=201,
    summary="Track a repository",
    responses={
        200: {"description": "Already tracked; metadata (and token, if given) updated"},
        400: {"description": "GitHub rejected the token"},
        404: {"description": "Repository not found or not visible with this token"},
    },
)
async def track_repository(
    body: RepositoryCreate, response: Response, services: ServicesDep, session: SessionDep
) -> RepositoryOut:
    """Validates the repository against GitHub before storing it. A token is encrypted
    (Fernet) before it reaches the database and is never returned, responses only say
    whether one is stored and show its last four characters."""
    try:
        owner, name = parse_repo_reference(body.repository)
    except InvalidRepoReference as exc:
        raise HTTPException(422, str(exc)) from exc

    token = body.github_token.get_secret_value().strip() if body.github_token else None
    try:
        async with services.github(token or services.settings.github_token_value) as client:
            data = await client.get_repository(owner, name)
    except GitHubNotFoundError as exc:
        raise HTTPException(
            404, "Repository not found on GitHub. Private repositories need a token with read access."
        ) from exc
    except GitHubAuthError as exc:
        raise HTTPException(400, "GitHub rejected that token.") from exc
    except GitHubRateLimitError as exc:
        raise HTTPException(429, str(exc)) from exc
    except GitHubError as exc:
        raise HTTPException(502, f"GitHub: {exc}") from exc

    full_name = data.get("full_name") or f"{owner}/{name}"
    repository = await session.scalar(select(Repository).where(Repository.full_name_key == full_name.lower()))
    created = repository is None
    if repository is None:
        repository = Repository(full_name_key=full_name.lower(), created_at=utcnow())
        session.add(repository)

    repository.owner = (data.get("owner") or {}).get("login", owner)
    repository.name = data.get("name", name)
    repository.full_name = full_name
    repository.html_url = data.get("html_url") or f"https://github.com/{full_name}"
    repository.description = data.get("description")
    repository.language = data.get("language")
    repository.stars = data.get("stargazers_count") or 0
    repository.is_private = bool(data.get("private"))
    repository.default_branch = data.get("default_branch")
    if token:
        repository.encrypted_token = services.cipher.encrypt(token)
        repository.token_hint = token_hint(token)
    await session.commit()

    response.status_code = 201 if created else 200
    [result] = await repositories_with_stats(session, [repository])
    return result


@router.get("", response_model=list[RepositoryOut], summary="List tracked repositories, most recently reviewed first")
async def list_repositories(session: SessionDep) -> list[RepositoryOut]:
    repositories = (await session.scalars(select(Repository))).all()
    results = await repositories_with_stats(session, list(repositories))
    return sorted(
        results,
        key=lambda repo: (repo.last_reviewed_at or repo.created_at).timestamp(),
        reverse=True,
    )


@router.get("/{repository_id}", response_model=RepositoryOut, summary="Get one tracked repository")
async def get_repository(repository_id: int, session: SessionDep) -> RepositoryOut:
    [result] = await repositories_with_stats(session, [await _repository_or_404(session, repository_id)])
    return result


@router.delete("/{repository_id}", status_code=204, summary="Stop tracking a repository")
async def delete_repository(repository_id: int, session: SessionDep) -> Response:
    """Removes the repository and its stored token. Past reviews are kept."""
    await session.delete(await _repository_or_404(session, repository_id))
    await session.commit()
    return Response(status_code=204)


async def _repository_or_404(session: AsyncSession, repository_id: int) -> Repository:
    repository = await session.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(404, "Repository not found.")
    return repository
