import { useCallback, useEffect, useMemo, useState } from "react";
import { NavLink } from "react-router-dom";

import { getHealth, toFriendlyErrorMessage } from "../api/client";

export default function Sidebar() {
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const [version, setVersion] = useState<string>("--");

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
        ? "rounded-lg bg-sky-600 px-3 py-2 text-sm font-medium text-white no-underline shadow shadow-sky-900/30"
        : "rounded-lg px-3 py-2 text-sm text-slate-200 no-underline hover:bg-slate-800",
    [],
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

  return (
    <aside className="relative z-20 w-full border-b border-slate-800 bg-slate-950 text-slate-100 md:fixed md:inset-y-0 md:left-0 md:w-[260px] md:border-b-0 md:border-r">
      <div className="flex items-center justify-between px-4 py-4 md:block md:px-4 md:py-6">
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-3 md:mb-6">
          <h1 className="m-0 text-lg font-semibold tracking-wide">AVAROS</h1>
          <p className="mt-1 text-xs uppercase tracking-wider text-slate-400">
            Control Panel
          </p>
        </div>

        <button
          type="button"
          aria-label={mobileMenuLabel}
          aria-expanded={isMobileOpen}
          onClick={() => setIsMobileOpen((prev) => !prev)}
          className="ml-3 inline-flex h-10 w-10 items-center justify-center rounded-lg border border-slate-700 bg-slate-900 text-slate-200 md:hidden"
        >
          <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor">
            {isMobileOpen ? (
              <path d="M6 6l12 12M18 6L6 18" strokeWidth="2" strokeLinecap="round" />
            ) : (
              <path d="M4 7h16M4 12h16M4 17h16" strokeWidth="2" strokeLinecap="round" />
            )}
          </svg>
        </button>
      </div>

      <div className={`${isMobileOpen ? "block" : "hidden"} px-4 pb-4 md:flex md:h-[calc(100%-96px)] md:flex-col md:px-4 md:pb-6`}>
        <nav className="flex flex-col gap-2">
          <NavLink
            to="/"
            className={({ isActive }) => navItemClass(isActive)}
            end
            onClick={() => setIsMobileOpen(false)}
          >
            <span className="inline-flex items-center gap-2">
              <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M3 12l9-8 9 8M5 10v10h14V10" strokeWidth="2" strokeLinecap="round" />
              </svg>
              Dashboard
            </span>
          </NavLink>

          <NavLink
            to="/settings"
            className={({ isActive }) => navItemClass(isActive)}
            onClick={() => setIsMobileOpen(false)}
          >
            <span className="inline-flex items-center gap-2">
              <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor">
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

        <div className="mt-4 md:mt-auto md:space-y-3">
          <button
            type="button"
            className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-sky-300 bg-sky-50 px-4 py-2 text-sm font-semibold text-sky-800 transition hover:bg-sky-100 disabled:cursor-not-allowed disabled:opacity-70"
            onClick={handleRefresh}
            disabled={isRefreshing}
          >
            <svg
              className={`h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`}
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
            >
              <path d="M20 12a8 8 0 10-2.3 5.7M20 12v-5m0 5h-5" strokeWidth="2" strokeLinecap="round" />
            </svg>
            {isRefreshing ? "Refreshing..." : "Refresh"}
          </button>

          <p className="m-0 text-center text-xs text-slate-400 md:text-left">
            AVAROS v{version}
          </p>
        </div>
      </div>
    </aside>
  );
}
