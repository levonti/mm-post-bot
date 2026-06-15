import type { Locale } from "../api/types";
import { Notice } from "../components/Notice";
import { t } from "../i18n";

type AuditRecord = {
  id: number;
  created_at: string;
  status: string;
  draft_id: number | null;
  bot_username: string | null;
  channel_link: string;
  mattermost_post_id: string | null;
  error_message: string | null;
};

export function AuditPage({
  locale = "en",
  publishedDraftId,
  records
}: {
  locale?: Locale;
  publishedDraftId?: string | null;
  records: AuditRecord[];
}) {
  return (
    <section className="page-panel">
      <h2>{t(locale, "web.audit.heading")}</h2>
      {publishedDraftId ? (
        <Notice
          kind="success"
          message={t(locale, "web.audit.published_banner", { draft_id: publishedDraftId })}
        />
      ) : null}
      {records.length === 0 ? (
        <div className="empty-state">
          <h3>{t(locale, "web.audit.empty.title")}</h3>
          <p>{t(locale, "web.audit.empty.body")}</p>
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>{t(locale, "web.audit.table.created")}</th>
                <th>{t(locale, "web.audit.table.status")}</th>
                <th>{t(locale, "web.audit.table.draft")}</th>
                <th>{t(locale, "web.audit.table.bot")}</th>
                <th>{t(locale, "web.audit.table.channel")}</th>
                <th>{t(locale, "web.audit.table.post")}</th>
                <th>{t(locale, "web.audit.table.error")}</th>
              </tr>
            </thead>
            <tbody>
              {records.map((record) => (
                <tr key={record.id}>
                  <td>{formatTimestamp(record.created_at)}</td>
                  <td>{record.status}</td>
                  <td>{record.draft_id ?? "-"}</td>
                  <td>{record.bot_username ?? "-"}</td>
                  <td>{record.channel_link}</td>
                  <td>{record.mattermost_post_id ?? "-"}</td>
                  <td>{record.error_message ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function formatTimestamp(value: string): string {
  return value.slice(0, 16).replace("T", " ");
}
