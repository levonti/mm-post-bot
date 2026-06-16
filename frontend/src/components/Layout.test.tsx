import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { vi } from "vitest";
import { Layout } from "./Layout";

describe("Layout", () => {
  it("renders navigation and username", () => {
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
    expect(screen.getByRole("link", { name: "Targets" })).toHaveAttribute(
      "aria-current",
      "page"
    );
    expect(screen.getByText("alice")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Targets body" })).toBeInTheDocument();
  });

  it("switches language from the topbar", async () => {
    const user = userEvent.setup();
    const onLocaleChange = vi.fn();
    render(
      <Layout
        activePage="composer"
        locale="en"
        nav={[{ href: "/", key: "composer", label: "Composer" }]}
        onLocaleChange={onLocaleChange}
        username="alice"
      >
        <h1>Composer body</h1>
      </Layout>
    );

    await user.click(screen.getByRole("button", { name: "Русский" }));

    expect(onLocaleChange).toHaveBeenCalledWith("ru");
  });

  it("exposes logout from the topbar", async () => {
    const user = userEvent.setup();
    const onLogout = vi.fn();
    render(
      <Layout
        activePage="composer"
        locale="en"
        nav={[{ href: "/", key: "composer", label: "Composer" }]}
        onLogout={onLogout}
        username="alice"
      >
        <h1>Composer body</h1>
      </Layout>
    );

    await user.click(screen.getByRole("button", { name: "Log out" }));

    expect(onLogout).toHaveBeenCalledOnce();
  });
});
