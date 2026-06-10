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
            "!send <draft_id> --bot <alias> --channel <channel_alias> - publish a draft"
        ),
        "help.admin.title": "Admin",
        "help.admin.approve": "!user approve <username|user_id> - approve a user",
        "help.admin.block": "!user block <username|user_id> - block a user",
        "help.admin.unblock": "!user unblock <username|user_id> - unblock and approve a user",
        "help.admin.list": "!user list [pending|approved|blocked] - list users",
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
        "channel.set_usage": "Usage: !channel set <alias> <channel_id>",
        "channel.remove_usage": "Usage: !channel remove <alias>",
        "channel.list_usage": "Usage: !channel list",
        "channel.show_usage": "Usage: !channel show <alias>",
        "channel.duplicate": (
            "You already have a channel named {alias}. Use !channel set {alias} <channel_id>."
        ),
        "channel.added": "Added channel {alias}.",
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
        "default.cleared": "Default target cleared.",
        "default.bot_not_found": "Could not find a bot named {alias}.",
        "default.channel_not_found": "Could not find a channel named {alias}.",
        "default.stale": (
            "Default target is incomplete because its bot or channel was removed. "
            "Set it again with:\n"
            "!default set --bot <alias> --channel <channel_alias>"
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
        "draft.saved": (
            "Draft #{draft_id} saved. Send it with:\n"
            "!send {draft_id}\n"
            "Or choose target explicitly:\n"
            "!send {draft_id} --bot <alias> --channel <channel_alias>"
        ),
        "send.usage": "Usage: !send <draft_id> [--bot <alias>] [--channel <channel_alias>]",
        "send.defaults_missing": (
            "No default bot/channel configured. Set one with:\n"
            "!default set --bot <alias> --channel <channel_alias>\n"
            "Or send explicitly with:\n"
            "!send <draft_id> --bot <alias> --channel <channel_alias>"
        ),
        "send.default_stale": (
            "Default target is incomplete because its bot or channel was removed. "
            "Set it again with:\n"
            "!default set --bot <alias> --channel <channel_alias>"
        ),
        "send.draft_unavailable": "Draft not found or unavailable.",
        "send.bot_not_found": "Could not find that bot.",
        "send.channel_not_found": "Could not find that channel alias.",
        "send.storage_misconfigured": (
            "Bot token storage is misconfigured. Please contact an administrator."
        ),
        "send.publish_failed": (
            "Could not publish the post. Please check bot permissions and channel id."
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
            "!send <draft_id> --bot <alias> --channel <channel_alias> - опубликовать черновик"
        ),
        "help.admin.title": "Администрирование",
        "help.admin.approve": "!user approve <username|user_id> - подтвердить пользователя",
        "help.admin.block": "!user block <username|user_id> - заблокировать пользователя",
        "help.admin.unblock": "!user unblock <username|user_id> - разблокировать пользователя",
        "help.admin.list": "!user list [pending|approved|blocked] - показать пользователей",
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
        "channel.set_usage": "Использование: !channel set <alias> <channel_id>",
        "channel.remove_usage": "Использование: !channel remove <alias>",
        "channel.list_usage": "Использование: !channel list",
        "channel.show_usage": "Использование: !channel show <alias>",
        "channel.duplicate": (
            "У вас уже есть channel alias {alias}. Используйте !channel set {alias} <channel_id>."
        ),
        "channel.added": "Channel alias {alias} добавлен.",
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
        "default.cleared": "Цель по умолчанию очищена.",
        "default.bot_not_found": "Бот с именем {alias} не найден.",
        "default.channel_not_found": "Channel alias {alias} не найден.",
        "default.stale": (
            "Цель по умолчанию неполная: bot или channel был удалён. Задайте её заново:\n"
            "!default set --bot <alias> --channel <channel_alias>"
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
        "draft.saved": (
            "Черновик #{draft_id} сохранён. Отправить его можно командой:\n"
            "!send {draft_id}\n"
            "Или выбрать цель явно:\n"
            "!send {draft_id} --bot <alias> --channel <channel_alias>"
        ),
        "send.usage": "Использование: !send <draft_id> [--bot <alias>] [--channel <channel_alias>]",
        "send.defaults_missing": (
            "Bot/channel по умолчанию не настроены. Задайте их командой:\n"
            "!default set --bot <alias> --channel <channel_alias>\n"
            "Или отправьте явно:\n"
            "!send <draft_id> --bot <alias> --channel <channel_alias>"
        ),
        "send.default_stale": (
            "Цель по умолчанию неполная: bot или channel был удалён. Задайте её заново:\n"
            "!default set --bot <alias> --channel <channel_alias>"
        ),
        "send.draft_unavailable": "Черновик не найден или недоступен.",
        "send.bot_not_found": "Указанный бот не найден.",
        "send.channel_not_found": "Указанный channel alias не найден.",
        "send.storage_misconfigured": (
            "Хранилище bot token настроено неверно. Обратитесь к администратору."
        ),
        "send.publish_failed": "Не удалось опубликовать пост. Проверьте права бота и channel id.",
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
