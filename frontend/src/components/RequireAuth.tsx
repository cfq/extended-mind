import { Navigate, Outlet, useLocation } from "react-router";

import { useSession } from "../lib/auth";

export function RequireAuth() {
  const { data: user, isPending } = useSession();
  const location = useLocation();

  if (isPending) return null;
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  return <Outlet />;
}
