import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TargetsPage } from "../TargetsPage";

describe("TargetsPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("renders channel display name with small muted id", () => {
    const { container } = render(
      <TargetsPage
        csrf="token"
        locale="en"
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

    expect(container.firstElementChild).toHaveClass("page-panel", "target-column");
    expect(
      screen.getByRole("listitem", { name: /Posting Demo/ }).querySelector("strong")
    ).toHaveTextContent("Posting Demo");
    expect(screen.getByText("channel-id")).toHaveClass("channel-id");
    expect(channelAlias("posting-demo")).toHaveTextContent("Alias: posting-demo");
    expect(screen.getByRole("listitem", { name: /Posting Demo/ })).toHaveClass(
      "channel-list-row"
    );
  });

  it("keeps channel search closed until add channel is clicked", async () => {
    const user = userEvent.setup();
    render(
      <TargetsPage
        csrf="token"
        locale="ru"
        targets={{ bots: [], channels: [], default: null, stale_default: false }}
      />
    );

    expect(screen.getByRole("heading", { name: "Каналы" })).toBeInTheDocument();
    expect(screen.queryByRole("searchbox", { name: "Поиск канала" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Добавить канал" }));

    expect(screen.getByRole("searchbox", { name: "Поиск канала" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Закрыть поиск" })).toBeInTheDocument();
  });

  it("closes channel search from the open add state", async () => {
    const user = userEvent.setup();
    render(
      <TargetsPage
        csrf="token"
        locale="en"
        targets={{ bots: [], channels: [], default: null, stale_default: false }}
      />
    );

    await user.click(screen.getByRole("button", { name: "Add channel" }));
    await user.click(screen.getByRole("button", { name: "Close search" }));

    expect(screen.queryByRole("searchbox", { name: "Search channel" })).not.toBeInTheDocument();
  });

  it("searches channels live and adds a selected result", async () => {
    const user = userEvent.setup();
    const fetchSpy = vi.spyOn(window, "fetch").mockImplementation(async (input, init) => {
      if (String(input) === "/api/web/targets/channels/search?q=town") {
        return jsonResponse({
          results: [
            {
              id: "town-channel-id",
              name: "town-square",
              display_name: "Town Square",
              team_name: "demo",
              label: "Town Square (demo/town-square)"
            }
          ]
        });
      }
      if (String(input) === "/api/web/targets/channels" && init?.method === "POST") {
        const form = init.body as FormData;
        expect(form.get("csrf")).toBe("token");
        expect(form.get("channel_alias")).toBe("town-square");
        expect(form.get("channel_id")).toBe("town-channel-id");
        return jsonResponse({
          alias: "town-square",
          channel_id: "town-channel-id",
          message: "Channel alias town-square added.",
          success: true
        });
      }
      throw new Error(`Unexpected fetch ${String(input)}`);
    });

    render(
      <TargetsPage
        csrf="token"
        locale="en"
        targets={{ bots: [], channels: [], default: null, stale_default: false }}
      />
    );

    await user.click(screen.getByRole("button", { name: "Add channel" }));
    await user.type(screen.getByRole("searchbox", { name: "Search channel" }), "town");
    expect(await screen.findByText("1 channel found")).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "Town Square (demo/town-square)" }));
    await user.click(screen.getByRole("button", { name: "Save channel" }));

    await waitFor(() => expect(screen.getByText("town-channel-id")).toBeInTheDocument());
    expect(screen.getByRole("status")).toHaveTextContent("Channel town-square saved.");
    expect(fetchSpy).toHaveBeenCalledWith("/api/web/targets/channels/search?q=town", {
      headers: { Accept: "application/json" }
    });
  });

  it("sets and clears the default target", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "fetch").mockImplementation(async (input, init) => {
      if (String(input) === "/api/web/targets/default") {
        const form = init?.body as FormData;
        expect(form.get("csrf")).toBe("token");
        expect(form.get("bot_alias")).toBe("news");
        expect(form.get("channel_alias")).toBe("town");
        return jsonResponse({ success: true });
      }
      if (String(input) === "/api/web/targets/default/clear") {
        const form = init?.body as FormData;
        expect(form.get("csrf")).toBe("token");
        return jsonResponse({ success: true });
      }
      throw new Error(`Unexpected fetch ${String(input)}`);
    });

    render(
      <TargetsPage
        csrf="token"
        locale="en"
        targets={{
          bots: [{ alias: "news", bot_display_name: "News Bot", bot_username: "news-bot" }],
          channels: [
            {
              alias: "town",
              channel_id: "channel-id",
              display_name: "Town Square",
              team_name: "demo"
            },
            {
              alias: "town-ops",
              channel_id: "channel-ops-id",
              display_name: "Town Square",
              team_name: "demo"
            }
          ],
          default: null,
          stale_default: false
        }}
      />
    );

    expect(screen.getByText("No default target selected.")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "News Bot" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Town Square (demo) / town" })).toBeInTheDocument();
    expect(
      screen.getByRole("option", { name: "Town Square (demo) / town-ops" })
    ).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Bot"), "news");
    await user.selectOptions(screen.getByLabelText("Channel"), "town");
    await user.click(screen.getByRole("button", { name: "Save default" }));

    expect(await screen.findByText("Current default")).toBeInTheDocument();
    expect(screen.getAllByText("News Bot").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Town Square").length).toBeGreaterThan(0);
    expect(screen.getAllByText("demo").length).toBeGreaterThan(0);
    expect(screen.getAllByText("channel-id").length).toBeGreaterThan(0);
    expect(screen.getByRole("status")).toHaveTextContent("Default target saved.");

    await user.click(screen.getByRole("button", { name: "Clear default" }));

    expect(await screen.findByText("No default target selected.")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Default target cleared.");
  });

  it("shows structured metadata for the current and selected default target", async () => {
    const user = userEvent.setup();
    render(
      <TargetsPage
        csrf="token"
        locale="en"
        targets={{
          bots: [
            { alias: "news", bot_display_name: "News Bot", bot_username: "news-bot" },
            { alias: "alerts", bot_display_name: null, bot_username: "alerts-bot" }
          ],
          channels: [
            {
              alias: "town",
              channel_id: "channel-id",
              display_name: "Town Square",
              team_name: "demo"
            },
            {
              alias: "town-ops",
              channel_id: "channel-ops-id",
              display_name: "Town Square",
              team_name: "ops"
            }
          ],
          default: { bot_alias: "news", channel_alias: "town" },
          stale_default: false
        }}
      />
    );

    const defaultPanel = screen.getByRole("region", { name: "Default target" });
    const currentSummary = within(defaultPanel).getByLabelText("Current default");
    expect(within(currentSummary).getByText("News Bot")).toBeInTheDocument();
    expect(within(currentSummary).getByText("news-bot")).toBeInTheDocument();
    expect(within(currentSummary).getByText("Town Square")).toBeInTheDocument();
    expect(within(currentSummary).getByText("demo")).toBeInTheDocument();
    expect(within(currentSummary).getByText("channel-id")).toBeInTheDocument();
    expect(within(currentSummary).getByText("Alias: town")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Bot"), "alerts");
    await user.selectOptions(screen.getByLabelText("Channel"), "town-ops");

    const selectedPreview = within(defaultPanel).getByLabelText("Selected target");
    expect(within(selectedPreview).getByText("alerts-bot")).toBeInTheDocument();
    expect(within(selectedPreview).getByText("ops")).toBeInTheDocument();
    expect(within(selectedPreview).getByText("channel-ops-id")).toBeInTheDocument();
    expect(within(selectedPreview).getByText("Alias: town-ops")).toBeInTheDocument();
  });

  it("shows an error when the selected bot is not in the channel", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "fetch").mockImplementation(async (input, init) => {
      if (String(input) === "/api/web/targets/default" && init?.method === "POST") {
        return jsonResponse(
          { detail: "First add bot news-bot to Mattermost channel town." },
          400
        );
      }
      throw new Error(`Unexpected fetch ${String(input)}`);
    });

    render(
      <TargetsPage
        csrf="token"
        locale="en"
        targets={{
          bots: [{ alias: "news", bot_username: "news-bot" }],
          channels: [{ alias: "town", channel_id: "channel-id" }],
          default: null,
          stale_default: false
        }}
      />
    );

    await user.click(screen.getByRole("button", { name: "Save default" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "First add bot news-bot to Mattermost channel town."
    );
    expect(screen.getByText("No default target selected.")).toBeInTheDocument();
  });

  it("renames a channel alias", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "fetch").mockImplementation(async (input, init) => {
      if (String(input) === "/api/web/targets/channels/posting-demo/rename") {
        const form = init?.body as FormData;
        expect(form.get("new_alias")).toBe("announcements");
        return jsonResponse({ alias: "announcements", channel_id: "channel-id" });
      }
      throw new Error(`Unexpected fetch ${String(input)}`);
    });

    render(
      <TargetsPage
        csrf="token"
        locale="en"
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

    await user.click(screen.getByRole("button", { name: "Edit alias posting-demo" }));
    await user.clear(screen.getByRole("textbox", { name: "Channel alias" }));
    await user.type(screen.getByRole("textbox", { name: "Channel alias" }), "announcements");
    await user.click(screen.getByRole("button", { name: "Save alias" }));

    await waitFor(() => expect(channelAlias("announcements")).toBeInTheDocument());
    expect(screen.getByRole("status")).toHaveTextContent("Channel alias renamed.");
  });

  it("confirms before deleting a channel", async () => {
    const user = userEvent.setup();
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);

    render(
      <TargetsPage
        csrf="token"
        locale="en"
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

  it("deletes a channel after confirmation", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.spyOn(window, "fetch").mockImplementation(async (input) => {
      if (String(input) === "/api/web/targets/channels/posting-demo/delete") {
        return jsonResponse({ success: true });
      }
      throw new Error(`Unexpected fetch ${String(input)}`);
    });

    render(
      <TargetsPage
        csrf="token"
        locale="en"
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

    await waitFor(() => expect(screen.queryByText("Posting Demo")).not.toBeInTheDocument());
    expect(screen.getByRole("status")).toHaveTextContent("Channel posting-demo deleted.");
  });
});

function jsonResponse(payload: object, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    headers: { "Content-Type": "application/json" },
    status
  });
}

function channelAlias(alias: string): HTMLElement {
  const element = screen
    .getAllByText((content) => content.includes(alias))
    .find((element) => element.classList.contains("channel-alias"));
  if (!element) {
    throw new Error(`Channel alias ${alias} was not rendered in the channel list`);
  }
  return element;
}
