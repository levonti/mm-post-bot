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


def user_status(ctx: CommandContext) -> str | None:
    try:
        return ctx.user_repo.get(ctx.caller_user_id).status
    except LookupError:
        return None


def setup_next_command(ctx: CommandContext) -> str:
    status = user_status(ctx)
    if status is None:
        return "!register"
    if status == "pending":
        return "!status"
    if status == "blocked":
        return "!status"
    if status != "approved":
        return "!status"
    if not ctx.user_bot_repo.list_for_owner(ctx.caller_user_id):
        return "!bot add <alias> <token>"
    if not ctx.user_channel_repo.list_for_owner(ctx.caller_user_id):
        return "!channel add <alias> <channel_id>"
    state = target_state(ctx)
    if state.status != "ready":
        return "!default set --bot <alias> --channel <channel_alias>"
    if not ctx.post_draft_repo.list_for_owner(ctx.caller_user_id):
        return "!draft"
    return "!draft list"


def setup_lines(ctx: CommandContext) -> list[str]:
    status = user_status(ctx)
    bots = (
        ctx.user_bot_repo.list_for_owner(ctx.caller_user_id)
        if status == "approved"
        else []
    )
    channels = (
        ctx.user_channel_repo.list_for_owner(ctx.caller_user_id)
        if status == "approved"
        else []
    )
    state = target_state(ctx) if status == "approved" else TargetState(status="missing")
    drafts = (
        ctx.post_draft_repo.list_for_owner(ctx.caller_user_id)
        if status == "approved"
        else []
    )
    status_text = status if status is not None else "not registered"
    bot_text = str(len(bots)) if bots else "none"
    channel_text = str(len(channels)) if channels else "none"
    if state.status == "ready":
        default_text = f"{state.bot_alias} -> {state.channel_alias}"
    elif state.status == "stale":
        default_text = "stale"
    else:
        default_text = "none"
    draft_text = str(len(drafts)) if drafts else "none"
    return [
        ctx.t("setup.registration", status=status_text),
        ctx.t("setup.bots", count=bot_text),
        ctx.t("setup.channels", count=channel_text),
        ctx.t("setup.default", value=default_text),
        ctx.t("setup.drafts", count=draft_text),
        ctx.t("setup.next", command=setup_next_command(ctx)),
    ]
