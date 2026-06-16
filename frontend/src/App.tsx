import { useEffect, useMemo, useState } from "react";
import { apiForm, apiGet } from "./api/client";
import type { BootstrapPayload } from "./api/types";
import { TargetsPage } from "./pages/TargetsPage";
import { AuditPage } from "./pages/AuditPage";
import { ComposerPage } from "./pages/ComposerPage";
import { DraftDetailPage, type PublishTarget } from "./pages/DraftDetailPage";
import { DraftsPage } from "./pages/DraftsPage";
import { Layout } from "./components/Layout";
import { Notice } from "./components/Notice";
import type { DraftAttachmentPayload, Locale } from "./api/types";

type DraftPayload = {
  attachments: DraftAttachmentPayload[];
  id: number;
  message: string;
  status: string;
  created_at: string;
  updated_at: string;
};

type TargetsPayload = Parameters<typeof TargetsPage>[0]["targets"];
type ComposerTargetsPayload = Parameters<typeof ComposerPage>[0]["targets"];
type AuditPayload = Parameters<typeof AuditPage>[0]["records"];
type BotPayload = TargetsPayload["bots"][number];
type ChannelPayload = TargetsPayload["channels"][number];
type DefaultTargetPayload = TargetsPayload["default"];
type TargetHealthPayload = {
  bot_alias: string;
  bot_username: string;
  channel_alias: string;
  channel_id: string;
  status: "bot_not_in_channel" | "check_failed" | "ok";
} | null;

type PageState =
  | { name: "composer"; targets: ComposerTargetsPayload }
  | { name: "targets"; targets: TargetsPayload }
  | { name: "drafts"; drafts: DraftPayload[] }
  | {
      name: "draft-detail";
      bots: BotPayload[];
      channels: ChannelPayload[];
      csrf: string;
      defaultTarget: DefaultTargetPayload;
      draft: DraftPayload;
      staleDefault: boolean;
      targetHealth: TargetHealthPayload;
    }
  | { name: "audit"; records: AuditPayload };

export function App() {
  const [bootstrap, setBootstrap] = useState<BootstrapPayload | null>(null);
  const [page, setPage] = useState<PageState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const path = window.location.pathname.replace(/^\/app/, "") || "/";
  const activePage = useMemo(() => {
    if (path.startsWith("/targets")) return "targets";
    if (path.startsWith("/drafts")) return "drafts";
    if (path.startsWith("/audit")) return "audit";
    return "composer";
  }, [path]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        setFormError(null);
        const nextBootstrap = await apiGet<BootstrapPayload>("/api/web/bootstrap");
        if (cancelled) return;
        setBootstrap(nextBootstrap);

        if (path.startsWith("/targets")) {
          const targets = await apiGet<TargetsPayload & { csrf: string }>("/api/web/targets");
          if (!cancelled) setPage({ name: "targets", targets });
          return;
        }
        if (path === "/drafts") {
          const payload = await apiGet<{ drafts: DraftPayload[] }>("/api/web/drafts");
          if (!cancelled) setPage({ name: "drafts", drafts: payload.drafts });
          return;
        }
        if (path.startsWith("/drafts/")) {
          const draftId = path.split("/")[2];
          const payload = await apiGet<{
            bots: BotPayload[];
            channels: ChannelPayload[];
            csrf: string;
            default: DefaultTargetPayload;
            draft: DraftPayload;
            stale_default: boolean;
            target_health: TargetHealthPayload;
          }>(`/api/web/drafts/${draftId}`);
          if (!cancelled) {
            setPage({
              name: "draft-detail",
              bots: payload.bots,
              channels: payload.channels,
              csrf: payload.csrf,
              defaultTarget: payload.default,
              draft: payload.draft,
              staleDefault: payload.stale_default,
              targetHealth: payload.target_health
            });
          }
          return;
        }
        if (path.startsWith("/audit")) {
          const payload = await apiGet<{ records: AuditPayload }>("/api/web/audit");
          if (!cancelled) setPage({ name: "audit", records: payload.records });
          return;
        }
        setPage({ name: "composer", targets: await loadComposerTargets() });
      } catch (caught) {
        if (!cancelled) {
          setError(caught instanceof Error ? caught.message : "Could not load page");
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [path]);

  if (error) {
    return <Notice kind="error" message={error} />;
  }

  if (bootstrap === null || page === null) {
    return <main className="shell">Loading...</main>;
  }

  const activeBootstrap = bootstrap;
  const nav = activeBootstrap.nav.map((item) => ({
    ...item,
    href: item.href
  }));

  return (
    <Layout
      activePage={activePage}
      homeHref="/"
      locale={activeBootstrap.locale}
      nav={nav}
      onLocaleChange={changeLanguage}
      onLogout={logout}
      username={activeBootstrap.session.username}
    >
      {page.name === "composer" ? (
        <ComposerPage
          csrf={activeBootstrap.csrf}
          error={formError}
          locale={activeBootstrap.locale}
          onSave={saveDraft}
          targets={page.targets}
        />
      ) : null}
      {page.name === "targets" ? (
        <TargetsPage
          csrf={activeBootstrap.csrf}
          locale={activeBootstrap.locale}
          targets={page.targets}
        />
      ) : null}
      {page.name === "drafts" ? (
        <DraftsPage drafts={page.drafts} locale={activeBootstrap.locale} />
      ) : null}
      {page.name === "draft-detail" ? (
        <DraftDetailPage
          bots={page.bots}
          channels={page.channels}
          csrf={page.csrf}
          defaultTarget={page.defaultTarget}
          draft={page.draft}
          error={formError}
          locale={activeBootstrap.locale}
          onDelete={() => deleteDraft(page.draft.id)}
          onAttachImages={(files) => attachDraftImages(page.draft.id, files)}
          onDeleteAttachment={(attachmentId) =>
            deleteDraftAttachment(page.draft.id, Number(attachmentId))
          }
          onPublish={(target) => publishDraft(page.draft.id, target)}
          onSave={(message) => updateDraft(page.draft.id, message)}
          staleDefault={page.staleDefault}
          targetHealth={page.targetHealth}
        />
      ) : null}
      {page.name === "audit" ? (
        <AuditPage
          locale={activeBootstrap.locale}
          publishedDraftId={new URLSearchParams(window.location.search).get("published")}
          records={page.records}
        />
      ) : null}
    </Layout>
  );

  async function saveDraft(message: string, files: File[] = []) {
    await submitForm(async () => {
      const form = new FormData();
      form.set("csrf", activeBootstrap.csrf);
      form.set("message", message);
      const result = await apiForm<{ id: number }>("/api/web/drafts", form);
      await uploadDraftImages(result.id, files);
      window.location.href = `/drafts/${result.id}`;
    });
  }

  async function updateDraft(draftId: number, message: string): Promise<boolean> {
    return submitForm(async () => {
      const form = new FormData();
      form.set("csrf", activeBootstrap.csrf);
      form.set("message", message);
      await apiForm(`/api/web/drafts/${draftId}`, form);
      setPage((current) => {
        if (current?.name !== "draft-detail" || current.draft.id !== draftId) return current;
        return {
          ...current,
          draft: {
            ...current.draft,
            message,
            updated_at: new Date().toISOString()
          }
        };
      });
    });
  }

  async function publishDraft(draftId: number, target: PublishTarget) {
    await submitForm(async () => {
      const form = new FormData();
      form.set("csrf", activeBootstrap.csrf);
      form.set("bot_alias", target.botAlias);
      form.set("channel_alias", target.channelAlias);
      const result = await apiForm<{ redirect: string }>(
        `/api/web/drafts/${draftId}/publish`,
        form
      );
      window.location.href = result.redirect;
    });
  }

  async function deleteDraft(draftId: number) {
    await submitForm(async () => {
      const form = new FormData();
      form.set("csrf", activeBootstrap.csrf);
      await apiForm(`/api/web/drafts/${draftId}/delete`, form);
      window.location.href = "/drafts";
    });
  }

  async function attachDraftImages(draftId: number, files: File[]) {
    await submitForm(async () => {
      const attachments = await uploadDraftImages(draftId, files);
      setPage((current) => {
        if (current?.name !== "draft-detail" || current.draft.id !== draftId) return current;
        return {
          ...current,
          draft: {
            ...current.draft,
            attachments: [...current.draft.attachments, ...attachments]
          }
        };
      });
    });
  }

  async function deleteDraftAttachment(draftId: number, attachmentId: number) {
    await submitForm(async () => {
      const form = new FormData();
      form.set("csrf", activeBootstrap.csrf);
      await apiForm(`/api/web/drafts/${draftId}/attachments/${attachmentId}/delete`, form);
      setPage((current) => {
        if (current?.name !== "draft-detail" || current.draft.id !== draftId) return current;
        return {
          ...current,
          draft: {
            ...current.draft,
            attachments: current.draft.attachments.filter(
              (attachment) => attachment.id !== attachmentId
            )
          }
        };
      });
    });
  }

  async function uploadDraftImages(
    draftId: number,
    files: File[]
  ): Promise<DraftAttachmentPayload[]> {
    const attachments: DraftAttachmentPayload[] = [];
    for (const file of files) {
      const form = new FormData();
      form.set("csrf", activeBootstrap.csrf);
      form.set("file", file);
      const payload = await apiForm<{ attachment: DraftAttachmentPayload }>(
        `/api/web/drafts/${draftId}/attachments`,
        form
      );
      attachments.push(payload.attachment);
    }
    return attachments;
  }

  async function changeLanguage(locale: Locale) {
    await submitForm(async () => {
      const form = new FormData();
      form.set("csrf", activeBootstrap.csrf);
      form.set("locale", locale);
      await apiForm("/api/web/language", form);
      window.location.reload();
    });
  }

  async function logout() {
    await submitForm(async () => {
      const form = new FormData();
      form.set("csrf", activeBootstrap.csrf);
      await apiForm("/api/web/logout", form);
      window.location.href = "/login-required";
    });
  }

  async function loadComposerTargets(): Promise<ComposerTargetsPayload> {
    try {
      const payload = await apiGet<unknown>("/api/web/targets");
      return isComposerTargetsPayload(payload) ? payload : null;
    } catch {
      return null;
    }
  }

  async function submitForm(action: () => Promise<void>): Promise<boolean> {
    try {
      setFormError(null);
      await action();
      return true;
    } catch (caught) {
      setFormError(caught instanceof Error ? caught.message : "Request failed");
      return false;
    }
  }
}

function isComposerTargetsPayload(payload: unknown): payload is Exclude<ComposerTargetsPayload, null | undefined> {
  if (typeof payload !== "object" || payload === null) return false;
  const candidate = payload as {
    bots?: unknown;
    channels?: unknown;
    default?: unknown;
    stale_default?: unknown;
  };
  return (
    Array.isArray(candidate.bots) &&
    Array.isArray(candidate.channels) &&
    (candidate.default === null || typeof candidate.default === "object") &&
    typeof candidate.stale_default === "boolean"
  );
}
