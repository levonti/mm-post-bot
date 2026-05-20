from collections.abc import Awaitable, Callable
from dataclasses import replace

from . import bot, draft, register, status, user_admin
from . import help as help_cmd
from .context import CommandContext
from .parser import ParsedArgs, parse_command

Handler = Callable[[CommandContext, ParsedArgs], Awaitable[str]]

REGISTRY: dict[tuple[str, ...], Handler] = {
    ("help",): help_cmd.handle,
    ("register",): register.handle,
    ("status",): status.handle,
    ("bot", "add"): bot.add,
    ("bot", "list"): bot.list_bots,
    ("bot", "remove"): bot.remove,
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
    for route in sorted(REGISTRY, key=len, reverse=True):
        if tokens[: len(route)] == route:
            remaining = parsed.positional[len(route) - 1 :]
            return REGISTRY[route], replace(parsed, positional=remaining)
    return None


async def dispatch(ctx: CommandContext, raw_text: str) -> str | None:
    if not raw_text.lstrip().startswith("!"):
        return "All commands must start with !."

    try:
        parsed = parse_command(raw_text)
    except ValueError as exc:
        return f"Could not parse command: {exc}"

    if not parsed.command:
        parsed = replace(parsed, command="help")

    matched = _match_handler(parsed)
    if matched is not None:
        handler, args = matched
        return await handler(ctx, args)
    return f"Unknown command: {parsed.command}"


__all__ = ["CommandContext", "dispatch", "parse_command"]
