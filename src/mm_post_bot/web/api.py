from typing import Annotated, cast

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)

from ..db import DbConn
from ..i18n import normalize_locale, translate
from ..mm_client import MattermostClient, MattermostError
from ..repository import (
    DraftAttachment,
    PostAuditRecord,
    PostDraft,
    UserBot,
    UserChannel,
    UserPostDefault,
    UserPreferenceRepo,
)
from ..services.posting import (
    BotChannelMembershipCheckError,
    BotNotInChannelError,
    DraftMessageEmpty,
    PublishDraftRequest,
    PublishError,
    TargetRequest,
    create_draft,
    publish_draft,
    update_draft_message,
    verify_bot_in_channel,
)
from ..services.web_auth import WebSession
from .deps import SESSION_COOKIE, csrf_token, current_session, repos, require_csrf, settings
from .routes import _command_context, _optional_alias, _session_locale, _web_error

api_router = APIRouter(prefix="/api/web")

ALLOWED_IMAGE_CONTENT_TYPES = {"image/gif", "image/jpeg", "image/png", "image/webp"}
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024

NAV_ITEMS = (
    ("/", "composer", "web.nav.composer"),
    ("/drafts", "drafts", "web.nav.drafts"),
    ("/targets", "targets", "web.nav.targets"),
    ("/audit", "audit", "web.nav.audit"),
)


@api_router.get("/bootstrap")
def bootstrap(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
    csrf: Annotated[str, Depends(csrf_token)],
) -> dict[str, object]:
    locale = _session_locale(request, session)
    return {
        "session": {
            "user_id": session.user_id,
            "username": session.username,
        },
        "locale": locale,
        "csrf": csrf,
        "nav": [
            {"href": href, "key": key, "label": translate(locale, label_key)}
            for href, key, label_key in NAV_ITEMS
        ],
    }


def _channel_payload(
    channel: UserChannel,
    *,
    display_name: str | None = None,
    team_name: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "alias": channel.alias,
        "channel_id": channel.channel_id,
        "created_at": channel.created_at.isoformat(),
        "updated_at": channel.updated_at.isoformat(),
    }
    if display_name:
        payload["display_name"] = display_name
    if team_name:
        payload["team_name"] = team_name
    return payload


def _bot_payload(bot: UserBot) -> dict[str, object]:
    return {
        "alias": bot.alias,
        "bot_user_id": bot.bot_user_id,
        "bot_username": bot.bot_username,
        "bot_display_name": bot.bot_display_name,
    }


def _attachment_payload(draft_id: int, attachment: DraftAttachment) -> dict[str, object]:
    return {
        "id": attachment.id,
        "filename": attachment.filename,
        "content_type": attachment.content_type,
        "size_bytes": attachment.size_bytes,
        "preview_url": f"/api/web/drafts/{draft_id}/attachments/{attachment.id}/content",
    }


def _safe_upload_filename(filename: str | None) -> str:
    if filename is None:
        return "image"
    normalized = filename.replace("\\", "/").split("/")[-1].strip()
    return normalized or "image"


def _draft_payload(
    draft: PostDraft,
    *,
    attachments: list[DraftAttachment] | None = None,
) -> dict[str, object]:
    return {
        "id": draft.id,
        "message": draft.message,
        "message_sha256": draft.message_sha256,
        "status": draft.status,
        "created_at": draft.created_at.isoformat(),
        "updated_at": draft.updated_at.isoformat(),
        "sent_at": draft.sent_at.isoformat() if draft.sent_at is not None else None,
        "sent_by_user_bot_id": draft.sent_by_user_bot_id,
        "sent_channel_id": draft.sent_channel_id,
        "mattermost_post_id": draft.mattermost_post_id,
        "attachments": [
            _attachment_payload(draft.id, attachment)
            for attachment in (attachments if attachments is not None else [])
        ],
    }


def _audit_payload(record: PostAuditRecord) -> dict[str, object]:
    return {
        "id": record.id,
        "caller_user_id": record.caller_user_id,
        "caller_username": record.caller_username,
        "draft_id": record.draft_id,
        "user_bot_id": record.user_bot_id,
        "bot_user_id": record.bot_user_id,
        "bot_username": record.bot_username,
        "channel_link": record.channel_link,
        "resolved_channel_id": record.resolved_channel_id,
        "resolved_team_name": record.resolved_team_name,
        "resolved_channel_name": record.resolved_channel_name,
        "message_sha256": record.message_sha256,
        "status": record.status,
        "mattermost_post_id": record.mattermost_post_id,
        "error_code": record.error_code,
        "error_message": record.error_message,
        "created_at": record.created_at.isoformat(),
    }


def _target_health_base(default: UserPostDefault) -> dict[str, object]:
    return {
        "bot_alias": default.bot.alias,
        "bot_username": default.bot.bot_username,
        "channel_alias": default.channel.alias,
        "channel_id": default.channel.channel_id,
    }


async def _target_health_payload(
    request: Request,
    session: WebSession,
    default: UserPostDefault | None,
) -> dict[str, object] | None:
    if default is None:
        return None

    ctx = _command_context(request, session)
    try:
        await verify_bot_in_channel(ctx, bot=default.bot, channel=default.channel)
        return {"status": "ok", **_target_health_base(default)}
    except BotNotInChannelError:
        return {"status": "bot_not_in_channel", **_target_health_base(default)}
    except BotChannelMembershipCheckError:
        return {"status": "check_failed", **_target_health_base(default)}
    finally:
        await ctx.manager_mm.aclose()


async def _channel_display_metadata(
    request: Request,
    channels: list[UserChannel],
) -> dict[str, dict[str, str]]:
    if not channels:
        return {}

    cfg = settings(request)
    client = MattermostClient(
        cfg.mm_rest_base,
        cfg.mm_bot_token,
        verify_ssl=cfg.mm_verify_ssl,
    )
    try:
        teams = await client.get_my_teams()
        team_names_by_id = {
            str(team.get("id") or ""): str(team.get("name") or team.get("display_name") or "")
            for team in teams
        }
        metadata: dict[str, dict[str, str]] = {}
        for channel in channels:
            try:
                raw_channel = await client.get_channel(channel.channel_id)
            except MattermostError:
                continue
            display_name = str(
                raw_channel.get("display_name")
                or raw_channel.get("name")
                or channel.alias
            )
            team_id = str(raw_channel.get("team_id") or "")
            team_name = team_names_by_id.get(team_id, "")
            metadata[channel.channel_id] = {
                "display_name": display_name,
                "team_name": team_name,
            }
        return metadata
    except MattermostError:
        return {}
    finally:
        await client.aclose()


async def _targets_payload(
    request: Request,
    session: WebSession,
    *,
    enrich_channels: bool = False,
) -> dict[str, object]:
    repo_set = repos(request)
    default = repo_set.user_post_defaults.get_for_owner(session.user_id)
    channels = repo_set.user_channels.list_for_owner(session.user_id)
    channel_metadata = (
        await _channel_display_metadata(request, channels) if enrich_channels else {}
    )
    return {
        "bots": [_bot_payload(bot) for bot in repo_set.user_bots.list_for_owner(session.user_id)],
        "channels": [
            _channel_payload(channel, **channel_metadata.get(channel.channel_id, {}))
            for channel in channels
        ],
        "default": (
            {"bot_alias": default.bot.alias, "channel_alias": default.channel.alias}
            if default is not None
            else None
        ),
        "stale_default": default is None
        and repo_set.user_post_defaults.has_for_owner(session.user_id),
    }


def _channel_search_label(team_name: str, channel_name: str, display_name: str) -> str:
    location = "/".join(part for part in (team_name, channel_name) if part)
    if location and display_name != channel_name:
        return f"{display_name} ({location})"
    return location or display_name


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


@api_router.post("/logout")
def logout_api(
    request: Request,
    response: Response,
    _csrf: Annotated[None, Depends(require_csrf)],
) -> dict[str, bool]:
    cfg = settings(request)
    response.delete_cookie(
        SESSION_COOKIE,
        secure=cfg.web_cookie_secure,
        httponly=True,
        samesite="lax",
    )
    return {"success": True}


@api_router.get("/targets")
async def targets_api(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
    csrf: Annotated[str, Depends(csrf_token)],
) -> dict[str, object]:
    return {
        "csrf": csrf,
        **await _targets_payload(request, session, enrich_channels=True),
    }


@api_router.get("/targets/channels/search")
async def search_channels_api(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
    q: Annotated[str, Query()] = "",
) -> dict[str, object]:
    query = q.strip()
    if len(query) < 2:
        return {"results": []}
    try:
        return {"results": await _search_mattermost_channels(request, query)}
    except MattermostError as exc:
        raise HTTPException(
            status_code=502,
            detail=_web_error(request, session, "channel_search_failed"),
        ) from exc


@api_router.post("/targets/channels")
def add_channel_api(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
    channel_alias: Annotated[str, Form(...)],
    channel_id: Annotated[str, Form(...)],
    _csrf: Annotated[None, Depends(require_csrf)],
    channel_label: Annotated[str, Form()] = "",
) -> dict[str, object]:
    alias = channel_alias.strip()
    selected_channel_id = channel_id.strip()
    if not alias or not selected_channel_id:
        raise HTTPException(
            status_code=400,
            detail=_web_error(request, session, "channel_add_invalid"),
        )

    repo_set = repos(request)
    try:
        repo_set.user_channels.get_by_owner_and_alias(session.user_id, alias)
    except LookupError:
        pass
    else:
        raise HTTPException(
            status_code=400,
            detail=_web_error(request, session, "channel_alias_duplicate"),
        )

    repo_set.user_channels.add(
        owner_user_id=session.user_id,
        alias=alias,
        channel_id=selected_channel_id,
    )
    return {
        "success": True,
        "alias": alias,
        "channel_id": selected_channel_id,
        "message": translate(
            _session_locale(request, session),
            "web.targets.channel_added_banner",
            alias=alias,
        ),
    }


@api_router.post("/targets/default")
async def set_default_target_api(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
    bot_alias: Annotated[str, Form(...)],
    channel_alias: Annotated[str, Form(...)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> dict[str, bool]:
    repo_set = repos(request)
    try:
        bot = repo_set.user_bots.get_by_owner_and_alias(session.user_id, bot_alias)
        channel = repo_set.user_channels.get_by_owner_and_alias(session.user_id, channel_alias)
    except LookupError as exc:
        raise HTTPException(
            status_code=400,
            detail=_web_error(request, session, "target_aliases_invalid"),
        ) from exc

    ctx = _command_context(request, session)
    try:
        await verify_bot_in_channel(ctx, bot=bot, channel=channel)
    except BotNotInChannelError as exc:
        raise HTTPException(
            status_code=400,
            detail=_web_error(
                request,
                session,
                "default_bot_not_in_channel",
                bot_username=bot.bot_username,
                channel_alias=channel.alias,
            ),
        ) from exc
    except BotChannelMembershipCheckError as exc:
        raise HTTPException(
            status_code=400,
            detail=_web_error(request, session, "default_membership_check_failed"),
        ) from exc
    finally:
        await ctx.manager_mm.aclose()

    try:
        repo_set.user_post_defaults.set_for_owner(
            session.user_id,
            bot_alias=bot_alias,
            channel_alias=channel_alias,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=400,
            detail=_web_error(request, session, "target_aliases_invalid"),
        ) from exc
    return {"success": True}


@api_router.post("/targets/default/clear")
def clear_default_target_api(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> dict[str, bool]:
    repos(request).user_post_defaults.clear_for_owner(session.user_id)
    return {"success": True}


@api_router.post("/targets/channels/{alias}/rename")
def rename_channel_api(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
    alias: str,
    new_alias: Annotated[str, Form(...)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> dict[str, object]:
    normalized_alias = new_alias.strip()
    if not normalized_alias:
        raise HTTPException(
            status_code=400,
            detail=_web_error(request, session, "channel_add_invalid"),
        )
    repo_set = repos(request)
    if normalized_alias != alias:
        try:
            repo_set.user_channels.get_by_owner_and_alias(session.user_id, normalized_alias)
        except LookupError:
            pass
        else:
            raise HTTPException(
                status_code=409,
                detail=_web_error(request, session, "channel_alias_duplicate"),
            )
    try:
        channel = repo_set.user_channels.rename_alias(
            session.user_id,
            alias,
            new_alias=normalized_alias,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail=_web_error(request, session, "channel_not_found"),
        ) from exc
    return _channel_payload(channel)


@api_router.post("/targets/channels/{alias}/delete")
def delete_channel_api(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
    alias: str,
    _csrf: Annotated[None, Depends(require_csrf)],
) -> dict[str, bool]:
    repos(request).user_channels.soft_delete(session.user_id, alias)
    return {"success": True}


@api_router.post("/drafts")
async def create_draft_api(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
    message: Annotated[str, Form(...)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> dict[str, int]:
    ctx = _command_context(request, session)
    try:
        draft = create_draft(ctx, message)
    except DraftMessageEmpty as exc:
        raise HTTPException(
            status_code=400,
            detail=_web_error(request, session, "draft_empty"),
        ) from exc
    finally:
        await ctx.manager_mm.aclose()
    return {"id": draft.id}


@api_router.get("/drafts")
def drafts_api(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
    csrf: Annotated[str, Depends(csrf_token)],
) -> dict[str, object]:
    repo_set = repos(request)
    return {
        "csrf": csrf,
        "drafts": [
            _draft_payload(
                draft,
                attachments=repo_set.draft_attachments.list_for_draft(session.user_id, draft.id),
            )
            for draft in repo_set.post_drafts.list_for_owner(session.user_id)
        ],
    }


@api_router.post("/drafts/{draft_id}")
async def update_draft_api(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
    draft_id: int,
    message: Annotated[str, Form(...)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> dict[str, int]:
    ctx = _command_context(request, session)
    try:
        update_draft_message(ctx, draft_id, message)
    except DraftMessageEmpty as exc:
        raise HTTPException(
            status_code=400,
            detail=_web_error(request, session, "draft_empty"),
        ) from exc
    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail=_web_error(request, session, "draft_not_found"),
        ) from exc
    finally:
        await ctx.manager_mm.aclose()
    return {"id": draft_id}


@api_router.get("/drafts/{draft_id}")
async def draft_detail_api(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
    csrf: Annotated[str, Depends(csrf_token)],
    draft_id: int,
) -> dict[str, object]:
    try:
        repo_set = repos(request)
        draft = repo_set.post_drafts.get_for_owner(session.user_id, draft_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail=_web_error(request, session, "draft_not_found"),
        ) from exc
    if draft.status != "draft":
        raise HTTPException(status_code=404, detail=_web_error(request, session, "draft_not_found"))
    default = repo_set.user_post_defaults.get_for_owner(session.user_id)
    return {
        "csrf": csrf,
        "draft": _draft_payload(
            draft,
            attachments=repo_set.draft_attachments.list_for_draft(session.user_id, draft.id),
        ),
        "target_health": await _target_health_payload(request, session, default),
        **await _targets_payload(request, session),
    }


@api_router.post("/drafts/{draft_id}/attachments")
async def upload_draft_attachment_api(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
    draft_id: int,
    file: Annotated[UploadFile, File(...)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> dict[str, object]:
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported image type")

    data = await file.read()
    if len(data) > MAX_ATTACHMENT_BYTES:
        raise HTTPException(status_code=400, detail="Image is too large")

    try:
        attachment = repos(request).draft_attachments.create(
            owner_user_id=session.user_id,
            draft_id=draft_id,
            filename=_safe_upload_filename(file.filename),
            content_type=content_type,
            size_bytes=len(data),
            data=data,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail=_web_error(request, session, "draft_not_found"),
        ) from exc
    return {"attachment": _attachment_payload(draft_id, attachment)}


@api_router.get("/drafts/{draft_id}/attachments/{attachment_id}/content")
def draft_attachment_content_api(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
    draft_id: int,
    attachment_id: int,
) -> Response:
    try:
        attachment = repos(request).draft_attachments.get_for_owner(
            session.user_id,
            draft_id,
            attachment_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Attachment not found") from exc
    return Response(content=attachment.data, media_type=attachment.content_type)


@api_router.post("/drafts/{draft_id}/attachments/{attachment_id}/delete")
def delete_draft_attachment_api(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
    draft_id: int,
    attachment_id: int,
    _csrf: Annotated[None, Depends(require_csrf)],
) -> dict[str, bool]:
    repos(request).draft_attachments.soft_delete(session.user_id, draft_id, attachment_id)
    return {"success": True}


@api_router.post("/drafts/{draft_id}/publish")
async def publish_draft_api(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
    draft_id: int,
    _csrf: Annotated[None, Depends(require_csrf)],
    bot_alias: Annotated[str, Form()] = "",
    channel_alias: Annotated[str, Form()] = "",
) -> dict[str, object]:
    ctx = _command_context(request, session)
    try:
        result = await publish_draft(
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
        raise HTTPException(status_code=400, detail=_web_error(request, session, exc.code)) from exc
    finally:
        await ctx.manager_mm.aclose()
    return {
        "draft_id": result.draft_id,
        "mattermost_post_id": result.mattermost_post_id,
        "redirect": f"/audit?published={result.draft_id}",
    }


@api_router.post("/drafts/{draft_id}/delete")
def delete_draft_api(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
    draft_id: int,
    _csrf: Annotated[None, Depends(require_csrf)],
) -> dict[str, bool]:
    try:
        draft = repos(request).post_drafts.get_for_owner(session.user_id, draft_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail=_web_error(request, session, "draft_not_found"),
        ) from exc
    if draft.status != "draft":
        raise HTTPException(status_code=404, detail=_web_error(request, session, "draft_not_found"))
    repos(request).post_drafts.soft_delete(session.user_id, draft_id)
    return {"success": True}


@api_router.get("/audit")
def audit_api(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
    csrf: Annotated[str, Depends(csrf_token)],
) -> dict[str, object]:
    return {
        "csrf": csrf,
        "records": [
            _audit_payload(record)
            for record in repos(request).audits.list_for_user(session.user_id, limit=50)
        ],
    }


@api_router.post("/language")
def set_language_api(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
    locale: Annotated[str, Form(...)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> dict[str, str]:
    normalized = normalize_locale(locale)
    if normalized is None:
        raise HTTPException(
            status_code=400,
            detail=_web_error(request, session, "unsupported_language"),
        )
    conn = cast(DbConn, request.app.state.conn)
    UserPreferenceRepo(conn).set_locale(session.user_id, normalized)
    return {"locale": normalized}
