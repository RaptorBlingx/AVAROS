import { useCallback, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import Toast from "../components/common/Toast";
import type { ToastItem } from "../components/common/Toast";
import IntentActivationSection from "../components/settings/IntentActivationSection";
import EmissionFactorsSection from "../components/settings/EmissionFactorsSection";
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
      className="brand-panel group overflow-hidden rounded-2xl p-0 transition-colors open:border-cyan-300/70 dark:open:border-cyan-500/40"
    >
      <summary className="flex w-full cursor-pointer list-none items-center justify-between gap-3 px-5 py-4 text-base font-semibold text-slate-900 marker:hidden hover:bg-white/30 dark:hover:bg-slate-900/30">
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
      <div className="border-t border-slate-100 px-5 pb-5 pt-4 dark:border-slate-700">{children}</div>
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

      <header className="brand-hero rounded-2xl p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="m-0 brand-title-gradient text-xs font-semibold uppercase tracking-[0.14em]">
              AVAROS Control Panel
            </p>
            <h2 className="m-0 mt-2 text-2xl font-semibold text-slate-900">
              Settings
            </h2>
            <p className="m-0 mt-2 text-sm text-slate-600">{headerSubtitle}</p>
          </div>
          <button
            type="button"
            className="btn-brand-primary rounded-lg px-4 py-2 text-sm font-semibold"
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

      <Section title="Emission Factors">
        <EmissionFactorsSection onNotify={notify} />
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
