import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState, type ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { MattermostEditor } from "./MattermostEditor";

describe("MattermostEditor", () => {
  it("wraps selected text with markdown formatting", async () => {
    const user = userEvent.setup();
    render(<EditorHarness initialValue="Hello" />);
    const textarea = screen.getByLabelText("Message") as HTMLTextAreaElement;
    textarea.focus();
    textarea.setSelectionRange(0, 5);

    await user.click(screen.getByRole("button", { name: "Bold" }));

    expect(textarea.value).toBe("**Hello**");
  });

  it("starts in edit mode with the composer toolbar below the message field", () => {
    const { container } = render(<EditorHarness initialValue="Hello" action={<button>Save draft</button>} />);

    const textarea = screen.getByLabelText("Message");
    const toolbar = screen.getByRole("toolbar", { name: "Formatting toolbar" });
    const frame = container.querySelector(".mattermost-composer-frame");

    expect(screen.getByRole("button", { name: "Edit" })).toHaveAttribute("aria-pressed", "true");
    expect(frame).toContainElement(textarea);
    expect(frame).toContainElement(toolbar);
    expect(textarea.compareDocumentPosition(toolbar) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByRole("button", { name: "Save draft" })).toBeInTheDocument();
  });

  it("inserts a link using selected text", async () => {
    const user = userEvent.setup();
    render(<EditorHarness initialValue="Mattermost" />);
    const textarea = screen.getByLabelText("Message") as HTMLTextAreaElement;
    textarea.focus();
    textarea.setSelectionRange(0, 10);

    await user.click(screen.getByRole("button", { name: "Link" }));

    expect(textarea.value).toBe("[Mattermost](https://)");
  });

  it("renders a preview without injecting raw html", async () => {
    const user = userEvent.setup();
    render(<EditorHarness initialValue={"# Title\n\n**Hello** <script>alert(1)</script>"} />);

    await user.click(screen.getByRole("button", { name: "Preview" }));

    expect(screen.getByRole("heading", { name: "Title" })).toBeInTheDocument();
    expect(screen.getByText("Hello").tagName).toBe("STRONG");
    expect(screen.getByText("<script>alert(1)</script>")).toBeInTheDocument();
  });

  it("shows the editor and rendered output together in split mode", async () => {
    const user = userEvent.setup();
    render(<EditorHarness initialValue={"# Title\n\nBody"} />);

    await user.click(screen.getByRole("button", { name: "Split" }));

    expect(screen.getByLabelText("Message")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Preview" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Title" })).toBeInTheDocument();
  });

  it("emits every text edit through onChange", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<EditorHarness initialValue="" onChange={onChange} />);

    await user.type(screen.getByLabelText("Message"), "Post");

    expect(onChange).toHaveBeenLastCalledWith("Post");
  });

  it("accepts image files from the composer attachment control", async () => {
    const user = userEvent.setup();
    const onAttachImages = vi.fn();
    const file = new File(["pngdata"], "launch.png", { type: "image/png" });
    const { container } = render(<EditorHarness initialValue="" onAttachImages={onAttachImages} />);

    const input = container.querySelector<HTMLInputElement>('input[type="file"]');
    expect(input).not.toBeNull();
    await user.upload(input!, file);

    expect(onAttachImages).toHaveBeenCalledWith([file]);
  });

  it("renders image attachments and removes them by id", async () => {
    const user = userEvent.setup();
    const onDeleteAttachment = vi.fn();
    render(
      <EditorHarness
        attachments={[
          {
            content_type: "image/png",
            filename: "launch.png",
            id: 7,
            preview_url: "/preview/7",
            size_bytes: 2048
          }
        ]}
        initialValue=""
        onDeleteAttachment={onDeleteAttachment}
      />
    );

    expect(screen.getByRole("img", { name: "launch.png" })).toHaveAttribute("src", "/preview/7");

    await user.click(screen.getByRole("button", { name: "Remove launch.png" }));

    expect(onDeleteAttachment).toHaveBeenCalledWith(7);
  });
});

function EditorHarness({
  action,
  attachments,
  initialValue,
  onAttachImages,
  onDeleteAttachment,
  onChange
}: {
  action?: ReactNode;
  attachments?: Array<{
    content_type: string;
    filename: string;
    id: number | string;
    preview_url: string;
    size_bytes: number;
  }>;
  initialValue: string;
  onAttachImages?: (files: File[]) => void;
  onDeleteAttachment?: (id: number | string) => void;
  onChange?: (value: string) => void;
}) {
  const [value, setValue] = useState(initialValue);
  return (
    <MattermostEditor
      action={action}
      attachments={attachments}
      id="message"
      label="Message"
      locale="en"
      onAttachImages={onAttachImages}
      onChange={(nextValue) => {
        setValue(nextValue);
        onChange?.(nextValue);
      }}
      onDeleteAttachment={onDeleteAttachment}
      value={value}
    />
  );
}
