from ..i18n import normalize_locale, translate
from .context import CommandContext
from .parser import ParsedArgs


async def handle(ctx: CommandContext, args: ParsedArgs) -> str:
    if len(args.positional) > 1:
        return ctx.t("lang.usage")
    if not args.positional:
        return ctx.t("lang.current", locale=ctx.locale)

    raw_locale = args.positional[0]
    locale = normalize_locale(raw_locale)
    if locale is None:
        return ctx.t("lang.unsupported", locale=raw_locale)

    ctx.user_preference_repo.set_locale(ctx.caller_user_id, locale)
    return translate(locale, f"lang.changed.{locale}")
