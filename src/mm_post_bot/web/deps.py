from dataclasses import dataclass
from typing import Annotated, cast

from fastapi import Form, HTTPException, Request
from itsdangerous import BadSignature

from ..config import Settings
from ..db import DbConn
from ..repository import (
    AuditRepo,
    DraftAttachmentRepo,
    PostDraftRepo,
    UserBotRepo,
    UserChannelRepo,
    UserPostDefaultRepo,
    UserRepo,
    WebLoginTokenRepo,
)
from ..services.web_auth import (
    WebSession,
    csrf_token_for_session,
    load_session,
    verify_csrf_token,
)

SESSION_COOKIE = "mmpost_session"


@dataclass(frozen=True, slots=True)
class WebRepos:
    users: UserRepo
    web_login_tokens: WebLoginTokenRepo
    user_bots: UserBotRepo
    user_channels: UserChannelRepo
    user_post_defaults: UserPostDefaultRepo
    post_drafts: PostDraftRepo
    draft_attachments: DraftAttachmentRepo
    audits: AuditRepo


def settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def repos(request: Request) -> WebRepos:
    conn = cast(DbConn, request.app.state.conn)
    return WebRepos(
        users=UserRepo(conn),
        web_login_tokens=WebLoginTokenRepo(conn),
        user_bots=UserBotRepo(conn),
        user_channels=UserChannelRepo(conn),
        user_post_defaults=UserPostDefaultRepo(conn),
        post_drafts=PostDraftRepo(conn),
        draft_attachments=DraftAttachmentRepo(conn),
        audits=AuditRepo(conn),
    )


def current_session(request: Request) -> WebSession:
    cookie_value = request.cookies.get(SESSION_COOKIE)
    if cookie_value is None:
        raise HTTPException(status_code=303, headers={"Location": "/login-required"})

    cfg = settings(request)
    try:
        return load_session(
            cfg.web_session_secret.get_secret_value(),
            cookie_value,
            max_age_seconds=cfg.web_session_max_age_seconds,
        )
    except BadSignature as exc:
        raise HTTPException(status_code=303, headers={"Location": "/login-required"}) from exc


def csrf_token(request: Request) -> str:
    session = current_session(request)
    cfg = settings(request)
    return csrf_token_for_session(cfg.web_session_secret.get_secret_value(), session.csrf_nonce)


def require_csrf(request: Request, csrf: Annotated[str, Form(...)]) -> None:
    session = current_session(request)
    cfg = settings(request)
    if not verify_csrf_token(
        cfg.web_session_secret.get_secret_value(),
        session.csrf_nonce,
        csrf,
    ):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")
