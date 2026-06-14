from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from secrets import token_urlsafe
from typing import Annotated, Any, cast
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from ..commands.context import CommandContext
from ..db import DbConn
from ..i18n import FALLBACK_LOCALE, SUPPORTED_LOCALES, normalize_locale, translate
from ..mm_client import MattermostClient, MattermostError
from ..repository import DraftCaptureRepo, PostDraft, UserPreferenceRepo
from ..services.posting import (
    DraftMessageEmpty,
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
WEB_LOCALES = tuple(sorted(SUPPORTED_LOCALES))


def _default_locale(request: Request) -> str:
    return normalize_locale(settings(request).default_locale) or FALLBACK_LOCALE


def _session_locale(request: Request, session: WebSession) -> str:
    conn = cast(DbConn, request.app.state.conn)
    user_preference_repo = UserPreferenceRepo(conn)
    return user_preference_repo.get_locale(session.user_id) or _default_locale(request)


def _translator(locale: str) -> Callable[..., str]:
    def t(key: str, **params: Any) -> str:
        return translate(locale, key, **params)

    return t


def _safe_next_path(next_path: str) -> str:
    if not next_path.startswith("/") or next_path.startswith("//"):
        return "/"
    return next_path


def _request_path(request: Request) -> str:
    path = request.url.path
    if request.url.query:
        return f"{path}?{request.url.query}"
    return path


def _base_context(
    request: Request,
    *,
    locale: str,
    title_key: str,
    title_params: dict[str, Any] | None = None,
    session: WebSession | None = None,
    csrf: str | None = None,
    active_page: str | None = None,
) -> dict[str, Any]:
    t = _translator(locale)
    return {
        "title": t(title_key, **(title_params or {})),
        "session": session,
        "csrf_token": csrf,
        "active_page": active_page,
        "locale": locale,
        "supported_locales": WEB_LOCALES,
        "current_path": _request_path(request),
        "error_message": None,
        "success_message": None,
        "t": t,
    }


def _authenticated_context(
    request: Request,
    *,
    session: WebSession,
    csrf: str,
    active_page: str,
    title_key: str,
    title_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _base_context(
        request,
        locale=_session_locale(request, session),
        title_key=title_key,
        title_params=title_params,
        session=session,
        csrf=csrf,
        active_page=active_page,
    )


def _web_error(request: Request, session: WebSession | None, key: str) -> str:
    locale = _session_locale(request, session) if session is not None else _default_locale(request)
    return translate(locale, f"web.error.{key}")


def _target_context(request: Request, session: WebSession) -> dict[str, Any]:
    repo_set = repos(request)
    default = repo_set.user_post_defaults.get_for_owner(session.user_id)
    return {
        "bots": repo_set.user_bots.list_for_owner(session.user_id),
        "channels": repo_set.user_channels.list_for_owner(session.user_id),
        "default": default,
        "stale_default": default is None
        and repo_set.user_post_defaults.has_for_owner(session.user_id),
    }


def _composer_context(
    request: Request,
    *,
    session: WebSession,
    csrf: str,
    draft_message: str = "",
    error_message: str | None = None,
) -> dict[str, Any]:
    context = _authenticated_context(
        request,
        session=session,
        csrf=csrf,
        active_page="composer",
        title_key="web.page.composer",
    )
    context.update(_target_context(request, session))
    context["draft_message"] = draft_message
    context["error_message"] = error_message
    return context


def _draft_detail_context(
    request: Request,
    *,
    session: WebSession,
    csrf: str,
    draft: PostDraft,
    error_message: str | None = None,
) -> dict[str, Any]:
    context = _authenticated_context(
        request,
        session=session,
        csrf=csrf,
        active_page="drafts",
        title_key="web.page.draft_detail",
        title_params={"draft_id": draft.id},
    )
    context.update(_target_context(request, session))
    context["draft"] = draft
    context["error_message"] = error_message
    return context


def _targets_context(
    request: Request,
    *,
    session: WebSession,
    csrf: str,
    error_message: str | None = None,
    success_message: str | None = None,
    channel_query: str = "",
    channel_search_results: list[dict[str, str]] | None = None,
    channel_search_performed: bool = False,
) -> dict[str, Any]:
    context = _authenticated_context(
        request,
        session=session,
        csrf=csrf,
        active_page="targets",
        title_key="web.page.targets",
    )
    context.update(_target_context(request, session))
    context["error_message"] = error_message
    context["success_message"] = success_message
    context["channel_query"] = channel_query
    context["channel_search_results"] = channel_search_results or []
    context["channel_search_performed"] = channel_search_performed
    return context


async def _search_mattermost_channels(request: Request, term: str) -> list[dict[str, str]]:
    cfg = settings(request)
    client = MattermostClient(
        cfg.mm_rest_base,
        cfg.mm_bot_token,
        verify_ssl=cfg.mm_verify_ssl,
    )
    results: list[dict[str, str]] = []
    seen_channel_ids: set[str] = set()
    try:
        teams = await client.get_my_teams()
        for team in teams:
            team_id = str(team.get("id") or "")
            team_name = str(team.get("name") or team.get("display_name") or "")
            if not team_id:
                continue
            for channel in await client.search_channels(team_id, term):
                channel_id = str(channel.get("id") or "")
                if not channel_id or channel_id in seen_channel_ids:
                    continue
                channel_name = str(channel.get("name") or "")
                display_name = str(channel.get("display_name") or channel_name or channel_id)
                results.append(
                    {
                        "id": channel_id,
                        "name": channel_name,
                        "display_name": display_name,
                        "team_name": team_name,
                        "label": _channel_search_label(team_name, channel_name, display_name),
                    }
                )
                seen_channel_ids.add(channel_id)
    finally:
        await client.aclose()
    return results


def _channel_search_label(team_name: str, channel_name: str, display_name: str) -> str:
    location = "/".join(part for part in (team_name, channel_name) if part)
    if location and display_name != channel_name:
        return f"{display_name} ({location})"
    return location or display_name


def _posted_channel_result(channel_id: str, label: str) -> list[dict[str, str]]:
    if not channel_id:
        return []
    return [{"id": channel_id, "label": label or channel_id}]


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
        raise HTTPException(
            status_code=404,
            detail=_web_error(request, session, "draft_not_found"),
        ) from exc
    if draft.status != "draft":
        raise HTTPException(status_code=404, detail=_web_error(request, session, "draft_not_found"))
    return draft


def _optional_alias(value: str) -> str | None:
    normalized = value.strip()
    return normalized or None


@router.get("/login-required")
def login_required(request: Request) -> Response:
    locale = _default_locale(request)
    context = _base_context(
        request,
        locale=locale,
        title_key="web.login_required.title",
    )
    context["content"] = context["t"]("web.login_required.content")
    return templates.TemplateResponse(
        request=request,
        name="base.html",
        context=context,
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


@router.post("/language")
def set_language(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
    locale: Annotated[str, Form(...)],
    _csrf: Annotated[None, Depends(require_csrf)],
    next_path: Annotated[str, Form(alias="next")] = "/",
) -> Response:
    normalized = normalize_locale(locale)
    if normalized is None:
        raise HTTPException(
            status_code=400,
            detail=_web_error(request, session, "unsupported_language"),
        )
    conn = cast(DbConn, request.app.state.conn)
    UserPreferenceRepo(conn).set_locale(session.user_id, normalized)
    return RedirectResponse(_safe_next_path(next_path), status_code=303)


@router.get("/")
def home(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
    csrf: Annotated[str, Depends(csrf_token)],
) -> Response:
    context = _composer_context(
        request,
        session=session,
        csrf=csrf,
    )
    return templates.TemplateResponse(
        request=request,
        name="composer.html",
        context=context,
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
    except DraftMessageEmpty:
        context = _composer_context(
            request,
            session=session,
            csrf=csrf_token(request),
            draft_message=message,
            error_message=_web_error(request, session, "draft_empty"),
        )
        return templates.TemplateResponse(
            request=request,
            name="composer.html",
            context=context,
            status_code=400,
        )
    finally:
        await ctx.manager_mm.aclose()
    return RedirectResponse("/drafts", status_code=303)


@router.get("/drafts")
def draft_list(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
    csrf: Annotated[str, Depends(csrf_token)],
) -> Response:
    drafts = repos(request).post_drafts.list_for_owner(session.user_id)
    context = _authenticated_context(
        request,
        session=session,
        csrf=csrf,
        active_page="drafts",
        title_key="web.page.drafts",
    )
    context["drafts"] = drafts
    return templates.TemplateResponse(
        request=request,
        name="drafts.html",
        context=context,
    )


@router.get("/audit")
def audit(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
    csrf: Annotated[str, Depends(csrf_token)],
    published: Annotated[int | None, Query()] = None,
) -> Response:
    records = repos(request).audits.list_for_user(session.user_id, limit=50)
    context = _authenticated_context(
        request,
        session=session,
        csrf=csrf,
        active_page="audit",
        title_key="web.page.audit",
    )
    context["records"] = records
    if published is not None:
        context["success_message"] = context["t"](
            "web.audit.published_banner",
            draft_id=published,
        )
    return templates.TemplateResponse(
        request=request,
        name="audit.html",
        context=context,
    )


@router.get("/targets")
async def targets(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
    csrf: Annotated[str, Depends(csrf_token)],
    channel_query: Annotated[str, Query()] = "",
    channel_added: Annotated[str | None, Query()] = None,
) -> Response:
    query = channel_query.strip()
    channel_search_results: list[dict[str, str]] = []
    error_message = None
    if query:
        try:
            channel_search_results = await _search_mattermost_channels(request, query)
        except MattermostError:
            error_message = _web_error(request, session, "channel_search_failed")
    success_message = None
    if channel_added:
        success_message = _translator(_session_locale(request, session))(
            "web.targets.channel_added_banner",
            alias=channel_added,
        )
    context = _targets_context(
        request,
        session=session,
        csrf=csrf,
        error_message=error_message,
        success_message=success_message,
        channel_query=query,
        channel_search_results=channel_search_results,
        channel_search_performed=bool(query),
    )
    return templates.TemplateResponse(
        request=request,
        name="targets.html",
        context=context,
    )


@router.post("/targets/channels")
def add_channel_from_search(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
    channel_alias: Annotated[str, Form(...)],
    channel_id: Annotated[str, Form(...)],
    _csrf: Annotated[None, Depends(require_csrf)],
    channel_label: Annotated[str, Form()] = "",
) -> Response:
    alias = channel_alias.strip()
    selected_channel_id = channel_id.strip()
    selected_channel_label = channel_label.strip() or selected_channel_id
    if not alias or not selected_channel_id:
        context = _targets_context(
            request,
            session=session,
            csrf=csrf_token(request),
            error_message=_web_error(request, session, "channel_add_invalid"),
            channel_search_results=_posted_channel_result(
                selected_channel_id,
                selected_channel_label,
            ),
            channel_search_performed=bool(selected_channel_id),
        )
        return templates.TemplateResponse(
            request=request,
            name="targets.html",
            context=context,
            status_code=400,
        )

    repo_set = repos(request)
    try:
        repo_set.user_channels.get_by_owner_and_alias(session.user_id, alias)
    except LookupError:
        pass
    else:
        context = _targets_context(
            request,
            session=session,
            csrf=csrf_token(request),
            error_message=_web_error(request, session, "channel_alias_duplicate"),
            channel_query=alias,
            channel_search_results=_posted_channel_result(
                selected_channel_id,
                selected_channel_label,
            ),
            channel_search_performed=True,
        )
        return templates.TemplateResponse(
            request=request,
            name="targets.html",
            context=context,
            status_code=400,
        )

    repo_set.user_channels.add(
        owner_user_id=session.user_id,
        alias=alias,
        channel_id=selected_channel_id,
    )
    return RedirectResponse(f"/targets?channel_added={quote(alias, safe='')}", status_code=303)


@router.post("/targets/default")
def set_default_target(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
    bot_alias: Annotated[str, Form(...)],
    channel_alias: Annotated[str, Form(...)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> Response:
    try:
        repos(request).user_post_defaults.set_for_owner(
            session.user_id,
            bot_alias=bot_alias,
            channel_alias=channel_alias,
        )
    except LookupError:
        context = _targets_context(
            request,
            session=session,
            csrf=csrf_token(request),
            error_message=_web_error(request, session, "target_aliases_invalid"),
        )
        return templates.TemplateResponse(
            request=request,
            name="targets.html",
            context=context,
            status_code=400,
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
    context = _draft_detail_context(
        request,
        session=session,
        csrf=csrf,
        draft=draft,
    )
    return templates.TemplateResponse(
        request=request,
        name="draft_detail.html",
        context=context,
    )


@router.post("/drafts/{draft_id}")
async def update_draft(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
    draft_id: int,
    message: Annotated[str, Form(...)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> Response:
    draft = _draft_or_404(request, session, draft_id)
    ctx = _command_context(request, session)
    try:
        update_draft_message(ctx, draft_id, message)
    except DraftMessageEmpty:
        context = _draft_detail_context(
            request,
            session=session,
            csrf=csrf_token(request),
            draft=draft,
            error_message=_web_error(request, session, "draft_empty"),
        )
        return templates.TemplateResponse(
            request=request,
            name="draft_detail.html",
            context=context,
            status_code=400,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail=_web_error(request, session, "draft_not_found"),
        ) from exc
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
    draft = _draft_or_404(request, session, draft_id)
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
        context = _draft_detail_context(
            request,
            session=session,
            csrf=csrf_token(request),
            draft=draft,
            error_message=_web_error(request, session, exc.code),
        )
        return templates.TemplateResponse(
            request=request,
            name="draft_detail.html",
            context=context,
            status_code=400,
        )
    finally:
        await ctx.manager_mm.aclose()
    return RedirectResponse(f"/audit?published={draft_id}", status_code=303)


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
