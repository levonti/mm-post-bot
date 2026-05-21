import json
import shlex
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from . import commands
from .commands.access import require_approved_user
from .commands.context import CommandContext
from .config import Settings
from .db import DbConn
from .mm_client import MattermostClient
from .repository import (
    AuditRepo,
    DraftCaptureRepo,
    PostDraftRepo,
    UserBotRepo,
    UserChannelRepo,
    UserRepo,
)
from .security import hash_message


class MessageRouter:
    def __init__(self, *, manager_user_id: str, manager_username: str) -> None:
        self._manager_user_id = manager_user_id
        self._manager_username = manager_username.lstrip("@")

    def extract_command(self, post: Mapping[str, Any], channel_type: str | None) -> str | None:
        if post.get("user_id") == self._manager_user_id:
            return None

        message = _post_message(post).strip()
        if not message:
            return None

        if channel_type == "D":
            return message if message.startswith("!") else None

        command = self._strip_manager_mention(message)
        if command is None:
            return None
        return command if command.startswith("!") else None

    def extract_draft_body(self, post: Mapping[str, Any], channel_type: str | None) -> str | None:
        if post.get("user_id") == self._manager_user_id or channel_type != "D":
            return None
        message = _post_message(post)
        if not message.strip() or self.extract_command(post, channel_type) is not None:
            return None
        return message

    def _strip_manager_mention(self, message: str) -> str | None:
        mention_prefixes = (f"@{self._manager_username}", f"<@{self._manager_user_id}>")
        for prefix in mention_prefixes:
            if message == prefix:
                return ""
            if message.startswith(f"{prefix} "):
                return message[len(prefix) :].strip()
        return None


class CommandContextFactory:
    def __init__(
        self,
        *,
        conn: DbConn,
        settings: Settings,
        manager_mm: MattermostClient,
        manager_user_id: str,
    ) -> None:
        self._conn = conn
        self._settings = settings
        self._manager_mm = manager_mm
        self._manager_user_id = manager_user_id

    def from_post(self, post: Mapping[str, Any], channel_type: str | None) -> CommandContext:
        return CommandContext(
            caller_user_id=str(post.get("user_id") or ""),
            caller_username=_post_username(post),
            channel_id=str(post.get("channel_id") or ""),
            channel_type=channel_type,
            user_repo=UserRepo(self._conn),
            user_bot_repo=UserBotRepo(self._conn),
            user_channel_repo=UserChannelRepo(self._conn),
            draft_capture_repo=DraftCaptureRepo(self._conn),
            post_draft_repo=PostDraftRepo(self._conn),
            audit_repo=AuditRepo(self._conn),
            manager_mm=self._manager_mm,
            manager_user_id=self._manager_user_id,
            admin_usernames=frozenset(self._settings.admin_usernames),
            mm_rest_base=self._settings.mm_rest_base,
            mm_url=str(self._settings.mm_url).rstrip("/"),
            token_encryption_key=self._settings.token_encryption_key,
            mm_verify_ssl=self._settings.mm_verify_ssl,
        )


def redact_command_for_log(raw_text: str) -> str:
    try:
        argv = shlex.split(raw_text)
    except ValueError:
        return "[UNPARSEABLE COMMAND]"

    if len(argv) >= 4 and argv[0] == "!bot" and argv[1] == "add":
        return " ".join([argv[0], argv[1], argv[2], "[REDACTED]"])
    return raw_text


async def handle_draft_body(ctx: CommandContext, body: str) -> str | None:
    capture = ctx.draft_capture_repo.get_active(ctx.caller_user_id, now=datetime.now(UTC))
    if capture is None:
        return None

    access_error = require_approved_user(ctx)
    if access_error is not None:
        return access_error

    draft = ctx.post_draft_repo.create(
        owner_user_id=ctx.caller_user_id,
        message=body,
        message_sha256=hash_message(body),
    )
    ctx.draft_capture_repo.clear(ctx.caller_user_id)
    return (
        f"Draft #{draft.id} saved. Send it with:\n"
        f"!send {draft.id} --bot <alias> --channel <mattermost-channel-link>"
    )


async def handle_event(
    event: Mapping[str, Any],
    *,
    router: MessageRouter,
    context_factory: CommandContextFactory,
) -> str | None:
    if event.get("event") != "posted":
        return None

    data = event.get("data")
    if not isinstance(data, Mapping):
        return None

    post = _post_from_event_data(data)
    if post is None:
        return None

    channel_type = _channel_type(data, post)
    command_text = router.extract_command(post, channel_type)
    if command_text is not None:
        ctx = context_factory.from_post(post, channel_type)
        response = await commands.dispatch(ctx, command_text)
        if response:
            await ctx.manager_mm.create_post(ctx.channel_id, response)
        return response

    draft_body = router.extract_draft_body(post, channel_type)
    if draft_body is not None:
        ctx = context_factory.from_post(post, channel_type)
        response = await handle_draft_body(ctx, draft_body)
        if response:
            await ctx.manager_mm.create_post(ctx.channel_id, response)
        return response

    return None


def _post_from_event_data(data: Mapping[str, Any]) -> dict[str, Any] | None:
    raw_post = data.get("post")
    if isinstance(raw_post, str):
        try:
            parsed = json.loads(raw_post)
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed, dict):
            return None
        post = dict(parsed)
    elif isinstance(raw_post, Mapping):
        post = dict(raw_post)
    else:
        return None

    if "sender_name" in data and "sender_name" not in post:
        post["sender_name"] = data["sender_name"]
    return post


def _channel_type(data: Mapping[str, Any], post: Mapping[str, Any]) -> str | None:
    value = data.get("channel_type") or post.get("channel_type")
    if value is None:
        return None
    return str(value)


def _post_message(post: Mapping[str, Any]) -> str:
    message = post.get("message")
    return message if isinstance(message, str) else ""


def _post_username(post: Mapping[str, Any]) -> str:
    username = post.get("username") or post.get("sender_name") or ""
    return str(username).lstrip("@")
