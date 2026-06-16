import type { Locale } from "../api/types";
import { t } from "../i18n";

type DraftSummary = {
  id: number;
  message: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export function DraftsPage({
  drafts,
  locale = "en"
}: {
  drafts: DraftSummary[];
  locale?: Locale;
}) {
  const countKey = drafts.length === 1 ? "web.drafts.count_one" : "web.drafts.count_many";

  return (
    <section className="page-panel">
      <div className="panel-heading-row">
        <h2>{t(locale, "web.drafts.heading")}</h2>
        <span className="muted-meta">{t(locale, countKey, { count: drafts.length })}</span>
      </div>
      {drafts.length === 0 ? (
        <div className="empty-state">
          <h3>{t(locale, "web.drafts.empty.title")}</h3>
          <p>{t(locale, "web.drafts.empty.body")}</p>
          <a className="secondary-button empty-state-action" href="/">
            {t(locale, "web.drafts.empty.action")}
          </a>
        </div>
      ) : (
        <ul className="record-list">
          {drafts.map((draft) => (
            <li className="record-row" key={draft.id}>
              <div>
                <strong>{t(locale, "web.draft_detail.eyebrow", { draft_id: draft.id })}</strong>
                <p>{draft.message}</p>
                <span className="muted-meta">
                  {t(locale, "web.draft_detail.created", {
                    timestamp: formatTimestamp(draft.created_at)
                  })}
                </span>
              </div>
              <a href={`/drafts/${draft.id}`}>
                {t(locale, "web.drafts.open_with_id", { draft_id: draft.id })}
              </a>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function formatTimestamp(value: string): string {
  return value.slice(0, 16).replace("T", " ");
}
