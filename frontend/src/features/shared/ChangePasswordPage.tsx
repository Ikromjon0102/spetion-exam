import { useState } from "react";
import { changePassword } from "../../api/authApi";
import { useAuth } from "../../auth/AuthContext";
import { AdminLayout, AppHeader, Button, Card } from "../../components/ui";
import { useLanguage } from "../../i18n/LanguageContext";
import { errorDetail } from "../../utils/errorDetail";

export default function ChangePasswordPage() {
  const { user } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const { t } = useLanguage();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(false);

    if (newPassword !== confirmPassword) {
      setError(t("changePassword.mismatch"));
      return;
    }

    setSubmitting(true);
    try {
      await changePassword(currentPassword, newPassword);
      setSuccess(true);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (e) {
      setError(errorDetail(e, t("changePassword.wrongCurrent")));
    } finally {
      setSubmitting(false);
    }
  }

  const content = (
    <div className="page" style={{ maxWidth: 420 }}>
      <h1 className="h2" style={{ marginBottom: "var(--space-6)" }}>
        {t("changePassword.title")}
      </h1>
      <Card>
        <form onSubmit={handleSubmit} className="stack">
          <div className="sp-field">
            <label className="sp-field__label">{t("changePassword.current")}</label>
            <input
              className="sp-input"
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              required
            />
          </div>
          <div className="sp-field">
            <label className="sp-field__label">{t("changePassword.new")}</label>
            <input
              className="sp-input"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              minLength={6}
              required
            />
          </div>
          <div className="sp-field">
            <label className="sp-field__label">{t("changePassword.confirm")}</label>
            <input
              className="sp-input"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              minLength={6}
              required
            />
          </div>
          {error && (
            <p role="alert" className="body-sm" style={{ color: "var(--danger)" }}>
              {error}
            </p>
          )}
          {success && (
            <p className="body-sm" style={{ color: "var(--success)" }}>
              {t("changePassword.success")}
            </p>
          )}
          <Button type="submit" block disabled={submitting}>
            {submitting ? t("changePassword.submitting") : t("changePassword.submit")}
          </Button>
        </form>
      </Card>
    </div>
  );

  if (user?.role === "student") {
    return (
      <>
        <AppHeader />
        {content}
      </>
    );
  }
  return <AdminLayout>{content}</AdminLayout>;
}
