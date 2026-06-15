import type { Locale } from "./api/types";

const TRANSLATIONS = {
  en: {
    "web.audit.empty.body": "Published drafts and failed publish attempts will appear here.",
    "web.audit.empty.title": "No audit records",
    "web.audit.heading": "Audit",
    "web.audit.published_banner": "Draft #{draft_id} published.",
    "web.audit.table.bot": "Bot",
    "web.audit.table.channel": "Channel",
    "web.audit.table.created": "Created",
    "web.audit.table.draft": "Draft",
    "web.audit.table.error": "Error",
    "web.audit.table.post": "Post",
    "web.audit.table.status": "Status",
    "web.common.default_target": "Default target",
    "web.common.target_missing": "No default target selected.",
    "web.common.target_stale": "Default target is incomplete.",
    "web.composer.heading": "New Mattermost post",
    "web.composer.message": "Message",
    "web.composer.placeholder": "Write the post body here.",
    "web.composer.save": "Save draft",
    "web.draft_detail.actions": "Actions",
    "web.draft_detail.back": "Back to drafts",
    "web.draft_detail.bot_alias": "Bot alias",
    "web.draft_detail.channel_alias": "Channel alias",
    "web.draft_detail.created": "Created {timestamp}",
    "web.draft_detail.delete": "Delete draft",
    "web.draft_detail.delete_confirm": "Delete draft {draft_id}?",
    "web.draft_detail.eyebrow": "Draft #{draft_id}",
    "web.draft_detail.heading": "Edit draft",
    "web.draft_detail.publish": "Publish",
    "web.draft_detail.save": "Save changes",
    "web.draft_detail.updated": "Updated {timestamp}",
    "web.draft_detail.use_default": "Use default",
    "web.draft_detail.use_default_value": "Use default: {value}",
    "web.drafts.count_many": "{count} drafts",
    "web.drafts.count_one": "{count} draft",
    "web.drafts.empty.action": "New draft",
    "web.drafts.empty.body": "Saved composer drafts will appear here.",
    "web.drafts.empty.title": "No drafts yet",
    "web.drafts.heading": "Saved drafts",
    "web.drafts.open": "Open",
    "web.drafts.open_with_id": "Open draft {draft_id}",
    "web.language.en": "English",
    "web.language.label": "Language",
    "web.language.ru": "Russian"
  },
  ru: {
    "web.audit.empty.body": "Опубликованные черновики и ошибки публикации появятся здесь.",
    "web.audit.empty.title": "Записей аудита нет",
    "web.audit.heading": "Аудит",
    "web.audit.published_banner": "Черновик #{draft_id} опубликован.",
    "web.audit.table.bot": "Бот",
    "web.audit.table.channel": "Канал",
    "web.audit.table.created": "Создано",
    "web.audit.table.draft": "Черновик",
    "web.audit.table.error": "Ошибка",
    "web.audit.table.post": "Пост",
    "web.audit.table.status": "Статус",
    "web.common.default_target": "Цель по умолчанию",
    "web.common.target_missing": "Цель по умолчанию не выбрана.",
    "web.common.target_stale": "Цель по умолчанию неполная.",
    "web.composer.heading": "Новый пост Mattermost",
    "web.composer.message": "Сообщение",
    "web.composer.placeholder": "Напишите текст поста здесь.",
    "web.composer.save": "Сохранить черновик",
    "web.draft_detail.actions": "Действия",
    "web.draft_detail.back": "Назад к черновикам",
    "web.draft_detail.bot_alias": "Алиас бота",
    "web.draft_detail.channel_alias": "Алиас канала",
    "web.draft_detail.created": "Создан {timestamp}",
    "web.draft_detail.delete": "Удалить черновик",
    "web.draft_detail.delete_confirm": "Удалить черновик {draft_id}?",
    "web.draft_detail.eyebrow": "Черновик #{draft_id}",
    "web.draft_detail.heading": "Редактировать черновик",
    "web.draft_detail.publish": "Опубликовать",
    "web.draft_detail.save": "Сохранить изменения",
    "web.draft_detail.updated": "Обновлён {timestamp}",
    "web.draft_detail.use_default": "Использовать по умолчанию",
    "web.draft_detail.use_default_value": "По умолчанию: {value}",
    "web.drafts.count_many": "{count} черновиков",
    "web.drafts.count_one": "{count} черновик",
    "web.drafts.empty.action": "Новый черновик",
    "web.drafts.empty.body": "Сохранённые черновики из редактора появятся здесь.",
    "web.drafts.empty.title": "Черновиков пока нет",
    "web.drafts.heading": "Сохранённые черновики",
    "web.drafts.open": "Открыть",
    "web.drafts.open_with_id": "Открыть черновик {draft_id}",
    "web.language.en": "Английский",
    "web.language.label": "Язык",
    "web.language.ru": "Русский"
  }
} as const;

type TranslationKey = keyof (typeof TRANSLATIONS)["en"];

export function t(
  locale: Locale,
  key: TranslationKey,
  params: Record<string, string | number> = {}
): string {
  let value: string = TRANSLATIONS[locale][key] || TRANSLATIONS.en[key];
  for (const [name, replacement] of Object.entries(params)) {
    value = value.replaceAll(`{${name}}`, String(replacement));
  }
  return value;
}
