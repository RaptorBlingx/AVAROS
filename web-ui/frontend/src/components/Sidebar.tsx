import { NavLink } from "react-router-dom";

export default function Sidebar() {
  const navItemClass = (isActive: boolean): string =>
    isActive
      ? "rounded-lg bg-sky-600 px-3 py-2 text-sm font-medium text-white no-underline shadow shadow-sky-900/30"
      : "rounded-lg px-3 py-2 text-sm text-slate-200 no-underline hover:bg-slate-800";

  return (
    <aside className="flex lg:min-h-screen flex-col border-r border-slate-800 bg-slate-950 px-4 py-6 text-slate-100">
      <div>
        <div className="mb-6 rounded-xl border border-slate-800 bg-slate-900/60 p-4">
          <h1 className="m-0 text-lg font-semibold tracking-wide">AVAROS</h1>
          <p className="mt-1 text-xs uppercase tracking-wider text-slate-400">
            Control Panel
          </p>
        </div>
        <nav className="flex flex-row flex-wrap gap-2 md:flex-col">
          <NavLink
            to="/"
            className={({ isActive }) => navItemClass(isActive)}
            end
          >
            <span className="inline-flex pt-[3px] items-center gap-2">
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
            to="/settings"
            className={({ isActive }) => navItemClass(isActive)}
          >
            <span className="inline-flex mt-[1px] justify-center items-center gap-2">
              <svg
                className="h-4 w-4 mt-[2px]"
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
      </div>
      <button
        type="button"
        className="lg:mt-auto inline-flex lg:mt-0 mt-4 items-center h-fit justify-center gap-2 rounded-lg border border-sky-300 bg-sky-50 px-4 py-2 text-sm font-semibold text-sky-800 transition hover:bg-sky-100"
        onClick={() => window.location.reload()}
      >
        <svg
          className="h-4 w-4"
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
        Refresh
      </button>
    </aside>
  );
}
