import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";

describe("App", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    window.history.replaceState(null, "", "/");
  });

  it("loads bootstrap and renders the composer shell", async () => {
    vi.spyOn(window, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          csrf: "token",
          locale: "en",
          nav: [{ href: "/", key: "composer", label: "Composer" }],
          session: { user_id: "alice-id", username: "alice" }
        }),
        { headers: { "Content-Type": "application/json" }, status: 200 }
      )
    );

    render(<App />);

    expect(await screen.findByText("alice")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "mm-post-bot" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Composer" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("button", { name: "Save draft" })).toBeInTheDocument();
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
    expect(screen.getByRole("link", { name: "Composer" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Drafts" })).toHaveAttribute("href", "/drafts");
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
});
