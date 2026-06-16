import {
  Fragment,
  useId,
  useRef,
  useState,
  type ChangeEvent,
  type ClipboardEvent,
  type DragEvent,
  type KeyboardEvent,
  type ReactNode
} from "react";
import {
  Bold,
  Code,
  Columns2,
  Eye,
  FileCode,
  ImagePlus,
  Italic,
  Link,
  List,
  ListOrdered,
  Pencil,
  Quote,
  Strikethrough,
  Table2,
  Trash2,
  type LucideIcon
} from "lucide-react";
import type { Locale } from "../api/types";
import { t } from "../i18n";

type MattermostEditorProps = {
  action?: ReactNode;
  attachments?: DraftEditorAttachment[];
  id: string;
  label: string;
  locale: Locale;
  name?: string;
  onAttachImages?: (files: File[]) => void | Promise<void>;
  onChange: (value: string) => void;
  onDeleteAttachment?: (id: number | string) => void | Promise<void>;
  placeholder?: string;
  rows?: number;
  value: string;
};

export type DraftEditorAttachment = {
  content_type: string;
  filename: string;
  id: number | string;
  preview_url: string;
  size_bytes: number;
};

type ToolbarAction =
  | "bold"
  | "italic"
  | "strike"
  | "inline_code"
  | "link"
  | "quote"
  | "bullet_list"
  | "numbered_list"
  | "code_block"
  | "table";

type EditorMode = "edit" | "preview" | "split";

const TOOLBAR_GROUPS: Array<{
  actions: ToolbarAction[];
  label: Parameters<typeof t>[1];
}> = [
  {
    label: "web.editor.group_text",
    actions: ["bold", "italic", "strike", "inline_code", "link"]
  },
  {
    label: "web.editor.group_blocks",
    actions: ["quote", "bullet_list", "numbered_list", "code_block", "table"]
  }
];

const ACTION_LABELS: Record<ToolbarAction, Parameters<typeof t>[1]> = {
  bold: "web.editor.bold",
  bullet_list: "web.editor.bullet_list",
  code_block: "web.editor.code_block",
  inline_code: "web.editor.inline_code",
  italic: "web.editor.italic",
  link: "web.editor.link",
  numbered_list: "web.editor.numbered_list",
  quote: "web.editor.quote",
  strike: "web.editor.strike",
  table: "web.editor.table"
};

const ACTION_ICONS: Record<ToolbarAction, LucideIcon> = {
  bold: Bold,
  bullet_list: List,
  code_block: FileCode,
  inline_code: Code,
  italic: Italic,
  link: Link,
  numbered_list: ListOrdered,
  quote: Quote,
  strike: Strikethrough,
  table: Table2
};

export function MattermostEditor({
  action,
  attachments = [],
  id,
  label,
  locale,
  name = "message",
  onAttachImages,
  onChange,
  onDeleteAttachment,
  placeholder,
  rows = 8,
  value
}: MattermostEditorProps) {
  const fileInputId = useId();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const [mode, setMode] = useState<EditorMode>("edit");

  return (
    <div className="mattermost-editor">
      <label htmlFor={id}>{label}</label>
      <div className="mattermost-composer-frame">
        <div
          className="editor-body"
          onDragOver={handleDragOver}
          onDrop={handleDrop}
        >
          {mode === "edit" ? renderTextarea() : null}
          {mode === "split" ? (
            <div className="editor-split">
              {renderTextarea()}
              <div
                className="editor-preview"
                role="region"
                aria-label={t(locale, "web.editor.preview")}
              >
                <MarkdownPreview locale={locale} value={value} />
              </div>
            </div>
          ) : null}
          {mode === "preview" ? (
            <div className="editor-preview" role="region" aria-label={t(locale, "web.editor.preview")}>
              <MarkdownPreview locale={locale} value={value} />
            </div>
          ) : null}
        </div>
        {attachments.length > 0 ? (
          <div className="editor-attachments" aria-label={t(locale, "web.editor.attachments")}>
            {attachments.map((attachment) => (
              <div className="editor-attachment" key={attachment.id}>
                <img alt={attachment.filename} src={attachment.preview_url} />
                <div className="editor-attachment-meta">
                  <strong>{attachment.filename}</strong>
                  <span>{formatBytes(attachment.size_bytes)}</span>
                </div>
                {onDeleteAttachment ? (
                  <button
                    aria-label={t(locale, "web.editor.remove_attachment", {
                      filename: attachment.filename
                    })}
                    className="editor-attachment-remove"
                    onClick={() => void onDeleteAttachment(attachment.id)}
                    title={t(locale, "web.editor.remove_attachment", {
                      filename: attachment.filename
                    })}
                    type="button"
                  >
                    <Trash2 aria-hidden="true" size={15} strokeWidth={2.1} />
                  </button>
                ) : null}
              </div>
            ))}
          </div>
        ) : null}
        <div className="editor-footer">
          <div className="editor-toolbar" aria-label={t(locale, "web.editor.toolbar")} role="toolbar">
            <div className="editor-format-actions">
              {TOOLBAR_GROUPS.map((group) => (
                <div
                  aria-label={t(locale, group.label)}
                  className="editor-tool-group"
                  key={group.label}
                  role="group"
                >
                  {group.actions.map((toolbarAction) => {
                    const Icon = ACTION_ICONS[toolbarAction];
                    return (
                      <button
                        aria-keyshortcuts={shortcutFor(toolbarAction)}
                        aria-label={t(locale, ACTION_LABELS[toolbarAction])}
                        className="editor-tool-button"
                        disabled={mode === "preview"}
                        key={toolbarAction}
                        onClick={() => applyAction(toolbarAction)}
                        title={t(locale, ACTION_LABELS[toolbarAction])}
                        type="button"
                      >
                        <Icon aria-hidden="true" size={16} strokeWidth={2.1} />
                      </button>
                    );
                  })}
                </div>
              ))}
              {onAttachImages ? (
                <div
                  aria-label={t(locale, "web.editor.group_media")}
                  className="editor-tool-group"
                  role="group"
                >
                  <input
                    accept="image/gif,image/jpeg,image/png,image/webp"
                    aria-hidden="true"
                    className="visually-hidden"
                    disabled={mode === "preview"}
                    id={fileInputId}
                    multiple
                    onChange={handleFileInputChange}
                    ref={fileInputRef}
                    tabIndex={-1}
                    type="file"
                  />
                  <button
                    aria-label={t(locale, "web.editor.add_image")}
                    className="editor-tool-button"
                    disabled={mode === "preview"}
                    onClick={() => fileInputRef.current?.click()}
                    title={t(locale, "web.editor.add_image")}
                    type="button"
                  >
                    <ImagePlus aria-hidden="true" size={16} strokeWidth={2.1} />
                  </button>
                </div>
              ) : null}
            </div>
          </div>
          <div className="editor-footer-actions">
            <div className="editor-mode-switch" role="group" aria-label={t(locale, "web.editor.mode")}>
              <button
                aria-pressed={mode === "edit"}
                aria-label={t(locale, "web.editor.edit")}
                className="editor-mode-button"
                onClick={() => setMode("edit")}
                title={t(locale, "web.editor.edit")}
                type="button"
              >
                <Pencil aria-hidden="true" size={15} strokeWidth={2.1} />
                <span className="visually-hidden">{t(locale, "web.editor.edit")}</span>
              </button>
              <button
                aria-pressed={mode === "split"}
                aria-label={t(locale, "web.editor.split")}
                className="editor-mode-button"
                onClick={() => setMode("split")}
                title={t(locale, "web.editor.split")}
                type="button"
              >
                <Columns2 aria-hidden="true" size={15} strokeWidth={2.1} />
                <span className="visually-hidden">{t(locale, "web.editor.split")}</span>
              </button>
              <button
                aria-pressed={mode === "preview"}
                aria-label={t(locale, "web.editor.preview")}
                className="editor-mode-button"
                onClick={() => setMode("preview")}
                title={t(locale, "web.editor.preview")}
                type="button"
              >
                <Eye aria-hidden="true" size={15} strokeWidth={2.1} />
                <span className="visually-hidden">{t(locale, "web.editor.preview")}</span>
              </button>
            </div>
            <div className="editor-meta">
              <span>{t(locale, "web.editor.characters", { count: value.length })}</span>
              <span>{t(locale, "web.editor.lines", { count: value ? value.split("\n").length : 0 })}</span>
            </div>
            {action ? <div className="editor-action-slot">{action}</div> : null}
          </div>
        </div>
      </div>
    </div>
  );

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    const withModifier = event.metaKey || event.ctrlKey;
    if (!withModifier) return;
    const key = event.key.toLowerCase();
    if (key === "b") {
      event.preventDefault();
      applyAction("bold");
    }
    if (key === "i") {
      event.preventDefault();
      applyAction("italic");
    }
    if (key === "k") {
      event.preventDefault();
      applyAction("link");
    }
  }

  function renderTextarea() {
    return (
      <textarea
        id={id}
        name={name}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={handleKeyDown}
        onPaste={handlePaste}
        placeholder={placeholder}
        ref={textareaRef}
        rows={rows}
        value={value}
      />
    );
  }

  function handleDragOver(event: DragEvent<HTMLDivElement>) {
    if (!onAttachImages || collectImageFiles(event.dataTransfer.files).length === 0) return;
    event.preventDefault();
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    if (!onAttachImages) return;
    const imageFiles = collectImageFiles(event.dataTransfer.files);
    if (imageFiles.length === 0) return;
    event.preventDefault();
    void onAttachImages(imageFiles);
  }

  function handleFileInputChange(event: ChangeEvent<HTMLInputElement>) {
    if (!onAttachImages) return;
    const imageFiles = collectImageFiles(event.target.files);
    if (imageFiles.length > 0) {
      void onAttachImages(imageFiles);
    }
    event.target.value = "";
  }

  function handlePaste(event: ClipboardEvent<HTMLTextAreaElement>) {
    if (!onAttachImages) return;
    const imageFiles = collectImageFiles(event.clipboardData.files);
    if (imageFiles.length === 0) return;
    event.preventDefault();
    void onAttachImages(imageFiles);
  }

  function applyAction(action: ToolbarAction) {
    if (action === "bold") wrapSelection("**", "**", "bold text");
    if (action === "italic") wrapSelection("_", "_", "italic text");
    if (action === "strike") wrapSelection("~~", "~~", "struck text");
    if (action === "inline_code") wrapSelection("`", "`", "code");
    if (action === "link") wrapSelection("[", "](https://)", "link text");
    if (action === "quote") prefixSelection("> ");
    if (action === "bullet_list") prefixSelection("- ");
    if (action === "numbered_list") prefixSelection("1. ");
    if (action === "code_block") insertBlock("```\ncode\n```");
    if (action === "table") insertBlock("| Column | Value |\n| --- | --- |\n| Item | Detail |");
  }

  function wrapSelection(prefix: string, suffix: string, fallback: string) {
    const textarea = textareaRef.current;
    if (!textarea) return;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selected = value.slice(start, end) || fallback;
    const nextValue = `${value.slice(0, start)}${prefix}${selected}${suffix}${value.slice(end)}`;
    const nextSelectionStart = start + prefix.length;
    const nextSelectionEnd = nextSelectionStart + selected.length;
    onChange(nextValue);
    restoreSelection(nextSelectionStart, nextSelectionEnd);
  }

  function prefixSelection(prefix: string) {
    const textarea = textareaRef.current;
    if (!textarea) return;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const lineStart = value.lastIndexOf("\n", Math.max(0, start - 1)) + 1;
    const lineEndIndex = value.indexOf("\n", end);
    const lineEnd = lineEndIndex === -1 ? value.length : lineEndIndex;
    const selectedBlock = value.slice(lineStart, lineEnd) || "list item";
    const transformed = selectedBlock
      .split("\n")
      .map((line, index) =>
        prefix === "1. " ? `${index + 1}. ${line.replace(/^\d+\.\s*/, "")}` : `${prefix}${line}`
      )
      .join("\n");
    const nextValue = `${value.slice(0, lineStart)}${transformed}${value.slice(lineEnd)}`;
    onChange(nextValue);
    restoreSelection(lineStart, lineStart + transformed.length);
  }

  function insertBlock(block: string) {
    const textarea = textareaRef.current;
    if (!textarea) return;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const before = value.slice(0, start);
    const after = value.slice(end);
    const needsLeadingBreak = before.length > 0 && !before.endsWith("\n") ? "\n\n" : "";
    const needsTrailingBreak = after.length > 0 && !after.startsWith("\n") ? "\n\n" : "";
    const insertion = `${needsLeadingBreak}${block}${needsTrailingBreak}`;
    const nextValue = `${before}${insertion}${after}`;
    onChange(nextValue);
    restoreSelection(start + needsLeadingBreak.length, start + needsLeadingBreak.length + block.length);
  }

  function restoreSelection(start: number, end: number) {
    window.setTimeout(() => {
      const textarea = textareaRef.current;
      if (!textarea) return;
      textarea.focus();
      textarea.setSelectionRange(start, end);
    }, 0);
  }
}

function shortcutFor(action: ToolbarAction): string | undefined {
  if (action === "bold") return "Control+B Meta+B";
  if (action === "italic") return "Control+I Meta+I";
  if (action === "link") return "Control+K Meta+K";
  return undefined;
}

function MarkdownPreview({ locale, value }: { locale: Locale; value: string }) {
  if (!value.trim()) {
    return <p className="muted-meta">{t(locale, "web.editor.empty_preview")}</p>;
  }
  return <>{renderBlocks(value)}</>;
}

function renderBlocks(value: string): ReactNode[] {
  const lines = value.split("\n");
  const blocks: ReactNode[] = [];
  let index = 0;
  while (index < lines.length) {
    const line = lines[index] ?? "";
    if (!line.trim()) {
      index += 1;
      continue;
    }
    if (line.startsWith("```")) {
      const codeLines: string[] = [];
      index += 1;
      while (index < lines.length && !lines[index].startsWith("```")) {
        codeLines.push(lines[index]);
        index += 1;
      }
      blocks.push(
        <pre key={`code-${index}`}>
          <code>{codeLines.join("\n")}</code>
        </pre>
      );
      index += 1;
      continue;
    }
    if (line.startsWith("|") && lines[index + 1]?.includes("---")) {
      const tableRows: string[][] = [];
      const header = splitTableRow(line);
      index += 2;
      while (index < lines.length && lines[index].startsWith("|")) {
        tableRows.push(splitTableRow(lines[index]));
        index += 1;
      }
      blocks.push(
        <table key={`table-${index}`}>
          <thead>
            <tr>{header.map((cell) => <th key={cell}>{renderInline(cell)}</th>)}</tr>
          </thead>
          <tbody>
            {tableRows.map((row, rowIndex) => (
              <tr key={`row-${rowIndex}`}>
                {row.map((cell, cellIndex) => (
                  <td key={`${rowIndex}-${cellIndex}`}>{renderInline(cell)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      );
      continue;
    }
    if (/^#{1,3}\s+/.test(line)) {
      const level = line.match(/^#+/)?.[0].length || 1;
      const content = line.replace(/^#{1,3}\s+/, "");
      if (level === 1) {
        blocks.push(<h3 key={`heading-${index}`}>{renderInline(content)}</h3>);
      } else if (level === 2) {
        blocks.push(<h4 key={`heading-${index}`}>{renderInline(content)}</h4>);
      } else {
        blocks.push(<h5 key={`heading-${index}`}>{renderInline(content)}</h5>);
      }
      index += 1;
      continue;
    }
    if (line.startsWith("> ")) {
      blocks.push(<blockquote key={`quote-${index}`}>{renderInline(line.slice(2))}</blockquote>);
      index += 1;
      continue;
    }
    if (/^-\s+/.test(line)) {
      const items: string[] = [];
      while (index < lines.length && /^-\s+/.test(lines[index])) {
        items.push(lines[index].replace(/^-\s+/, ""));
        index += 1;
      }
      blocks.push(
        <ul key={`ul-${index}`}>{items.map((item) => <li key={item}>{renderInline(item)}</li>)}</ul>
      );
      continue;
    }
    if (/^\d+\.\s+/.test(line)) {
      const items: string[] = [];
      while (index < lines.length && /^\d+\.\s+/.test(lines[index])) {
        items.push(lines[index].replace(/^\d+\.\s+/, ""));
        index += 1;
      }
      blocks.push(
        <ol key={`ol-${index}`}>{items.map((item) => <li key={item}>{renderInline(item)}</li>)}</ol>
      );
      continue;
    }
    blocks.push(<p key={`p-${index}`}>{renderInline(line)}</p>);
    index += 1;
  }
  return blocks;
}

function renderInline(text: string): ReactNode[] {
  const token = findFirstInlineToken(text);
  if (!token) return [text];
  return [
    ...renderInline(text.slice(0, token.start)),
    token.node,
    ...renderInline(text.slice(token.end))
  ];
}

function findFirstInlineToken(text: string): { end: number; node: ReactNode; start: number } | null {
  const patterns: Array<{
    build: (match: RegExpMatchArray) => ReactNode;
    regex: RegExp;
  }> = [
    {
      regex: /\*\*([^*]+)\*\*/,
      build: (match) => <strong key={`${match.index}-bold`}>{renderInline(match[1])}</strong>
    },
    {
      regex: /_([^_]+)_/,
      build: (match) => <em key={`${match.index}-italic`}>{renderInline(match[1])}</em>
    },
    {
      regex: /~~([^~]+)~~/,
      build: (match) => <s key={`${match.index}-strike`}>{renderInline(match[1])}</s>
    },
    {
      regex: /`([^`]+)`/,
      build: (match) => <code key={`${match.index}-code`}>{match[1]}</code>
    },
    {
      regex: /\[([^\]]+)]\(([^)]+)\)/,
      build: (match) => (
        <a href={safeHref(match[2])} key={`${match.index}-link`}>
          {renderInline(match[1])}
        </a>
      )
    }
  ];

  const matches: Array<{ end: number; node: ReactNode; start: number }> = [];
  for (const { build, regex } of patterns) {
    const match = text.match(regex);
    if (!match || match.index === undefined) continue;
    matches.push({
      end: match.index + match[0].length,
      node: <Fragment key={`${match.index}-${match[0]}`}>{build(match)}</Fragment>,
      start: match.index
    });
  }
  return matches.sort((left, right) => left.start - right.start)[0] ?? null;
}

function safeHref(value: string): string {
  if (/^(https?:|mailto:)/.test(value)) return value;
  return "#";
}

function splitTableRow(line: string): string[] {
  return line
    .split("|")
    .slice(1, -1)
    .map((cell) => cell.trim());
}

function collectImageFiles(files: FileList | null): File[] {
  if (!files) return [];
  return Array.from(files).filter((file) => file.type.startsWith("image/"));
}

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}
