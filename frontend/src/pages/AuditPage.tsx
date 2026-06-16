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
  const summary = summarizeRecords(records);

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
        <>
          <section
            aria-label={t(locale, "web.audit.summary.label")}
            className="audit-summary-grid"
          >
            <div className="audit-summary-card">
              <strong>{summary.total}</strong>
              <span>{t(locale, "web.audit.summary.total")}</span>
            </div>
            <div className="audit-summary-card audit-summary-success">
              <strong>
                {t(locale, "web.audit.summary.successful", { count: summary.successful })}
              </strong>
              <span>{t(locale, "web.audit.summary.success_note")}</span>
            </div>
            <div className="audit-summary-card audit-summary-failed">
              <strong>{t(locale, "web.audit.summary.failed", { count: summary.failed })}</strong>
              <span>{t(locale, "web.audit.summary.failed_note")}</span>
            </div>
            <div className="audit-summary-card">
              <strong>
                {t(locale, "web.audit.summary.latest", {
                  status: statusLabel(locale, summary.latestStatus)
                })}
              </strong>
              <span>{formatTimestamp(summary.latestCreatedAt)}</span>
            </div>
          </section>
          <div className="table-wrap">
            <table className="audit-table">
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
                    <td data-label={t(locale, "web.audit.table.created")}>
                      {formatTimestamp(record.created_at)}
                    </td>
                    <td data-label={t(locale, "web.audit.table.status")}>
                      <span className={`status-badge ${statusClass(record.status)}`}>
                        {statusLabel(locale, record.status)}
                      </span>
                    </td>
                    <td data-label={t(locale, "web.audit.table.draft")}>
                      {record.draft_id ? (
                        <span className="audit-record-id">#{record.draft_id}</span>
                      ) : (
                        "-"
                      )}
                    </td>
                    <td data-label={t(locale, "web.audit.table.bot")}>
                      {record.bot_username ?? "-"}
                    </td>
                    <td data-label={t(locale, "web.audit.table.channel")}>
                      <span className="audit-monospace">{record.channel_link}</span>
                    </td>
                    <td data-label={t(locale, "web.audit.table.post")}>
                      {record.mattermost_post_id ? (
                        <span className="audit-monospace">{record.mattermost_post_id}</span>
                      ) : (
                        "-"
                      )}
                    </td>
                    <td data-label={t(locale, "web.audit.table.error")}>
                      {record.error_message ? (
                        <span className="audit-error-text">{record.error_message}</span>
                      ) : (
                        "-"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}

function formatTimestamp(value: string): string {
  return value.slice(0, 16).replace("T", " ");
}

function summarizeRecords(records: AuditRecord[]) {
  const successful = records.filter((record) => record.status === "success").length;
  const failed = records.filter((record) => record.status !== "success").length;
  const latest = records[0];
  return {
    failed,
    latestCreatedAt: latest?.created_at || "",
    latestStatus: latest?.status || "-",
    successful,
    total: records.length
  };
}

function statusClass(status: string) {
  return status === "success" ? "status-badge-success" : "status-badge-failed";
}

function statusLabel(locale: Locale, status: string) {
  if (status === "success") {
    return t(locale, "web.audit.status.success");
  }
  if (status === "failed") {
    return t(locale, "web.audit.status.failed");
  }
  return status;
}
