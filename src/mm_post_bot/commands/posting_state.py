from dataclasses import dataclass
from typing import Literal

from .context import CommandContext

TargetStatus = Literal["ready", "missing", "stale"]


@dataclass(frozen=True, slots=True)
class TargetState:
    status: TargetStatus
    bot_alias: str | None = None
    bot_username: str | None = None
    channel_alias: str | None = None
    channel_id: str | None = None


def preview_line(message: str, *, max_length: int = 80) -> str:
    first_line = message.splitlines()[0].strip() if message.splitlines() else ""
    if len(first_line) <= max_length:
        return first_line
    return f"{first_line[: max_length - 3]}..."


def target_state(ctx: CommandContext) -> TargetState:
    default = ctx.user_post_default_repo.get_for_owner(ctx.caller_user_id)
    if default is not None:
        return TargetState(
            status="ready",
            bot_alias=default.bot.alias,
            bot_username=default.bot.bot_username,
            channel_alias=default.channel.alias,
            channel_id=default.channel.channel_id,
        )
    if ctx.user_post_default_repo.has_for_owner(ctx.caller_user_id):
        return TargetState(status="stale")
    return TargetState(status="missing")


def target_line(ctx: CommandContext, state: TargetState) -> str:
    if state.status == "ready":
        return ctx.t(
            "posting_state.target.ready",
            bot_alias=state.bot_alias,
            bot_username=state.bot_username,
            channel_alias=state.channel_alias,
            channel_id=state.channel_id,
        )
    if state.status == "stale":
        return ctx.t("posting_state.target.stale")
    return ctx.t("posting_state.target.missing")


def publish_hint(ctx: CommandContext, draft_id: int, state: TargetState) -> str:
    if state.status == "ready":
        return ctx.t("posting_state.publish.short", draft_id=draft_id)
    return ctx.t("posting_state.publish.explicit", draft_id=draft_id)


def default_recovery(ctx: CommandContext) -> str:
    return ctx.t("posting_state.default_recovery")
