import { FormEvent, useState } from "react";
import type { Locale } from "../api/types";
import { Notice } from "../components/Notice";
import { t } from "../i18n";

type ComposerPageProps = {
  csrf: string;
  error?: string | null;
  locale?: Locale;
  onSave?: (message: string) => void | Promise<void>;
};

export function ComposerPage({ csrf, error, locale = "en", onSave }: ComposerPageProps) {
  const [message, setMessage] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSave?.(message);
  }

  return (
    <section className="page-panel">
      <h2>{t(locale, "web.composer.heading")}</h2>
      {error ? <Notice kind="error" message={error} /> : null}
      <form className="stack-form" onSubmit={handleSubmit}>
        <input name="csrf" type="hidden" value={csrf} />
        <label htmlFor="composer-message">{t(locale, "web.composer.message")}</label>
        <textarea
          id="composer-message"
          name="message"
          onChange={(event) => setMessage(event.target.value)}
          placeholder={t(locale, "web.composer.placeholder")}
          rows={8}
          value={message}
        />
        <button type="submit">{t(locale, "web.composer.save")}</button>
      </form>
    </section>
  );
}
