import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { App } from "./App";

describe("App", () => {
  it("renders the React preview shell", () => {
    render(<App />);

    expect(screen.getByText("mm-post-bot React preview")).toBeInTheDocument();
  });
});
