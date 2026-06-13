from .context import CommandContext
from .parser import ParsedArgs
from .posting_state import setup_lines, setup_next_command


async def show(ctx: CommandContext, args: ParsedArgs) -> str:
    if args.positional or args.flags:
        return ctx.t("setup.usage")
    return "\n".join(setup_lines(ctx))


async def next_action(ctx: CommandContext, args: ParsedArgs) -> str:
    if args.positional or args.flags:
        return ctx.t("next.usage")
    return ctx.t("setup.next", command=setup_next_command(ctx))
