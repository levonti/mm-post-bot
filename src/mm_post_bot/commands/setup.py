from .context import CommandContext
from .parser import ParsedArgs
from .posting_state import setup_lines, setup_next_command


def _require_dm(ctx: CommandContext) -> str | None:
    if ctx.channel_type != "D":
        return ctx.t("setup.dm_only")
    return None


async def show(ctx: CommandContext, args: ParsedArgs) -> str:
    if args.positional or args.flags:
        return ctx.t("setup.usage")
    if dm_error := _require_dm(ctx):
        return dm_error
    return "\n".join(setup_lines(ctx))


async def next_action(ctx: CommandContext, args: ParsedArgs) -> str:
    if args.positional or args.flags:
        return ctx.t("next.usage")
    if dm_error := _require_dm(ctx):
        return dm_error
    return ctx.t("setup.next", command=setup_next_command(ctx))
