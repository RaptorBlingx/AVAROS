import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import OnboardingOverlay from "../components/common/OnboardingOverlay";
import Toast from "../components/common/Toast";
import type { ToastItem } from "../components/common/Toast";
import Tooltip from "../components/common/Tooltip";
import IntentActivationSection from "../components/settings/IntentActivationSection";
import IntentBindingsSection from "../components/settings/IntentBindingsSection";
import EmissionFactorsSection from "../components/settings/EmissionFactorsSection";
import MetricMappingsSection from "../components/settings/MetricMappingsSection";
import PlatformConfigSection from "../components/settings/PlatformConfigSection";
import SystemInfoSection from "../components/settings/SystemInfoSection";

function Section({
  title,
  helpText,
  targetId,
  defaultOpen = false,
  children,
}: {
  title: string;
  helpText: string;
  targetId: string;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  return (
    <details
      open={defaultOpen}
      data-onboarding-target={targetId}
      className="brand-panel group overflow-visible rounded-2xl p-0 transition-colors open:border-cyan-300/70 dark:open:border-cyan-500/40"
    >
      <summary className="flex w-full cursor-pointer list-none items-center justify-between gap-3 px-5 py-4 text-base font-semibold text-slate-900 marker:hidden hover:bg-white/30 dark:hover:bg-slate-900/30">
        <span className="inline-flex items-center gap-2">
          {title}
          <Tooltip content={helpText} ariaLabel={`Help for ${title}`} />
        </span>
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
  const [onboardingOpen, setOnboardingOpen] = useState(false);
  const [profileRefreshKey, setProfileRefreshKey] = useState(0);
  const [activeProfileName, setActiveProfileName] = useState("mock");
  const activeProfileRef = useRef("mock");
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
      "Manage platform config, metric mappings, intent bindings, intents, and live system state.",
    [],
  );

  const onboardingSteps = useMemo(
    () => [
      {
        title: "Settings Overview",
        description: "This page controls platform connection, mappings, intents, and runtime status.",
        selector: '[data-onboarding-target="settings-header"]',
      },
      {
        title: "Platform Configuration",
        description: "Connect AVAROS to your platform and test credentials safely.",
        selector: '[data-onboarding-target="settings-platform-config"]',
      },
      {
        title: "Metric Mappings",
        description: "Map canonical AVAROS metrics to your API fields.",
        selector: '[data-onboarding-target="settings-metric-mappings"]',
      },
      {
        title: "Intent Bindings",
        description: "Map non-metric intents (control/status/help) to your API endpoints.",
        selector: '[data-onboarding-target="settings-intent-bindings"]',
      },
      {
        title: "Intent Activation",
        description: "Enable operational intents once required metrics are available.",
        selector: '[data-onboarding-target="settings-intent-activation"]',
      },
      {
        title: "System Information",
        description: "Monitor live backend status and runtime details from this section.",
        selector: '[data-onboarding-target="settings-system-information"]',
      },
    ] as const,
    [],
  );

  useEffect(() => {
    const onRerun = () => setOnboardingOpen(true);
    window.addEventListener("avaros:rerun-onboarding", onRerun);
    return () => window.removeEventListener("avaros:rerun-onboarding", onRerun);
  }, []);

  const syncActiveProfile = useCallback((profileName: string) => {
    if (activeProfileRef.current === profileName) {
      return;
    }
    activeProfileRef.current = profileName;
    setActiveProfileName(profileName);
    setProfileRefreshKey((value) => value + 1);
  }, []);

  const handleProfileSwitch = useCallback(
    (profileName: string, voiceReloaded: boolean) => {
      syncActiveProfile(profileName);
      if (!voiceReloaded) {
        notify(
          "error",
          "Voice runtime was not notified — voice queries may use the previous profile until next restart.",
        );
      }
    },
    [notify, syncActiveProfile],
  );

  const handleActiveProfileResolved = useCallback(
    (profileName: string) => {
      syncActiveProfile(profileName);
    },
    [syncActiveProfile],
  );

  return (
    <section className="space-y-4">
      <Toast toasts={toasts} onDismiss={dismissToast} />

      <header className="brand-hero rounded-2xl p-6" data-onboarding-target="settings-header">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="m-0 brand-title-gradient text-xs font-semibold uppercase tracking-[0.14em]">
              AVAROS Control Panel
            </p>
            <h2 className="m-0 mt-2 text-2xl font-semibold text-slate-900">
              Settings
            </h2>
            <p className="m-0 mt-2 text-sm text-slate-600">
              {headerSubtitle}
              <span className="ml-2 inline-flex items-center rounded-full bg-cyan-100 px-2.5 py-0.5 text-xs font-medium text-cyan-700 dark:bg-cyan-900/40 dark:text-cyan-300">
                Profile: {activeProfileName}
              </span>
            </p>
          </div>
          <div className="flex w-full flex-col gap-2 sm:w-auto">
            <button
              type="button"
              className="btn-brand-primary rounded-lg px-4 py-2 text-sm font-semibold"
              onClick={() => navigate("/wizard?force=1")}
            >
              Run Wizard
            </button>
            <button
              type="button"
              className="btn-brand-subtle rounded-lg px-4 py-2 text-sm font-semibold"
              onClick={() => setOnboardingOpen(true)}
            >
              Re-run Onboarding Tour
            </button>
          </div>
        </div>
      </header>

      <Section
        title="Platform Configuration"
        helpText="Connect AVAROS to your energy monitoring platform and validate connectivity."
        targetId="settings-platform-config"
        defaultOpen={true}
      >
        <PlatformConfigSection
          onNotify={notify}
          onProfileSwitch={handleProfileSwitch}
          onActiveProfileResolved={handleActiveProfileResolved}
        />
      </Section>

      <Section
        title="Metric Mappings"
        helpText="Map canonical AVAROS metrics to your platform endpoint fields."
        targetId="settings-metric-mappings"
      >
        <MetricMappingsSection
          onNotify={notify}
          refreshKey={profileRefreshKey}
          activeProfile={activeProfileName}
        />
      </Section>

      <Section
        title="Intent Bindings"
        helpText="Map non-metric intents like control, status, and help to your platform APIs."
        targetId="settings-intent-bindings"
      >
        <IntentBindingsSection
          onNotify={notify}
          refreshKey={profileRefreshKey}
          activeProfile={activeProfileName}
        />
      </Section>

      <Section
        title="Emission Factors"
        helpText="Configure CO2 conversion factors per energy source or apply country presets."
        targetId="settings-emission-factors"
      >
        <EmissionFactorsSection
          onNotify={notify}
          refreshKey={profileRefreshKey}
          activeProfile={activeProfileName}
        />
      </Section>

      <Section
        title="Intent Activation"
        helpText="Enable business intents and verify required metrics are available."
        targetId="settings-intent-activation"
      >
        <IntentActivationSection
          onNotify={notify}
          refreshKey={profileRefreshKey}
          activeProfile={activeProfileName}
        />
      </Section>

      <Section
        title="System Information"
        helpText="View live runtime state, adapter details, and backend health information."
        targetId="settings-system-information"
      >
        <SystemInfoSection onNotify={notify} />
      </Section>

      <OnboardingOverlay
        open={onboardingOpen}
        steps={onboardingSteps}
        onClose={() => {
          localStorage.setItem("avaros_onboarding_complete", "1");
          setOnboardingOpen(false);
        }}
      />
    </section>
  );
}
