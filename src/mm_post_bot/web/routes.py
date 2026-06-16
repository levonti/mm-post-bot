from datetime import UTC, datetime
from html import escape
from secrets import token_urlsafe
from typing import Annotated, cast

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from ..commands.context import CommandContext
from ..db import DbConn
from ..i18n import FALLBACK_LOCALE, normalize_locale, translate
from ..mm_client import MattermostClient
from ..repository import DraftCaptureRepo, UserPreferenceRepo
from ..services.web_auth import WebSession, hash_login_token, sign_session
from .deps import SESSION_COOKIE, repos, settings

router = APIRouter()


def _default_locale(request: Request) -> str:
    return normalize_locale(settings(request).default_locale) or FALLBACK_LOCALE


def _session_locale(request: Request, session: WebSession) -> str:
    conn = cast(DbConn, request.app.state.conn)
    user_preference_repo = UserPreferenceRepo(conn)
    return user_preference_repo.get_locale(session.user_id) or _default_locale(request)


def _web_error(request: Request, session: WebSession | None, key: str, **params: object) -> str:
    locale = _session_locale(request, session) if session is not None else _default_locale(request)
    return translate(locale, f"web.error.{key}", **params)


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
        draft_attachment_repo=repo_set.draft_attachments,
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


def _optional_alias(value: str) -> str | None:
    normalized = value.strip()
    return normalized or None


@router.get("/login-required")
def login_required(request: Request) -> Response:
    locale = _default_locale(request)
    title = translate(locale, "web.login_required.title")
    content = translate(locale, "web.login_required.content")
    return HTMLResponse(
        "\n".join(
            [
                "<!doctype html>",
                f'<html lang="{escape(locale)}">',
                "<head>",
                '<meta charset="utf-8">',
                '<meta name="viewport" content="width=device-width, initial-scale=1">',
                f"<title>{escape(title)}</title>",
                "</head>",
                "<body>",
                f"<main><h1>{escape(title)}</h1><p>{escape(content)}</p></main>",
                "</body>",
                "</html>",
            ]
        ),
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
        raise HTTPException(status_code=400, detail=_web_error(request, None, "login_invalid"))

    user = repo_set.users.get(login_token.owner_user_id)
    if user.status != "approved":
        raise HTTPException(status_code=403, detail=_web_error(request, None, "user_not_approved"))

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
