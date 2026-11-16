import type { ReactElement } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "./AuthContext";
import { useLanguage } from "../i18n/LanguageContext";
import type { MeOut } from "../api/authApi";

export default function RequireRole({
  roles,
  children,
}: {
  roles: Array<MeOut["role"]>;
  children: ReactElement;
}) {
  const { user, loading } = useAuth();
  const { t } = useLanguage();

  if (loading) {
    return (
      <div className="page">
        <p className="ink-muted">{t("taking.loading")}</p>
      </div>
    );
  }
  if (!user) return <Navigate to="/" replace />;
  // Signed in but on the other side's page (a teacher on a student URL, or
  // the reverse): "/" sends each role to its own home.
  if (!roles.includes(user.role)) return <Navigate to="/" replace />;
  return children;
}
