import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { login } from "../../api/authApi";
import { useAuth } from "../../auth/AuthContext";
import { useLanguage } from "../../i18n/LanguageContext";
import { Button, Card, LanguageSwitcher, Logo, ThemeToggle } from "../../components/ui";

/** Teacher/admin login — no class picker, unlike the student login. */
export default function StaffLoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const { setTokens } = useAuth();
  const { t } = useLanguage();
  const navigate = useNavigate();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const tokens = await login(username, password);
      setTokens(tokens.access_token, tokens.refresh_token);
      navigate("/admin/dashboard");
    } catch {
      setError(t("login.staffError"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="center-screen">
      <div style={{ width: "100%", maxWidth: 380 }}>
        <div style={{ display: "flex", justifyContent: "center", gap: "var(--space-2)", marginBottom: "var(--space-4)" }}>
          <LanguageSwitcher />
          <ThemeToggle />
        </div>
        <div style={{ display: "flex", justifyContent: "center", marginBottom: "var(--space-8)" }}>
          <Logo variant="stacked" tone="red" height={96} />
        </div>
        <Card>
          <h1 className="h3" style={{ marginBottom: "var(--space-1)" }}>
            {t("login.staffTitle")}
          </h1>
          <p className="body-sm ink-muted" style={{ marginBottom: "var(--space-5)" }}>
            {t("login.staffSubtitle")}
          </p>
          <form onSubmit={handleSubmit} className="stack">
            <div className="sp-field">
              <input
                className="sp-input"
                placeholder={t("login.username")}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
              />
            </div>
            <div className="sp-field">
              <input
                className="sp-input"
                type="password"
                placeholder={t("login.password")}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            {error && (
              <p role="alert" className="body-sm" style={{ color: "var(--danger)" }}>
                {error}
              </p>
            )}
            <Button type="submit" block disabled={submitting}>
              {submitting ? t("login.submitting") : t("login.submit")}
            </Button>
          </form>
        </Card>
        <p className="body-sm" style={{ textAlign: "center", marginTop: "var(--space-5)" }}>
          <a href="/">{t("login.toStudent")}</a>
        </p>
      </div>
    </div>
  );
}
