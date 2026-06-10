# Порядок обновления

Перед обновлением зафиксируйте текущий deployed commit и убедитесь, что сервисы доступны:

```bash
git rev-parse HEAD
docker compose ps
docker compose logs --tail=100 mm-post-bot
```

Сделайте backup PostgreSQL. Это особенно важно перед версиями, которые добавляют таблицы или
индексы; схема приложения создается idempotent SQL-ом при старте.

```bash
docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  > backup-before-update.sql
```

Обновите код и пересоберите сервис:

```bash
git checkout main
git pull --ff-only origin main
docker compose up -d --build
```

Проверьте, что в `.env` сохранены прежние значения `MM_URL`, `MM_BOT_TOKEN`, `MM_ADMINS`,
`POSTGRES_PASSWORD` и `TOKEN_ENCRYPTION_KEY`. Не меняйте `TOKEN_ENCRYPTION_KEY` при обычном
обновлении: иначе сохраненные posting bot tokens станут нерасшифровываемыми.

После старта проверьте логи:

```bash
docker compose logs -f mm-post-bot
```

Ожидаемо: приложение стартует без ошибок PostgreSQL, Mattermost token validation и WebSocket
подключения. При необходимости можно проверить наличие таблицы defaults:

```bash
docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\dt user_post_default"'
```

Сделайте smoke test в DM manager-боту от approved user:

```text
!help
!default
!default set --bot <existing_bot_alias> --channel <existing_channel_alias>
!default
!draft
```

Отправьте тело черновика обычным DM, затем опубликуйте его короткой командой:

```text
!send <draft_id>
```

Дополнительно проверьте явный выбор цели, чтобы подтвердить обратную совместимость:

```text
!send <another_draft_id> --bot <alias> --channel <channel_alias>
```

Если после обновления нужно откатиться, верните предыдущий commit и пересоберите сервис:

```bash
git checkout <previous_commit>
docker compose up -d --build
```

Добавленные таблицы можно оставить: старая версия приложения их игнорирует. После rollback
короткая отправка через defaults может быть недоступна, но явная команда
`!send <draft_id> --bot <alias> --channel <channel_alias>` остается рабочим путем.
