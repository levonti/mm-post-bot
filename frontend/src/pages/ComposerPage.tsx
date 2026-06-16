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
};

export function ComposerPage({ csrf, error, locale = "en", onSave }: ComposerPageProps) {
  const [message, setMessage] = useState("");
  const [pendingAttachments, setPendingAttachments] = useState<
    Array<DraftEditorAttachment & { file: File }>
  >([]);
  const pendingAttachmentsRef = useRef(pendingAttachments);

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
      <h2>{t(locale, "web.composer.heading")}</h2>
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
