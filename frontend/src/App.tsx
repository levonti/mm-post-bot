import { Layout } from "./components/Layout";
import { TargetsPage } from "./pages/TargetsPage";

export function App() {
  return (
    <Layout
      activePage="targets"
      locale="en"
      nav={[
        { href: "/", key: "composer", label: "Composer" },
        { href: "/drafts", key: "drafts", label: "Drafts" },
        { href: "/targets", key: "targets", label: "Targets" },
        { href: "/audit", key: "audit", label: "Audit" }
      ]}
      username="preview"
    >
      <h1>mm-post-bot React preview</h1>
      <TargetsPage
        csrf="preview"
        targets={{
          bots: [],
          channels: [
            {
              alias: "posting-demo",
              channel_id: "preview-channel-id",
              display_name: "Posting Demo"
            }
          ],
          default: null,
          stale_default: false
        }}
      />
    </Layout>
  );
}
