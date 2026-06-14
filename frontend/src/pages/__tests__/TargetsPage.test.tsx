import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TargetsPage } from "../TargetsPage";

describe("TargetsPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders channel display name with small muted id", () => {
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

  it("confirms before deleting a channel", async () => {
    const user = userEvent.setup();
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);

    render(
      <TargetsPage
        csrf="token"
        targets={{
          bots: [],
          channels: [
            { alias: "posting-demo", channel_id: "channel-id", display_name: "Posting Demo" }
          ],
          default: null,
          stale_default: false
        }}
      />
    );

    await user.click(screen.getByRole("button", { name: "Delete posting-demo" }));

    expect(confirmSpy).toHaveBeenCalled();
  });
});
