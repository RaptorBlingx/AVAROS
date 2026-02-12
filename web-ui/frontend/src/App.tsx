import { useCallback, useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { ApiError, clearStoredApiKey, getStatus, getStoredApiKey } from "./api/client";
import ErrorBoundary from "./components/common/ErrorBoundary";
import { useTheme } from "./components/common/ThemeProvider";
import Sidebar from "./components/Sidebar";
import Dashboard from "./pages/Dashboard";
import KPIDashboard from "./pages/KPIDashboard";
import Login from "./pages/Login";
import Settings from "./pages/Settings";
import Wizard from "./pages/Wizard";

export default function App() {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const { isDark } = useTheme();

  const checkAuth = useCallback(async () => {
    // If no stored key, go straight to login
    if (!getStoredApiKey()) {
      setAuthenticated(false);
      return;
    }
    try {
      await getStatus();
      setAuthenticated(true);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        clearStoredApiKey();
        setAuthenticated(false);
      } else {
        // Server down or network error — show app anyway to display error
        setAuthenticated(true);
      }
    }
  }, []);

  useEffect(() => {
    void checkAuth();
  }, [checkAuth]);

  // Still checking auth status
  if (authenticated === null) {
    return null;
  }

  if (!authenticated) {
    return <Login onAuthenticated={() => setAuthenticated(true)} />;
  }

  return (
    <ErrorBoundary>
      <BrowserRouter>
        <div
          className={`relative min-h-screen overflow-hidden transition-colors duration-300 ${
            isDark
              ? "bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950"
              : "bg-gradient-to-br from-slate-100 via-sky-50 to-slate-200"
          }`}
        >
          <div
            className={`pointer-events-none absolute -left-16 -top-20 h-56 w-56 rounded-full blur-3xl ${
              isDark ? "bg-sky-500/10" : "bg-sky-200/40"
            }`}
          />
          <div
            className={`pointer-events-none absolute -bottom-20 -right-12 h-64 w-64 rounded-full blur-3xl ${
              isDark ? "bg-emerald-500/10" : "bg-emerald-200/40"
            }`}
          />
          <Sidebar />
          <main className="relative p-4 md:ml-[260px] md:p-8">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/kpi" element={<KPIDashboard />} />
              <Route path="/wizard" element={<Wizard />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
