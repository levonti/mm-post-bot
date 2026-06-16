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

    expect(onSave).toHaveBeenCalledWith("Hello post", []);
  });

  it("formats composer text before saving", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn();
    render(<ComposerPage csrf="token" onSave={onSave} />);
    const textarea = screen.getByLabelText("Message") as HTMLTextAreaElement;

    await user.type(textarea, "Hello post");
    textarea.setSelectionRange(0, 5);
    await user.click(screen.getByRole("button", { name: "Bold" }));
    await user.click(screen.getByRole("button", { name: "Save draft" }));

    expect(onSave).toHaveBeenCalledWith("**Hello** post", []);
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
        draft={{ attachments: [], id: 3, message: "Draft body", status: "draft" }}
        onDelete={onDelete}
        onPublish={vi.fn()}
        onSave={vi.fn()}
      />
    );

    await user.click(screen.getByRole("button", { name: "Delete draft" }));

    expect(onDelete).toHaveBeenCalled();
  });

  it("formats and saves an existing draft", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn();
    render(
      <DraftDetailPage
        csrf="token"
        draft={{ attachments: [], id: 3, message: "Draft body", status: "draft" }}
        onDelete={vi.fn()}
        onPublish={vi.fn()}
        onSave={onSave}
      />
    );
    const textarea = screen.getByLabelText("Message") as HTMLTextAreaElement;

    textarea.focus();
    textarea.setSelectionRange(0, 5);
    await user.click(screen.getByRole("button", { name: "Italic" }));
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(onSave).toHaveBeenCalledWith("_Draft_ body");
  });

  it("shows confirmation after saving an existing draft", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn().mockResolvedValue(true);
    render(
      <DraftDetailPage
        csrf="token"
        draft={{ attachments: [], id: 3, message: "Draft body", status: "draft" }}
        onDelete={vi.fn()}
        onPublish={vi.fn()}
        onSave={onSave}
      />
    );

    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Draft changes saved.");
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
        draft={{ attachments: [], id: 3, message: "Draft body", status: "draft" }}
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

  it("blocks default publish when the selected bot is missing from the default channel", async () => {
    const user = userEvent.setup();
    const onPublish = vi.fn();
    render(
      <DraftDetailPage
        bots={[{ alias: "news", bot_username: "news-bot" }]}
        channels={[
          { alias: "town", channel_id: "town-id" },
          { alias: "alerts", channel_id: "alerts-id" }
        ]}
        csrf="token"
        defaultTarget={{ bot_alias: "news", channel_alias: "town" }}
        draft={{ attachments: [], id: 3, message: "Draft body", status: "draft" }}
        onDelete={vi.fn()}
        onPublish={onPublish}
        onSave={vi.fn()}
        targetHealth={{
          bot_alias: "news",
          bot_username: "news-bot",
          channel_alias: "town",
          channel_id: "town-id",
          status: "bot_not_in_channel"
        }}
      />
    );

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Bot news-bot is not in town. Add it in Mattermost or choose another channel below."
    );
    expect(screen.getByRole("button", { name: "Add bot to channel" })).toBeDisabled();

    await user.selectOptions(screen.getByLabelText("Channel alias"), "alerts");

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Publish" }));

    expect(onPublish).toHaveBeenCalledWith({ botAlias: "", channelAlias: "alerts" });
  });

  it("adds and removes images from an existing draft editor", async () => {
    const user = userEvent.setup();
    const onAttachImages = vi.fn();
    const onDeleteAttachment = vi.fn();
    render(
      <DraftDetailPage
        csrf="token"
        draft={{
          attachments: [
            {
              content_type: "image/png",
              filename: "diagram.png",
              id: 9,
              preview_url: "/api/web/drafts/3/attachments/9/content",
              size_bytes: 2048
            }
          ],
          id: 3,
          message: "Draft body",
          status: "draft"
        }}
        onAttachImages={onAttachImages}
        onDelete={vi.fn()}
        onDeleteAttachment={onDeleteAttachment}
        onPublish={vi.fn()}
        onSave={vi.fn()}
      />
    );

    const file = new File(["png"], "screen.png", { type: "image/png" });
    const input = document.querySelector<HTMLInputElement>('input[type="file"]');
    expect(input).not.toBeNull();
    await user.upload(input!, file);
    await user.click(screen.getByRole("button", { name: "Remove diagram.png" }));

    expect(onAttachImages).toHaveBeenCalledWith([file]);
    expect(onDeleteAttachment).toHaveBeenCalledWith(9);
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
