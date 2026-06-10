from .context import CommandContext
from .parser import ParsedArgs


async def handle(ctx: CommandContext, args: ParsedArgs) -> str:
    username = ctx.caller_username.lstrip("@")
    user_status = _caller_status(ctx)
    is_configured_admin = username in ctx.admin_usernames
    sections = [
        _section(
            ctx.t("help.core.title"),
            [
                ctx.t("help.core.help"),
                ctx.t("help.core.register"),
                ctx.t("help.core.status"),
                ctx.t("help.core.lang"),
            ],
        )
    ]

    if is_configured_admin and user_status != "approved":
        sections.append(
            _section(
                ctx.t("help.admin_bootstrap.title"),
                [
                    ctx.t("help.admin_bootstrap.configured"),
                    ctx.t("help.admin_bootstrap.can_approve"),
                    ctx.t("help.admin_bootstrap.register"),
                ],
            )
        )

    if user_status == "pending":
        sections.append(
            _section(ctx.t("help.registration.title"), [ctx.t("help.registration.pending")])
        )
    elif user_status == "blocked":
        sections.append(
            _section(ctx.t("help.registration.title"), [ctx.t("help.registration.blocked")])
        )
    elif user_status == "approved":
        sections.extend(_approved_user_sections(ctx))
    elif not is_configured_admin:
        sections.append(
            _section(ctx.t("help.registration.title"), [ctx.t("help.registration.unregistered")])
        )

    if is_configured_admin:
        sections.append(
            _section(
                ctx.t("help.admin.title"),
                [
                    ctx.t("help.admin.approve"),
                    ctx.t("help.admin.block"),
                    ctx.t("help.admin.unblock"),
                    ctx.t("help.admin.list"),
                ],
            )
        )

    return "\n\n".join(sections)


def _approved_user_sections(ctx: CommandContext) -> list[str]:
    return [
        _section(
            ctx.t("help.posting_bots.title"),
            [
                ctx.t("help.posting_bots.add"),
                ctx.t("help.posting_bots.list"),
                ctx.t("help.posting_bots.remove"),
            ],
        ),
        _section(
            ctx.t("help.channels.title"),
            [
                ctx.t("help.channels.add"),
                ctx.t("help.channels.set"),
                ctx.t("help.channels.remove"),
                ctx.t("help.channels.list"),
                ctx.t("help.channels.show"),
            ],
        ),
        _section(
            ctx.t("help.defaults.title"),
            [
                ctx.t("help.defaults.show"),
                ctx.t("help.defaults.set"),
                ctx.t("help.defaults.clear"),
            ],
        ),
        _section(
            ctx.t("help.drafts.title"),
            [
                ctx.t("help.drafts.start"),
                ctx.t("help.drafts.cancel"),
                ctx.t("help.drafts.list"),
                ctx.t("help.drafts.show"),
                ctx.t("help.drafts.delete"),
            ],
        ),
        _section(
            ctx.t("help.publishing.title"),
            [ctx.t("help.publishing.send")],
        ),
    ]


def _section(title: str, rows: list[str]) -> str:
    return "\n".join([f"{title}:", *rows])


def _caller_status(ctx: CommandContext) -> str | None:
    try:
        return ctx.user_repo.get(ctx.caller_user_id).status
    except LookupError:
        return None
