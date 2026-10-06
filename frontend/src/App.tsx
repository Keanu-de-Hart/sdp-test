/** Application shell: routing + providers. */
import { BrowserRouter, Navigate, Route, Routes, useParams } from "react-router-dom";
import { NavBar } from "./components/NavBar";
import { AuthorsPage } from "./pages/AuthorsPage";
import { DashboardPage } from "./pages/DashboardPage";
import { ReposPage } from "./pages/ReposPage";
import { FiltersProvider } from "./state/FiltersContext";
import { ToastProvider } from "./state/ToastContext";

function DashboardRoute() {
  const params = useParams();
  const repoId = Number(params.repoId);
  if (!Number.isFinite(repoId) || repoId <= 0) return <Navigate to="/" replace />;
  return (
    <FiltersProvider repoId={repoId}>
      <DashboardPage />
    </FiltersProvider>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <div className="app-shell">
          <NavBar />
          <Routes>
            <Route path="/" element={<ReposPage />} />
            <Route path="/repos/:repoId/dashboard" element={<DashboardRoute />} />
            <Route path="/repos/:repoId/authors" element={<AuthorsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </ToastProvider>
    </BrowserRouter>
  );
}
