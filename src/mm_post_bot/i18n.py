# ruff: noqa: RUF001
from typing import Any

SUPPORTED_LOCALES = frozenset({"en", "ru"})
FALLBACK_LOCALE = "en"

CATALOG: dict[str, dict[str, str]] = {
    "en": {
        "command.must_start": "All commands must start with !.",
        "command.parse_error": "Could not parse command: {error}",
        "command.unknown": "Unknown command: {command}",
        "lang.current": "Current language: {locale}. Supported languages: en, ru.",
        "lang.changed.en": "Language changed to English.",
        "lang.changed.ru": "Language changed to Russian.",
        "lang.usage": "Usage: !lang [en|ru]",
        "lang.unsupported": "Unsupported language: {locale}. Supported languages: en, ru.",
        "access.not_registered": "You are not registered yet. Run !register to request approval.",
        "access.not_registered_status": (
            "You are not registered yet. Run !register to request access."
        ),
        "access.blocked": "Your access is blocked. Contact an admin for help.",
        "access.pending": (
            "Your account is pending approval. Please wait for an admin to approve you."
        ),
        "register.admin": (
            "Registered {username} as admin.\n"
            "Your access is approved automatically because your username is configured "
            "in MM_ADMINS.\n"
            "You can approve users and use posting commands."
        ),
        "register.user": "Registered {username} as {role}. Current status: {status}.",
        "register.admin_request": (
            "New registration request from {username} ({user_id}).\n"
            "Approve with: !user approve {username}"
        ),
        "status.line": "{username} is {status} as {role}.",
        "help.core.title": "Core",
        "help.core.help": "!help - show available commands",
        "help.core.register": "!register - register for posting access",
        "help.core.status": "!status - show your registration status",
        "help.core.setup": "!setup - show posting setup checklist",
        "help.core.next": "!next - show the next recommended posting step",
        "help.core.lang": "!lang [en|ru] - show or change reply language",
        "help.admin_bootstrap.title": "Admin bootstrap",
        "help.admin_bootstrap.configured": "You are configured as an admin in MM_ADMINS.",
        "help.admin_bootstrap.can_approve": "You can approve registration requests now.",
        "help.admin_bootstrap.register": (
            "Run !register to activate your local admin account and enable posting commands."
        ),
        "help.registration.title": "Registration",
        "help.registration.pending": "Your account is pending approval.",
        "help.registration.blocked": "Your access is blocked. Contact an admin.",
        "help.registration.unregistered": "Run !register to request posting access.",
        "help.posting_bots.title": "Posting bots",
        "help.posting_bots.add": "!bot add <alias> <token> - add a posting bot token",
        "help.posting_bots.list": "!bot list - list your posting bots",
        "help.posting_bots.remove": "!bot remove <alias> - remove a posting bot",
        "help.channels.title": "Channels",
        "help.channels.add": "!channel add <alias> <channel_id> - add a channel alias",
        "help.channels.add_current": (
            "@postbot !channel add-current <alias> - save the current channel as an alias"
        ),
        "help.channels.set": "!channel set <alias> <channel_id> - update a channel alias",
        "help.channels.remove": "!channel remove <alias> - remove a channel alias",
        "help.channels.list": "!channel list - list your channel aliases",
        "help.channels.show": "!channel show <alias> - show a channel alias",
        "help.defaults.title": "Defaults",
        "help.defaults.show": "!default - show your default bot and channel",
        "help.defaults.set": (
            "!default set --bot <alias> --channel <channel_alias> - set default target"
        ),
        "help.defaults.clear": "!default clear - clear default target",
        "help.drafts.title": "Drafts",
        "help.drafts.start": "!draft - capture your next DM as a draft",
        "help.drafts.cancel": "!draft cancel - cancel active draft capture",
        "help.drafts.list": "!draft list - list saved drafts",
        "help.drafts.show": "!draft show <draft_id> - show a saved draft",
        "help.drafts.delete": "!draft delete <draft_id> - delete a saved draft",
        "help.publishing.title": "Publishing",
        "help.publishing.send": (
            "!send <draft_id> [--bot <alias>] [--channel <channel_alias>] - publish a draft"
        ),
        "help.publishing.web": "!web - open the web UI",
        "help.admin.title": "Admin",
        "help.admin.approve": "!user approve <username|user_id> - approve a user",
        "help.admin.block": "!user block <username|user_id> - block a user",
        "help.admin.unblock": "!user unblock <username|user_id> - unblock and approve a user",
        "help.admin.list": "!user list [pending|approved|blocked] - list users",
        "web.usage": "Usage: !web",
        "web.dm_only": "Run !web in DM so the login link is private.",
        "web.link": "Open web UI: {url}\nThis link is single-use and expires soon.",
        "web.nav.primary": "Primary",
        "web.nav.composer": "Composer",
        "web.nav.drafts": "Drafts",
        "web.nav.targets": "Targets",
        "web.nav.audit": "Audit",
        "web.language.label": "Language",
        "web.language.apply": "Apply",
        "web.language.en": "English",
        "web.language.ru": "Russian",
        "web.login_required.title": "Login required",
        "web.login_required.content": (
            "Open a fresh login link from Mattermost to use the web composer."
        ),
        "web.page.composer": "Composer",
        "web.page.drafts": "Drafts",
        "web.page.targets": "Targets",
        "web.page.audit": "Audit",
        "web.page.draft_detail": "Draft {draft_id}",
        "web.composer.eyebrow": "Composer",
        "web.composer.heading": "New Mattermost post",
        "web.composer.message": "Message",
        "web.composer.placeholder": "Write the post body here.",
        "web.composer.save": "Save draft",
        "web.composer.defaults_aria": "Posting defaults",
        "web.common.targets": "Targets",
        "web.common.bot": "Bot",
        "web.common.channel": "Channel",
        "web.common.not_selected": "Not selected",
        "web.common.default_target": "Default target",
        "web.common.ready_to_publish": "Ready to publish",
        "web.common.target_missing": "No default target selected.",
        "web.common.target_stale": "Default target is incomplete.",
        "web.drafts.eyebrow": "Drafts",
        "web.drafts.heading": "Saved drafts",
        "web.drafts.count_one": "{count} draft",
        "web.drafts.count_many": "{count} drafts",
        "web.drafts.aria": "Saved drafts",
        "web.drafts.table.id": "ID",
        "web.drafts.table.preview": "Preview",
        "web.drafts.table.created": "Created",
        "web.drafts.table.action": "Action",
        "web.drafts.open": "Open",
        "web.drafts.empty.title": "No drafts yet",
        "web.drafts.empty.body": "Saved composer drafts will appear here.",
        "web.drafts.empty.action": "New draft",
        "web.draft_detail.eyebrow": "Draft #{draft_id}",
        "web.draft_detail.heading": "Edit draft",
        "web.draft_detail.created": "Created {timestamp}",
        "web.draft_detail.updated": "Updated {timestamp}",
        "web.draft_detail.back": "Back to drafts",
        "web.draft_detail.save": "Save changes",
        "web.draft_detail.actions_aria": "Draft actions",
        "web.draft_detail.actions": "Actions",
        "web.draft_detail.bot_alias": "Bot alias",
        "web.draft_detail.channel_alias": "Channel alias",
        "web.draft_detail.use_default": "Use default",
        "web.draft_detail.use_default_value": "Use default: {value}",
        "web.draft_detail.publish": "Publish",
        "web.draft_detail.delete": "Delete draft",
        "web.targets.eyebrow": "Targets",
        "web.targets.heading": "Posting targets",
        "web.targets.bots_count_one": "{count} bot",
        "web.targets.bots_count_many": "{count} bots",
        "web.targets.channels_count_one": "{count} channel",
        "web.targets.channels_count_many": "{count} channels",
        "web.targets.default_aria": "Default target",
        "web.targets.default_current": "Default: {bot_alias} -> {channel_alias}",
        "web.targets.default_stale": (
            "Default target is missing because its bot or channel was removed."
        ),
        "web.targets.default_none": "No default target selected.",
        "web.targets.bots": "Bots",
        "web.targets.channels": "Channels",
        "web.targets.default": "Default",
        "web.targets.no_bots": "No posting bots yet.",
        "web.targets.no_channels": "No channels yet.",
        "web.targets.bot_alias": "Bot alias",
        "web.targets.channel_alias": "Channel alias",
        "web.targets.set_default": "Set default",
        "web.targets.clear_default": "Clear default",
        "web.targets.channel_search_aria": "Mattermost channel search",
        "web.targets.channel_search": "Search Mattermost channels",
        "web.targets.channel_search_body": (
            "Find an existing channel from the teams available to the manager bot, "
            "then save it as a posting alias."
        ),
        "web.targets.channel_search_query": "Channel name",
        "web.targets.channel_search_placeholder": "town-square or marketing",
        "web.targets.channel_search_submit": "Search",
        "web.targets.channel_search_alias": "New alias",
        "web.targets.channel_search_alias_placeholder": "Short posting alias",
        "web.targets.channel_search_channel": "Found channel",
        "web.targets.channel_search_add": "Add channel",
        "web.targets.channel_search_save": "Save channel",
        "web.targets.channel_search_selected": "Selected:",
        "web.targets.channel_search_min_query": "Type at least 2 characters to search.",
        "web.targets.channel_search_loading": "Searching channels...",
        "web.targets.channel_search_empty": "No channels found for that search.",
        "web.targets.channel_added_banner": "Channel alias {alias} added.",
        "web.audit.eyebrow": "Recent activity",
        "web.audit.heading": "Audit",
        "web.audit.last_records": "Last 50 records",
        "web.audit.aria": "Audit records",
        "web.audit.table.created": "Created",
        "web.audit.table.status": "Status",
        "web.audit.table.draft": "Draft",
        "web.audit.table.bot": "Bot",
        "web.audit.table.channel": "Channel",
        "web.audit.table.post": "Post",
        "web.audit.table.error": "Error",
        "web.audit.empty.title": "No audit records",
        "web.audit.empty.body": "Published drafts and failed publish attempts will appear here.",
        "web.audit.published_banner": "Draft #{draft_id} published.",
        "web.error.login_invalid": "Login link is invalid or expired",
        "web.error.user_not_approved": "User is not approved",
        "web.error.draft_not_found": "Draft not found",
        "web.error.draft_empty": "Draft message cannot be empty",
        "web.error.target_aliases_invalid": "Target aliases are invalid",
        "web.error.default_bot_not_in_channel": (
            "First add bot {bot_username} to Mattermost channel {channel_alias}."
        ),
        "web.error.default_membership_check_failed": (
            "Could not verify that the bot is in this Mattermost channel."
        ),
        "web.error.channel_alias_duplicate": "Channel alias already exists",
        "web.error.channel_add_invalid": "Choose a channel and enter an alias.",
        "web.error.channel_search_failed": "Could not search Mattermost channels.",
        "web.error.unsupported_language": "Unsupported language",
        "web.error.defaults_missing": "No default bot/channel configured.",
        "web.error.default_stale": "Default target is incomplete.",
        "web.error.draft_unavailable": "Draft not found or unavailable.",
        "web.error.bot_not_found": "Could not find that bot.",
        "web.error.channel_not_found": "Could not find that channel alias.",
        "web.error.storage_misconfigured": "Bot token storage is misconfigured.",
        "web.error.bot_not_in_channel": (
            "Add the selected bot to the target Mattermost channel before publishing."
        ),
        "web.error.publish_failed": "Could not publish the post.",
        "web.error.local_update_failed": "Mattermost accepted the post, but local update failed.",
        "bot.dm_only": "Please add bot tokens in a direct message.",
        "bot.add_usage": "Usage: !bot add <alias> <token>",
        "bot.duplicate": (
            "You already have a bot named {alias}. Remove it before adding it again."
        ),
        "bot.validate_failed": "Could not validate that bot token. Please check it and try again.",
        "bot.regular_user_token": (
            "That token belongs to a regular user. Please provide a bot token."
        ),
        "bot.storage_misconfigured": (
            "Bot token storage is misconfigured. Please contact an administrator."
        ),
        "bot.added": "Added bot {alias} ({bot_username}).",
        "bot.list_empty": "No bots added yet.",
        "bot.remove_usage": "Usage: !bot remove <alias>",
        "bot.not_found": "Could not find a bot named {alias}.",
        "bot.removed": "Removed bot {alias}.",
        "channel.add_usage": "Usage: !channel add <alias> <channel_id>",
        "channel.add_current_usage": "Usage: !channel add-current <alias>",
        "channel.add_current_channel_only": (
            "Run this from the Mattermost channel you want to save, for example: "
            "@postbot !channel add-current town"
        ),
        "channel.set_usage": "Usage: !channel set <alias> <channel_id>",
        "channel.remove_usage": "Usage: !channel remove <alias>",
        "channel.list_usage": "Usage: !channel list",
        "channel.show_usage": "Usage: !channel show <alias>",
        "channel.duplicate": (
            "You already have a channel named {alias}. Use !channel set {alias} <channel_id>."
        ),
        "channel.added": "Added channel {alias}.",
        "channel.add_current_added": "Added current channel as {alias}.",
        "channel.updated": "Updated channel {alias}.",
        "channel.removed": "Removed channel {alias}.",
        "channel.not_found": "Could not find a channel named {alias}.",
        "channel.list_empty": "No channels added yet.",
        "channel.dm_only": "Please manage channel aliases in a direct message.",
        "channel.id_not_link": "Please provide a Mattermost channel id, not a channel link.",
        "default.usage": "Usage: !default [set --bot <alias> --channel <channel_alias>|clear]",
        "default.set_usage": "Usage: !default set --bot <alias> --channel <channel_alias>",
        "default.clear_usage": "Usage: !default clear",
        "default.dm_only": "Please manage defaults in a direct message.",
        "default.none": (
            "No default bot/channel configured. Set one with:\n"
            "!default set --bot <alias> --channel <channel_alias>"
        ),
        "default.current": (
            "Default bot: {bot_alias} ({bot_username})\n"
            "Default channel: {channel_alias} ({channel_id})"
        ),
        "default.set": "Default target set: bot {bot_alias}, channel {channel_alias}.",
        "default.bot_not_in_channel": (
            "Add bot {bot_username} to Mattermost channel {channel_alias} before setting "
            "this default."
        ),
        "default.membership_check_failed": (
            "Could not verify that the bot is in this Mattermost channel."
        ),
        "default.cleared": "Default target cleared.",
        "default.bot_not_found": "Could not find a bot named {alias}.",
        "default.channel_not_found": "Could not find a channel named {alias}.",
        "default.stale": (
            "Default target is incomplete because its bot or channel was removed.\n"
            "Check aliases: !bot list and !channel list\n"
            "Set it again: !default set --bot <alias> --channel <channel_alias>\n"
            "Or clear it: !default clear"
        ),
        "draft.start_usage": "Usage: !draft",
        "draft.started": "Draft capture started. Please send the post body in this direct message.",
        "draft.cancel_usage": "Usage: !draft cancel",
        "draft.cancelled": "Draft capture cancelled.",
        "draft.list_usage": "Usage: !draft list",
        "draft.list_empty": "No saved drafts.",
        "draft.show_usage": "Usage: !draft show <draft_id>",
        "draft.delete_usage": "Usage: !draft delete <draft_id>",
        "draft.not_found": "Draft not found.",
        "draft.show": "Draft #{draft_id}:\n{message}",
        "draft.deleted": "Draft #{draft_id} deleted.",
        "draft.dm_only": "Please use draft commands in a direct message.",
        "draft.saved_header": "Draft #{draft_id} saved.",
        "draft.saved": (
            "Draft #{draft_id} saved. Send it with:\n"
            "!send {draft_id}\n"
            "Or choose target explicitly:\n"
            "!send {draft_id} --bot <alias> --channel <channel_alias>"
        ),
        "posting_state.preview": "Preview: {preview}",
        "posting_state.target.ready": (
            "Target: bot {bot_alias} ({bot_username}), channel {channel_alias} ({channel_id})"
        ),
        "posting_state.target.missing": "Target: no default bot/channel configured.",
        "posting_state.target.stale": (
            "Target: default bot/channel is incomplete because one was removed."
        ),
        "posting_state.publish.short": "Publish: !send {draft_id}",
        "posting_state.publish.explicit": (
            "Publish: !send {draft_id} --bot <alias> --channel <channel_alias>"
        ),
        "posting_state.default_recovery": (
            "Set a default with: !default set --bot <alias> --channel <channel_alias>"
        ),
        "posting_state.delete_hint": "Delete: !draft delete {draft_id}",
        "posting_state.review_hint": "Review: !draft show {draft_id}",
        "setup.usage": "Usage: !setup",
        "next.usage": "Usage: !next",
        "setup.dm_only": "Please use setup commands in a direct message.",
        "setup.registration": "Registration: {status}",
        "setup.bots": "Posting bots: {count}",
        "setup.channels": "Channels: {count}",
        "setup.default": "Default: {value}",
        "setup.drafts": "Drafts: {count}",
        "setup.next": "Next: {command}",
        "next.context.register": "Register first so an admin can approve posting access.",
        "next.context.status": "Check your access status before continuing.",
        "next.context.bot": "Add a posting bot alias before you can publish.",
        "next.context.channel": "Add a channel alias so posts have a destination.",
        "next.context.default": "Set a default target to enable the short send command.",
        "next.context.draft": "Start draft capture when you are ready to write the post.",
        "next.context.draft_list": "Review saved drafts before publishing or deleting them.",
        "send.usage": "Usage: !send <draft_id> [--bot <alias>] [--channel <channel_alias>]",
        "send.defaults_missing": (
            "No default bot/channel configured.\n"
            "Check aliases: !bot list and !channel list\n"
            "Set a default: !default set --bot <alias> --channel <channel_alias>\n"
            "Or send explicitly: "
            "!send <draft_id> --bot <alias> --channel <channel_alias>"
        ),
        "send.default_stale": (
            "Default target is incomplete because its bot or channel was removed.\n"
            "Check aliases: !bot list and !channel list\n"
            "Set it again: !default set --bot <alias> --channel <channel_alias>\n"
            "Or clear it: !default clear"
        ),
        "send.draft_unavailable": "Draft not found or unavailable. Check drafts: !draft list",
        "send.bot_not_found": "Could not find that bot. Check aliases with: !bot list",
        "send.channel_not_found": (
            "Could not find that channel alias.\n"
            "Check aliases: !channel list\n"
            "From a channel, save it with: @postbot !channel add-current <alias>"
        ),
        "send.storage_misconfigured": (
            "Bot token storage is misconfigured. Please contact an administrator."
        ),
        "send.publish_failed": (
            "Could not publish the post. Please check bot permissions and channel id."
        ),
        "send.bot_not_in_channel": (
            "Add the selected bot to the target Mattermost channel before publishing."
        ),
        "send.local_update_failed": (
            "Mattermost accepted the post, but the local status update failed. "
            "Please contact an administrator before retrying this draft."
        ),
        "send.published": "Draft #{draft_id} published.",
        "user.admin_only": "Only admins can use this command.",
        "user.approve_usage": "Usage: !user approve <username|user_id>",
        "user.block_usage": "Usage: !user block <username|user_id>",
        "user.unblock_usage": "Usage: !user unblock <username|user_id>",
        "user.not_found": "Could not find user {target}.",
        "user.configured_admin_block": "Configured admins cannot be blocked.",
        "user.approved": "Approved {username} ({user_id}).",
        "user.blocked": "Blocked {username} ({user_id}).",
        "user.unblocked": "Unblocked and approved {username} ({user_id}).",
        "user.invalid_status": "Status must be one of: pending, approved, blocked.",
        "user.list_empty": "No users{suffix}.",
        "user.list_empty_suffix": " with status {status}",
        "user.notify_approved": "Your mm-post-bot access has been approved.",
        "user.notify_blocked": "Your mm-post-bot access has been blocked.",
        "user.notify_unblocked": "Your mm-post-bot access has been unblocked and approved.",
    },
    "ru": {
        "command.must_start": "Все команды должны начинаться с !.",
        "command.parse_error": "Не удалось разобрать команду: {error}",
        "command.unknown": "Неизвестная команда: {command}",
        "lang.current": "Текущий язык: {locale}. Доступные языки: en, ru.",
        "lang.changed.en": "Язык изменён на английский.",
        "lang.changed.ru": "Язык изменён на русский.",
        "lang.usage": "Использование: !lang [en|ru]",
        "lang.unsupported": "Неподдерживаемый язык: {locale}. Доступные языки: en, ru.",
        "access.not_registered": (
            "Вы ещё не зарегистрированы. Выполните !register, чтобы запросить доступ."
        ),
        "access.not_registered_status": (
            "Вы ещё не зарегистрированы. Выполните !register, чтобы запросить доступ."
        ),
        "access.blocked": "Ваш доступ заблокирован. Обратитесь к администратору.",
        "access.pending": "Ваша заявка ожидает подтверждения администратором.",
        "register.admin": (
            "Пользователь {username} зарегистрирован как admin.\n"
            "Доступ подтверждён автоматически, потому что username указан в MM_ADMINS.\n"
            "Теперь можно подтверждать пользователей и пользоваться posting-командами."
        ),
        "register.user": (
            "Пользователь {username} зарегистрирован как {role}. Текущий статус: {status}."
        ),
        "register.admin_request": (
            "Новая заявка на регистрацию от {username} ({user_id}).\n"
            "Подтвердить: !user approve {username}"
        ),
        "status.line": "{username}: статус {status}, роль {role}.",
        "help.core.title": "Основное",
        "help.core.help": "!help - показать доступные команды",
        "help.core.register": "!register - запросить доступ к постингу",
        "help.core.status": "!status - показать статус регистрации",
        "help.core.setup": "!setup - показать checklist настройки постинга",
        "help.core.next": "!next - показать следующий рекомендуемый шаг",
        "help.core.lang": "!lang [en|ru] - показать или изменить язык ответов",
        "help.admin_bootstrap.title": "Старт администратора",
        "help.admin_bootstrap.configured": "Вы указаны как администратор в MM_ADMINS.",
        "help.admin_bootstrap.can_approve": "Вы уже можете подтверждать заявки на регистрацию.",
        "help.admin_bootstrap.register": (
            "Выполните !register, чтобы активировать локальную admin-запись и posting-команды."
        ),
        "help.registration.title": "Регистрация",
        "help.registration.pending": "Ваша заявка ожидает подтверждения.",
        "help.registration.blocked": "Ваш доступ заблокирован. Обратитесь к администратору.",
        "help.registration.unregistered": "Выполните !register, чтобы запросить доступ к постингу.",
        "help.posting_bots.title": "Posting-боты",
        "help.posting_bots.add": "!bot add <alias> <token> - добавить token posting-бота",
        "help.posting_bots.list": "!bot list - показать ваших posting-ботов",
        "help.posting_bots.remove": "!bot remove <alias> - удалить posting-бота",
        "help.channels.title": "Каналы",
        "help.channels.add": "!channel add <alias> <channel_id> - добавить alias канала",
        "help.channels.add_current": (
            "@postbot !channel add-current <alias> - сохранить текущий канал как alias"
        ),
        "help.channels.set": "!channel set <alias> <channel_id> - изменить alias канала",
        "help.channels.remove": "!channel remove <alias> - удалить alias канала",
        "help.channels.list": "!channel list - показать aliases каналов",
        "help.channels.show": "!channel show <alias> - показать alias канала",
        "help.defaults.title": "По умолчанию",
        "help.defaults.show": "!default - показать bot и channel по умолчанию",
        "help.defaults.set": (
            "!default set --bot <alias> --channel <channel_alias> - задать цель по умолчанию"
        ),
        "help.defaults.clear": "!default clear - очистить цель по умолчанию",
        "help.drafts.title": "Черновики",
        "help.drafts.start": "!draft - сохранить следующее DM как черновик",
        "help.drafts.cancel": "!draft cancel - отменить ожидание черновика",
        "help.drafts.list": "!draft list - показать сохранённые черновики",
        "help.drafts.show": "!draft show <draft_id> - показать черновик",
        "help.drafts.delete": "!draft delete <draft_id> - удалить черновик",
        "help.publishing.title": "Публикация",
        "help.publishing.send": (
            "!send <draft_id> [--bot <alias>] [--channel <channel_alias>] - опубликовать черновик"
        ),
        "help.publishing.web": "!web - открыть web UI",
        "help.admin.title": "Администрирование",
        "help.admin.approve": "!user approve <username|user_id> - подтвердить пользователя",
        "help.admin.block": "!user block <username|user_id> - заблокировать пользователя",
        "help.admin.unblock": "!user unblock <username|user_id> - разблокировать пользователя",
        "help.admin.list": "!user list [pending|approved|blocked] - показать пользователей",
        "web.usage": "Использование: !web",
        "web.dm_only": "Выполните !web в DM, чтобы ссылка входа осталась приватной.",
        "web.link": "Открыть web UI: {url}\nСсылка одноразовая и скоро истечёт.",
        "web.nav.primary": "Основная навигация",
        "web.nav.composer": "Редактор",
        "web.nav.drafts": "Черновики",
        "web.nav.targets": "Цели",
        "web.nav.audit": "Аудит",
        "web.language.label": "Язык",
        "web.language.apply": "Применить",
        "web.language.en": "Английский",
        "web.language.ru": "Русский",
        "web.login_required.title": "Требуется вход",
        "web.login_required.content": (
            "Откройте свежую ссылку входа из Mattermost, чтобы пользоваться web-редактором."
        ),
        "web.page.composer": "Редактор",
        "web.page.drafts": "Черновики",
        "web.page.targets": "Цели",
        "web.page.audit": "Аудит",
        "web.page.draft_detail": "Черновик {draft_id}",
        "web.composer.eyebrow": "Редактор",
        "web.composer.heading": "Новый пост Mattermost",
        "web.composer.message": "Сообщение",
        "web.composer.placeholder": "Напишите текст поста здесь.",
        "web.composer.save": "Сохранить черновик",
        "web.composer.defaults_aria": "Цели публикации по умолчанию",
        "web.common.targets": "Цели",
        "web.common.bot": "Бот",
        "web.common.channel": "Канал",
        "web.common.not_selected": "Не выбрано",
        "web.common.default_target": "Цель по умолчанию",
        "web.common.ready_to_publish": "Готово к публикации",
        "web.common.target_missing": "Цель по умолчанию не выбрана.",
        "web.common.target_stale": "Цель по умолчанию неполная.",
        "web.drafts.eyebrow": "Черновики",
        "web.drafts.heading": "Сохранённые черновики",
        "web.drafts.count_one": "{count} черновик",
        "web.drafts.count_many": "{count} черновиков",
        "web.drafts.aria": "Сохранённые черновики",
        "web.drafts.table.id": "ID",
        "web.drafts.table.preview": "Превью",
        "web.drafts.table.created": "Создан",
        "web.drafts.table.action": "Действие",
        "web.drafts.open": "Открыть",
        "web.drafts.empty.title": "Черновиков пока нет",
        "web.drafts.empty.body": "Сохранённые черновики из редактора появятся здесь.",
        "web.drafts.empty.action": "Новый черновик",
        "web.draft_detail.eyebrow": "Черновик #{draft_id}",
        "web.draft_detail.heading": "Редактировать черновик",
        "web.draft_detail.created": "Создан {timestamp}",
        "web.draft_detail.updated": "Обновлён {timestamp}",
        "web.draft_detail.back": "Назад к черновикам",
        "web.draft_detail.save": "Сохранить изменения",
        "web.draft_detail.actions_aria": "Действия с черновиком",
        "web.draft_detail.actions": "Действия",
        "web.draft_detail.bot_alias": "Алиас бота",
        "web.draft_detail.channel_alias": "Алиас канала",
        "web.draft_detail.use_default": "Использовать по умолчанию",
        "web.draft_detail.use_default_value": "По умолчанию: {value}",
        "web.draft_detail.publish": "Опубликовать",
        "web.draft_detail.delete": "Удалить черновик",
        "web.targets.eyebrow": "Цели",
        "web.targets.heading": "Цели публикации",
        "web.targets.bots_count_one": "{count} бот",
        "web.targets.bots_count_many": "{count} ботов",
        "web.targets.channels_count_one": "{count} канал",
        "web.targets.channels_count_many": "{count} каналов",
        "web.targets.default_aria": "Цель по умолчанию",
        "web.targets.default_current": "По умолчанию: {bot_alias} -> {channel_alias}",
        "web.targets.default_stale": "Цель по умолчанию неполная: бот или канал был удалён.",
        "web.targets.default_none": "Цель по умолчанию не выбрана.",
        "web.targets.bots": "Боты",
        "web.targets.channels": "Каналы",
        "web.targets.default": "По умолчанию",
        "web.targets.no_bots": "Боты для публикации пока не добавлены.",
        "web.targets.no_channels": "Каналы пока не добавлены.",
        "web.targets.bot_alias": "Алиас бота",
        "web.targets.channel_alias": "Алиас канала",
        "web.targets.set_default": "Задать по умолчанию",
        "web.targets.clear_default": "Очистить",
        "web.targets.channel_search_aria": "Поиск каналов Mattermost",
        "web.targets.channel_search": "Поиск каналов Mattermost",
        "web.targets.channel_search_body": (
            "Найдите существующий канал из команд, доступных manager-боту, "
            "и сохраните его как алиас для публикаций."
        ),
        "web.targets.channel_search_query": "Название канала",
        "web.targets.channel_search_placeholder": "town-square или marketing",
        "web.targets.channel_search_submit": "Искать",
        "web.targets.channel_search_alias": "Новый алиас",
        "web.targets.channel_search_alias_placeholder": "Короткий алиас для постинга",
        "web.targets.channel_search_channel": "Найденный канал",
        "web.targets.channel_search_add": "Добавить канал",
        "web.targets.channel_search_save": "Сохранить канал",
        "web.targets.channel_search_selected": "Выбран:",
        "web.targets.channel_search_min_query": "Введите минимум 2 символа для поиска.",
        "web.targets.channel_search_loading": "Ищем каналы...",
        "web.targets.channel_search_empty": "По этому запросу каналы не найдены.",
        "web.targets.channel_added_banner": "Алиас канала {alias} добавлен.",
        "web.audit.eyebrow": "Активность",
        "web.audit.heading": "Аудит",
        "web.audit.last_records": "Последние 50 записей",
        "web.audit.aria": "Записи аудита",
        "web.audit.table.created": "Создано",
        "web.audit.table.status": "Статус",
        "web.audit.table.draft": "Черновик",
        "web.audit.table.bot": "Бот",
        "web.audit.table.channel": "Канал",
        "web.audit.table.post": "Пост",
        "web.audit.table.error": "Ошибка",
        "web.audit.empty.title": "Записей аудита нет",
        "web.audit.empty.body": "Опубликованные черновики и ошибки публикации появятся здесь.",
        "web.audit.published_banner": "Черновик #{draft_id} опубликован.",
        "web.error.login_invalid": "Ссылка входа недействительна или истекла",
        "web.error.user_not_approved": "Пользователь не подтверждён",
        "web.error.draft_not_found": "Черновик не найден",
        "web.error.draft_empty": "Текст черновика не может быть пустым",
        "web.error.target_aliases_invalid": "Target aliases указаны неверно",
        "web.error.default_bot_not_in_channel": (
            "Сначала добавьте бота {bot_username} в Mattermost-канал {channel_alias}."
        ),
        "web.error.default_membership_check_failed": (
            "Не удалось проверить, что бот добавлен в этот Mattermost-канал."
        ),
        "web.error.channel_alias_duplicate": "Алиас канала уже существует",
        "web.error.channel_add_invalid": "Выберите канал и укажите алиас.",
        "web.error.channel_search_failed": "Не удалось выполнить поиск каналов Mattermost.",
        "web.error.unsupported_language": "Неподдерживаемый язык",
        "web.error.defaults_missing": "Bot/channel по умолчанию не настроены.",
        "web.error.default_stale": "Цель по умолчанию неполная.",
        "web.error.draft_unavailable": "Черновик не найден или недоступен.",
        "web.error.bot_not_found": "Указанный бот не найден.",
        "web.error.channel_not_found": "Указанный channel alias не найден.",
        "web.error.storage_misconfigured": "Хранилище bot token настроено неверно.",
        "web.error.bot_not_in_channel": (
            "Добавьте выбранного бота в целевой Mattermost-канал перед публикацией."
        ),
        "web.error.publish_failed": "Не удалось опубликовать пост.",
        "web.error.local_update_failed": (
            "Mattermost принял пост, но локальный статус не обновился."
        ),
        "bot.dm_only": "Добавляйте token бота только в direct message.",
        "bot.add_usage": "Использование: !bot add <alias> <token>",
        "bot.duplicate": (
            "У вас уже есть bot alias {alias}. Удалите его перед повторным добавлением."
        ),
        "bot.validate_failed": "Не удалось проверить token бота. Проверьте его и попробуйте снова.",
        "bot.regular_user_token": (
            "Этот token принадлежит обычному пользователю. Укажите token бота."
        ),
        "bot.storage_misconfigured": (
            "Хранилище bot token настроено неверно. Обратитесь к администратору."
        ),
        "bot.added": "Bot {alias} ({bot_username}) добавлен.",
        "bot.list_empty": "Боты ещё не добавлены.",
        "bot.remove_usage": "Использование: !bot remove <alias>",
        "bot.not_found": "Бот с именем {alias} не найден.",
        "bot.removed": "Bot {alias} удалён.",
        "channel.add_usage": "Использование: !channel add <alias> <channel_id>",
        "channel.add_current_usage": "Использование: !channel add-current <alias>",
        "channel.add_current_channel_only": (
            "Выполните эту команду в нужном Mattermost-канале, например: "
            "@postbot !channel add-current town"
        ),
        "channel.set_usage": "Использование: !channel set <alias> <channel_id>",
        "channel.remove_usage": "Использование: !channel remove <alias>",
        "channel.list_usage": "Использование: !channel list",
        "channel.show_usage": "Использование: !channel show <alias>",
        "channel.duplicate": (
            "У вас уже есть channel alias {alias}. Используйте !channel set {alias} <channel_id>."
        ),
        "channel.added": "Channel alias {alias} добавлен.",
        "channel.add_current_added": "Текущий канал сохранён как {alias}.",
        "channel.updated": "Channel alias {alias} обновлён.",
        "channel.removed": "Channel alias {alias} удалён.",
        "channel.not_found": "Channel alias {alias} не найден.",
        "channel.list_empty": "Каналы ещё не добавлены.",
        "channel.dm_only": "Управляйте channel aliases только в direct message.",
        "channel.id_not_link": "Укажите Mattermost channel id, а не ссылку на канал.",
        "default.usage": (
            "Использование: !default [set --bot <alias> --channel <channel_alias>|clear]"
        ),
        "default.set_usage": "Использование: !default set --bot <alias> --channel <channel_alias>",
        "default.clear_usage": "Использование: !default clear",
        "default.dm_only": "Управляйте настройками по умолчанию только в direct message.",
        "default.none": (
            "Bot/channel по умолчанию не настроены. Задать можно командой:\n"
            "!default set --bot <alias> --channel <channel_alias>"
        ),
        "default.current": (
            "Bot по умолчанию: {bot_alias} ({bot_username})\n"
            "Channel по умолчанию: {channel_alias} ({channel_id})"
        ),
        "default.set": "Цель по умолчанию задана: bot {bot_alias}, channel {channel_alias}.",
        "default.bot_not_in_channel": (
            "Добавьте бота {bot_username} в Mattermost-канал {channel_alias}, прежде чем "
            "задавать эту цель."
        ),
        "default.membership_check_failed": (
            "Не удалось проверить, что бот добавлен в этот Mattermost-канал."
        ),
        "default.cleared": "Цель по умолчанию очищена.",
        "default.bot_not_found": "Бот с именем {alias} не найден.",
        "default.channel_not_found": "Channel alias {alias} не найден.",
        "default.stale": (
            "Цель по умолчанию неполная: bot или channel был удалён.\n"
            "Проверить aliases: !bot list и !channel list\n"
            "Задать заново: !default set --bot <alias> --channel <channel_alias>\n"
            "Или очистить: !default clear"
        ),
        "draft.start_usage": "Использование: !draft",
        "draft.started": (
            "Ожидание черновика включено. Отправьте текст поста в этом direct message."
        ),
        "draft.cancel_usage": "Использование: !draft cancel",
        "draft.cancelled": "Ожидание черновика отменено.",
        "draft.list_usage": "Использование: !draft list",
        "draft.list_empty": "Сохранённых черновиков нет.",
        "draft.show_usage": "Использование: !draft show <draft_id>",
        "draft.delete_usage": "Использование: !draft delete <draft_id>",
        "draft.not_found": "Черновик не найден.",
        "draft.show": "Черновик #{draft_id}:\n{message}",
        "draft.deleted": "Черновик #{draft_id} удалён.",
        "draft.dm_only": "Используйте команды черновиков только в direct message.",
        "draft.saved_header": "Черновик #{draft_id} сохранён.",
        "draft.saved": (
            "Черновик #{draft_id} сохранён. Отправить его можно командой:\n"
            "!send {draft_id}\n"
            "Или выбрать цель явно:\n"
            "!send {draft_id} --bot <alias> --channel <channel_alias>"
        ),
        "posting_state.preview": "Предпросмотр: {preview}",
        "posting_state.target.ready": (
            "Цель: bot {bot_alias} ({bot_username}), channel {channel_alias} ({channel_id})"
        ),
        "posting_state.target.missing": "Цель: bot/channel по умолчанию не настроены.",
        "posting_state.target.stale": (
            "Цель: bot/channel по умолчанию неполная, потому что один alias удалён."
        ),
        "posting_state.publish.short": "Опубликовать: !send {draft_id}",
        "posting_state.publish.explicit": (
            "Опубликовать: !send {draft_id} --bot <alias> --channel <channel_alias>"
        ),
        "posting_state.default_recovery": (
            "Задать цель по умолчанию: !default set --bot <alias> --channel <channel_alias>"
        ),
        "posting_state.delete_hint": "Удалить: !draft delete {draft_id}",
        "posting_state.review_hint": "Проверить: !draft show {draft_id}",
        "setup.usage": "Использование: !setup",
        "next.usage": "Использование: !next",
        "setup.dm_only": "Используйте команды настройки только в direct message.",
        "setup.registration": "Регистрация: {status}",
        "setup.bots": "Posting-боты: {count}",
        "setup.channels": "Каналы: {count}",
        "setup.default": "По умолчанию: {value}",
        "setup.drafts": "Черновики: {count}",
        "setup.next": "Дальше: {command}",
        "next.context.register": "Сначала зарегистрируйтесь, чтобы админ открыл доступ.",
        "next.context.status": "Проверьте статус доступа перед продолжением.",
        "next.context.bot": "Добавьте bot alias, чтобы потом публиковать посты.",
        "next.context.channel": "Добавьте channel alias, чтобы постам было куда отправляться.",
        "next.context.default": "Задайте цель по умолчанию для короткой команды отправки.",
        "next.context.draft": "Начните черновик, когда будете готовы написать пост.",
        "next.context.draft_list": (
            "Проверьте сохранённые черновики перед публикацией или удалением."
        ),
        "send.usage": "Использование: !send <draft_id> [--bot <alias>] [--channel <channel_alias>]",
        "send.defaults_missing": (
            "Bot/channel по умолчанию не настроены.\n"
            "Проверить aliases: !bot list и !channel list\n"
            "Задать цель: !default set --bot <alias> --channel <channel_alias>\n"
            "Или отправить явно: "
            "!send <draft_id> --bot <alias> --channel <channel_alias>"
        ),
        "send.default_stale": (
            "Цель по умолчанию неполная: bot или channel был удалён.\n"
            "Проверить aliases: !bot list и !channel list\n"
            "Задать заново: !default set --bot <alias> --channel <channel_alias>\n"
            "Или очистить: !default clear"
        ),
        "send.draft_unavailable": "Черновик не найден или недоступен. Проверьте: !draft list",
        "send.bot_not_found": "Указанный бот не найден. Проверить aliases: !bot list",
        "send.channel_not_found": (
            "Указанный channel alias не найден.\n"
            "Проверить aliases: !channel list\n"
            "Из канала можно сохранить alias: @postbot !channel add-current <alias>"
        ),
        "send.storage_misconfigured": (
            "Хранилище bot token настроено неверно. Обратитесь к администратору."
        ),
        "send.publish_failed": "Не удалось опубликовать пост. Проверьте права бота и channel id.",
        "send.bot_not_in_channel": (
            "Добавьте выбранного бота в целевой Mattermost-канал перед публикацией."
        ),
        "send.local_update_failed": (
            "Mattermost принял пост, но локальный статус не обновился. "
            "Обратитесь к администратору перед повторной отправкой этого черновика."
        ),
        "send.published": "Черновик #{draft_id} опубликован.",
        "user.admin_only": "Эта команда доступна только администраторам.",
        "user.approve_usage": "Использование: !user approve <username|user_id>",
        "user.block_usage": "Использование: !user block <username|user_id>",
        "user.unblock_usage": "Использование: !user unblock <username|user_id>",
        "user.not_found": "Пользователь {target} не найден.",
        "user.configured_admin_block": "Configured admins нельзя блокировать.",
        "user.approved": "Пользователь {username} ({user_id}) подтверждён.",
        "user.blocked": "Пользователь {username} ({user_id}) заблокирован.",
        "user.unblocked": "Пользователь {username} ({user_id}) разблокирован и подтверждён.",
        "user.invalid_status": "Статус должен быть одним из: pending, approved, blocked.",
        "user.list_empty": "Пользователей нет{suffix}.",
        "user.list_empty_suffix": " со статусом {status}",
        "user.notify_approved": "Ваш доступ к mm-post-bot подтверждён.",
        "user.notify_blocked": "Ваш доступ к mm-post-bot заблокирован.",
        "user.notify_unblocked": "Ваш доступ к mm-post-bot разблокирован и подтверждён.",
    },
}


def normalize_locale(value: str | None) -> str | None:
    if value is None:
        return None
    locale = value.strip().lower()
    return locale if locale in SUPPORTED_LOCALES else None


def translate(selected_locale: str | None, key: str, **params: Any) -> str:
    normalized = normalize_locale(selected_locale) or FALLBACK_LOCALE
    template = CATALOG.get(normalized, {}).get(key) or CATALOG[FALLBACK_LOCALE][key]
    return template.format(**params)


def recipient_locale(
    preferences: Any,
    user_id: str,
    *,
    default_locale: str,
) -> str:
    try:
        stored = preferences.get_locale(user_id)
    except Exception:
        stored = None
    return normalize_locale(stored) or normalize_locale(default_locale) or FALLBACK_LOCALE
