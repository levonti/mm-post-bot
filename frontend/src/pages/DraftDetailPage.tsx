import { FormEvent, useState } from "react";
import type { Locale } from "../api/types";
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
  created_at?: string;
  id: number;
  message: string;
  status: string;
  updated_at?: string;
};

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
  onDelete?: () => void | Promise<void>;
  onPublish?: (target: PublishTarget) => void | Promise<void>;
  onSave?: (message: string) => void | Promise<void>;
  staleDefault?: boolean;
};

export function DraftDetailPage({
  bots = [],
  channels = [],
  csrf,
  defaultTarget = null,
  draft,
  error,
  locale = "en",
  onDelete,
  onPublish,
  onSave,
  staleDefault = false
}: DraftDetailPageProps) {
  const [message, setMessage] = useState(draft.message);
  const [botAlias, setBotAlias] = useState("");
  const [channelAlias, setChannelAlias] = useState("");

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSave?.(message);
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
  const publishDisabled = defaultTarget === null && (bots.length === 0 || channels.length === 0);

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
      <div className="draft-detail-grid">
        <form className="stack-form" onSubmit={handleSave}>
          <input name="csrf" type="hidden" value={csrf} />
          <label htmlFor="draft-message">{t(locale, "web.composer.message")}</label>
          <textarea
            id="draft-message"
            name="message"
            onChange={(event) => setMessage(event.target.value)}
            rows={8}
            value={message}
          />
          <div className="button-row">
            <a className="secondary-link" href="/drafts">
              {t(locale, "web.draft_detail.back")}
            </a>
            <button type="submit">{t(locale, "web.draft_detail.save")}</button>
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
              {t(locale, "web.draft_detail.publish")}
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
