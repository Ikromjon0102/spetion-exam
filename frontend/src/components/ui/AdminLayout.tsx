import { useEffect, useState, type ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { useLanguage } from "../../i18n/LanguageContext";
import Icon from "./Icon";
import Logo from "./Logo";
import ThemeToggle from "./ThemeToggle";
import LanguageSwitcher from "./LanguageSwitcher";
import "./adminlayout.css";

const NARROW_BREAKPOINT = 720;

function readStoredCollapsed(): boolean {
  try {
    return localStorage.getItem("sidebarCollapsed") === "1";
  } catch {
    return false;
  }
}

function useIsNarrow(): boolean {
  const [narrow, setNarrow] = useState(() => window.innerWidth < NARROW_BREAKPOINT);
  useEffect(() => {
    const mq = window.matchMedia(`(max-width: ${NARROW_BREAKPOINT - 1}px)`);
    const handler = () => setNarrow(mq.matches);
    handler();
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);
  return narrow;
}

export default function AdminLayout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const { t } = useLanguage();
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(readStoredCollapsed);
  const isNarrow = useIsNarrow();
  // On a narrow viewport the sidebar is always icon-only regardless of the
  // stored preference — but that preference must still drive every bit of
  // conditional rendering (not just the CSS width), or controls like the
  // language switcher render their wide variant in a narrow column and
  // look broken. This is the single source of truth for "is it collapsed
  // right now"; `collapsed` alone is only the user's stored choice.
  const effectiveCollapsed = collapsed || isNarrow;

  useEffect(() => {
    try {
      localStorage.setItem("sidebarCollapsed", collapsed ? "1" : "0");
    } catch {
      // ignore — private browsing / storage blocked
    }
  }, [collapsed]);

  const isAdmin = user?.role === "admin";

  function handleLogout() {
    logout();
    navigate("/staff-login");
  }

  const items: { to: string; label: string; icon: Parameters<typeof Icon>[0]["name"] }[] = [
    { to: "/admin/dashboard", label: t("header.dashboard"), icon: "home" },
    { to: "/admin/exams", label: t("adminExamList.title"), icon: "list" },
    { to: "/classes", label: t("adminNav.classes"), icon: "grid" },
    ...(isAdmin
      ? ([
          { to: "/admin/manage/subjects", label: t("adminNav.subjects"), icon: "book" },
          { to: "/admin/manage/students", label: t("adminNav.students"), icon: "users" },
          { to: "/admin/manage/teachers", label: t("adminNav.teachers"), icon: "user-check" },
        ] as const)
      : []),
  ];

  return (
    <div className="sp-shell">
      <aside className={`sp-sidebar${effectiveCollapsed ? " sp-sidebar--collapsed" : ""}`}>
        <div className="sp-sidebar__brand">
          <Logo variant={effectiveCollapsed ? "mark" : "horizontal"} tone="red" height={effectiveCollapsed ? 26 : 22} />
        </div>

        <nav className="sp-sidebar__nav">
          {items.map((item) => {
            const active = location.pathname === item.to || location.pathname.startsWith(item.to + "/");
            return (
              <a
                key={item.to}
                href={item.to}
                className={`sp-sidebar__link${active ? " sp-sidebar__link--active" : ""}`}
                title={effectiveCollapsed ? item.label : undefined}
              >
                <Icon name={item.icon} />
                {!effectiveCollapsed && <span>{item.label}</span>}
              </a>
            );
          })}
        </nav>

        <div className="sp-sidebar__foot">
          <a
            href="/change-password"
            className="sp-sidebar__link"
            title={effectiveCollapsed ? t("header.changePassword") : undefined}
          >
            <Icon name="lock" />
            {!effectiveCollapsed && <span>{t("header.changePassword")}</span>}
          </a>
          <button className="sp-sidebar__link sp-sidebar__link--button" onClick={handleLogout}>
            <Icon name="log-out" />
            {!effectiveCollapsed && <span>{t("header.logout")}</span>}
          </button>

          {!effectiveCollapsed && (
            <div className="sp-sidebar__user">
              <span className="body-sm ink-muted">{user?.full_name}</span>
            </div>
          )}

          <div className="sp-sidebar__tools">
            <LanguageSwitcher compact={effectiveCollapsed} />
            <ThemeToggle />
            {!isNarrow && (
              <button
                className="sp-sidebar__collapse"
                onClick={() => setCollapsed((c) => !c)}
                aria-label={t(collapsed ? "sidebar.expand" : "sidebar.collapse")}
              >
                <Icon name={collapsed ? "chevron-right" : "chevron-left"} size={16} />
              </button>
            )}
          </div>
        </div>
      </aside>
      <div className="sp-shell__content">{children}</div>
    </div>
  );
}
