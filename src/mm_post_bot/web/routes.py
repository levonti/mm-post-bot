from datetime import UTC, datetime
from pathlib import Path
from secrets import token_urlsafe
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from ..commands.context import CommandContext
from ..db import DbConn
from ..i18n import FALLBACK_LOCALE, normalize_locale
from ..mm_client import MattermostClient
from ..repository import DraftCaptureRepo, PostDraft, UserPreferenceRepo
from ..services.posting import (
    PublishDraftRequest,
    PublishError,
    TargetRequest,
    create_draft,
    publish_draft,
    update_draft_message,
)
from ..services.web_auth import WebSession, hash_login_token, sign_session
from .deps import SESSION_COOKIE, csrf_token, current_session, repos, require_csrf, settings

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


def _command_context(request: Request, session: WebSession) -> CommandContext:
    cfg = settings(request)
    repo_set = repos(request)
    conn = cast(DbConn, request.app.state.conn)
    user_preference_repo = UserPreferenceRepo(conn)
    default_locale = normalize_locale(cfg.default_locale) or FALLBACK_LOCALE
    locale = user_preference_repo.get_locale(session.user_id) or default_locale
    return CommandContext(
        caller_user_id=session.user_id,
        caller_username=session.username,
        channel_id="",
        channel_type=None,
        user_repo=repo_set.users,
        user_preference_repo=user_preference_repo,
        user_bot_repo=repo_set.user_bots,
        user_channel_repo=repo_set.user_channels,
        user_post_default_repo=repo_set.user_post_defaults,
        draft_capture_repo=DraftCaptureRepo(conn),
        post_draft_repo=repo_set.post_drafts,
        web_login_token_repo=repo_set.web_login_tokens,
        audit_repo=repo_set.audits,
        manager_mm=MattermostClient(
            cfg.mm_rest_base,
            cfg.mm_bot_token,
            verify_ssl=cfg.mm_verify_ssl,
        ),
        manager_user_id="",
        admin_usernames=frozenset(cfg.admin_usernames),
        mm_rest_base=cfg.mm_rest_base,
        mm_url=str(cfg.mm_url).rstrip("/"),
        token_encryption_key=cfg.token_encryption_key,
        mm_verify_ssl=cfg.mm_verify_ssl,
        web_base_url=str(cfg.web_base_url).rstrip("/"),
        web_login_token_ttl_seconds=cfg.web_login_token_ttl_seconds,
        default_locale=default_locale,
        locale=locale,
    )


def _draft_or_404(request: Request, session: WebSession, draft_id: int) -> PostDraft:
    try:
        draft = repos(request).post_drafts.get_for_owner(session.user_id, draft_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Draft not found") from exc
    if draft.status != "draft":
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft


def _optional_alias(value: str) -> str | None:
    normalized = value.strip()
    return normalized or None


@router.get("/login-required")
def login_required(request: Request) -> Response:
    return templates.TemplateResponse(
        request=request,
        name="base.html",
        context={
            "title": "Login required",
            "session": None,
            "content": "Open a fresh login link from Mattermost to use the web composer.",
        },
        status_code=401,
    )


@router.get("/login")
def login(request: Request, token: Annotated[str, Query(min_length=1)]) -> Response:
    cfg = settings(request)
    repo_set = repos(request)
    login_token = repo_set.web_login_tokens.consume(
        hash_login_token(token),
        now=datetime.now(UTC),
    )
    if login_token is None:
        raise HTTPException(status_code=400, detail="Login link is invalid or expired")

    user = repo_set.users.get(login_token.owner_user_id)
    if user.status != "approved":
        raise HTTPException(status_code=403, detail="User is not approved")

    cookie_value = sign_session(
        cfg.web_session_secret.get_secret_value(),
        user_id=user.user_id,
        username=user.username,
        csrf_nonce=token_urlsafe(32),
    )
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        SESSION_COOKIE,
        cookie_value,
        max_age=cfg.web_session_max_age_seconds,
        httponly=True,
        secure=cfg.web_cookie_secure,
        samesite="lax",
    )
    return response


@router.get("/")
def home(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
    csrf: Annotated[str, Depends(csrf_token)],
) -> Response:
    return templates.TemplateResponse(
        request=request,
        name="composer.html",
        context={
            "title": "Composer",
            "session": session,
            "csrf_token": csrf,
            "active_page": "composer",
            "draft_message": "",
        },
    )


@router.post("/drafts")
async def save_draft(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
    message: Annotated[str, Form(...)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> Response:
    ctx = _command_context(request, session)
    try:
        create_draft(ctx, message)
    finally:
        await ctx.manager_mm.aclose()
    return RedirectResponse("/drafts", status_code=303)


@router.get("/drafts")
def draft_list(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
) -> Response:
    drafts = repos(request).post_drafts.list_for_owner(session.user_id)
    return templates.TemplateResponse(
        request=request,
        name="drafts.html",
        context={
            "title": "Drafts",
            "session": session,
            "active_page": "drafts",
            "drafts": drafts,
        },
    )


@router.get("/audit")
def audit(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
) -> Response:
    records = repos(request).audits.list_for_user(session.user_id, limit=50)
    return templates.TemplateResponse(
        request=request,
        name="audit.html",
        context={
            "title": "Audit",
            "session": session,
            "active_page": "audit",
            "records": records,
        },
    )


@router.get("/targets")
def targets(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
    csrf: Annotated[str, Depends(csrf_token)],
) -> Response:
    repo_set = repos(request)
    default = repo_set.user_post_defaults.get_for_owner(session.user_id)
    stale_default = default is None and repo_set.user_post_defaults.has_for_owner(session.user_id)
    return templates.TemplateResponse(
        request=request,
        name="targets.html",
        context={
            "title": "Targets",
            "session": session,
            "csrf_token": csrf,
            "active_page": "targets",
            "bots": repo_set.user_bots.list_for_owner(session.user_id),
            "channels": repo_set.user_channels.list_for_owner(session.user_id),
            "default": default,
            "stale_default": stale_default,
        },
    )


@router.post("/targets/default")
def set_default_target(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
    bot_alias: Annotated[str, Form(...)],
    channel_alias: Annotated[str, Form(...)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> Response:
    repos(request).user_post_defaults.set_for_owner(
        session.user_id,
        bot_alias=bot_alias,
        channel_alias=channel_alias,
    )
    return RedirectResponse("/targets", status_code=303)


@router.post("/targets/default/clear")
def clear_default_target(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> Response:
    repos(request).user_post_defaults.clear_for_owner(session.user_id)
    return RedirectResponse("/targets", status_code=303)


@router.get("/drafts/{draft_id}")
def draft_detail(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
    csrf: Annotated[str, Depends(csrf_token)],
    draft_id: int,
) -> Response:
    draft = _draft_or_404(request, session, draft_id)
    return templates.TemplateResponse(
        request=request,
        name="draft_detail.html",
        context={
            "title": f"Draft {draft.id}",
            "session": session,
            "active_page": "drafts",
            "csrf_token": csrf,
            "draft": draft,
        },
    )


@router.post("/drafts/{draft_id}")
async def update_draft(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
    draft_id: int,
    message: Annotated[str, Form(...)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> Response:
    ctx = _command_context(request, session)
    try:
        update_draft_message(ctx, draft_id, message)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Draft not found") from exc
    finally:
        await ctx.manager_mm.aclose()
    return RedirectResponse(f"/drafts/{draft_id}", status_code=303)


@router.post("/drafts/{draft_id}/publish")
async def publish_draft_from_web(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
    draft_id: int,
    _csrf: Annotated[None, Depends(require_csrf)],
    bot_alias: Annotated[str, Form()] = "",
    channel_alias: Annotated[str, Form()] = "",
) -> Response:
    ctx = _command_context(request, session)
    try:
        await publish_draft(
            ctx,
            PublishDraftRequest(
                draft_id=draft_id,
                target=TargetRequest(
                    bot_alias=_optional_alias(bot_alias),
                    channel_alias=_optional_alias(channel_alias),
                ),
            ),
        )
    except PublishError as exc:
        raise HTTPException(status_code=400, detail=exc.code) from exc
    finally:
        await ctx.manager_mm.aclose()
    return RedirectResponse("/audit", status_code=303)


@router.post("/drafts/{draft_id}/delete")
def delete_draft(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
    draft_id: int,
    _csrf: Annotated[None, Depends(require_csrf)],
) -> Response:
    _draft_or_404(request, session, draft_id)
    repos(request).post_drafts.soft_delete(session.user_id, draft_id)
    return RedirectResponse("/drafts", status_code=303)
