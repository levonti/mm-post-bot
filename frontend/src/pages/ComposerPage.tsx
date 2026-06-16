import { FormEvent, useEffect, useRef, useState } from "react";
import { Save } from "lucide-react";
import type { Locale } from "../api/types";
import type { DraftEditorAttachment } from "../components/MattermostEditor";
import { MattermostEditor } from "../components/MattermostEditor";
import { Notice } from "../components/Notice";
import { t } from "../i18n";

type ComposerPageProps = {
  csrf: string;
  error?: string | null;
  locale?: Locale;
  onSave?: (message: string, files: File[]) => void | Promise<void>;
  targets?: ComposerTargetsPayload;
};

type ComposerTargetBot = {
  alias: string;
  bot_display_name?: string | null;
  bot_username: string;
};

type ComposerTargetChannel = {
  alias: string;
  channel_id: string;
  display_name?: string;
  team_name?: string;
};

type ComposerTargetsPayload = {
  bots: ComposerTargetBot[];
  channels: ComposerTargetChannel[];
  default: null | { bot_alias: string; channel_alias: string };
  stale_default: boolean;
} | null;

type TargetSummaryState =
  | {
      kind: "ready";
      botName: string;
      channelName: string;
      channelMeta: string[];
    }
  | { kind: "missing"; message: string };

export function ComposerPage({
  csrf,
  error,
  locale = "en",
  onSave,
  targets = null
}: ComposerPageProps) {
  const [message, setMessage] = useState("");
  const [pendingAttachments, setPendingAttachments] = useState<
    Array<DraftEditorAttachment & { file: File }>
  >([]);
  const pendingAttachmentsRef = useRef(pendingAttachments);
  const targetSummary = getTargetSummary(targets, locale);

  useEffect(() => {
    pendingAttachmentsRef.current = pendingAttachments;
  }, [pendingAttachments]);

  useEffect(() => {
    return () => {
      pendingAttachmentsRef.current.forEach((attachment) => {
        if (attachment.preview_url.startsWith("blob:")) URL.revokeObjectURL(attachment.preview_url);
      });
    };
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSave?.(
      message,
      pendingAttachments.map((attachment) => attachment.file)
    );
  }

  return (
    <section className="page-panel">
      <div className="composer-heading-row">
        <h2>{t(locale, "web.composer.heading")}</h2>
        <a className="secondary-button composer-drafts-link" href="/drafts">
          {t(locale, "web.composer.open_drafts")}
        </a>
      </div>
      {targetSummary ? <ComposerTargetCard locale={locale} summary={targetSummary} /> : null}
      {error ? <Notice kind="error" message={error} /> : null}
      <form className="stack-form" onSubmit={handleSubmit}>
        <input name="csrf" type="hidden" value={csrf} />
        <MattermostEditor
          action={
            <button className="editor-primary-action" type="submit">
              <Save aria-hidden="true" size={15} strokeWidth={2.1} />
              {t(locale, "web.composer.save")}
            </button>
          }
          attachments={pendingAttachments}
          id="composer-message"
          label={t(locale, "web.composer.message")}
          locale={locale}
          onAttachImages={addPendingAttachments}
          onChange={setMessage}
          onDeleteAttachment={deletePendingAttachment}
          placeholder={t(locale, "web.composer.placeholder")}
          rows={8}
          value={message}
        />
      </form>
    </section>
  );

  function addPendingAttachments(files: File[]) {
    setPendingAttachments((current) => [
      ...current,
      ...files.map((file, index) => ({
        content_type: file.type,
        file,
        filename: file.name,
        id: `pending-${Date.now()}-${index}`,
        preview_url: URL.createObjectURL(file),
        size_bytes: file.size
      }))
    ]);
  }

  function deletePendingAttachment(id: number | string) {
    setPendingAttachments((current) => {
      const removed = current.find((attachment) => attachment.id === id);
      if (removed?.preview_url.startsWith("blob:")) URL.revokeObjectURL(removed.preview_url);
      return current.filter((attachment) => attachment.id !== id);
    });
  }
}

function ComposerTargetCard({
  locale,
  summary
}: {
  locale: Locale;
  summary: TargetSummaryState;
}) {
  return (
    <section
      aria-label={t(locale, "web.common.default_target")}
      className={
        summary.kind === "ready"
          ? "composer-target-card"
          : "composer-target-card composer-target-card-warning"
      }
    >
      <div className="composer-target-main">
        <span className="composer-target-label">{t(locale, "web.common.default_target")}</span>
        {summary.kind === "ready" ? (
          <div className="composer-target-identity">
            <strong>{summary.botName}</strong>
            <span aria-hidden="true" className="composer-target-arrow">
              -&gt;
            </span>
            <strong>{summary.channelName}</strong>
            <span className="composer-target-meta">{summary.channelMeta.join(" ")}</span>
          </div>
        ) : (
          <strong>{summary.message}</strong>
        )}
      </div>
      <a className="secondary-button composer-target-link" href="/targets">
        {t(locale, "web.composer.configure_target")}
      </a>
    </section>
  );
}

function getTargetSummary(
  targets: ComposerTargetsPayload,
  locale: Locale
): TargetSummaryState | null {
  if (targets === null) return null;
  if (targets.default === null) {
    return { kind: "missing", message: t(locale, "web.common.target_missing") };
  }
  if (targets.stale_default) {
    return { kind: "missing", message: t(locale, "web.common.target_stale") };
  }
  const bot = targets.bots.find((item) => item.alias === targets.default?.bot_alias);
  const channel = targets.channels.find((item) => item.alias === targets.default?.channel_alias);
  return {
    kind: "ready",
    botName: displayBot(bot, targets.default.bot_alias),
    channelName: displayChannel(channel, targets.default.channel_alias),
    channelMeta: [channel?.team_name, channel?.channel_id].filter(Boolean) as string[]
  };
}

function displayBot(bot: ComposerTargetBot | undefined, fallback: string) {
  return bot?.bot_display_name || bot?.bot_username || bot?.alias || fallback;
}

function displayChannel(channel: ComposerTargetChannel | undefined, fallback: string) {
  return channel?.display_name || channel?.alias || fallback;
}
