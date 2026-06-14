from datetime import UTC, datetime
from pathlib import Path
from secrets import token_urlsafe
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from ..services.web_auth import WebSession, hash_login_token, sign_session
from .deps import SESSION_COOKIE, csrf_token, current_session, repos, settings

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


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
