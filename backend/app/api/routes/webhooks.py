import hashlib
import hmac
import json
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request, Response
from sqlalchemy import select

from app.api.deps import ServicesDep, SessionDep
from app.github.urls import PRRef
from app.models import Repository
from app.services.review_service import start_review

router = APIRouter(prefix="/api/github", tags=["github"])

TRIGGER_ACTIONS = frozenset({"opened", "reopened", "synchronize", "ready_for_review"})


@router.post(
    "/webhook",
    status_code=202,
    summary="GitHub webhook: review new and updated pull requests automatically",
    responses={
        200: {"description": "Delivery accepted but ignored (with a reason)"},
        401: {"description": "Missing or invalid X-Hub-Signature-256"},
        503: {"description": "GITHUB_WEBHOOK_SECRET is not configured"},
    },
)
async def github_webhook(
    request: Request,
    response: Response,
    services: ServicesDep,
    session: SessionDep,
    x_github_event: Annotated[str, Header()],
    x_hub_signature_256: Annotated[str | None, Header()] = None,
) -> dict:
    """Configure a webhook on a tracked repository with the `pull_request` event and the
    same secret as `GITHUB_WEBHOOK_SECRET`. Deliveries are authenticated with HMAC-SHA256
    over the raw body; unsigned deliveries are always rejected."""
    secret = services.settings.github_webhook_secret
    if secret is None or not secret.get_secret_value():
        raise HTTPException(503, "Set GITHUB_WEBHOOK_SECRET to accept GitHub webhooks.")

    body = await request.body()
    expected = "sha256=" + hmac.new(secret.get_secret_value().encode(), body, hashlib.sha256).hexdigest()
    if not x_hub_signature_256 or not hmac.compare_digest(expected, x_hub_signature_256):
        raise HTTPException(401, "Invalid webhook signature.")

    response.status_code = 200
    if x_github_event == "ping":
        return {"status": "pong"}
    if x_github_event != "pull_request":
        return {"status": "ignored", "reason": f"'{x_github_event}' events are not handled"}

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(400, "Webhook body is not JSON.") from exc

    action = payload.get("action")
    pull_request = payload.get("pull_request") or {}
    full_name = (payload.get("repository") or {}).get("full_name", "")
    if action not in TRIGGER_ACTIONS:
        return {"status": "ignored", "reason": f"action '{action}' does not trigger a review"}
    if pull_request.get("draft"):
        return {"status": "ignored", "reason": "draft pull requests are not reviewed"}

    repository = await session.scalar(select(Repository).where(Repository.full_name_key == full_name.lower()))
    if repository is None:
        return {"status": "ignored", "reason": f"{full_name or 'this repository'} is not tracked"}
    if not services.llm_status().configured:
        return {"status": "ignored", "reason": "no LLM provider is configured"}

    ref = PRRef(repository.owner, repository.name, int(pull_request["number"]))
    review, created = await start_review(session, services, ref)
    response.status_code = 202
    return {"status": "queued" if created else "already_running", "review_id": review.id}
