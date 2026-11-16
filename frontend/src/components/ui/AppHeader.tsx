import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { useLanguage } from "../../i18n/LanguageContext";
import Logo from "./Logo";
import Button from "./Button";
import ThemeToggle from "./ThemeToggle";
import LanguageSwitcher from "./LanguageSwitcher";
import "./appheader.css";

// Student-facing top header only — teacher/admin pages use AdminLayout's
// left sidebar instead (see components/ui/AdminLayout.tsx).
export default function AppHeader() {
  const { user, logout } = useAuth();
  const { t } = useLanguage();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/");
  }

  return (
    <header className="sp-header">
      <div className="sp-header__inner">
        {/* Links, not <a href>: a plain anchor reloads the whole app. */}
        <Link to="/student/exams" className="sp-header__brand">
          <Logo variant="horizontal" tone="red" height={24} />
        </Link>
        <div className="sp-header__user">
          <LanguageSwitcher compact />
          <ThemeToggle />
          {user && (
            <>
              <Link to="/student/profile" className="body-sm sp-header__link">
                {t("header.profile")}
              </Link>
              <Link to="/change-password" className="body-sm sp-header__link">
                {t("header.changePassword")}
              </Link>
              <span className="body-sm ink-muted sp-header__name">{user.full_name}</span>
              <Button variant="ghost" size="sm" onClick={handleLogout}>
                {t("header.logout")}
              </Button>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
