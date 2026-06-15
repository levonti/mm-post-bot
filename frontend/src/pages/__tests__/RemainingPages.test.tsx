import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AuditPage } from "../AuditPage";
import { ComposerPage } from "../ComposerPage";
import { DraftDetailPage } from "../DraftDetailPage";
import { DraftsPage } from "../DraftsPage";

describe("remaining React pages", () => {
  it("submits a composer draft through the provided handler", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn();
    render(<ComposerPage csrf="token" onSave={onSave} />);

    await user.type(screen.getByLabelText("Message"), "Hello post");
    await user.click(screen.getByRole("button", { name: "Save draft" }));

    expect(onSave).toHaveBeenCalledWith("Hello post");
  });

  it("renders draft links", () => {
    render(
      <DraftsPage
        drafts={[
          {
            id: 7,
            message: "Draft body",
            status: "draft",
            created_at: "2026-06-15T00:00:00Z",
            updated_at: "2026-06-15T00:00:00Z"
          }
        ]}
      />
    );

    expect(screen.getByRole("link", { name: "Open draft 7" })).toHaveAttribute(
      "href",
      "/drafts/7"
    );
    expect(screen.getByText("Draft body")).toBeInTheDocument();
  });

  it("confirms before deleting a draft", async () => {
    const user = userEvent.setup();
    const onDelete = vi.fn();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(
      <DraftDetailPage
        csrf="token"
        draft={{ id: 3, message: "Draft body", status: "draft" }}
        onDelete={onDelete}
        onPublish={vi.fn()}
        onSave={vi.fn()}
      />
    );

    await user.click(screen.getByRole("button", { name: "Delete draft" }));

    expect(onDelete).toHaveBeenCalled();
  });

  it("publishes a draft with selected target aliases", async () => {
    const user = userEvent.setup();
    const onPublish = vi.fn();
    render(
      <DraftDetailPage
        bots={[{ alias: "news", bot_username: "news-bot" }]}
        channels={[{ alias: "town", channel_id: "channel-id" }]}
        csrf="token"
        defaultTarget={null}
        draft={{ id: 3, message: "Draft body", status: "draft" }}
        onDelete={vi.fn()}
        onPublish={onPublish}
        onSave={vi.fn()}
        staleDefault={false}
      />
    );

    await user.selectOptions(screen.getByLabelText("Bot alias"), "news");
    await user.selectOptions(screen.getByLabelText("Channel alias"), "town");
    await user.click(screen.getByRole("button", { name: "Publish" }));

    expect(onPublish).toHaveBeenCalledWith({ botAlias: "news", channelAlias: "town" });
  });

  it("renders form errors through an alert notice", () => {
    render(<ComposerPage csrf="token" error="Draft message cannot be empty" onSave={vi.fn()} />);

    expect(screen.getByRole("alert")).toHaveTextContent("Draft message cannot be empty");
  });

  it("renders audit records", () => {
    render(
      <AuditPage
        records={[
          {
            id: 1,
            created_at: "2026-06-15T00:00:00Z",
            status: "success",
            draft_id: 3,
            bot_username: "news-bot",
            channel_link: "town",
            mattermost_post_id: "post-id",
            error_message: null
          }
        ]}
      />
    );

    expect(screen.getByText("success")).toBeInTheDocument();
    expect(screen.getByText("post-id")).toBeInTheDocument();
  });
});
