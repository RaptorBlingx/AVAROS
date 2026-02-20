import type { ReactNode } from "react";

import type { SystemStatusResponse } from "../api/types";

type StatusTone = "info" | "good" | "warning";

export type DashboardStatusCard = {
  label: string;
  value: string;
  icon: ReactNode;
  tone: StatusTone;
  helpText: string;
};

export type KpiSummaryItem = {
  title: string;
  description: string;
  icon: ReactNode;
};

export const DASHBOARD_ONBOARDING_STEPS = [
  {
    title: "Welcome to AVAROS",
    description:
      "This dashboard gives a quick operational and KPI readiness overview.",
    selector: '[data-onboarding-target="dashboard-header"]',
  },
  {
    title: "Your KPIs",
    description:
      "These KPI cards are placeholders until data sources are fully configured.",
    selector: '[data-onboarding-target="kpi-summary"]',
  },
  {
    title: "System Status",
    description:
      "Track adapter, intents, and database connectivity from one view.",
    selector: '[data-onboarding-target="system-status"]',
  },
  {
    title: "Voice Widget",
    description:
      "Use this button to open the assistant and start push-to-talk interaction.",
    selector: '[data-onboarding-target="voice-widget-trigger"]',
  },
  {
    title: "Voice + Chat Panel",
    description:
      "This panel combines voice controls and chat, ready immediately after onboarding.",
    selector: '[data-onboarding-target="voice-widget-panel"]',
  },
  {
    title: "Settings & Configuration",
    description:
      "Use Settings to configure platform, metrics, intents, and emission factors.",
    selector: '[data-onboarding-target="settings-nav-link"]',
  },
] as const;

export const KPI_SUMMARY_ITEMS: KpiSummaryItem[] = [
  {
    title: "Energy per Unit",
    description: "Track electricity intensity per produced unit.",
    icon: (
      <svg
        viewBox="0 0 24 24"
        className="h-5 w-5"
        fill="none"
        stroke="currentColor"
      >
        <path
          d="M13 2L6 13h5l-1 9 8-12h-5l0-8z"
          strokeWidth="2"
          strokeLinejoin="round"
        />
      </svg>
    ),
  },
  {
    title: "Material Efficiency",
    description: "Compare consumed material against quality output.",
    icon: (
      <svg
        viewBox="0 0 24 24"
        className="h-5 w-5"
        fill="none"
        stroke="currentColor"
      >
        <path
          d="M4 7h16M7 7v12m10-12v12M6 19h12"
          strokeWidth="2"
          strokeLinecap="round"
        />
      </svg>
    ),
  },
  {
    title: "CO2 Emissions",
    description: "Follow derived carbon performance over time.",
    icon: (
      <svg
        viewBox="0 0 24 24"
        className="h-5 w-5"
        fill="none"
        stroke="currentColor"
      >
        <path
          d="M4 15a4 4 0 014-4h7a4 4 0 110 8H8a4 4 0 01-4-4z"
          strokeWidth="2"
        />
        <path d="M9 11l2-3 2 3" strokeWidth="2" strokeLinecap="round" />
      </svg>
    ),
  },
];

export function buildDashboardStatusCards(
  status: SystemStatusResponse,
): DashboardStatusCard[] {
  const boolText = (value: boolean): string => (value ? "Yes" : "No");
  const iconClass = "h-4 w-4";

  return [
    {
      label: "Configured",
      value: boolText(status.configured),
      icon: (
        <svg
          className={iconClass}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
        >
          <path d="M5 12.5L10 17L19 8" strokeWidth="2" strokeLinecap="round" />
        </svg>
      ),
      tone: "info",
      helpText: "Indicates whether initial platform setup has been completed.",
    },
    {
      label: "Active Adapter",
      value: status.active_adapter,
      icon: (
        <svg
          className={iconClass}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
        >
          <rect x="4" y="4" width="16" height="16" rx="2" strokeWidth="2" />
          <path d="M8 9h8M8 15h5" strokeWidth="2" strokeLinecap="round" />
        </svg>
      ),
      tone: "info",
      helpText:
        "Shows the currently active platform connector AVAROS is using.",
    },
    {
      label: "Platform Type",
      value: status.platform_type,
      icon: (
        <svg
          className={iconClass}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
        >
          <path
            d="M12 3l8 4.5v9L12 21l-8-4.5v-9L12 3z"
            strokeWidth="2"
            strokeLinejoin="round"
          />
        </svg>
      ),
      tone: "info",
      helpText: "Configured platform profile type for API communication.",
    },
    {
      label: "Loaded Intents",
      value: String(status.loaded_intents),
      icon: (
        <svg
          className={iconClass}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
        >
          <path
            d="M5 6h14M5 12h14M5 18h9"
            strokeWidth="2"
            strokeLinecap="round"
          />
        </svg>
      ),
      tone: "info",
      helpText: "Number of intent modules loaded and available for activation.",
    },
    {
      label: "Database Connected",
      value: boolText(status.database_connected),
      icon: (
        <svg
          className={iconClass}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
        >
          <ellipse cx="12" cy="6" rx="7" ry="3" strokeWidth="2" />
          <path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6" strokeWidth="2" />
          <path d="M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" strokeWidth="2" />
        </svg>
      ),
      tone: "info",
      helpText:
        "Confirms whether AVAROS can persist/read configuration and runtime data.",
    },
    {
      label: "Version",
      value: status.version,
      icon: (
        <svg
          className={iconClass}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
        >
          <path
            d="M12 2l2.2 4.5 5 .7-3.6 3.5.8 5-4.4-2.3-4.4 2.3.8-5L4.8 7.2l5-.7L12 2z"
            strokeWidth="1.8"
            strokeLinejoin="round"
          />
        </svg>
      ),
      tone: "info",
      helpText: "Current backend version reported by the health endpoint.",
    },
  ];
}
