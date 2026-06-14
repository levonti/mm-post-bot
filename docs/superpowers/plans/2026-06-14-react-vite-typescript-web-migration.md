# React Vite TypeScript Web Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the existing FastAPI/Jinja web UI to a React + Vite + TypeScript SPA while preserving login, CSRF, i18n, posting workflows, Mattermost channel search, and the current Docker deployment.

**Architecture:** FastAPI remains the backend, session owner, CSRF issuer, and Mattermost/database integration layer. React is introduced as a strangler UI: first served in parallel under `/app`, then promoted to `/` after parity. Backend HTML routes stay in place until each React screen has API coverage and browser verification.

**Tech Stack:** FastAPI, Python 3.14, React, Vite, TypeScript, Vitest, Testing Library, Docker multi-stage build, existing pytest/ruff/mypy.

---

## File Structure

Create:

- `frontend/package.json` - Node scripts and frontend dependencies.
- `frontend/package-lock.json` - locked npm dependency graph.
- `frontend/index.html` - Vite HTML entry.
- `frontend/vite.config.ts` - Vite config, dev proxy to FastAPI, build output.
- `frontend/tsconfig.json` - strict TypeScript settings for the React app.
- `frontend/tsconfig.node.json` - TypeScript settings for Vite config.
- `frontend/src/main.tsx` - React entrypoint.
- `frontend/src/App.tsx` - route selection and app shell.
- `frontend/src/api/client.ts` - typed `fetch` wrapper with CSRF handling.
- `frontend/src/api/types.ts` - shared frontend DTO types matching FastAPI JSON.
- `frontend/src/i18n.ts` - frontend translation helper seeded by backend locale.
- `frontend/src/components/Layout.tsx` - topbar, language toggle, notices, page container.
- `frontend/src/components/Notice.tsx` - reusable success/error banner.
- `frontend/src/pages/ComposerPage.tsx` - draft creation page.
- `frontend/src/pages/DraftsPage.tsx` - draft list page.
- `frontend/src/pages/DraftDetailPage.tsx` - edit/publish/delete draft page.
- `frontend/src/pages/TargetsPage.tsx` - bots/channels/default target page.
- `frontend/src/pages/AuditPage.tsx` - audit table page.
- `frontend/src/pages/LoginRequiredPage.tsx` - unauthenticated fallback.
- `frontend/src/pages/__tests__/TargetsPage.test.tsx` - React tests for target/channel UX.
- `frontend/src/setupTests.ts` - Testing Library setup.
- `src/mm_post_bot/web/api.py` - JSON API router for React.
- `tests/test_web_api.py` - backend API contract tests for React.

Modify:

- `src/mm_post_bot/web/app.py` - include API router; serve Vite build; add SPA fallback.
- `src/mm_post_bot/web/routes.py` - keep login and legacy Jinja routes during migration; remove duplicate JSON endpoints only after API parity.
- `src/mm_post_bot/web/templates/base.html` - add link from legacy UI to React preview during Phase 1 only.
- `src/mm_post_bot/i18n.py` - add API-facing web labels only when frontend needs backend-provided strings.
- `Dockerfile` - add Node build stage and copy Vite build into the Python runtime image.
- `docker-compose.yml` - optional dev profile for Vite dev server.
- `pyproject.toml` - no frontend dependencies; keep Python tooling unchanged.
- `tests/test_web_app.py` - keep legacy route tests until final removal; adjust after root switch.
- `.gitignore` - ignore `frontend/node_modules`, `frontend/dist`, and Vite cache.

Do not remove `src/mm_post_bot/web/templates/*`, `src/mm_post_bot/web/static/app.css`, or `src/mm_post_bot/web/static/app.js` until the final parity task.

---

## Phase 1: API Foundation

### Task 1: Add React Bootstrap API

**Files:**

- Create: `src/mm_post_bot/web/api.py`
- Modify: `src/mm_post_bot/web/app.py`
- Test: `tests/test_web_api.py`

- [ ] **Step 1: Write failing backend tests**

Add `tests/test_web_api.py`:

```python
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from test_commands import FERNET_KEY
from test_commands import ctx as _commands_ctx
from test_commands import pg_conn as _commands_pg_conn

from mm_post_bot.config import Settings
from mm_post_bot.services.web_auth import create_login_token, hash_login_token
from mm_post_bot.web.app import create_app

ctx = _commands_ctx
pg_conn = _commands_pg_conn


@pytest.fixture()
def web_settings():
    return Settings(
        mm_url="https://mm.internal",
        mm_bot_token="manager-token",
        mm_admins="alice",
        db_url="postgresql://mm_post:secret@postgres/mm_post_bot",
        token_encryption_key=FERNET_KEY,
        web_base_url="https://posts.internal",
        web_session_secret="s" * 32,
    )


def _login(client: TestClient, ctx) -> None:
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    raw = create_login_token(
        token_repo=ctx.web_login_tokens,
        owner_user_id="alice-id",
        now=datetime.now(UTC),
        ttl_seconds=300,
    )
    response = client.get(f"/login?token={raw}", follow_redirects=False)
    assert response.status_code == 303
    assert ctx.web_login_tokens.get_usable(hash_login_token(raw), now=datetime.now(UTC)) is None


def test_api_bootstrap_returns_session_csrf_locale_and_nav(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)

    response = client.get("/api/web/bootstrap")

    assert response.status_code == 200
    assert response.json()["session"] == {"user_id": "alice-id", "username": "alice"}
    assert response.json()["locale"] == "en"
    assert response.json()["csrf"]
    assert response.json()["nav"] == [
        {"href": "/", "key": "composer", "label": "Composer"},
        {"href": "/drafts", "key": "drafts", "label": "Drafts"},
        {"href": "/targets", "key": "targets", "label": "Targets"},
        {"href": "/audit", "key": "audit", "label": "Audit"},
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider tests/test_web_api.py::test_api_bootstrap_returns_session_csrf_locale_and_nav
```

Expected: `404 Not Found` for `/api/web/bootstrap`.

- [ ] **Step 3: Implement minimal API router**

Create `src/mm_post_bot/web/api.py`:

```python
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response

from ..i18n import translate
from .deps import csrf_token, current_session, settings
from .routes import _session_locale

api_router = APIRouter(prefix="/api/web")


@api_router.get("/bootstrap")
def bootstrap(
    request: Request,
    session: Annotated[object, Depends(current_session)],
    csrf: Annotated[str, Depends(csrf_token)],
) -> Response:
    locale = _session_locale(request, session)
    nav = [
        {"href": "/", "key": "composer", "label": translate(locale, "web.nav.composer")},
        {"href": "/drafts", "key": "drafts", "label": translate(locale, "web.nav.drafts")},
        {"href": "/targets", "key": "targets", "label": translate(locale, "web.nav.targets")},
        {"href": "/audit", "key": "audit", "label": translate(locale, "web.nav.audit")},
    ]
    return JSONResponse(
        {
            "session": {"user_id": session.user_id, "username": session.username},
            "csrf": csrf,
            "locale": locale,
            "default_locale": settings(request).default_locale,
            "nav": nav,
        }
    )
```

Modify `src/mm_post_bot/web/app.py`:

```python
from .api import api_router
from .routes import router

# inside create_app(...)
app.include_router(api_router)
app.include_router(router)
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider tests/test_web_api.py::test_api_bootstrap_returns_session_csrf_locale_and_nav
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/mm_post_bot/web/api.py src/mm_post_bot/web/app.py tests/test_web_api.py
git commit -m "feat: add web bootstrap api"
```

### Task 2: Add JSON APIs For Existing Screens

**Files:**

- Modify: `src/mm_post_bot/web/api.py`
- Test: `tests/test_web_api.py`

- [ ] **Step 1: Write failing API tests**

Append tests for:

```python
def test_api_targets_returns_bots_channels_default_and_csrf(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    ctx.user_bots.add(
        owner_user_id="alice-id",
        alias="news",
        bot_user_id="bot-id",
        bot_username="news-bot",
        bot_display_name=None,
        token_ciphertext="cipher",
        token_fingerprint="fp",
    )
    ctx.user_channels.add(owner_user_id="alice-id", alias="town", channel_id="channel-id")
    ctx.user_post_defaults.set_for_owner("alice-id", bot_alias="news", channel_alias="town")

    response = client.get("/api/web/targets")

    assert response.status_code == 200
    payload = response.json()
    assert payload["bots"][0]["alias"] == "news"
    assert payload["channels"][0]["alias"] == "town"
    assert payload["channels"][0]["channel_id"] == "channel-id"
    assert payload["default"] == {"bot_alias": "news", "channel_alias": "town"}
    assert payload["csrf"]


def test_api_drafts_returns_drafts(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    draft = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="Hello from API",
        message_sha256="hash",
    )

    response = client.get("/api/web/drafts")

    assert response.status_code == 200
    assert response.json()["drafts"][0]["id"] == draft.id
    assert response.json()["drafts"][0]["message"] == "Hello from API"


def test_api_audit_returns_records(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    ctx.audits.record(
        caller_user_id="alice-id",
        caller_username="alice",
        draft_id=None,
        user_bot_id=None,
        bot_user_id="bot-id",
        bot_username="news-bot",
        channel_link="town",
        resolved_channel_id="channel-id",
        resolved_team_name=None,
        resolved_channel_name=None,
        message_sha256="hash",
        status="success",
        mattermost_post_id="post-id",
        error_code=None,
        error_message=None,
    )

    response = client.get("/api/web/audit")

    assert response.status_code == 200
    assert response.json()["records"][0]["mattermost_post_id"] == "post-id"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider tests/test_web_api.py
```

Expected: failures for missing `/api/web/targets`, `/api/web/drafts`, and `/api/web/audit`.

- [ ] **Step 3: Implement read endpoints**

Add serializer helpers in `src/mm_post_bot/web/api.py`:

```python
def _channel_payload(channel) -> dict[str, object]:
    return {
        "alias": channel.alias,
        "channel_id": channel.channel_id,
        "created_at": channel.created_at.isoformat(),
        "updated_at": channel.updated_at.isoformat(),
    }


def _bot_payload(bot) -> dict[str, object]:
    return {
        "alias": bot.alias,
        "bot_user_id": bot.bot_user_id,
        "bot_username": bot.bot_username,
        "bot_display_name": bot.bot_display_name,
    }
```

Add endpoints:

```python
@api_router.get("/targets")
def targets_api(
    request: Request,
    session: Annotated[object, Depends(current_session)],
    csrf: Annotated[str, Depends(csrf_token)],
) -> Response:
    repo_set = repos(request)
    default = repo_set.user_post_defaults.get_for_owner(session.user_id)
    return JSONResponse(
        {
            "csrf": csrf,
            "bots": [_bot_payload(bot) for bot in repo_set.user_bots.list_for_owner(session.user_id)],
            "channels": [
                _channel_payload(channel)
                for channel in repo_set.user_channels.list_for_owner(session.user_id)
            ],
            "default": (
                {"bot_alias": default.bot.alias, "channel_alias": default.channel.alias}
                if default is not None
                else None
            ),
            "stale_default": default is None
            and repo_set.user_post_defaults.has_for_owner(session.user_id),
        }
    )
```

Use the same repository methods currently used by Jinja routes for drafts and audit.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider tests/test_web_api.py
```

Expected: all `tests/test_web_api.py` tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/mm_post_bot/web/api.py tests/test_web_api.py
git commit -m "feat: add web read api"
```

---

## Phase 2: Frontend Toolchain

### Task 3: Add Vite React TypeScript App Skeleton

**Files:**

- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/setupTests.ts`
- Modify: `.gitignore`

- [ ] **Step 1: Create package manifest**

Create `frontend/package.json`:

```json
{
  "name": "mm-post-bot-web",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite --host 0.0.0.0",
    "build": "tsc -b && vite build",
    "preview": "vite preview --host 0.0.0.0",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "@vitejs/plugin-react": "latest",
    "vite": "latest",
    "typescript": "latest",
    "react": "latest",
    "react-dom": "latest"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "latest",
    "@testing-library/react": "latest",
    "@testing-library/user-event": "latest",
    "@types/react": "latest",
    "@types/react-dom": "latest",
    "jsdom": "latest",
    "vitest": "latest"
  }
}
```

Use `npm install` from `frontend/` to generate `package-lock.json`.

- [ ] **Step 2: Add Vite config**

Create `frontend/vite.config.ts`:

```ts
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8080",
      "/login": "http://localhost:8080",
      "/login-required": "http://localhost:8080"
    }
  },
  build: {
    outDir: "../src/mm_post_bot/web/static/spa",
    emptyOutDir: true
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/setupTests.ts"
  }
});
```

- [ ] **Step 3: Add TypeScript configs**

Create `frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["DOM", "DOM.Iterable", "ES2022"],
    "allowJs": false,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "module": "ESNext",
    "moduleResolution": "Node",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx"
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

Create `frontend/tsconfig.node.json`:

```json
{
  "compilerOptions": {
    "composite": true,
    "module": "ESNext",
    "moduleResolution": "Node",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 4: Add React entry files**

Create `frontend/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>mm-post-bot</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

Create `frontend/src/main.tsx`:

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

Create `frontend/src/App.tsx`:

```tsx
export function App() {
  return <div>mm-post-bot React preview</div>;
}
```

Create `frontend/src/setupTests.ts`:

```ts
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 5: Add ignores**

Modify `.gitignore`:

```gitignore
frontend/node_modules/
frontend/dist/
src/mm_post_bot/web/static/spa/
```

Do not ignore `frontend/package-lock.json`.

- [ ] **Step 6: Run frontend install and build**

Run:

```bash
cd frontend
npm install
npm run build
```

Expected: Vite build writes files under `src/mm_post_bot/web/static/spa`.

- [ ] **Step 7: Commit**

```bash
git add .gitignore frontend/package.json frontend/package-lock.json frontend/index.html frontend/vite.config.ts frontend/tsconfig.json frontend/tsconfig.node.json frontend/src
git commit -m "chore: add react vite frontend"
```

### Task 4: Serve React Build From FastAPI

**Files:**

- Modify: `src/mm_post_bot/web/app.py`
- Test: `tests/test_web_app.py`

- [ ] **Step 1: Write failing tests for SPA preview route**

Add to `tests/test_web_app.py`:

```python
def test_react_preview_route_serves_spa_shell(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)

    response = client.get("/app")

    assert response.status_code == 200
    assert '<div id="root"></div>' in response.text
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider tests/test_web_app.py::test_react_preview_route_serves_spa_shell
```

Expected: `404 Not Found` or missing React shell.

- [ ] **Step 3: Implement SPA serving**

Modify `src/mm_post_bot/web/app.py`:

```python
from fastapi.responses import FileResponse


def _spa_index(web_dir: Path) -> Path:
    return web_dir / "static" / "spa" / "index.html"
```

Inside `create_app`, after mounting `/static`:

```python
spa_dir = web_dir / "static" / "spa"
if spa_dir.exists():
    app.mount("/app/assets", StaticFiles(directory=spa_dir / "assets"), name="spa-assets")

    @app.get("/app")
    @app.get("/app/{path:path}")
    def react_app(path: str = "") -> FileResponse:
        return FileResponse(_spa_index(web_dir))
```

If tests run without a Vite build, create a minimal test fixture file in the test using `tmp_path` only if `create_app` can be pointed to that path. Prefer building once before running this test in CI.

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
cd frontend && npm run build
cd ..
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider tests/test_web_app.py::test_react_preview_route_serves_spa_shell
```

Expected: test passes.

- [ ] **Step 5: Commit**

```bash
git add src/mm_post_bot/web/app.py tests/test_web_app.py
git commit -m "feat: serve react preview app"
```

---

## Phase 3: React App Parity

### Task 5: Add Frontend API Client And Layout

**Files:**

- Create: `frontend/src/api/types.ts`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/components/Layout.tsx`
- Create: `frontend/src/components/Notice.tsx`
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/components/Layout.test.tsx`

- [ ] **Step 1: Write frontend tests**

Create `frontend/src/components/Layout.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { Layout } from "./Layout";

test("renders navigation and username", () => {
  render(
    <Layout
      activePage="targets"
      locale="en"
      nav={[
        { href: "/", key: "composer", label: "Composer" },
        { href: "/targets", key: "targets", label: "Targets" }
      ]}
      username="alice"
    >
      <h1>Targets body</h1>
    </Layout>
  );

  expect(screen.getByRole("link", { name: "Composer" })).toHaveAttribute("href", "/");
  expect(screen.getByRole("link", { name: "Targets" })).toHaveClass("active");
  expect(screen.getByText("alice")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Targets body" })).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd frontend
npm test -- Layout.test.tsx
```

Expected: module not found for `Layout`.

- [ ] **Step 3: Implement types and API client**

Create `frontend/src/api/types.ts`:

```ts
export type Locale = "en" | "ru";

export type NavItem = {
  href: string;
  key: string;
  label: string;
};

export type BootstrapPayload = {
  session: { user_id: string; username: string };
  csrf: string;
  locale: Locale;
  default_locale: Locale;
  nav: NavItem[];
};
```

Create `frontend/src/api/client.ts`:

```ts
export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(path, { headers: { Accept: "application/json" } });
  if (!response.ok) {
    throw new Error(`GET ${path} failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function apiForm<T>(path: string, form: FormData): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: { Accept: "application/json" },
    body: form
  });
  if (!response.ok) {
    const payload = (await response.json()) as { detail?: string };
    throw new Error(payload.detail || `POST ${path} failed: ${response.status}`);
  }
  return (await response.json()) as T;
}
```

- [ ] **Step 4: Implement Layout and Notice**

Create `frontend/src/components/Notice.tsx`:

```tsx
export function Notice({ kind, message }: { kind: "error" | "success"; message: string }) {
  return (
    <section className={`notice-banner notice-${kind}`} role={kind === "error" ? "alert" : "status"}>
      {message}
    </section>
  );
}
```

Create `frontend/src/components/Layout.tsx`:

```tsx
import type { NavItem, Locale } from "../api/types";

type LayoutProps = {
  activePage: string;
  children: React.ReactNode;
  locale: Locale;
  nav: NavItem[];
  username: string;
};

export function Layout({ activePage, children, locale, nav, username }: LayoutProps) {
  return (
    <>
      <header className="topbar">
        <a className="brand" href="/">mm-post-bot</a>
        <nav className="primary-nav" aria-label={locale === "ru" ? "Основная навигация" : "Primary navigation"}>
          {nav.map((item) => (
            <a key={item.key} className={activePage === item.key ? "active" : ""} href={item.href}>
              {item.label}
            </a>
          ))}
        </nav>
        <div className="topbar-actions">
          <div className="user-chip">{username}</div>
        </div>
      </header>
      <main className="shell">{children}</main>
    </>
  );
}
```

- [ ] **Step 5: Run frontend tests**

Run:

```bash
cd frontend
npm test -- Layout.test.tsx
```

Expected: test passes.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api frontend/src/components frontend/src/App.tsx
git commit -m "feat: add react app shell"
```

### Task 6: Migrate Targets Page First

**Files:**

- Create: `frontend/src/pages/TargetsPage.tsx`
- Test: `frontend/src/pages/__tests__/TargetsPage.test.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `src/mm_post_bot/web/api.py`
- Test: `tests/test_web_api.py`

- [ ] **Step 1: Extend backend API for target mutations**

Add tests for:

```python
def test_api_targets_renames_channel_alias(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    ctx.user_channels.add(owner_user_id="alice-id", alias="town", channel_id="channel-id")
    csrf = client.get("/api/web/bootstrap").json()["csrf"]

    response = client.post(
        "/api/web/targets/channels/town/rename",
        data={"csrf": csrf, "new_alias": "announcements"},
    )

    assert response.status_code == 200
    assert response.json()["alias"] == "announcements"
    assert ctx.user_channels.get_by_owner_and_alias("alice-id", "announcements").channel_id == "channel-id"


def test_api_targets_deletes_channel_alias(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    ctx.user_channels.add(owner_user_id="alice-id", alias="town", channel_id="channel-id")
    csrf = client.get("/api/web/bootstrap").json()["csrf"]

    response = client.post(
        "/api/web/targets/channels/town/delete",
        data={"csrf": csrf},
    )

    assert response.status_code == 200
    assert response.json() == {"success": True}
    with pytest.raises(LookupError):
        ctx.user_channels.get_by_owner_and_alias("alice-id", "town")
```

Implement repo method `rename_alias` if it does not exist:

```python
def rename_alias(self, owner_user_id: str, alias: str, *, new_alias: str) -> UserChannel:
    now = _now()
    row = self._conn.execute(
        """
        UPDATE user_channel
        SET alias = %s,
            updated_at = %s
        WHERE owner_user_id = %s
          AND alias = %s
          AND deleted_at IS NULL
        RETURNING *
        """,
        (new_alias, now, owner_user_id, alias),
    ).fetchone()
    if row is None:
        raise LookupError(f"user_channel not found: {owner_user_id}/{alias}")
    return _user_channel_from_row(row)
```

- [ ] **Step 2: Write React TargetsPage tests**

Create `frontend/src/pages/__tests__/TargetsPage.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TargetsPage } from "../TargetsPage";

test("renders channel display name with small muted id", () => {
  render(
    <TargetsPage
      csrf="token"
      targets={{
        bots: [],
        channels: [
          {
            alias: "posting-demo",
            channel_id: "channel-id",
            display_name: "Posting Demo",
            team_name: "mm-post-demo"
          }
        ],
        default: null,
        stale_default: false
      }}
    />
  );

  expect(screen.getByText("Posting Demo")).toBeInTheDocument();
  expect(screen.getByText("channel-id")).toHaveClass("channel-id");
  expect(screen.getByText("posting-demo")).toBeInTheDocument();
});

test("confirms before deleting a channel", async () => {
  const user = userEvent.setup();
  const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);

  render(
    <TargetsPage
      csrf="token"
      targets={{
        bots: [],
        channels: [{ alias: "posting-demo", channel_id: "channel-id", display_name: "Posting Demo" }],
        default: null,
        stale_default: false
      }}
    />
  );

  await user.click(screen.getByRole("button", { name: "Delete posting-demo" }));

  expect(confirmSpy).toHaveBeenCalled();
});
```

- [ ] **Step 3: Implement React TargetsPage**

Implement:

```tsx
type Channel = {
  alias: string;
  channel_id: string;
  display_name?: string;
  team_name?: string;
};

type TargetsPayload = {
  bots: Array<{ alias: string; bot_username: string }>;
  channels: Channel[];
  default: null | { bot_alias: string; channel_alias: string };
  stale_default: boolean;
};

export function TargetsPage({ csrf, targets }: { csrf: string; targets: TargetsPayload }) {
  return (
    <section className="target-column">
      <div className="target-column-header">
        <h2>Channels</h2>
        <button className="secondary-button" type="button">Add channel</button>
      </div>
      <ul className="target-list">
        {targets.channels.map((channel) => (
          <li className="channel-row" key={channel.alias}>
            <div>
              <strong>{channel.display_name || channel.alias}</strong>
              <span className="channel-id">{channel.channel_id}</span>
            </div>
            <span>{channel.alias}</span>
            <button type="button">Edit alias</button>
            <button
              type="button"
              aria-label={`Delete ${channel.alias}`}
              onClick={() => window.confirm(`Delete channel ${channel.alias}?`)}
            >
              Delete
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
```

Then wire actual API calls in a later step after the presentational tests pass.

- [ ] **Step 4: Run frontend target tests**

Run:

```bash
cd frontend
npm test -- TargetsPage.test.tsx
```

Expected: tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/mm_post_bot/web/api.py src/mm_post_bot/repository.py tests/test_web_api.py frontend/src/pages frontend/src/App.tsx
git commit -m "feat: migrate targets page to react"
```

### Task 7: Migrate Composer, Drafts, Draft Detail, And Audit

**Files:**

- Create: `frontend/src/pages/ComposerPage.tsx`
- Create: `frontend/src/pages/DraftsPage.tsx`
- Create: `frontend/src/pages/DraftDetailPage.tsx`
- Create: `frontend/src/pages/AuditPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `src/mm_post_bot/web/api.py`
- Test: `tests/test_web_api.py`
- Test: frontend page tests under `frontend/src/pages/__tests__/`

- [ ] **Step 1: Add API tests for each mutation**

Cover:

- `POST /api/web/drafts` creates draft and returns `{id}`.
- `POST /api/web/drafts/{id}` updates message.
- `POST /api/web/drafts/{id}/publish` publishes and returns audit redirect target.
- `POST /api/web/drafts/{id}/delete` soft deletes.
- `POST /api/web/targets/default` sets default.
- `POST /api/web/targets/default/clear` clears default.
- `POST /api/web/language` changes locale.

- [ ] **Step 2: Implement JSON endpoints by wrapping existing service functions**

Reuse existing logic in `routes.py`:

- `create_draft`
- `update_draft_message`
- `publish_draft`
- `repo_set.user_post_defaults.set_for_owner`
- `repo_set.user_post_defaults.clear_for_owner`
- `UserPreferenceRepo.set_locale`

Return JSON responses instead of redirects.

- [ ] **Step 3: Build React pages**

Each page should:

- Load data through `apiGet`.
- Submit forms through `apiForm`.
- Render inline errors using `Notice`.
- Keep existing labels and workflow order.
- Avoid large marketing-style layouts.

- [ ] **Step 4: Run backend and frontend tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider tests/test_web_api.py
cd frontend
npm test
npm run build
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/mm_post_bot/web/api.py tests/test_web_api.py frontend/src
git commit -m "feat: migrate remaining web pages to react"
```

---

## Phase 4: Build, Docker, And Route Switch

### Task 8: Build React In Docker

**Files:**

- Modify: `Dockerfile`
- Modify: `.dockerignore`
- Test: Docker build command

- [ ] **Step 1: Update Dockerfile**

Add a frontend stage before the Python builder:

```dockerfile
FROM node:22-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build
```

Then copy the built SPA into the Python builder or runtime:

```dockerfile
COPY --from=frontend-builder /app/src/mm_post_bot/web/static/spa /app/src/mm_post_bot/web/static/spa
```

If Vite writes to `../src/mm_post_bot/web/static/spa`, set `WORKDIR /app` in the frontend stage and run:

```dockerfile
COPY frontend ./frontend
COPY src ./src
RUN cd frontend && npm ci && npm run build
```

- [ ] **Step 2: Update `.dockerignore`**

Add:

```dockerignore
frontend/node_modules
frontend/dist
```

Do not ignore `frontend/package-lock.json`.

- [ ] **Step 3: Build image**

Run:

```bash
docker compose --env-file /private/tmp/mm_post_live.env build mm-post-bot-web
```

Expected: frontend and backend stages build successfully.

- [ ] **Step 4: Commit**

```bash
git add Dockerfile .dockerignore
git commit -m "build: compile react app in docker"
```

### Task 9: Promote React From `/app` To `/`

**Files:**

- Modify: `src/mm_post_bot/web/app.py`
- Modify: `src/mm_post_bot/web/routes.py`
- Modify: `tests/test_web_app.py`

- [ ] **Step 1: Write route-switch tests**

Update tests:

```python
def test_home_serves_react_app_after_migration(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)

    response = client.get("/")

    assert response.status_code == 200
    assert '<div id="root"></div>' in response.text
```

Add tests that login still redirects to `/`:

```python
def test_login_redirects_to_react_home(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    raw = create_login_token(
        token_repo=ctx.web_login_tokens,
        owner_user_id="alice-id",
        now=datetime.now(UTC),
        ttl_seconds=300,
    )

    response = client.get(f"/login?token={raw}", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/"
```

- [ ] **Step 2: Move Jinja routes to `/legacy` or delete after parity**

Keep these server routes:

- `/login`
- `/login-required`
- `/api/web/*`
- `/static/*`
- SPA fallback for `/`, `/drafts`, `/drafts/{id}`, `/targets`, `/audit`

Remove or move these legacy HTML routes:

- `GET /`
- `GET /drafts`
- `GET /drafts/{draft_id}`
- `GET /targets`
- `GET /audit`

- [ ] **Step 3: Run browser parity check**

Start demo:

```bash
docker compose --env-file /private/tmp/mm_post_live.env up -d --build mm-post-bot-web
```

Verify in browser:

- `/` renders React Composer.
- `/drafts` renders React Drafts.
- `/targets` renders React Targets.
- `/audit` renders React Audit.
- Login token still lands on `/`.
- Refreshing any React route returns the SPA shell.

- [ ] **Step 4: Commit**

```bash
git add src/mm_post_bot/web/app.py src/mm_post_bot/web/routes.py tests/test_web_app.py
git commit -m "feat: promote react web ui"
```

### Task 10: Remove Legacy Jinja Assets

**Files:**

- Delete: `src/mm_post_bot/web/templates/*.html`
- Delete or reduce: `src/mm_post_bot/web/static/app.js`
- Keep or migrate: `src/mm_post_bot/web/static/app.css`
- Modify: `src/mm_post_bot/web/routes.py`
- Test: full suite

- [ ] **Step 1: Delete unused templates after React parity**

Delete templates only after route-switch browser QA passes:

```bash
git rm src/mm_post_bot/web/templates/base.html \
  src/mm_post_bot/web/templates/composer.html \
  src/mm_post_bot/web/templates/drafts.html \
  src/mm_post_bot/web/templates/draft_detail.html \
  src/mm_post_bot/web/templates/targets.html \
  src/mm_post_bot/web/templates/audit.html
```

- [ ] **Step 2: Move CSS ownership**

Either:

- Move existing `app.css` into `frontend/src/styles.css`, or
- Keep `src/mm_post_bot/web/static/app.css` as a global stylesheet imported by React.

Prefer moving to `frontend/src/styles.css` so Vite owns frontend assets.

- [ ] **Step 3: Remove legacy tests**

Delete Jinja-specific assertions from `tests/test_web_app.py`, but keep:

- login tests
- cookie/session tests
- SPA serving tests
- API tests

- [ ] **Step 4: Run full verification**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run ruff check .
PYTHONDONTWRITEBYTECODE=1 uv run mypy src/mm_post_bot
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider
cd frontend
npm test
npm run build
docker compose --env-file /private/tmp/mm_post_live.env up -d --build mm-post-bot-web
```

Expected:

- Python checks pass.
- Frontend tests and build pass.
- Docker demo serves React UI on `http://localhost:8080/`.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: remove legacy jinja web ui"
```

---

## Rollout Notes

- Keep `/api/web/*` as the only frontend contract. Do not let React call old HTML routes.
- Keep cookie-based session auth. React should not store session tokens in local storage.
- Keep CSRF as a backend-issued value from `/api/web/bootstrap`; send it in `FormData` for mutating requests.
- Keep Mattermost calls server-side. React should never call Mattermost directly.
- Keep the current language switch behavior, but expose it through `/api/web/language`.
- First migrated screen should be `Targets`, because channel search/edit/delete needs richer interactivity and benefits most from React.
- Do not remove legacy UI until React has browser parity for Composer, Drafts, Draft Detail, Targets, and Audit.

## Final Verification Checklist

- [ ] `PYTHONDONTWRITEBYTECODE=1 uv run ruff check .`
- [ ] `PYTHONDONTWRITEBYTECODE=1 uv run mypy src/mm_post_bot`
- [ ] `PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider`
- [ ] `cd frontend && npm test`
- [ ] `cd frontend && npm run build`
- [ ] `docker compose --env-file /private/tmp/mm_post_live.env up -d --build mm-post-bot-web`
- [ ] Browser: `/`, `/drafts`, `/targets`, `/audit`, and a draft detail route render after refresh.
- [ ] Browser: publishing a draft still posts to Mattermost.
- [ ] Browser: targets channel search, alias rename, delete confirmation, and default target changes work.
