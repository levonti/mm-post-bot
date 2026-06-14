from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request

from ..i18n import translate
from ..repository import PostAuditRecord, PostDraft, UserBot, UserChannel
from ..services.web_auth import WebSession
from .deps import csrf_token, current_session, repos, require_csrf
from .routes import _session_locale

api_router = APIRouter(prefix="/api/web")

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


def _channel_payload(channel: UserChannel) -> dict[str, object]:
    return {
        "alias": channel.alias,
        "channel_id": channel.channel_id,
        "created_at": channel.created_at.isoformat(),
        "updated_at": channel.updated_at.isoformat(),
    }


def _bot_payload(bot: UserBot) -> dict[str, object]:
    return {
        "alias": bot.alias,
        "bot_user_id": bot.bot_user_id,
        "bot_username": bot.bot_username,
        "bot_display_name": bot.bot_display_name,
    }


def _draft_payload(draft: PostDraft) -> dict[str, object]:
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


@api_router.get("/targets")
def targets_api(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
    csrf: Annotated[str, Depends(csrf_token)],
) -> dict[str, object]:
    repo_set = repos(request)
    default = repo_set.user_post_defaults.get_for_owner(session.user_id)
    return {
        "csrf": csrf,
        "bots": [_bot_payload(bot) for bot in repo_set.user_bots.list_for_owner(session.user_id)],
        "channels": [
            _channel_payload(channel)
            for channel in repo_set.user_channels.list_for_owner(session.user_id)
        ],
        "default": (
            {"bot_alias": default.bot.alias, "channel_alias": default.channel.alias}
            if default is not None
            else None
        ),
        "stale_default": default is None
        and repo_set.user_post_defaults.has_for_owner(session.user_id),
    }


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
        raise HTTPException(status_code=400, detail="Channel alias cannot be empty")
    repo_set = repos(request)
    if normalized_alias != alias:
        try:
            repo_set.user_channels.get_by_owner_and_alias(session.user_id, normalized_alias)
        except LookupError:
            pass
        else:
            raise HTTPException(status_code=409, detail="Channel alias already exists")
    try:
        channel = repo_set.user_channels.rename_alias(
            session.user_id,
            alias,
            new_alias=normalized_alias,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Channel alias not found") from exc
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


@api_router.get("/drafts")
def drafts_api(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
    csrf: Annotated[str, Depends(csrf_token)],
) -> dict[str, object]:
    return {
        "csrf": csrf,
        "drafts": [
            _draft_payload(draft)
            for draft in repos(request).post_drafts.list_for_owner(session.user_id)
        ],
    }


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
