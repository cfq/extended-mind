import { Navigate, Outlet } from "react-router";

import { useSession } from "../lib/auth";

export function RequireAuth() {
  const { data: user, isPending } = useSession();

  if (isPending) return null;
  if (!user) return <Navigate to="/login" replace />;
  return <Outlet />;
}
