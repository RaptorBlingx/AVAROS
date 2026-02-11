import { useCallback, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import Toast from "../components/common/Toast";
import type { ToastItem } from "../components/common/Toast";
import IntentActivationSection from "../components/settings/IntentActivationSection";
import MetricMappingsSection from "../components/settings/MetricMappingsSection";
import PlatformConfigSection from "../components/settings/PlatformConfigSection";
import SystemInfoSection from "../components/settings/SystemInfoSection";

function Section({
  title,
  defaultOpen = true,
  children,
}: {
  title: string;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  return (
    <details
      open={defaultOpen}
      className="group rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition-colors open:border-sky-200"
    >
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-base font-semibold text-slate-900 marker:hidden">
        <span>{title}</span>
        <svg
          className="h-4 w-4 text-slate-500 transition-transform duration-200 group-open:rotate-180"
          viewBox="0 0 20 20"
          fill="none"
          aria-hidden="true"
        >
          <path
            d="M5 7.5L10 12.5L15 7.5"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </summary>
      <div className="mt-4 border-t border-slate-100 pt-4">{children}</div>
    </details>
  );
}

export default function Settings() {
  const navigate = useNavigate();
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const notify = useCallback((type: "success" | "error", message: string) => {
    setToasts((prev) => [
      ...prev,
      { id: Date.now() + Math.random(), type, message },
    ]);
  }, []);

  const dismissToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  const headerSubtitle = useMemo(
    () =>
      "Manage platform config, metric mappings, intents, and live system state.",
    [],
  );

  return (
    <section className="space-y-4">
      <Toast toasts={toasts} onDismiss={dismissToast} />

      <header className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-sky-700">
              AVAROS Control Panel
            </p>
            <h2 className="m-0 mt-2 text-2xl font-semibold text-slate-900">
              Settings
            </h2>
            <p className="m-0 mt-2 text-sm text-slate-600">{headerSubtitle}</p>
          </div>
          <button
            type="button"
            className="rounded-lg border border-sky-300 bg-sky-50 px-4 py-2 text-sm font-semibold text-sky-800 transition hover:bg-sky-100"
            onClick={() => navigate("/wizard?force=1")}
          >
            Run Wizard
          </button>
        </div>
      </header>

      <Section title="Platform Configuration">
        <PlatformConfigSection onNotify={notify} />
      </Section>

      <Section title="Metric Mappings">
        <MetricMappingsSection onNotify={notify} />
      </Section>

      <Section title="Intent Activation">
        <IntentActivationSection onNotify={notify} />
      </Section>

      <Section title="System Information" defaultOpen={true}>
        <SystemInfoSection onNotify={notify} />
      </Section>
    </section>
  );
}
