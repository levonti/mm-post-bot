import { Layout } from "./components/Layout";

export function App() {
  return (
    <Layout
      activePage="composer"
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
    </Layout>
  );
}
