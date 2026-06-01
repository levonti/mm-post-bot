# mm-post-bot

`mm-post-bot` - MVP-бот для Mattermost, который помогает пользователям готовить черновики
и публиковать их в каналы от имени уже существующих posting bot accounts.

## Что входит в MVP

- Один manager bot слушает личные сообщения и упоминания в каналах.
- Пользователь регистрируется, администратор одобряет доступ.
- Пользователь добавляет токены уже созданных Mattermost-ботов под локальными alias.
- Пользователь добавляет Mattermost channel IDs под локальными channel alias.
- Сообщение сначала сохраняется как draft, затем отправляется явной командой `!send`.
- Целевой канал выбирается по пользовательскому channel alias; сам alias хранит Mattermost
  channel ID.
- Токены posting-ботов хранятся в PostgreSQL в зашифрованном виде.
- Каждая попытка отправки записывается в audit log.

В первой версии бот не создает аккаунты Mattermost-ботов, не управляет системными правами и
не использует system admin PAT.

## Требования Mattermost

Нужно подготовить в Mattermost:

- Manager bot account с personal access token. Этот токен задается в `MM_BOT_TOKEN`.
- Уже существующие posting bot accounts. Их токены пользователи добавляют командой
  `!bot add <alias> <token>`.
- Каналы, куда разрешена публикация. Пользователь добавляет Mattermost channel ID командой
  `!channel add <alias> <channel_id>`, а при отправке использует alias.
- Администраторы приложения задаются username-ами в `MM_ADMINS`; это не системные
  администраторы Mattermost, а админы внутри этого приложения.

Важно: переменной `MM_TOKEN` нет. System-admin PAT не нужен и не поддерживается.

## Конфигурация

Скопируйте пример:

```bash
cp .env.example .env
```

Переменные:

| Name | Required | Description |
| --- | --- | --- |
| `MM_URL` | yes | Базовый URL Mattermost, например `https://mm.internal`. |
| `MM_BOT_TOKEN` | yes | Token manager bot account. |
| `MM_ADMINS` | yes | Список admin username через запятую, например `alice,bob`. |
| `MM_VERIFY_SSL` | no | Проверять TLS-сертификат Mattermost, по умолчанию `true`. |
| `DB_URL` | yes | PostgreSQL DSN для локального запуска через `uv`. |
| `TOKEN_ENCRYPTION_KEY` | yes | Fernet key для шифрования user bot tokens. |
| `LOG_LEVEL` | no | Уровень логирования, по умолчанию `INFO`. |
| `MAX_EVENT_TASKS` | no | Максимум одновременно обрабатываемых Mattermost events, по умолчанию `32`. |
| `DEFAULT_LOCALE` | no | Язык ответов по умолчанию: `en` или `ru`, по умолчанию `en`. |
| `POSTGRES_USER` | Docker | Пользователь PostgreSQL для compose. |
| `POSTGRES_DB` | Docker | База PostgreSQL для compose. |
| `POSTGRES_PASSWORD` | Docker | Пароль PostgreSQL для compose; должен быть задан явно. |

Сгенерировать ключ:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Локальный запуск через uv

Поднимите PostgreSQL отдельно и заполните `.env`, включая `DB_URL`.

```bash
uv sync
uv run mm-post-bot
```

Эквивалентный запуск модуля:

```bash
uv run python -m mm_post_bot
```

## Запуск через Docker Compose

```bash
cp .env.example .env
docker compose up -d --build
docker compose logs -f mm-post-bot
```

Compose поднимает сервис `mm-post-bot` и `postgres:15-alpine`. `DB_URL` внутри контейнера
формируется из `POSTGRES_USER`, `POSTGRES_PASSWORD` и `POSTGRES_DB`; compose не задает
пароль PostgreSQL по умолчанию.

## Команды

Пользовательские команды:

```text
!help
!lang
!lang en
!lang ru
!register
!status
!bot add <alias> <token>
!bot list
!bot remove <alias>
!channel add <alias> <channel_id>
!channel set <alias> <channel_id>
!channel remove <alias>
!channel list
!channel show <alias>
!draft
!draft cancel
!draft list
!draft show <draft_id>
!draft delete <draft_id>
!send <draft_id> --bot <alias> --channel <channel_alias>
```

Админские команды:

```text
!user approve <username-or-user_id>
!user block <username-or-user_id>
!user unblock <username-or-user_id>
!user list [pending|approved|blocked]
```

### Мультиязычность

Команды и их аргументы всегда пишутся на английском: `!help`, `!register`, `!send`,
`!channel`, `!bot`, `!user`, `!lang`. Язык ответов бота можно посмотреть и изменить
командой `!lang [en|ru]`. Настройка языка хранится по Mattermost `user_id` и работает
даже до `!register`.

### Администраторы из MM_ADMINS

Пользователь, чей username указан в `MM_ADMINS`, считается configured admin даже до локальной
регистрации в `app_user`. Такой админ уже может получать заявки на регистрацию и выполнять
`!user approve`, `!user block`, `!user unblock`, `!user list`.

Чтобы использовать posting-команды (`!bot`, `!channel`, `!draft`, `!send`), configured admin
должен один раз выполнить `!register`. После этого локальная запись создается сразу со статусом
`approved` и ролью `admin`; дополнительный approval не нужен.

Как работает draft-first flow:

1. Отправьте `!draft` в DM manager-боту.
2. Следующее обычное DM-сообщение сохранится как черновик.
3. Проверьте черновик через `!draft list` или `!draft show <draft_id>`.
4. Опубликуйте его через `!send <draft_id> --bot <alias> --channel <channel_alias>`.

В каналах команды должны начинаться с упоминания manager-бота, например
`@postbot !status`. В DM упоминание не нужно.

## Manual smoke test для https://mm.internal

Подготовьте реальный manager bot token, реальный posting bot token и Mattermost channel ID
целевого канала.

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
cp .env.example .env
docker compose up -d --build
docker compose logs -f mm-post-bot
```

В Mattermost DM с manager-ботом:

```text
!register
```

Администратор из `MM_ADMINS` одобряет пользователя:

```text
!user approve <username-or-user_id>
```

Пользователь добавляет уже существующий posting bot token:

```text
!bot add news <existing-bot-token>
!channel add town <mattermost-channel-id>
!draft
```

Следующим обычным DM отправьте тело черновика:

```text
Smoke test from mm-post-bot.
```

Затем отправьте:

```text
!send 1 --bot news --channel town
```

Ожидаемый результат: в целевом канале появится `Smoke test from mm-post-bot.` от выбранного
posting bot account.

## Безопасность и ограничения

- Не используйте system admin PAT: боту нужен только manager bot token и токены уже созданных
  posting bot accounts.
- `MM_BOT_TOKEN` должен принадлежать Mattermost bot account; обычный user token будет
  отклонен при старте.
- `TOKEN_ENCRYPTION_KEY` должен храниться как secret. Потеря ключа сделает сохраненные токены
  нерасшифровываемыми.
- Токен, добавленный через `!bot add`, доступен приложению для отправки сообщений от имени
  соответствующего Mattermost-бота.
- Удаление alias через `!bot remove` мягкое: старые audit records сохраняются.
- Удаление channel alias через `!channel remove` мягкое: старые audit records сохраняются.
- MVP не реализует UI, очередь повторных отправок, rate limiting, ротацию ключей шифрования и
  автоматическое создание Mattermost bot accounts.
- WebSocket listener переподключается с backoff, но длительная недоступность Mattermost или
  PostgreSQL все еще требует наблюдения через логи и внешний process supervisor.
