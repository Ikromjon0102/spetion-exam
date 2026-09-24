import type { ReactElement } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "./AuthContext";
import type { MeOut } from "../api/authApi";

export default function RequireRole({
  roles,
  children,
}: {
  roles: Array<MeOut["role"]>;
  children: ReactElement;
}) {
  const { user, loading } = useAuth();

  if (loading) return <p>Yuklanmoqda...</p>;
  if (!user) return <Navigate to="/" replace />;
  if (!roles.includes(user.role)) return <Navigate to="/" replace />;
  return children;
}
