from .context import CommandContext
from .parser import parse_command


async def dispatch(ctx: CommandContext, raw_text: str) -> str | None:
    parsed = parse_command(raw_text)
    if not parsed.command or parsed.command == "help":
        return "Post bot command routing is ready. Command handlers will be added in later tasks."
    if not raw_text.lstrip().startswith("!"):
        return "All commands must start with !."
    return f"Unknown command: {parsed.command}"


__all__ = ["CommandContext", "dispatch", "parse_command"]
