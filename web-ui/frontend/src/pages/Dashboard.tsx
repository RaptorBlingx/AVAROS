import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import {
  ApiError,
  DEFAULT_SITE_ID,
  getHealth,
  getSiteProgress,
  getStatus,
  toFriendlyErrorMessage,
} from "../api/client";
import type {
  HealthResponse,
  SiteProgressResponse,
  SystemStatusResponse,
} from "../api/types";
import EmptyState from "../components/common/EmptyState";
import ErrorMessage from "../components/common/ErrorMessage";
import KPISummaryCard from "../components/common/KPISummaryCard";
import LoadingSpinner from "../components/common/LoadingSpinner";
import OnboardingOverlay from "../components/common/OnboardingOverlay";
import {
  dispatchOnboardingVoiceFocus,
  ONBOARDING_RERUN_EVENT,
  ONBOARDING_STORAGE_KEY,
  shouldOpenOnboardingForScope,
  type OnboardingRerunDetail,
} from "../components/common/onboarding";
import StatusCard from "../components/StatusCard";
import { useTheme } from "../components/common/ThemeProvider";
import {
  buildDashboardKpiCards,
  buildDashboardStatusCards,
  DASHBOARD_ONBOARDING_STEPS,
} from "./dashboard.helpers";

export default function Dashboard() {
  const navigate = useNavigate();
  const { isDark } = useTheme();
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [status, setStatus] = useState<SystemStatusResponse | null>(null);
  const [siteProgress, setSiteProgress] = useState<SiteProgressResponse | null>(
    null,
  );
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [onboardingOpen, setOnboardingOpen] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [healthData, statusData] = await Promise.all([
        getHealth(),
        getStatus(),
      ]);
      const shouldLoadLiveKpis =
        statusData.configured && statusData.live_connection_verified === true;
      let progressData: SiteProgressResponse | null = null;
      if (shouldLoadLiveKpis) {
        try {
          progressData = await getSiteProgress(DEFAULT_SITE_ID);
        } catch (err) {
          if (!(err instanceof ApiError && err.status === 404)) {
            throw err;
          }
        }
      }
      const shouldRedirectToWizard =
        !import.meta.env.DEV &&
        !statusData.configured &&
        statusData.platform_type === "unconfigured";
      if (shouldRedirectToWizard) {
        const skipRedirectUntilRaw = sessionStorage.getItem(
          "avaros_skip_wizard_until",
        );
        const skipRedirectUntil = skipRedirectUntilRaw
          ? Number(skipRedirectUntilRaw)
          : 0;
        if (skipRedirectUntil > Date.now()) {
          setHealth(healthData);
          setStatus(statusData);
          return;
        }
        sessionStorage.removeItem("avaros_skip_wizard_until");
        navigate("/wizard", { replace: true });
        return;
      }
      setHealth(healthData);
      setStatus(statusData);
      setSiteProgress(progressData);
    } catch (err) {
      setError(toFriendlyErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [navigate]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  useEffect(() => {
    const isComplete = localStorage.getItem(ONBOARDING_STORAGE_KEY) === "1";
    if (!isComplete) {
      setOnboardingOpen(true);
    }
  }, []);

  useEffect(() => {
    const onRerun = (event: Event) => {
      const detail = (event as CustomEvent<OnboardingRerunDetail>).detail;
      if (detail && shouldOpenOnboardingForScope(detail.scope, "dashboard")) {
        setOnboardingOpen(true);
      }
    };
    window.addEventListener(ONBOARDING_RERUN_EVENT, onRerun);
    return () => window.removeEventListener(ONBOARDING_RERUN_EVENT, onRerun);
  }, []);

  const healthy = useMemo(() => health?.status === "ok", [health]);
  const isLiveConnectionVerified = status?.live_connection_verified === true;
  const isLiveConnectionBlocked =
    status?.configured === true && !isLiveConnectionVerified;
  const systemHealthy =
    healthy && (!status?.configured || isLiveConnectionVerified);
  const cards = useMemo(
    () => (status ? buildDashboardStatusCards(status) : []),
    [status],
  );
  const kpiCards = useMemo(
    () => buildDashboardKpiCards(siteProgress?.progress ?? []),
    [siteProgress?.progress],
  );
  const showKpiEmptyState =
    !loading &&
    !error &&
    !isLiveConnectionBlocked &&
    (siteProgress?.progress.length ?? 0) === 0;

  return (
    <section className="space-y-5">
      <header
        className="brand-hero relative overflow-hidden rounded-2xl p-6"
        data-onboarding-target="dashboard-header"
      >
        <div className="pointer-events-none absolute -right-10 -top-14 h-36 w-36 rounded-full bg-cyan-300/35 blur-2xl dark:bg-cyan-400/15" />
        <div className="pointer-events-none absolute -bottom-16 right-16 h-28 w-28 rounded-full bg-emerald-300/30 blur-2xl dark:bg-emerald-400/15" />
        <div className="flex flex-wrap items-center justify-center gap-3 lg:justify-between">
          <div>
            <p className="m-0 brand-title-gradient text-xs font-bold uppercase tracking-[0.14em]">
              AVAROS Control Center
            </p>
            <h2 className="m-0 mt-1 text-2xl font-semibold text-slate-900">
              Dashboard
            </h2>
            <p
              className={`mb-0 mt-1 text-sm opacity-80 ${
                isDark ? "text-white" : "text-slate-600"
              }`}
            >
              Live operational summary for configuration and platform readiness.
            </p>
          </div>
          <div className="flex flex-col items-end gap-1">
            {!loading && systemHealthy && (
              <div
                className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 ${
                  isDark
                    ? "border-slate-700 bg-slate-900/85"
                    : "border-slate-200 bg-white/90"
                }`}
              >
                <span className="relative inline-flex h-2.5 w-2.5">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-70" />
                  <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.45)]" />
                </span>
                <p
                  className={`m-0 text-sm font-semibold ${
                    isDark ? "text-slate-100" : "text-slate-700"
                  }`}
                >
                  System Healthy
                </p>
              </div>
            )}
            {!loading && isLiveConnectionBlocked && (
              <span
                className={`rounded-lg border px-3 py-2 text-center text-sm font-semibold ${
                  isDark
                    ? "border-amber-700 bg-amber-950/40 text-amber-200"
                    : "border-amber-200 bg-amber-50/80 text-amber-700"
                }`}
              >
                Live platform connection is not verified.
              </span>
            )}
            {!loading && status && !status.configured && (
              <span
                className={`rounded-lg border px-3 py-2 text-center text-sm font-semibold ${
                  isDark
                    ? "border-rose-800 bg-rose-950/40 text-rose-200"
                    : "border-rose-200 bg-rose-50/80 text-rose-700"
                }`}
              >
                Setup Required: platform configuration is not complete.
              </span>
            )}
          </div>
        </div>
      </header>

      <section
        className="brand-panel rounded-2xl p-5"
        data-onboarding-target="kpi-summary"
      >
        <div className="mb-4">
          <p className="m-0 text-xs font-semibold uppercase tracking-[0.12em] text-sky-700 dark:text-sky-300">
            KPI Summary
          </p>
          <h3 className="m-0 mt-1 text-lg font-semibold text-slate-900 dark:text-slate-100">
            Quick Access WASABI KPIs
          </h3>
        </div>
        {isLiveConnectionBlocked ? (
          <div className="brand-surface rounded-xl px-5 py-6 text-center">
            <p className="m-0 text-sm font-semibold text-slate-900 dark:text-slate-100">
              Live KPI cards are hidden until platform connection is verified.
            </p>
            <p className="m-0 mt-2 text-sm text-slate-600 dark:text-slate-300">
              {status?.live_connection_message ||
                "Test and save a valid platform connection in Settings."}
            </p>
            <div className="mt-3 flex justify-center gap-3">
              <Link
                to="/settings"
                className="inline-flex text-sm font-semibold text-sky-700 underline underline-offset-2 hover:text-sky-600 dark:text-sky-300 dark:hover:text-sky-200"
              >
                Open Settings
              </Link>
              <button
                type="button"
                onClick={() => void loadData()}
                className="btn-brand-subtle rounded-lg px-3 py-1.5 text-xs font-semibold"
              >
                Retry Check
              </button>
            </div>
          </div>
        ) : showKpiEmptyState ? (
          <div className="brand-surface rounded-xl px-5 py-6 text-center">
            <p className="m-0 text-sm font-semibold text-slate-900 dark:text-slate-100">
              No KPI data available — configure a platform and record a baseline.
            </p>
            <Link
              to="/settings"
              className="mt-3 inline-flex text-sm font-semibold text-sky-700 underline underline-offset-2 hover:text-sky-600 dark:text-sky-300 dark:hover:text-sky-200"
            >
              Configure in Settings
            </Link>
          </div>
        ) : (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {kpiCards.map((item) => (
              <KPISummaryCard
                key={item.title}
                title={item.title}
                description={item.description}
                icon={item.icon}
                currentValue={item.currentValue}
                baselineValue={item.baselineValue}
                improvementLabel={item.improvementLabel}
                targetLabel={item.targetLabel}
                targetMet={item.targetMet}
                directionLabel={item.directionLabel}
              />
            ))}
          </div>
        )}
      </section>

      <div
        className="brand-panel rounded-2xl p-5"
        data-onboarding-target="system-status"
      >
        {loading && (
          <div className="brand-surface-muted mb-4 rounded-lg px-4 py-3 opacity-50">
            <LoadingSpinner label="Loading system status..." size="sm" />
          </div>
        )}
        {error && (
          <div className="mb-4">
            <ErrorMessage
              title="Unable to load dashboard"
              message={error}
              onRetry={() => void loadData()}
            />
          </div>
        )}
        {cards.length > 0 && (
          <div
            className={`grid gap-3 sm:grid-cols-2 xl:grid-cols-3 ${
              !loading ? "dash-cards" : ""
            }`}
          >
            {cards.map((card) => (
              <StatusCard
                key={card.label}
                label={card.label}
                value={card.value}
                icon={card.icon}
                tone={card.tone}
                helpText={card.helpText}
              />
            ))}
          </div>
        )}
        {!loading && !error && cards.length === 0 && (
          <EmptyState
            title="No status data yet"
            message="Dashboard data is empty. Try refreshing after AVAROS services are ready."
            actionLabel="Refresh"
            onAction={() => void loadData()}
          />
        )}
      </div>

      <OnboardingOverlay
        open={onboardingOpen}
        steps={DASHBOARD_ONBOARDING_STEPS}
        onStepChange={(index) => {
          const selector = DASHBOARD_ONBOARDING_STEPS[index]?.selector ?? "";
          const shouldExpandVoiceWidget =
            selector.includes("voice-widget-trigger") ||
            selector.includes("voice-widget-panel");
          dispatchOnboardingVoiceFocus(shouldExpandVoiceWidget);
        }}
        onClose={() => {
          dispatchOnboardingVoiceFocus(false);
          localStorage.setItem(ONBOARDING_STORAGE_KEY, "1");
          setOnboardingOpen(false);
        }}
      />
    </section>
  );
}
