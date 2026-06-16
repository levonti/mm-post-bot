export type Locale = "en" | "ru";

export type NavItem = {
  href: string;
  key: string;
  label: string;
};

export type BootstrapPayload = {
  session: { user_id: string; username: string };
  csrf: string;
  locale: Locale;
  nav: NavItem[];
};

export type DraftAttachmentPayload = {
  id: number;
  filename: string;
  content_type: string;
  size_bytes: number;
  preview_url: string;
};
