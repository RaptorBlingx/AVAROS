import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";

import { ApiError, clearStoredApiKey, getStatus, getStoredApiKey } from "./api/client";
import ErrorBoundary from "./components/common/ErrorBoundary";
import { useTheme } from "./components/common/ThemeProvider";
import Sidebar from "./components/Sidebar";
import VoiceWidget from "./components/voice/VoiceWidget";
import Dashboard from "./pages/Dashboard";
import KPIDashboard from "./pages/KPIDashboard";
import Login from "./pages/Login";
import ProductionData from "./pages/ProductionData";
import Settings from "./pages/Settings";
import Wizard from "./pages/Wizard";

const ROUTE_ORDER: Record<string, number> = {
  "/": 0,
  "/kpi": 1,
  "/production-data": 2,
  "/settings": 3,
  "/wizard": 4,
};

function AppContent({ isDark }: { isDark: boolean }) {
  const location = useLocation();
  const prevPathRef = useRef(location.pathname);

  const transitionClass = useMemo(() => {
    const prevIndex = ROUTE_ORDER[prevPathRef.current] ?? 0;
    const nextIndex = ROUTE_ORDER[location.pathname] ?? 0;
    if (nextIndex === prevIndex) return "route-stay";
    return nextIndex > prevIndex ? "route-forward" : "route-backward";
  }, [location.pathname]);

  useEffect(() => {
    prevPathRef.current = location.pathname;
  }, [location.pathname]);

  return (
    <div
      className={`brand-app-bg relative min-h-screen overflow-hidden transition-colors duration-300 ${
        isDark ? "brand-app-bg--dark" : "brand-app-bg--light"
      }`}
    >
      <div
        className={`pointer-events-none absolute -left-16 -top-20 h-56 w-56 rounded-full blur-3xl ${
          isDark ? "bg-cyan-400/15" : "bg-cyan-300/35"
        }`}
      />
      <div
        className={`pointer-events-none absolute -bottom-20 -right-12 h-64 w-64 rounded-full blur-3xl ${
          isDark ? "bg-emerald-400/15" : "bg-emerald-300/30"
        }`}
      />
      <Sidebar />
      <main className={`route-shell ${transitionClass} relative p-3 md:ml-[260px] md:px-7 md:pb-7 md:pt-4 lg:px-8 lg:pb-8 lg:pt-5`}>
        <Routes location={location}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/kpi" element={<KPIDashboard />} />
          <Route path="/production-data" element={<ProductionData />} />
          <Route path="/wizard" element={<Wizard />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      <VoiceWidget />
    </div>
  );
}

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
        <AppContent isDark={isDark} />
      </BrowserRouter>
    </ErrorBoundary>
  );
}
