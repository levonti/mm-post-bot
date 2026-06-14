import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
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
});
