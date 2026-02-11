import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { NavLink } from "react-router-dom";

import { getHealth, toFriendlyErrorMessage } from "../api/client";
import initialLightLogo from "../assets/logo.svg";
import initialDarkLogo from "../assets/logodark.svg";
import { useTheme } from "./common/ThemeProvider";

export default function Sidebar() {
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const [version, setVersion] = useState<string>("--");
  const sidebarRef = useRef<HTMLElement | null>(null);
  const { isDark, theme, toggleTheme } = useTheme();

  useEffect(() => {
    let isMounted = true;
    void getHealth()
      .then((health) => {
        if (isMounted) {
          setVersion(health.version);
        }
      })
      .catch((error: unknown) => {
        if (isMounted) {
          const message = toFriendlyErrorMessage(error);
          if (!message.includes("Connection lost")) {
            console.error(message);
          }
          setVersion("--");
        }
      });
    return () => {
      isMounted = false;
    };
  }, []);

  const navItemClass = useCallback(
    (isActive: boolean): string =>
      isActive
        ? isDark
          ? "nav-bubble-enter rounded-xl bg-gradient-to-r from-sky-700/95 via-cyan-600/90 to-emerald-600/90 px-3 py-2 text-sm font-medium text-white no-underline shadow-lg shadow-sky-950/35"
          : "nav-bubble-enter rounded-xl bg-gradient-to-r from-cyan-100 via-sky-100 to-emerald-100 px-3 py-2 text-sm font-semibold text-sky-900 no-underline shadow-sm shadow-cyan-100/80"
        : isDark
          ? "rounded-xl px-3 py-2 text-sm text-slate-200 no-underline hover:bg-slate-800/70"
          : "rounded-xl px-3 py-2 text-sm text-slate-700 no-underline hover:bg-sky-100/70",
    [isDark],
  );

  const handleRefresh = useCallback(() => {
    if (isRefreshing) {
      return;
    }
    setIsRefreshing(true);
    window.setTimeout(() => {
      window.location.reload();
    }, 1200);
  }, [isRefreshing]);

  const mobileMenuLabel = useMemo(
    () => (isMobileOpen ? "Close navigation" : "Open navigation"),
    [isMobileOpen],
  );

  useEffect(() => {
    if (!isMobileOpen) {
      return;
    }

    const handlePointerDown = (event: MouseEvent | TouchEvent) => {
      const target = event.target as Node | null;
      if (!target || !sidebarRef.current) {
        return;
      }
      if (!sidebarRef.current.contains(target)) {
        setIsMobileOpen(false);
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsMobileOpen(false);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("touchstart", handlePointerDown, { passive: true });
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("touchstart", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isMobileOpen]);

  const actions = (
    <>
      <button
        type="button"
        onClick={toggleTheme}
        aria-label={`Switch to ${isDark ? "light" : "dark"} mode`}
        className={`group inline-flex w-full items-center justify-between rounded-lg px-3 py-2 text-sm font-semibold transition ${
          isDark
            ? "bg-slate-800/85 text-slate-100 hover:bg-slate-700/90"
            : "bg-white/85 text-slate-800 hover:bg-white"
        }`}
      >
        <span className="inline-flex items-center gap-2">
          <svg
            className={`h-4 w-4 transition-transform duration-300 ${
              isDark ? "rotate-0" : "rotate-180"
            }`}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
          >
            {isDark ? (
              <path
                d="M21 12.8A9 9 0 1111.2 3a7 7 0 109.8 9.8z"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            ) : (
              <>
                <circle cx="12" cy="12" r="4" strokeWidth="2" />
                <path
                  d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              </>
            )}
          </svg>
          {theme === "dark" ? "Dark mode" : "Light mode"}
        </span>
        <span
          className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-300 ${
            isDark
              ? "bg-sky-900/50"
              : "bg-slate-100"
          }`}
        >
          <span
            className={`h-4 w-4 rounded-full shadow transition-transform duration-300 ${
              isDark ? "translate-x-6 bg-sky-400" : "translate-x-1 bg-slate-900"
            }`}
          />
        </span>
      </button>

      <button
        type="button"
        className={`inline-flex !mb-6 w-full items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-70 ${
          theme === "dark"
            ? "bg-slate-800/85 text-slate-100 hover:bg-slate-700/90"
            : "bg-white/85 text-slate-700 hover:bg-white"
        }`}
        onClick={handleRefresh}
        disabled={isRefreshing}
      >
        <svg
          className={`h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
        >
          <path
            d="M20 12a8 8 0 10-2.3 5.7M20 12v-5m0 5h-5"
            strokeWidth="2"
            strokeLinecap="round"
          />
        </svg>
        {isRefreshing ? "Refreshing..." : "Refresh"}
      </button>

      <p
        className={`m-0 text-center text-xs md:text-left ${
          isDark ? "text-slate-400" : "text-slate-500"
        }`}
      >
        AVAROS v{version}
      </p>
    </>
  );

  return (
    <aside
      ref={sidebarRef}
      className={`relative z-20 w-full backdrop-blur-sm md:fixed md:inset-y-0 md:left-0 md:w-[260px] md:border-b-0 md:border-r ${
        isDark
          ? "border-b border-slate-800/80 bg-gradient-to-b from-slate-950/95 via-slate-900/95 to-slate-950/92 text-slate-100"
          : "border-b border-cyan-200/70 bg-gradient-to-b from-white/95 via-sky-50/75 to-emerald-50/40 text-slate-800"
      }`}
    >
      <div className="relative px-4 py-4 md:hidden">
        <NavLink
          to="/"
          end
          onClick={() => setIsMobileOpen(false)}
          className={`mx-auto flex h-fit w-60 flex-col items-center justify-center rounded-xl px-4 py-3 text-center no-underline transition ${
            isDark
              ? "border border-slate-700 bg-slate-900/65 hover:bg-slate-900"
              : "border border-cyan-200/70 bg-gradient-to-br from-white to-cyan-50/70 hover:from-cyan-50 hover:to-emerald-50/70"
          }`}
        >
          <img
            src={isDark ? initialDarkLogo : initialLightLogo}
            alt="AVAROS Logo"
            className="h-fit object-cover"
          />
          <p
            className={`mt-1 text-xs tracking-widest ${
              isDark ? "text-slate-400" : "text-slate-600"
            }`}
          >
            AI Voice Assistant
          </p>
        </NavLink>

        <button
          type="button"
          aria-label={mobileMenuLabel}
          aria-expanded={isMobileOpen}
          onClick={() => setIsMobileOpen((prev) => !prev)}
          className={`absolute right-4 top-1/2 inline-flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-lg ${
            isDark
              ? "border border-slate-700 bg-slate-900 text-slate-200"
              : "border border-slate-300 bg-white text-slate-700"
          }`}
        >
          <svg
            viewBox="0 0 24 24"
            className="h-5 w-5"
            fill="none"
            stroke="currentColor"
          >
            {isMobileOpen ? (
              <path
                d="M6 6l12 12M18 6L6 18"
                strokeWidth="2"
                strokeLinecap="round"
              />
            ) : (
              <path
                d="M4 7h16M4 12h16M4 17h16"
                strokeWidth="2"
                strokeLinecap="round"
              />
            )}
          </svg>
        </button>
      </div>

      <div
        className={`absolute left-0 right-0 top-full z-30 backdrop-blur-md transition-all duration-300 ease-out md:hidden ${
          isDark
            ? "border-b border-slate-800 bg-slate-950/95"
            : "border-b border-cyan-200/70 bg-white/95"
        } ${
          isMobileOpen
            ? "pointer-events-auto translate-y-0 opacity-100"
            : "pointer-events-none -translate-y-2 opacity-0"
        }`}
      >
        <div className="px-4 pb-4">
          <nav className="flex flex-col gap-2">
            <NavLink
              to="/"
              className={({ isActive }) => navItemClass(isActive)}
              end
              onClick={() => setIsMobileOpen(false)}
            >
              <span className="inline-flex items-center gap-2">
                <svg
                  className="h-4 w-4"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                >
                  <path
                    d="M3 12l9-8 9 8M5 10v10h14V10"
                    strokeWidth="2"
                    strokeLinecap="round"
                  />
                </svg>
                Dashboard
              </span>
            </NavLink>

            <NavLink
              to="/kpi"
              className={({ isActive }) => navItemClass(isActive)}
              onClick={() => setIsMobileOpen(false)}
            >
              <span className="inline-flex items-center gap-2">
                <svg
                  className="h-4 w-4"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                >
                  <path
                    d="M4 18V8m6 10V6m6 12v-8m4 8H2"
                    strokeWidth="2"
                    strokeLinecap="round"
                  />
                </svg>
                KPI Dashboard
              </span>
            </NavLink>

            <NavLink
              to="/settings"
              className={({ isActive }) => navItemClass(isActive)}
              onClick={() => setIsMobileOpen(false)}
            >
              <span className="inline-flex items-center gap-2">
                <svg
                  className="h-4 w-4"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                >
                  <path
                    d="M12 8a4 4 0 100 8 4 4 0 000-8zm8 4l-2 1 1 2-2 2-2-1-1 2h-4l-1-2-2 1-2-2 1-2-2-1v-4l2-1-1-2 2-2 2 1 1-2h4l1 2 2-1 2 2-1 2 2 1v4z"
                    strokeWidth="1.5"
                    strokeLinejoin="round"
                  />
                </svg>
                Settings
              </span>
            </NavLink>
          </nav>

          <div className="mt-4 flex flex-col gap-4">{actions}</div>
        </div>
      </div>

      <div className="hidden px-4 py-6 md:block">
        <NavLink
          to="/"
          end
          className={`flex flex-col items-center justify-center rounded-xl px-4 py-3 no-underline transition md:mb-6 ${
            isDark
              ? "bg-slate-900/60 hover:bg-slate-900"
              : "bg-white/70 hover:bg-white/90"
          }`}
        >
          <img
            src={isDark ? initialDarkLogo : initialLightLogo}
            alt="AVAROS Logo"
            className="h-fit w-50 object-cover"
          />
          <p
            className={`mt-1 text-xs tracking-widest ${
              isDark ? "text-slate-400" : "text-slate-600"
            }`}
          >
            AI Voice Assistant
          </p>
        </NavLink>
      </div>

      <div className="hidden md:flex md:h-[calc(100%-96px)] md:flex-col md:px-4 md:pb-6">
        <nav className="flex flex-col gap-2">
          <NavLink
            to="/"
            className={({ isActive }) => navItemClass(isActive)}
            end
          >
            <span className="inline-flex items-center gap-2">
              <svg
                className="h-4 w-4"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
              >
                <path
                  d="M3 12l9-8 9 8M5 10v10h14V10"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              </svg>
              Dashboard
            </span>
          </NavLink>

          <NavLink
            to="/kpi"
            className={({ isActive }) => navItemClass(isActive)}
          >
            <span className="inline-flex items-center gap-2">
              <svg
                className="h-4 w-4"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
              >
                <path
                  d="M4 18V8m6 10V6m6 12v-8m4 8H2"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              </svg>
              KPI Dashboard
            </span>
          </NavLink>

          <NavLink
            to="/settings"
            className={({ isActive }) => navItemClass(isActive)}
          >
            <span className="inline-flex items-center gap-2">
              <svg
                className="h-4 w-4"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
              >
                <path
                  d="M12 8a4 4 0 100 8 4 4 0 000-8zm8 4l-2 1 1 2-2 2-2-1-1 2h-4l-1-2-2 1-2-2 1-2-2-1v-4l2-1-1-2 2-2 2 1 1-2h4l1 2 2-1 2 2-1 2 2 1v4z"
                  strokeWidth="1.5"
                  strokeLinejoin="round"
                />
              </svg>
              Settings
            </span>
          </NavLink>
        </nav>

        <div className="mt-4 flex flex-col gap-4 md:mt-auto md:space-y-3">
          {actions}
        </div>
      </div>
    </aside>
  );
}
