import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";

describe("App", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    window.history.replaceState(null, "", "/");
  });

  it("loads bootstrap and renders the composer shell", async () => {
    const fetchSpy = vi.spyOn(window, "fetch").mockImplementation(async (input) => {
      if (String(input) === "/api/web/bootstrap") {
        return jsonResponse({
          csrf: "token",
          locale: "en",
          nav: [{ href: "/", key: "composer", label: "Composer" }],
          session: { user_id: "alice-id", username: "alice" }
        });
      }
      if (String(input) === "/api/web/targets") {
        return jsonResponse({
          bots: [{ alias: "news", bot_display_name: "News Bot", bot_username: "news-bot" }],
          channels: [
            {
              alias: "town",
              channel_id: "channel-id",
              display_name: "Town Square",
              team_name: "demo"
            }
          ],
          default: { bot_alias: "news", channel_alias: "town" },
          stale_default: false
        });
      }
      throw new Error(`Unexpected request ${String(input)}`);
    });

    render(<App />);

    expect(await screen.findByText("alice")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "mm-post-bot" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Composer" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Drafts" })).toHaveAttribute("href", "/drafts");
    expect(screen.getByText("Default target")).toBeInTheDocument();
    expect(screen.getByText("News Bot")).toBeInTheDocument();
    expect(screen.getByText("Town Square")).toBeInTheDocument();
    expect(screen.getByText((content) => content.includes("demo"))).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save draft" })).toBeInTheDocument();
    expect(fetchSpy).toHaveBeenCalledWith("/api/web/targets", {
      headers: { Accept: "application/json" }
    });
  });

  it("renders root links when opened through the app compatibility path", async () => {
    window.history.replaceState(null, "", "/app");
    vi.spyOn(window, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          csrf: "token",
          locale: "en",
          nav: [
            { href: "/", key: "composer", label: "Composer" },
            { href: "/drafts", key: "drafts", label: "Drafts" }
          ],
          session: { user_id: "alice-id", username: "alice" }
        }),
        { headers: { "Content-Type": "application/json" }, status: 200 }
      )
    );

    render(<App />);

    expect(await screen.findByText("alice")).toBeInTheDocument();
    const navigation = screen.getByRole("navigation", { name: "Primary navigation" });
    expect(within(navigation).getByRole("link", { name: "Composer" })).toHaveAttribute("href", "/");
    expect(within(navigation).getByRole("link", { name: "Drafts" })).toHaveAttribute(
      "href",
      "/drafts"
    );
  });

  it("renders mutation errors inline", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "fetch").mockImplementation(async (input, init) => {
      if (String(input) === "/api/web/bootstrap") {
        return new Response(
          JSON.stringify({
            csrf: "token",
            locale: "en",
            nav: [{ href: "/", key: "composer", label: "Composer" }],
            session: { user_id: "alice-id", username: "alice" }
          }),
          { headers: { "Content-Type": "application/json" }, status: 200 }
        );
      }
      if (String(input) === "/api/web/drafts" && init?.method === "POST") {
        return new Response(JSON.stringify({ detail: "Draft message cannot be empty" }), {
          headers: { "Content-Type": "application/json" },
          status: 400
        });
      }
      throw new Error(`Unexpected request ${String(input)}`);
    });

    render(<App />);

    await screen.findByText("alice");
    await user.click(screen.getByRole("button", { name: "Save draft" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Draft message cannot be empty"
    );
  });

  it("uploads composer images after creating a draft", async () => {
    const user = userEvent.setup();
    const originalCreateObjectUrl = URL.createObjectURL;
    const originalRevokeObjectUrl = URL.revokeObjectURL;
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: vi.fn(() => "blob:composer-preview")
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      value: vi.fn()
    });
    const hrefSetter = vi.fn();
    const originalLocation = window.location;
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { ...originalLocation, set href(value: string) { hrefSetter(value); } }
    });
    const fetchSpy = vi.spyOn(window, "fetch").mockImplementation(async (input, init) => {
      if (String(input) === "/api/web/bootstrap") {
        return new Response(
          JSON.stringify({
            csrf: "token",
            locale: "en",
            nav: [{ href: "/", key: "composer", label: "Composer" }],
            session: { user_id: "alice-id", username: "alice" }
          }),
          { headers: { "Content-Type": "application/json" }, status: 200 }
        );
      }
      if (String(input) === "/api/web/drafts" && init?.method === "POST") {
        const form = init.body as FormData;
        expect(form.get("csrf")).toBe("token");
        expect(form.get("message")).toBe("Hello with image");
        return new Response(JSON.stringify({ id: 12 }), {
          headers: { "Content-Type": "application/json" },
          status: 200
        });
      }
      if (String(input) === "/api/web/drafts/12/attachments" && init?.method === "POST") {
        const form = init.body as FormData;
        expect(form.get("csrf")).toBe("token");
        expect(form.get("file")).toBeInstanceOf(File);
        return new Response(
          JSON.stringify({
            attachment: {
              content_type: "image/png",
              filename: "screen.png",
              id: 4,
              preview_url: "/api/web/drafts/12/attachments/4/content",
              size_bytes: 3
            }
          }),
          { headers: { "Content-Type": "application/json" }, status: 200 }
        );
      }
      throw new Error(`Unexpected request ${String(input)}`);
    });

    render(<App />);

    await screen.findByText("alice");
    await user.type(screen.getByLabelText("Message"), "Hello with image");
    const composerFileInput = document.querySelector<HTMLInputElement>('input[type="file"]');
    expect(composerFileInput).not.toBeNull();
    await user.upload(
      composerFileInput!,
      new File(["png"], "screen.png", { type: "image/png" })
    );
    await user.click(screen.getByRole("button", { name: "Save draft" }));

    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/web/drafts/12/attachments",
      expect.objectContaining({ method: "POST" })
    );
    expect(hrefSetter).toHaveBeenCalledWith("/drafts/12");

    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: originalCreateObjectUrl
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      value: originalRevokeObjectUrl
    });
    Object.defineProperty(window, "location", {
      configurable: true,
      value: originalLocation
    });
  });

  it("adds and removes draft detail image attachments through the API", async () => {
    window.history.replaceState(null, "", "/drafts/12");
    const user = userEvent.setup();
    const fetchSpy = vi.spyOn(window, "fetch").mockImplementation(async (input, init) => {
      if (String(input) === "/api/web/bootstrap") {
        return new Response(
          JSON.stringify({
            csrf: "token",
            locale: "en",
            nav: [{ href: "/drafts", key: "drafts", label: "Drafts" }],
            session: { user_id: "alice-id", username: "alice" }
          }),
          { headers: { "Content-Type": "application/json" }, status: 200 }
        );
      }
      if (String(input) === "/api/web/drafts/12") {
        return new Response(
          JSON.stringify({
            bots: [],
            channels: [],
            csrf: "token",
            default: null,
            draft: {
              attachments: [],
              created_at: "2026-06-15T00:00:00Z",
              id: 12,
              message: "Draft body",
              status: "draft",
              updated_at: "2026-06-15T00:00:00Z"
            },
            stale_default: false,
            target_health: null
          }),
          { headers: { "Content-Type": "application/json" }, status: 200 }
        );
      }
      if (String(input) === "/api/web/drafts/12/attachments" && init?.method === "POST") {
        const form = init.body as FormData;
        expect(form.get("csrf")).toBe("token");
        expect(form.get("file")).toBeInstanceOf(File);
        return new Response(
          JSON.stringify({
            attachment: {
              content_type: "image/png",
              filename: "diagram.png",
              id: 8,
              preview_url: "/api/web/drafts/12/attachments/8/content",
              size_bytes: 3
            }
          }),
          { headers: { "Content-Type": "application/json" }, status: 200 }
        );
      }
      if (
        String(input) === "/api/web/drafts/12/attachments/8/delete" &&
        init?.method === "POST"
      ) {
        const form = init.body as FormData;
        expect(form.get("csrf")).toBe("token");
        return new Response(JSON.stringify({ success: true }), {
          headers: { "Content-Type": "application/json" },
          status: 200
        });
      }
      throw new Error(`Unexpected request ${String(input)}`);
    });

    render(<App />);

    await screen.findByText("Draft body");
    const draftFileInput = document.querySelector<HTMLInputElement>('input[type="file"]');
    expect(draftFileInput).not.toBeNull();
    await user.upload(
      draftFileInput!,
      new File(["png"], "diagram.png", { type: "image/png" })
    );
    expect(await screen.findByAltText("diagram.png")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Remove diagram.png" }));

    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/web/drafts/12/attachments/8/delete",
      expect.objectContaining({ method: "POST" })
    );
    expect(screen.queryByAltText("diagram.png")).not.toBeInTheDocument();
  });

  it("shows confirmation after saving a draft detail page", async () => {
    window.history.replaceState(null, "", "/drafts/12");
    const user = userEvent.setup();
    const fetchSpy = vi.spyOn(window, "fetch").mockImplementation(async (input, init) => {
      if (String(input) === "/api/web/bootstrap") {
        return new Response(
          JSON.stringify({
            csrf: "token",
            locale: "en",
            nav: [{ href: "/drafts", key: "drafts", label: "Drafts" }],
            session: { user_id: "alice-id", username: "alice" }
          }),
          { headers: { "Content-Type": "application/json" }, status: 200 }
        );
      }
      if (String(input) === "/api/web/drafts/12" && init?.method !== "POST") {
        return new Response(
          JSON.stringify({
            bots: [],
            channels: [],
            csrf: "token",
            default: null,
            draft: {
              attachments: [],
              created_at: "2026-06-15T00:00:00Z",
              id: 12,
              message: "Draft body",
              status: "draft",
              updated_at: "2026-06-15T00:00:00Z"
            },
            stale_default: false,
            target_health: null
          }),
          { headers: { "Content-Type": "application/json" }, status: 200 }
        );
      }
      if (String(input) === "/api/web/drafts/12" && init?.method === "POST") {
        const form = init.body as FormData;
        expect(form.get("csrf")).toBe("token");
        expect(form.get("message")).toBe("Draft body updated");
        return new Response(JSON.stringify({ id: 12 }), {
          headers: { "Content-Type": "application/json" },
          status: 200
        });
      }
      throw new Error(`Unexpected request ${String(input)}`);
    });

    render(<App />);

    await screen.findByText("Draft body");
    const textarea = screen.getByLabelText("Message");
    await user.clear(textarea);
    await user.type(textarea, "Draft body updated");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/web/drafts/12",
      expect.objectContaining({ method: "POST" })
    );
    expect(await screen.findByRole("status")).toHaveTextContent("Draft changes saved.");
  });

  it("logs out through the topbar", async () => {
    const user = userEvent.setup();
    const fetchSpy = vi.spyOn(window, "fetch").mockImplementation(async (input, init) => {
      if (String(input) === "/api/web/bootstrap") {
        return new Response(
          JSON.stringify({
            csrf: "token",
            locale: "en",
            nav: [{ href: "/", key: "composer", label: "Composer" }],
            session: { user_id: "alice-id", username: "alice" }
          }),
          { headers: { "Content-Type": "application/json" }, status: 200 }
        );
      }
      if (String(input) === "/api/web/logout" && init?.method === "POST") {
        const form = init.body as FormData;
        expect(form.get("csrf")).toBe("token");
        return new Response(JSON.stringify({ success: true }), {
          headers: { "Content-Type": "application/json" },
          status: 200
        });
      }
      throw new Error(`Unexpected request ${String(input)}`);
    });
    const hrefSetter = vi.fn();
    const originalLocation = window.location;
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { ...originalLocation, set href(value: string) { hrefSetter(value); } }
    });

    render(<App />);

    await screen.findByText("alice");
    await user.click(screen.getByRole("button", { name: "Log out" }));

    expect(fetchSpy).toHaveBeenCalledWith("/api/web/logout", expect.objectContaining({ method: "POST" }));
    expect(hrefSetter).toHaveBeenCalledWith("/login-required");

    Object.defineProperty(window, "location", {
      configurable: true,
      value: originalLocation
    });
  });
});

function jsonResponse(payload: object, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    headers: { "Content-Type": "application/json" },
    status
  });
}
