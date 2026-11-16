import { useEffect, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { listClasses, login, type ClassOut } from "../../api/authApi";
import { useAuth } from "../../auth/AuthContext";
import { useLanguage } from "../../i18n/LanguageContext";
import { Button, Card, LanguageSwitcher, Logo, PasswordInput, ThemeToggle } from "../../components/ui";

/** Student login: pick a class (sinf), then username/password. */
export default function ClassLoginPage() {
  const [classes, setClasses] = useState<ClassOut[]>([]);
  const [classId, setClassId] = useState<number | "">("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const { setTokens, user, loading } = useAuth();
  const { t } = useLanguage();
  const navigate = useNavigate();

  useEffect(() => {
    listClasses().then(setClasses).catch(() => setError(t("login.classesLoadError")));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const tokens = await login(username, password, classId === "" ? undefined : classId);
      setTokens(tokens.access_token, tokens.refresh_token);
      navigate("/student/exams");
    } catch (e) {
      // Only a rejected login is "wrong password"; no answer at all is the
      // network, and telling the user to retype their password is wrong.
      const reached = (e as { response?: unknown })?.response !== undefined;
      setError(t(reached ? "login.studentError" : "login.networkError"));
    } finally {
      setSubmitting(false);
    }
  }

  // Already signed in (a returning visit, or the logo link): go straight to
  // your own home instead of showing the login form again.
  if (!loading && user && !submitting) {
    return <Navigate to={user.role === "student" ? "/student/exams" : "/admin/dashboard"} replace />;
  }

  return (
    <div className="center-screen login-screen">
      <div style={{ width: "100%", maxWidth: 380 }}>
        <div style={{ display: "flex", justifyContent: "center", gap: "var(--space-2)", marginBottom: "var(--space-4)" }}>
          <LanguageSwitcher />
          <ThemeToggle />
        </div>
        <div style={{ display: "flex", justifyContent: "center", marginBottom: "var(--space-8)" }}>
          <Logo variant="stacked" tone="red" height={96} />
        </div>
        <Card className="login-card">
          <h1 className="h3" style={{ marginBottom: "var(--space-1)" }}>
            {t("login.studentTitle")}
          </h1>
          <p className="body-sm ink-muted" style={{ marginBottom: "var(--space-5)" }}>
            {t("login.studentSubtitle")}
          </p>
          <form onSubmit={handleSubmit} className="stack">
            <div className="sp-field">
              <label className="sp-field__label" htmlFor="login-class">
                {t("login.class")}
              </label>
              <select
                id="login-class"
                className="sp-select"
                value={classId}
                onChange={(e) => setClassId(Number(e.target.value))}
                required
              >
                <option value="">{t("login.selectClass")}</option>
                {classes.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.display_name}
                  </option>
                ))}
              </select>
            </div>
            <div className="sp-field">
              <label className="sp-field__label" htmlFor="login-username">
                {t("login.username")}
              </label>
              <input
                id="login-username"
                className="sp-input"
                autoComplete="username"
                autoCapitalize="none"
                spellCheck={false}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
              />
            </div>
            <div className="sp-field">
              <label className="sp-field__label" htmlFor="login-password">
                {t("login.password")}
              </label>
              <PasswordInput
                id="login-password"
                autoComplete="current-password"
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
          <Link to="/staff-login">{t("login.toStaff")}</Link>
        </p>
      </div>
    </div>
  );
}
