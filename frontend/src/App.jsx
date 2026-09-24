import { Route, Routes } from "react-router-dom";
import AppLayout from "./components/AppLayout.jsx";
import { ProtectedRoute, PublicOnlyRoute } from "./components/RouteGuards.jsx";
import CloudFilesPage from "./pages/CloudFilesPage.jsx";
import DashboardPage from "./pages/DashboardPage.jsx";
import GeneratePlanPage from "./pages/GeneratePlanPage.jsx";
import LandingPage from "./pages/LandingPage.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import NotFoundPage from "./pages/NotFoundPage.jsx";
import PlanResultPage from "./pages/PlanResultPage.jsx";
import ProfilePage from "./pages/ProfilePage.jsx";
import RegisterPage from "./pages/RegisterPage.jsx";
import SavedPlansPage from "./pages/SavedPlansPage.jsx";

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<LandingPage />} />

        <Route element={<PublicOnlyRoute />}>
          <Route path="login" element={<LoginPage />} />
          <Route path="register" element={<RegisterPage />} />
        </Route>

        <Route element={<ProtectedRoute />}>
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="generate" element={<GeneratePlanPage />} />
          <Route path="plans" element={<SavedPlansPage />} />
          <Route path="plans/:planId" element={<PlanResultPage />} />
          <Route path="files" element={<CloudFilesPage />} />
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
