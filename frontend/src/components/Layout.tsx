import type { ReactNode } from "react";
import type { Locale, NavItem } from "../api/types";

type LayoutProps = {
  activePage: string;
  children: ReactNode;
  locale: Locale;
  nav: NavItem[];
  username: string;
};

export function Layout({ activePage, children, locale, nav, username }: LayoutProps) {
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
          <div className="user-chip">{username}</div>
        </div>
      </header>
      <main className="shell">{children}</main>
    </>
  );
}
