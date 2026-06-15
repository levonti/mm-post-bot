from collections.abc import Awaitable, Callable
from dataclasses import replace
from functools import cache

from .context import CommandContext
from .parser import ParsedArgs, parse_command

Handler = Callable[[CommandContext, ParsedArgs], Awaitable[str]]


@cache
def _registry() -> dict[tuple[str, ...], Handler]:
    from . import (
        bot,
        channel,
        defaults,
        draft,
        lang,
        register,
        send,
        setup,
        status,
        user_admin,
        web,
    )
    from . import help as help_cmd

    return {
        ("help",): help_cmd.handle,
        ("lang",): lang.handle,
        ("register",): register.handle,
        ("status",): status.handle,
        ("setup",): setup.show,
        ("next",): setup.next_action,
        ("web",): web.handle,
        ("send",): send.handle,
        ("bot", "add"): bot.add,
        ("bot", "list"): bot.list_bots,
        ("bot", "remove"): bot.remove,
        ("channel", "add"): channel.add,
        ("channel", "add-current"): channel.add_current,
        ("channel", "set"): channel.set_channel,
        ("channel", "remove"): channel.remove,
        ("channel", "list"): channel.list_channels,
        ("channel", "show"): channel.show,
        ("default",): defaults.show,
        ("default", "set"): defaults.set_defaults,
        ("default", "clear"): defaults.clear,
        ("draft",): draft.start,
        ("draft", "cancel"): draft.cancel,
        ("draft", "list"): draft.list_drafts,
        ("draft", "show"): draft.show,
        ("draft", "delete"): draft.delete,
        ("user", "approve"): user_admin.approve,
        ("user", "block"): user_admin.block,
        ("user", "unblock"): user_admin.unblock,
        ("user", "list"): user_admin.list_users,
    }


def _match_handler(parsed: ParsedArgs) -> tuple[Handler, ParsedArgs] | None:
    tokens = (parsed.command, *parsed.positional)
    registry = _registry()
    for route in sorted(registry, key=len, reverse=True):
        if tokens[: len(route)] == route:
            remaining = parsed.positional[len(route) - 1 :]
            return registry[route], replace(parsed, positional=remaining)
    return None


async def dispatch(ctx: CommandContext, raw_text: str) -> str | None:
    if not raw_text.lstrip().startswith("!"):
        return ctx.t("command.must_start")

    try:
        parsed = parse_command(raw_text)
    except ValueError as exc:
        return ctx.t("command.parse_error", error=str(exc))

    if not parsed.command:
        parsed = replace(parsed, command="help")

    matched = _match_handler(parsed)
    if matched is not None:
        handler, args = matched
        return await handler(ctx, args)
    return ctx.t("command.unknown", command=parsed.command)


__all__ = ["CommandContext", "dispatch", "parse_command"]
