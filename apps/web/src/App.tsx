import { Navigate, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuth } from "./auth/AuthProvider";
import { AppShell } from "./components/shell/AppShell";
import { ApprovalsPage } from "./pages/ApprovalsPage";
import { AdminPage } from "./pages/AdminPage";
import { CommercePage } from "./pages/CommercePage";
import { CustomerPage } from "./pages/CustomerPage";
import { EvidencePage } from "./pages/EvidencePage";
import { OverviewPage } from "./pages/OverviewPage";
import { ResolutionPage } from "./pages/ResolutionPage";

export default function App() {
  return <Routes><Route element={<AppShell />}>
    <Route index element={<OverviewPage />} />
    <Route path="resolution" element={<ResolutionPage />} />
    <Route path="approvals" element={<RoleRoute roles={["supervisor", "admin"]}><ApprovalsPage /></RoleRoute>} />
    <Route path="traces" element={<RoleRoute roles={["support_agent", "supervisor", "admin"]}><EvidencePage kind="traces" /></RoleRoute>} />
    <Route path="evaluation" element={<RoleRoute roles={["supervisor", "admin"]}><EvidencePage kind="evaluation" /></RoleRoute>} />
    <Route path="rag-evolution" element={<RoleRoute roles={["supervisor", "admin"]}><EvidencePage kind="rag" /></RoleRoute>} />
    <Route path="cost" element={<RoleRoute roles={["supervisor", "admin"]}><EvidencePage kind="cost" /></RoleRoute>} />
    <Route path="customers" element={<RoleRoute roles={["support_agent", "supervisor", "admin"]}><CustomerPage /></RoleRoute>} />
    <Route path="signals" element={<RoleRoute roles={["support_agent", "supervisor", "admin"]}><CommercePage kind="signals" /></RoleRoute>} />
    <Route path="anomalies" element={<RoleRoute roles={["support_agent", "supervisor", "admin"]}><CommercePage kind="anomalies" /></RoleRoute>} />
    <Route path="root-cause" element={<RoleRoute roles={["supervisor", "admin"]}><CommercePage kind="root-cause" /></RoleRoute>} />
    <Route path="actions" element={<RoleRoute roles={["supervisor", "admin"]}><CommercePage kind="actions" /></RoleRoute>} />
    <Route path="outcomes" element={<RoleRoute roles={["supervisor", "admin"]}><CommercePage kind="outcomes" /></RoleRoute>} />
    {(["models", "policies", "audit", "reports", "health", "settings", "knowledge"] as const).map((page) => <Route key={page} path={page} element={<RoleRoute roles={pageRoles[page]}><AdminPage kind={page} /></RoleRoute>} />)}
    <Route path="*" element={<Navigate to="/" replace />} />
  </Route></Routes>;
}

const pageRoles: Record<string, string[]> = {
  models: ["admin"],
  policies: ["supervisor", "admin"],
  audit: ["supervisor", "admin"],
  reports: ["supervisor", "admin"],
  health: ["admin"],
  settings: ["admin"],
  knowledge: ["support_agent", "supervisor", "admin"],
};

function RoleRoute({ roles, children }: { roles: string[]; children: ReactNode }) {
  const auth = useAuth();
  return auth.hasAnyRole(roles) ? children : <Navigate to="/" replace />;
}
