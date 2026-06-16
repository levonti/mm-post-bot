import { FormEvent, useState } from "react";
import { Save } from "lucide-react";
import type { DraftAttachmentPayload, Locale } from "../api/types";
import { MattermostEditor } from "../components/MattermostEditor";
import { Notice } from "../components/Notice";
import { t } from "../i18n";

type BotOption = {
  alias: string;
  bot_username: string;
};

type ChannelOption = {
  alias: string;
  channel_id: string;
};

type DraftDetail = {
  attachments: DraftAttachmentPayload[];
  created_at?: string;
  id: number;
  message: string;
  status: string;
  updated_at?: string;
};

type TargetHealth =
  | {
      bot_alias: string;
      bot_username: string;
      channel_alias: string;
      channel_id: string;
      status: "bot_not_in_channel" | "check_failed" | "ok";
    }
  | null;

export type PublishTarget = {
  botAlias: string;
  channelAlias: string;
};

type DraftDetailPageProps = {
  bots?: BotOption[];
  channels?: ChannelOption[];
  csrf: string;
  defaultTarget?: null | { bot_alias: string; channel_alias: string };
  draft: DraftDetail;
  error?: string | null;
  locale?: Locale;
  onAttachImages?: (files: File[]) => void | Promise<void>;
  onDelete?: () => void | Promise<void>;
  onDeleteAttachment?: (attachmentId: number | string) => void | Promise<void>;
  onPublish?: (target: PublishTarget) => void | Promise<void>;
  onSave?: (message: string) => boolean | void | Promise<boolean | void>;
  staleDefault?: boolean;
  targetHealth?: TargetHealth;
};

export function DraftDetailPage({
  bots = [],
  channels = [],
  csrf,
  defaultTarget = null,
  draft,
  error,
  locale = "en",
  onAttachImages,
  onDelete,
  onDeleteAttachment,
  onPublish,
  onSave,
  staleDefault = false,
  targetHealth = null
}: DraftDetailPageProps) {
  const [message, setMessage] = useState(draft.message);
  const [botAlias, setBotAlias] = useState("");
  const [channelAlias, setChannelAlias] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [saveNotice, setSaveNotice] = useState(false);

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaveNotice(false);
    setIsSaving(true);
    try {
      const saved = await onSave?.(message);
      if (saved !== false) {
        setSaveNotice(true);
      }
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDelete() {
    if (window.confirm(t(locale, "web.draft_detail.delete_confirm", { draft_id: draft.id }))) {
      await onDelete?.();
    }
  }

  async function handlePublish(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onPublish?.({ botAlias, channelAlias });
  }

  const defaultSummary = defaultTarget
    ? `${defaultTarget.bot_alias} -> ${defaultTarget.channel_alias}`
    : staleDefault
      ? t(locale, "web.common.target_stale")
      : t(locale, "web.common.target_missing");
  const defaultBotOption = defaultTarget
    ? t(locale, "web.draft_detail.use_default_value", { value: defaultTarget.bot_alias })
    : t(locale, "web.draft_detail.use_default");
  const defaultChannelOption = defaultTarget
    ? t(locale, "web.draft_detail.use_default_value", { value: defaultTarget.channel_alias })
    : t(locale, "web.draft_detail.use_default");
  const usesDefaultTarget = botAlias === "" && channelAlias === "";
  const blocksDefaultPublish =
    usesDefaultTarget && targetHealth?.status === "bot_not_in_channel";
  const publishDisabled =
    (defaultTarget === null && (bots.length === 0 || channels.length === 0)) ||
    blocksDefaultPublish;
  const targetHealthMessage = targetHealth
    ? targetHealth.status === "bot_not_in_channel"
      ? t(locale, "web.draft_detail.bot_not_in_channel", {
          bot_username: targetHealth.bot_username,
          channel_alias: targetHealth.channel_alias
        })
      : targetHealth.status === "check_failed"
        ? t(locale, "web.draft_detail.target_check_failed")
        : null
    : null;
  const showTargetHealth = usesDefaultTarget && targetHealth && targetHealthMessage;

  return (
    <section className="page-panel">
      <div className="panel-heading-row">
        <h2>{t(locale, "web.draft_detail.heading")}</h2>
        <div className="workspace-meta">
          {draft.created_at ? (
            <span>
              {t(locale, "web.draft_detail.created", {
                timestamp: formatTimestamp(draft.created_at)
              })}
            </span>
          ) : null}
          {draft.updated_at ? (
            <span>
              {t(locale, "web.draft_detail.updated", {
                timestamp: formatTimestamp(draft.updated_at)
              })}
            </span>
          ) : null}
        </div>
      </div>
      {error ? <Notice kind="error" message={error} /> : null}
      {saveNotice && !error ? (
        <Notice kind="success" message={t(locale, "web.draft_detail.saved")} />
      ) : null}
      <div className="draft-detail-grid">
        <form className="stack-form" onSubmit={handleSave}>
          <input name="csrf" type="hidden" value={csrf} />
          <MattermostEditor
            action={
              <button className="editor-primary-action" disabled={isSaving} type="submit">
                <Save aria-hidden="true" size={15} strokeWidth={2.1} />
                {isSaving
                  ? t(locale, "web.draft_detail.saving")
                  : t(locale, "web.draft_detail.save")}
              </button>
            }
            attachments={draft.attachments}
            id="draft-message"
            label={t(locale, "web.composer.message")}
            locale={locale}
            onAttachImages={onAttachImages}
            onChange={(value) => {
              setMessage(value);
              setSaveNotice(false);
            }}
            onDeleteAttachment={onDeleteAttachment}
            rows={8}
            value={message}
          />
          <div className="button-row">
            <a className="secondary-link" href="/drafts">
              {t(locale, "web.draft_detail.back")}
            </a>
          </div>
        </form>
        <aside className="side-panel" aria-label={t(locale, "web.draft_detail.actions")}>
          <h3>{t(locale, "web.draft_detail.actions")}</h3>
          <section className="target-summary-block">
            <h4>{t(locale, "web.common.default_target")}</h4>
            <p className={staleDefault ? "target-summary warning" : "target-summary"}>
              {defaultSummary}
            </p>
          </section>
          {showTargetHealth ? (
            <section
              aria-live="polite"
              className={
                targetHealth?.status === "bot_not_in_channel"
                  ? "target-health-warning"
                  : "target-health-note"
              }
              role={targetHealth?.status === "bot_not_in_channel" ? "alert" : "status"}
            >
              <strong>
                {targetHealth.status === "bot_not_in_channel"
                  ? t(locale, "web.draft_detail.target_blocked")
                  : t(locale, "web.draft_detail.target_check")}
              </strong>
              <p>{targetHealthMessage}</p>
            </section>
          ) : null}
          <form className="stack-form" onSubmit={handlePublish}>
            <input name="csrf" type="hidden" value={csrf} />
            <label htmlFor="bot-alias">{t(locale, "web.draft_detail.bot_alias")}</label>
            <select
              id="bot-alias"
              name="bot_alias"
              onChange={(event) => setBotAlias(event.target.value)}
              value={botAlias}
            >
              <option value="">{defaultBotOption}</option>
              {bots.map((bot) => (
                <option key={bot.alias} value={bot.alias}>
                  {bot.alias}
                </option>
              ))}
            </select>
            <label htmlFor="channel-alias">{t(locale, "web.draft_detail.channel_alias")}</label>
            <select
              id="channel-alias"
              name="channel_alias"
              onChange={(event) => setChannelAlias(event.target.value)}
              value={channelAlias}
            >
              <option value="">{defaultChannelOption}</option>
              {channels.map((channel) => (
                <option key={channel.alias} value={channel.alias}>
                  {channel.alias}
                </option>
              ))}
            </select>
            <button disabled={publishDisabled} type="submit">
              {blocksDefaultPublish
                ? t(locale, "web.draft_detail.publish_blocked")
                : t(locale, "web.draft_detail.publish")}
            </button>
          </form>
          <button className="danger-button" onClick={handleDelete} type="button">
            {t(locale, "web.draft_detail.delete")}
          </button>
        </aside>
      </div>
    </section>
  );
}

function formatTimestamp(value: string): string {
  return value.slice(0, 16).replace("T", " ");
}
