# Web UI i18n Design

## Goal

Make the web UI multilingual in the same way as bot conversations: each approved user's
`user_preference.locale` controls both bot replies and web interface language.

## Scope

- Support `en` and `ru`, matching the existing bot language set.
- Localize page titles, navigation, headings, form labels, buttons, empty states, table headers,
  validation errors, and publish errors shown by the web layer.
- Add a web language switcher for authenticated users.
- Keep the current bot `!lang en|ru` command as a first-class way to change the same preference.

## Behavior

- Authenticated pages resolve locale from `UserPreferenceRepo.get_locale(session.user_id)`.
- If a user has no stored preference, web falls back to `DEFAULT_LOCALE`, then to `en`.
- `/login-required` and login errors use the default locale because no authenticated user is
  available yet.
- The language switcher is a small form in the top bar. It posts `locale` and `next` to a new
  state-changing route protected by the existing CSRF dependency.
- The route accepts only supported locales via `normalize_locale`; unsupported values return 400.
- The `next` redirect target must be a local path beginning with `/` and must not begin with `//`.
  Invalid values redirect to `/`.

## Architecture

- Reuse `src/mm_post_bot/i18n.py` as the single translation catalog.
- Add `web.*` keys to the existing `CATALOG`.
- Add a small helper in `src/mm_post_bot/web/routes.py` that builds shared template context:
  `locale`, `supported_locales`, `t`, and localized `title`.
- Update Jinja templates to call `t("web.key")`.
- Keep templates server-rendered; do not add frontend JavaScript for this feature.

## Testing

- Web route tests verify Russian strings render when `user_preference.locale` is `ru`.
- Web route tests verify the language switcher updates the same preference used by bot replies.
- Web route tests verify invalid locale and unsafe `next` handling.
- Existing web behavior remains covered by the current draft, target, publish, and audit tests.

