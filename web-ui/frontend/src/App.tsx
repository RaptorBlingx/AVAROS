import { useCallback, useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { clearStoredApiKey, getStatus, getStoredApiKey } from "./api/client";
import { ApiError } from "./api/client";
import Sidebar from "./components/Sidebar";
import Dashboard from "./pages/Dashboard";
import Login from "./pages/Login";
import Settings from "./pages/Settings";
import Wizard from "./pages/Wizard";

export default function App() {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);

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
    <BrowserRouter>
      <div className="relative sm:grid min-h-screen grid-cols-1 overflow-hidden bg-gradient-to-br from-slate-100 via-sky-50 to-slate-200 md:grid-cols-[260px_1fr]">
        <div className="pointer-events-none absolute -left-16 -top-20 h-56 w-56 rounded-full bg-sky-200/40 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-20 -right-12 h-64 w-64 rounded-full bg-emerald-200/40 blur-3xl" />
        <Sidebar />
        <main className="relative p-4 md:p-8">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/wizard" element={<Wizard />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
