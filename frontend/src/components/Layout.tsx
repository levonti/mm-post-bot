import type { ReactNode } from "react";
import type { Locale, NavItem } from "../api/types";
import { t } from "../i18n";

type LayoutProps = {
  activePage: string;
  children: ReactNode;
  locale: Locale;
  nav: NavItem[];
  onLocaleChange?: (locale: Locale) => void | Promise<void>;
  username: string;
};

export function Layout({
  activePage,
  children,
  locale,
  nav,
  onLocaleChange,
  username
}: LayoutProps) {
  return (
    <>
      <header className="topbar">
        <a className="brand" href="/">
          mm-post-bot
        </a>
        <nav
          className="primary-nav"
          aria-label={locale === "ru" ? "Основная навигация" : "Primary navigation"}
        >
          {nav.map((item) => (
            <a
              key={item.key}
              aria-current={activePage === item.key ? "page" : undefined}
              className={activePage === item.key ? "active" : ""}
              href={item.href}
            >
              {item.label}
            </a>
          ))}
        </nav>
        <div className="topbar-actions">
          <div
            aria-label={t(locale, "web.language.label")}
            className="locale-switch"
            role="group"
          >
            <button
              aria-pressed={locale === "en"}
              onClick={() => onLocaleChange?.("en")}
              type="button"
            >
              EN
            </button>
            <button
              aria-label="Русский"
              aria-pressed={locale === "ru"}
              onClick={() => onLocaleChange?.("ru")}
              type="button"
            >
              RU
            </button>
          </div>
          <div className="user-chip">{username}</div>
        </div>
      </header>
      <main className="shell">{children}</main>
    </>
  );
}
