import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { PageLoader } from "./Loader.jsx";

// Pages behind login. The API enforces authorization on every request; this guard only
// decides what to *show* (the dashboard or the login page).
export function ProtectedRoute() {
  const { status } = useAuth();
  const location = useLocation();
  if (status === "loading") return <PageLoader label="Checking your session" />;
  if (status !== "authenticated") return <Navigate to="/login" replace state={{ from: location }} />;
  return <Outlet />;
}

// Login and registration make no sense once logged in: send the user on to where the login
// or registration asked for (e.g. the profile page for new accounts), or the dashboard.
export function PublicOnlyRoute() {
  const { status, redirectTo } = useAuth();
  if (status === "loading") return <PageLoader label="Checking your session" />;
  if (status === "authenticated") {
    return <Navigate to={redirectTo?.to ?? "/dashboard"} state={redirectTo?.state} replace />;
  }
  return <Outlet />;
}
