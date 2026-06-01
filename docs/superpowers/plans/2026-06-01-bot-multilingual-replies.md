# Bot Multilingual Replies Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add multilingual bot replies for English and Russian while keeping every bot command and command syntax in English.

**Architecture:** Keep the command router English-only and localize only bot responses, help text, errors, notifications, and future button labels. Add a small in-package i18n catalog, a `!lang [en|ru]` command, and a `user_preference` table keyed by Mattermost `user_id` so language can be selected before registration. Resolve locale per incoming post in `CommandContextFactory`, fall back to `DEFAULT_LOCALE`, and localize notifications by recipient locale when possible.

**Tech Stack:** Python 3.14, PostgreSQL 15, pytest, pydantic-settings, existing Mattermost WebSocket command handlers.

---

## File Structure

- Create `src/mm_post_bot/i18n.py`: supported locales, message catalog, `normalize_locale()`, `translate()`, `recipient_locale()`.
- Create `src/mm_post_bot/commands/lang.py`: English-only `!lang`, `!lang en`, `!lang ru`.
- Modify `src/mm_post_bot/config.py`: add validated `DEFAULT_LOCALE`.
- Modify `src/mm_post_bot/db.py`: add `user_preference` table.
- Modify `src/mm_post_bot/repository.py`: add `UserPreference` dataclass and `UserPreferenceRepo`.
- Modify `src/mm_post_bot/commands/context.py`: add `user_preference_repo`, `locale`, `default_locale`, and `t()`.
- Modify `src/mm_post_bot/dispatcher.py`: wire `UserPreferenceRepo`, resolve locale, localize draft body response.
- Modify `src/mm_post_bot/commands/__init__.py`: register `!lang`, localize dispatcher-level parse/unknown errors.
- Modify command modules `access.py`, `bot.py`, `channel.py`, `draft.py`, `help.py`, `register.py`, `send.py`, `status.py`, `user_admin.py`: replace user-facing strings with i18n keys.
- Modify tests: `tests/test_i18n.py`, `tests/test_config.py`, `tests/test_repository_postgres.py`, `tests/test_dispatcher.py`, `tests/test_commands.py`.
- Modify docs: `.env.example`, `README.md`.

## Translation Rules

- Commands and examples remain English: `!help`, `!register`, `!status`, `!bot`, `!channel`, `!draft`, `!send`, `!user`, `!lang`.
- Dynamic status values stored in DB remain English internally: `pending`, `approved`, `blocked`, `admin`, `user`, `draft`, `sent`, `deleted`.
- User-facing sentences may translate those values with catalog keys where helpful, but command arguments such as `!user list pending` stay English.
- If a key is missing in the selected locale, fall back to English.
- If the selected locale is unknown, fall back to `DEFAULT_LOCALE`, then English.
- `!lang` must work before `!register`.
- Localized admin/user notifications must use the recipient locale when the recipient has a stored preference; otherwise use `DEFAULT_LOCALE`.

### Required Catalog Keys

Use these keys exactly. English text should preserve current command syntax and current behavior where possible.

```python
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
        "access.not_registered_status": "You are not registered yet. Run !register to request access.",
        "access.blocked": "Your access is blocked. Contact an admin for help.",
        "access.pending": "Your account is pending approval. Please wait for an admin to approve you.",
        "register.admin": (
            "Registered {username} as admin.\n"
            "Your access is approved automatically because your username is configured in MM_ADMINS.\n"
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
        "bot.duplicate": "You already have a bot named {alias}. Remove it before adding it again.",
        "bot.validate_failed": "Could not validate that bot token. Please check it and try again.",
        "bot.regular_user_token": "That token belongs to a regular user. Please provide a bot token.",
        "bot.storage_misconfigured": "Bot token storage is misconfigured. Please contact an administrator.",
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
            "!send {draft_id} --bot <alias> --channel <channel_alias>"
        ),
        "send.usage": "Usage: !send <draft_id> --bot <alias> --channel <channel_alias>",
        "send.draft_unavailable": "Draft not found or unavailable.",
        "send.bot_not_found": "Could not find that bot.",
        "send.channel_not_found": "Could not find that channel alias.",
        "send.storage_misconfigured": (
            "Bot token storage is misconfigured. Please contact an administrator."
        ),
        "send.publish_failed": "Could not publish the post. Please check bot permissions and channel id.",
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
        "access.not_registered": "Вы ещё не зарегистрированы. Выполните !register, чтобы запросить доступ.",
        "access.not_registered_status": "Вы ещё не зарегистрированы. Выполните !register, чтобы запросить доступ.",
        "access.blocked": "Ваш доступ заблокирован. Обратитесь к администратору.",
        "access.pending": "Ваша заявка ожидает подтверждения администратором.",
        "register.admin": (
            "Пользователь {username} зарегистрирован как admin.\n"
            "Доступ подтверждён автоматически, потому что username указан в MM_ADMINS.\n"
            "Теперь можно подтверждать пользователей и пользоваться posting-командами."
        ),
        "register.user": "Пользователь {username} зарегистрирован как {role}. Текущий статус: {status}.",
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
        "bot.duplicate": "У вас уже есть bot alias {alias}. Удалите его перед повторным добавлением.",
        "bot.validate_failed": "Не удалось проверить token бота. Проверьте его и попробуйте снова.",
        "bot.regular_user_token": "Этот token принадлежит обычному пользователю. Укажите token бота.",
        "bot.storage_misconfigured": "Хранилище bot token настроено неверно. Обратитесь к администратору.",
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
        "draft.start_usage": "Использование: !draft",
        "draft.started": "Ожидание черновика включено. Отправьте текст поста в этом direct message.",
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
            "!send {draft_id} --bot <alias> --channel <channel_alias>"
        ),
        "send.usage": "Использование: !send <draft_id> --bot <alias> --channel <channel_alias>",
        "send.draft_unavailable": "Черновик не найден или недоступен.",
        "send.bot_not_found": "Указанный бот не найден.",
        "send.channel_not_found": "Указанный channel alias не найден.",
        "send.storage_misconfigured": "Хранилище bot token настроено неверно. Обратитесь к администратору.",
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
```

### Task 1: I18n Core And Default Locale

**Files:**
- Create: `src/mm_post_bot/i18n.py`
- Create: `tests/test_i18n.py`
- Modify: `src/mm_post_bot/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write failing i18n tests**

Create `tests/test_i18n.py`:

```python
import pytest

from mm_post_bot.i18n import CATALOG, SUPPORTED_LOCALES, normalize_locale, translate


def test_supported_locales_are_english_and_russian():
    assert SUPPORTED_LOCALES == frozenset({"en", "ru"})


def test_normalize_locale_accepts_supported_values():
    assert normalize_locale("EN") == "en"
    assert normalize_locale(" ru ") == "ru"


@pytest.mark.parametrize("value", ["", "fr", "russian", None])
def test_normalize_locale_rejects_unknown_values(value: str | None):
    assert normalize_locale(value) is None


def test_translate_uses_selected_locale():
    assert translate("ru", "lang.changed.ru") == "Язык изменён на русский."


def test_translate_formats_parameters():
    assert translate("en", "command.unknown", command="привет") == "Unknown command: привет"


def test_translate_falls_back_to_english_for_unknown_locale():
    assert translate("fr", "lang.changed.en") == "Language changed to English."


def test_catalogs_have_same_keys():
    english_keys = set(CATALOG["en"])
    russian_keys = set(CATALOG["ru"])
    assert russian_keys == english_keys
```

- [ ] **Step 2: Write failing config tests**

Add to `tests/test_config.py`:

```python
def test_settings_default_locale_defaults_to_english():
    settings = Settings(
        mm_url="https://mm.internal",
        mm_bot_token="manager-token",
        mm_admins="alice",
        db_url="postgresql://mm_post:secret@postgres/mm_post_bot",
        token_encryption_key=VALID_FERNET_KEY,
    )

    assert settings.default_locale == "en"


def test_settings_normalize_default_locale():
    settings = Settings(
        mm_url="https://mm.internal",
        mm_bot_token="manager-token",
        mm_admins="alice",
        db_url="postgresql://mm_post:secret@postgres/mm_post_bot",
        token_encryption_key=VALID_FERNET_KEY,
        default_locale=" RU ",
    )

    assert settings.default_locale == "ru"


def test_settings_reject_unknown_default_locale():
    with pytest.raises(ValidationError, match="DEFAULT_LOCALE must be one of: en, ru"):
        Settings(
            mm_url="https://mm.internal",
            mm_bot_token="manager-token",
            mm_admins="alice",
            db_url="postgresql://mm_post:secret@postgres/mm_post_bot",
            token_encryption_key=VALID_FERNET_KEY,
            default_locale="fr",
        )
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_i18n.py tests/test_config.py::test_settings_default_locale_defaults_to_english tests/test_config.py::test_settings_normalize_default_locale tests/test_config.py::test_settings_reject_unknown_default_locale -q
```

Expected: tests fail because `mm_post_bot.i18n` and `Settings.default_locale` do not exist.

- [ ] **Step 4: Implement i18n core and config**

Create `src/mm_post_bot/i18n.py` with the catalog above and these helpers:

```python
from typing import Any

SUPPORTED_LOCALES = frozenset({"en", "ru"})
FALLBACK_LOCALE = "en"

# Define CATALOG with the complete literal from "Required Catalog Keys" above.


def normalize_locale(value: str | None) -> str | None:
    if value is None:
        return None
    locale = value.strip().lower()
    return locale if locale in SUPPORTED_LOCALES else None


def translate(locale: str | None, key: str, **params: Any) -> str:
    normalized = normalize_locale(locale) or FALLBACK_LOCALE
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
```

Modify `src/mm_post_bot/config.py`:

```python
from .i18n import SUPPORTED_LOCALES, normalize_locale


class Settings(BaseSettings):
    ...
    default_locale: str = Field(default="en")

    @field_validator("default_locale")
    @classmethod
    def validate_default_locale(cls, value: str) -> str:
        locale = normalize_locale(value)
        if locale is None:
            supported = ", ".join(sorted(SUPPORTED_LOCALES))
            raise ValueError(f"DEFAULT_LOCALE must be one of: {supported}")
        return locale
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
uv run pytest tests/test_i18n.py tests/test_config.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add src/mm_post_bot/i18n.py src/mm_post_bot/config.py tests/test_i18n.py tests/test_config.py
git commit -m "feat: add i18n catalog and default locale"
```

### Task 2: User Preference Storage

**Files:**
- Modify: `src/mm_post_bot/db.py`
- Modify: `src/mm_post_bot/repository.py`
- Modify: `tests/test_repository_postgres.py`

- [ ] **Step 1: Write failing repository tests**

Add to `tests/test_repository_postgres.py`:

```python
from mm_post_bot.repository import UserPreferenceRepo


def test_user_preference_locale_round_trip_without_registration(pg_conn):
    pg_conn.execute("BEGIN")
    preferences = UserPreferenceRepo(pg_conn)

    try:
        assert preferences.get_locale("new-user-id") is None

        preference = preferences.set_locale("new-user-id", "ru")

        assert preference.user_id == "new-user-id"
        assert preference.locale == "ru"
        assert preferences.get_locale("new-user-id") == "ru"
    finally:
        pg_conn.execute("ROLLBACK")


def test_user_preference_locale_update(pg_conn):
    pg_conn.execute("BEGIN")
    preferences = UserPreferenceRepo(pg_conn)

    try:
        preferences.set_locale("user-id", "ru")
        updated = preferences.set_locale("user-id", "en")

        assert updated.locale == "en"
        assert preferences.get_locale("user-id") == "en"
    finally:
        pg_conn.execute("ROLLBACK")
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_repository_postgres.py::test_user_preference_locale_round_trip_without_registration tests/test_repository_postgres.py::test_user_preference_locale_update -q
```

Expected: tests fail because `UserPreferenceRepo` and `user_preference` table do not exist.

- [ ] **Step 3: Implement DB table and repository**

In `src/mm_post_bot/db.py`, add after `app_user` table:

```sql
CREATE TABLE IF NOT EXISTS user_preference (
    user_id    TEXT PRIMARY KEY,
    locale     TEXT NOT NULL CHECK (locale IN ('en', 'ru')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

In `src/mm_post_bot/repository.py`, add:

```python
@dataclass(frozen=True, slots=True)
class UserPreference:
    user_id: str
    locale: str
    created_at: datetime
    updated_at: datetime


def _user_preference_from_row(row: Any) -> UserPreference:
    return UserPreference(
        user_id=row["user_id"],
        locale=row["locale"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class UserPreferenceRepo:
    def __init__(self, conn: DbConn) -> None:
        self._conn = conn

    def get_locale(self, user_id: str) -> str | None:
        row = self._conn.execute(
            "SELECT locale FROM user_preference WHERE user_id = %s",
            (user_id,),
        ).fetchone()
        if row is None:
            return None
        return row["locale"]

    def set_locale(self, user_id: str, locale: str) -> UserPreference:
        now = _now()
        row = self._conn.execute(
            """
            INSERT INTO user_preference (user_id, locale, updated_at)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                locale = EXCLUDED.locale,
                updated_at = EXCLUDED.updated_at
            RETURNING *
            """,
            (user_id, locale, now),
        ).fetchone()
        return _user_preference_from_row(row)
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run pytest tests/test_repository_postgres.py::test_user_preference_locale_round_trip_without_registration tests/test_repository_postgres.py::test_user_preference_locale_update -q
```

Expected: both tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/mm_post_bot/db.py src/mm_post_bot/repository.py tests/test_repository_postgres.py
git commit -m "feat: store user language preferences"
```

### Task 3: Locale-Aware Command Context

**Files:**
- Modify: `src/mm_post_bot/commands/context.py`
- Modify: `src/mm_post_bot/dispatcher.py`
- Modify: `tests/test_dispatcher.py`
- Modify: `tests/test_commands.py`

- [ ] **Step 1: Write failing context tests**

Add imports to `tests/test_commands.py`:

```python
from mm_post_bot.config import Settings
from mm_post_bot.dispatcher import CommandContextFactory
```

Add these tests to `tests/test_commands.py`, which already has a real `pg_conn` fixture:

```python
def test_context_factory_uses_default_locale_without_preference(pg_conn):
    settings = Settings(
        mm_url="https://mm.internal",
        mm_bot_token="manager-token",
        mm_admins="levonti",
        db_url="postgresql://mm_post:secret@postgres/mm_post_bot",
        token_encryption_key=VALID_FERNET_KEY,
        default_locale="ru",
    )
    factory = CommandContextFactory(
        conn=pg_conn,
        settings=settings,
        manager_mm=cast(Any, object()),
        manager_user_id="mgr",
    )

    ctx = factory.from_post({"user_id": "u-locale-default", "sender_name": "alice"}, "D")

    assert ctx.locale == "ru"
    assert ctx.default_locale == "ru"


def test_context_factory_uses_stored_user_locale(pg_conn):
    from mm_post_bot.repository import UserPreferenceRepo

    UserPreferenceRepo(pg_conn).set_locale("u-locale-stored", "ru")
    settings = Settings(
        mm_url="https://mm.internal",
        mm_bot_token="manager-token",
        mm_admins="levonti",
        db_url="postgresql://mm_post:secret@postgres/mm_post_bot",
        token_encryption_key=VALID_FERNET_KEY,
        default_locale="en",
    )
    factory = CommandContextFactory(
        conn=pg_conn,
        settings=settings,
        manager_mm=cast(Any, object()),
        manager_user_id="mgr",
    )

    ctx = factory.from_post({"user_id": "u-locale-stored", "sender_name": "alice"}, "D")

    assert ctx.locale == "ru"
    assert ctx.t("lang.changed.ru") == "Язык изменён на русский."
```

Update `_draft_body_ctx()` in `tests/test_dispatcher.py` and `CommandFixture.make()` in `tests/test_commands.py` to pass the new `user_preference_repo`, `locale`, and `default_locale` fields. Use `"en"` by default.

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_commands.py::test_context_factory_uses_default_locale_without_preference tests/test_commands.py::test_context_factory_uses_stored_user_locale -q
```

Expected: tests fail because `CommandContext` has no locale fields.

- [ ] **Step 3: Implement context fields**

Modify `src/mm_post_bot/commands/context.py`:

```python
from typing import Any

from ..i18n import translate
from ..repository import UserPreferenceRepo


@dataclass(frozen=True, slots=True)
class CommandContext:
    ...
    user_preference_repo: UserPreferenceRepo
    default_locale: str
    locale: str

    def t(self, key: str, **params: Any) -> str:
        return translate(self.locale, key, **params)
```

Modify `src/mm_post_bot/dispatcher.py`:

```python
from .i18n import FALLBACK_LOCALE, normalize_locale
from .repository import UserPreferenceRepo
```

Inside `CommandContextFactory.from_post()`:

```python
caller_user_id = str(post.get("user_id") or "")
user_preference_repo = UserPreferenceRepo(self._conn)
default_locale = normalize_locale(self._settings.default_locale) or FALLBACK_LOCALE
locale = user_preference_repo.get_locale(caller_user_id) or default_locale
return CommandContext(
    caller_user_id=caller_user_id,
    ...
    user_preference_repo=user_preference_repo,
    default_locale=default_locale,
    locale=locale,
)
```

Update all test `CommandContext(...)` constructors with:

```python
user_preference_repo=cast(Any, object()),
default_locale="en",
locale="en",
```

Update `CommandFixture` to include `user_preferences: UserPreferenceRepo` and pass the real repository from the fixture.

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run pytest tests/test_dispatcher.py tests/test_commands.py::test_register_creates_pending_user -q
```

Expected: all listed tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/mm_post_bot/commands/context.py src/mm_post_bot/dispatcher.py tests/test_dispatcher.py tests/test_commands.py
git commit -m "feat: resolve command locale per user"
```

### Task 4: English-Only `!lang` Command

**Files:**
- Create: `src/mm_post_bot/commands/lang.py`
- Modify: `src/mm_post_bot/commands/__init__.py`
- Modify: `src/mm_post_bot/commands/help.py`
- Modify: `tests/test_commands.py`

- [ ] **Step 1: Write failing command tests**

Add to `tests/test_commands.py`:

```python
async def test_lang_shows_current_language_before_registration(ctx: CommandFixture):
    reply = await dispatch(ctx.make("alice-id", "alice"), "!lang")

    assert reply == "Current language: en. Supported languages: en, ru."


async def test_lang_changes_language_before_registration(ctx: CommandFixture):
    reply = await dispatch(ctx.make("alice-id", "alice"), "!lang ru")

    assert reply == "Язык изменён на русский."
    assert ctx.user_preferences.get_locale("alice-id") == "ru"


async def test_lang_rejects_unknown_locale(ctx: CommandFixture):
    reply = await dispatch(ctx.make("alice-id", "alice"), "!lang fr")

    assert reply == "Unsupported language: fr. Supported languages: en, ru."


async def test_lang_command_name_stays_english_only(ctx: CommandFixture):
    reply = await dispatch(ctx.make("alice-id", "alice"), "!язык ru")

    assert reply == "Unknown command: язык"
    assert ctx.user_preferences.get_locale("alice-id") is None


async def test_help_mentions_lang_command(ctx: CommandFixture):
    reply = await dispatch(ctx.make("alice-id", "alice"), "!help")

    assert reply is not None
    assert "!lang [en|ru]" in reply
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_commands.py::test_lang_shows_current_language_before_registration tests/test_commands.py::test_lang_changes_language_before_registration tests/test_commands.py::test_lang_rejects_unknown_locale tests/test_commands.py::test_lang_command_name_stays_english_only tests/test_commands.py::test_help_mentions_lang_command -q
```

Expected: tests fail because `!lang` is unknown and help has no `!lang`.

- [ ] **Step 3: Implement `!lang` and help entry**

Create `src/mm_post_bot/commands/lang.py`:

```python
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
```

Modify `src/mm_post_bot/commands/__init__.py`:

```python
from . import bot, channel, draft, lang, register, send, status, user_admin

REGISTRY = {
    ("lang",): lang.handle,
    ...
}
```

Modify `src/mm_post_bot/commands/help.py` Core rows to include:

```python
ctx.t("help.core.lang")
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run pytest tests/test_commands.py::test_lang_shows_current_language_before_registration tests/test_commands.py::test_lang_changes_language_before_registration tests/test_commands.py::test_lang_rejects_unknown_locale tests/test_commands.py::test_lang_command_name_stays_english_only tests/test_commands.py::test_help_mentions_lang_command -q
```

Expected: all listed tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/mm_post_bot/commands/lang.py src/mm_post_bot/commands/__init__.py src/mm_post_bot/commands/help.py tests/test_commands.py
git commit -m "feat: add language preference command"
```

### Task 5: Localize Core Dispatcher, Access, And Draft Capture

**Files:**
- Modify: `src/mm_post_bot/commands/__init__.py`
- Modify: `src/mm_post_bot/commands/access.py`
- Modify: `src/mm_post_bot/dispatcher.py`
- Modify: `tests/test_dispatcher.py`
- Modify: `tests/test_commands.py`

- [ ] **Step 1: Write failing localization tests**

Add to `tests/test_commands.py`:

```python
async def test_dispatcher_errors_use_selected_locale(ctx: CommandFixture):
    await dispatch(ctx.make("alice-id", "alice"), "!lang ru")

    missing_bang = await dispatch(ctx.make("alice-id", "alice"), "help")
    unknown = await dispatch(ctx.make("alice-id", "alice"), "!unknown")

    assert missing_bang == "Все команды должны начинаться с !."
    assert unknown == "Неизвестная команда: unknown"


async def test_access_errors_use_selected_locale(ctx: CommandFixture):
    await dispatch(ctx.make("alice-id", "alice"), "!lang ru")

    reply = await dispatch(ctx.make("alice-id", "alice"), "!bot list")

    assert reply == "Вы ещё не зарегистрированы. Выполните !register, чтобы запросить доступ."
```

Add to `tests/test_dispatcher.py`:

```python
async def test_handle_draft_body_uses_selected_locale():
    ctx = _draft_body_ctx(locale="ru")

    response = await handle_draft_body(ctx, "текст черновика")

    assert response is not None
    assert response.startswith("Черновик #42 сохранён.")
    assert "!send 42 --bot <alias> --channel <channel_alias>" in response
```

Update `_draft_body_ctx()` signature to accept `locale: str = "en"` and pass it into `CommandContext`.

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_commands.py::test_dispatcher_errors_use_selected_locale tests/test_commands.py::test_access_errors_use_selected_locale tests/test_dispatcher.py::test_handle_draft_body_uses_selected_locale -q
```

Expected: tests fail because these responses are still hardcoded in English.

- [ ] **Step 3: Localize dispatcher, access, and draft body**

Modify `src/mm_post_bot/commands/__init__.py`:

```python
if not raw_text.lstrip().startswith("!"):
    return ctx.t("command.must_start")
...
except ValueError as exc:
    return ctx.t("command.parse_error", error=str(exc))
...
return ctx.t("command.unknown", command=parsed.command)
```

Modify `src/mm_post_bot/commands/access.py`:

```python
return ctx.t("access.not_registered")
return ctx.t("access.blocked")
return ctx.t("access.pending")
```

Modify `src/mm_post_bot/dispatcher.py` in `handle_draft_body()`:

```python
return ctx.t("draft.saved", draft_id=draft.id)
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run pytest tests/test_commands.py::test_dispatcher_errors_use_selected_locale tests/test_commands.py::test_access_errors_use_selected_locale tests/test_dispatcher.py::test_handle_draft_body_saves_active_capture tests/test_dispatcher.py::test_handle_draft_body_uses_selected_locale -q
```

Expected: all listed tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/mm_post_bot/commands/__init__.py src/mm_post_bot/commands/access.py src/mm_post_bot/dispatcher.py tests/test_dispatcher.py tests/test_commands.py
git commit -m "feat: localize core command responses"
```

### Task 6: Localize Registration, Status, Help, And Admin Notifications

**Files:**
- Modify: `src/mm_post_bot/commands/register.py`
- Modify: `src/mm_post_bot/commands/status.py`
- Modify: `src/mm_post_bot/commands/help.py`
- Modify: `src/mm_post_bot/commands/user_admin.py`
- Modify: `tests/test_commands.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_commands.py`:

```python
async def test_register_uses_selected_locale(ctx: CommandFixture):
    await dispatch(ctx.make("alice-id", "alice"), "!lang ru")

    reply = await dispatch(ctx.make("alice-id", "alice"), "!register")

    assert reply is not None
    assert "Пользователь alice зарегистрирован как user" in reply
    assert "Текущий статус: pending" in reply


async def test_status_uses_selected_locale(ctx: CommandFixture):
    await dispatch(ctx.make("alice-id", "alice"), "!lang ru")
    await dispatch(ctx.make("alice-id", "alice"), "!register")

    reply = await dispatch(ctx.make("alice-id", "alice"), "!status")

    assert reply == "alice: статус pending, роль user."


async def test_help_uses_selected_locale_but_keeps_commands_english(ctx: CommandFixture):
    await dispatch(ctx.make("alice-id", "alice"), "!lang ru")

    reply = await dispatch(ctx.make("alice-id", "alice"), "!help")

    assert reply is not None
    assert "Основное:" in reply
    assert "!register - запросить доступ к постингу" in reply
    assert "!lang [en|ru]" in reply


async def test_registration_request_notification_uses_admin_locale(ctx: CommandFixture):
    ctx.manager_mm.users_by_username["admin"] = {"id": "admin-id", "username": "admin"}
    await dispatch(ctx.make("admin-id", "admin", admin_usernames={"admin"}), "!lang ru")

    await dispatch(ctx.make("alice-id", "alice", admin_usernames={"admin"}), "!register")

    assert ctx.manager_mm.posts == [
        {
            "channel_id": "dm-manager-id-admin-id",
            "message": (
                "Новая заявка на регистрацию от alice (alice-id).\n"
                "Подтвердить: !user approve alice"
            ),
        }
    ]


async def test_user_status_notification_uses_target_locale(ctx: CommandFixture):
    await dispatch(ctx.make("alice-id", "alice"), "!lang ru")
    await dispatch(ctx.make("alice-id", "alice", admin_usernames={"admin"}), "!register")

    reply = await dispatch(
        ctx.make("admin-id", "admin", admin_usernames={"admin"}),
        "!user approve alice",
    )

    assert reply is not None
    assert "Approved alice" in reply
    assert ctx.manager_mm.posts[-1] == {
        "channel_id": "dm-manager-id-alice-id",
        "message": "Ваш доступ к mm-post-bot подтверждён.",
    }
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_commands.py::test_register_uses_selected_locale tests/test_commands.py::test_status_uses_selected_locale tests/test_commands.py::test_help_uses_selected_locale_but_keeps_commands_english tests/test_commands.py::test_registration_request_notification_uses_admin_locale tests/test_commands.py::test_user_status_notification_uses_target_locale -q
```

Expected: tests fail because the command modules still return English strings.

- [ ] **Step 3: Localize modules**

Replace hardcoded responses:

`src/mm_post_bot/commands/register.py`:

```python
if is_admin:
    return ctx.t("register.admin", username=user.username)
await _notify_admins(ctx, username=username)
return ctx.t("register.user", username=user.username, role=user.role, status=user.status)
```

In `_notify_admins()`:

```python
from ..i18n import recipient_locale, translate

locale = recipient_locale(
    ctx.user_preference_repo,
    admin_user_id,
    default_locale=ctx.default_locale,
)
message = translate(
    locale,
    "register.admin_request",
    username=username,
    user_id=ctx.caller_user_id,
)
await ctx.manager_mm.create_post(channel_id, message)
```

`src/mm_post_bot/commands/status.py`:

```python
except LookupError:
    return ctx.t("access.not_registered_status")
return ctx.t("status.line", username=user.username, status=user.status, role=user.role)
```

`src/mm_post_bot/commands/help.py`:

Use `ctx.t(...)` for all section titles and rows listed in Required Catalog Keys. Keep command syntax in the translated values.

`src/mm_post_bot/commands/user_admin.py`:

Use `ctx.t(...)` for admin command replies and errors. Change `_notify_user_status()` signature:

```python
async def _notify_user_status(ctx: CommandContext, user: AppUser, *, message_key: str) -> None:
    ...
    locale = recipient_locale(
        ctx.user_preference_repo,
        user.user_id,
        default_locale=ctx.default_locale,
    )
    await ctx.manager_mm.create_post(channel_id, translate(locale, message_key))
```

Call it with `message_key="user.notify_approved"`, `message_key="user.notify_blocked"`, and `message_key="user.notify_unblocked"`.

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run pytest tests/test_commands.py::test_register_uses_selected_locale tests/test_commands.py::test_status_uses_selected_locale tests/test_commands.py::test_help_uses_selected_locale_but_keeps_commands_english tests/test_commands.py::test_registration_request_notification_uses_admin_locale tests/test_commands.py::test_user_status_notification_uses_target_locale tests/test_commands.py::test_configured_admin_can_approve_without_local_registration -q
```

Expected: all listed tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/mm_post_bot/commands/register.py src/mm_post_bot/commands/status.py src/mm_post_bot/commands/help.py src/mm_post_bot/commands/user_admin.py tests/test_commands.py
git commit -m "feat: localize registration and admin replies"
```

### Task 7: Localize Bot, Channel, Draft, And Send Commands

**Files:**
- Modify: `src/mm_post_bot/commands/bot.py`
- Modify: `src/mm_post_bot/commands/channel.py`
- Modify: `src/mm_post_bot/commands/draft.py`
- Modify: `src/mm_post_bot/commands/send.py`
- Modify: `tests/test_commands.py`

- [ ] **Step 1: Write failing representative tests**

Add to `tests/test_commands.py`:

```python
async def test_channel_errors_use_selected_locale(ctx: CommandFixture):
    await dispatch(ctx.make("alice-id", "alice"), "!lang ru")
    await dispatch(ctx.make("alice-id", "alice"), "!register")
    ctx.users.approve("alice-id", approved_by="admin-id")

    reply = await dispatch(
        ctx.make("alice-id", "alice"),
        "!channel add town https://mm.internal/team/channels/town",
    )

    assert reply == "Укажите Mattermost channel id, а не ссылку на канал."


async def test_draft_flow_uses_selected_locale(ctx: CommandFixture):
    await dispatch(ctx.make("alice-id", "alice"), "!lang ru")
    await dispatch(ctx.make("alice-id", "alice"), "!register")
    ctx.users.approve("alice-id", approved_by="admin-id")

    started = await dispatch(ctx.make("alice-id", "alice"), "!draft")
    cancelled = await dispatch(ctx.make("alice-id", "alice"), "!draft cancel")

    assert started == "Ожидание черновика включено. Отправьте текст поста в этом direct message."
    assert cancelled == "Ожидание черновика отменено."


async def test_send_success_uses_selected_locale(ctx: CommandFixture):
    await dispatch(ctx.make("alice-id", "alice"), "!lang ru")
    await dispatch(ctx.make("alice-id", "alice"), "!register")
    ctx.users.approve("alice-id", approved_by="admin-id")
    ctx.token_identities["secret-token"] = {
        "id": "bot-id",
        "username": "poster",
        "is_bot": True,
    }
    await dispatch(ctx.make("alice-id", "alice"), "!bot add news secret-token")
    await dispatch(ctx.make("alice-id", "alice"), "!channel add town channel-id")
    draft = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="Привет",
        message_sha256=hash_message("Привет"),
    )

    reply = await dispatch(
        ctx.make("alice-id", "alice"),
        f"!send {draft.id} --bot news --channel town",
    )

    assert reply == f"Черновик #{draft.id} опубликован."


async def test_bot_validation_errors_use_selected_locale(ctx: CommandFixture):
    await dispatch(ctx.make("alice-id", "alice"), "!lang ru")
    await dispatch(ctx.make("alice-id", "alice"), "!register")
    ctx.users.approve("alice-id", approved_by="admin-id")
    ctx.token_identities["human-token"] = {
        "id": "human-id",
        "username": "alice",
        "is_bot": False,
    }

    reply = await dispatch(ctx.make("alice-id", "alice"), "!bot add personal human-token")

    assert reply == "Этот token принадлежит обычному пользователю. Укажите token бота."
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_commands.py::test_channel_errors_use_selected_locale tests/test_commands.py::test_draft_flow_uses_selected_locale tests/test_commands.py::test_send_success_uses_selected_locale tests/test_commands.py::test_bot_validation_errors_use_selected_locale -q
```

Expected: tests fail because these modules still return English strings.

- [ ] **Step 3: Localize modules**

Replace every hardcoded user-facing return in `bot.py`, `channel.py`, `draft.py`, and `send.py` with the matching catalog key from "Required Catalog Keys".

Examples:

```python
return ctx.t("bot.add_usage")
return ctx.t("bot.duplicate", alias=alias)
return ctx.t("channel.id_not_link")
return ctx.t("draft.started")
return ctx.t("draft.show", draft_id=draft.id, message=draft.message)
return ctx.t("send.published", draft_id=draft.id)
```

Keep audit `error_code` values unchanged. Keep audit `error_message` values stable in English because audit records are operational data and already store fixed codes.

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run pytest tests/test_commands.py::test_channel_errors_use_selected_locale tests/test_commands.py::test_draft_flow_uses_selected_locale tests/test_commands.py::test_send_success_uses_selected_locale tests/test_commands.py::test_bot_validation_errors_use_selected_locale tests/test_commands.py::test_send_posts_saved_draft -q
```

Expected: all listed tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/mm_post_bot/commands/bot.py src/mm_post_bot/commands/channel.py src/mm_post_bot/commands/draft.py src/mm_post_bot/commands/send.py tests/test_commands.py
git commit -m "feat: localize posting command replies"
```

### Task 8: Documentation And Final Verification

**Files:**
- Modify: `.env.example`
- Modify: `README.md`

- [ ] **Step 1: Update configuration docs**

Add to `.env.example`:

```dotenv
DEFAULT_LOCALE=en
```

Update the README configuration table with:

```markdown
| `DEFAULT_LOCALE` | no | Язык ответов по умолчанию: `en` или `ru`, по умолчанию `en`. |
```

Add to README command list:

```text
!lang
!lang en
!lang ru
```

Add under `## Команды`:

```markdown
### Мультиязычность

Команды и их аргументы всегда пишутся на английском: `!help`, `!register`, `!send`,
`!channel`, `!bot`, `!user`, `!lang`. Язык ответов бота можно посмотреть и изменить
командой `!lang [en|ru]`. Настройка языка хранится по Mattermost `user_id` и работает
даже до `!register`.
```

- [ ] **Step 2: Run docs check**

Run:

```bash
rg -n "DEFAULT_LOCALE|!lang|Мультиязычность|en\\|ru" README.md .env.example
```

Expected: output includes `.env.example`, README config table, command list, and multilingual section.

- [ ] **Step 3: Commit docs**

Run:

```bash
git add .env.example README.md
git commit -m "docs: explain multilingual replies"
```

- [ ] **Step 4: Run full verification**

Run:

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy
uv run pytest -q
```

Expected:

```text
All checks passed!
32 files already formatted
Success: no issues found in 24 source files
155 passed
```

If the pytest count differs because existing tests were refactored instead of strictly added, pytest must still exit 0 with no failures.

- [ ] **Step 5: Inspect final diff**

Run:

```bash
git status --short
git diff --stat origin/main..HEAD
```

Expected: worktree is clean after commit, and diff includes i18n/config/db/repository/command/tests/docs changes only.

- [ ] **Step 6: Push and update MR**

Run:

```bash
git push origin ai/mattermost-post-bot-mvp
glab mr view 3 --output json
```

Expected MR fields:

```json
{
  "state": "opened",
  "detailed_merge_status": "mergeable",
  "has_conflicts": false
}
```
