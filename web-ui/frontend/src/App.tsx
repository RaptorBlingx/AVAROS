import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import Sidebar from "./components/Sidebar";
import Dashboard from "./pages/Dashboard";
import Settings from "./pages/Settings";
import Wizard from "./pages/Wizard";

export default function App() {
  return (
    <BrowserRouter>
      <div className="relative min-h-screen overflow-hidden bg-gradient-to-br from-slate-100 via-sky-50 to-slate-200">
        <div className="pointer-events-none absolute -left-16 -top-20 h-56 w-56 rounded-full bg-sky-200/40 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-20 -right-12 h-64 w-64 rounded-full bg-emerald-200/40 blur-3xl" />
        <Sidebar />
        <main className="relative p-4 md:ml-[260px] md:p-8">
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
