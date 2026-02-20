import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  ApiError,
  DEFAULT_SITE_ID,
  getBaselines,
  getSiteProgress,
  getSnapshots,
  toFriendlyErrorMessage,
} from "../api/client";
import type {
  BaselineResponse,
  KPIProgressItem,
  KPIMetricName,
  SiteProgressResponse,
  SnapshotResponse,
} from "../api/types";
import EmptyState from "../components/common/EmptyState";
import ErrorMessage from "../components/common/ErrorMessage";
import LoadingSpinner from "../components/common/LoadingSpinner";
import OnboardingOverlay from "../components/common/OnboardingOverlay";
import {
  ONBOARDING_RERUN_EVENT,
  shouldOpenOnboardingForScope,
  type OnboardingRerunDetail,
} from "../components/common/onboarding";
import KPITrendChart from "../components/kpi/KPITrendChart";
import KPITargetCard from "../components/kpi/KPITargetCard";
import {
  KPI_METRICS,
  PERIOD_OPTIONS,
  buildPeriodAwareProgressMap,
  formatDateTime,
  getLatestCurrentDate,
  getTargetLineValue,
  toIsoDateRange,
  type PeriodOption,
} from "./kpi/helpers";

export default function KPIDashboard() {
  const navigate = useNavigate();

  const [period, setPeriod] = useState<PeriodOption>("30d");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showEmpty, setShowEmpty] = useState(false);
  const [onboardingOpen, setOnboardingOpen] = useState(false);

  const [siteProgress, setSiteProgress] = useState<SiteProgressResponse | null>(
    null,
  );
  const [baselines, setBaselines] = useState<BaselineResponse[]>([]);
  const [snapshotsByMetric, setSnapshotsByMetric] = useState<
    Partial<Record<KPIMetricName, SnapshotResponse[]>>
  >({});

  const loadKPIData = useCallback(async () => {
    setLoading(true);
    setError("");
    setShowEmpty(false);

    try {
      const [progressResult, baselineResult] = await Promise.allSettled([
        getSiteProgress(DEFAULT_SITE_ID),
        getBaselines(DEFAULT_SITE_ID),
      ]);

      if (
        progressResult.status === "rejected" &&
        progressResult.reason instanceof ApiError &&
        progressResult.reason.status === 404
      ) {
        setShowEmpty(true);
        setSiteProgress(null);
        setBaselines([]);
        setSnapshotsByMetric({});
        return;
      }

      if (progressResult.status === "rejected") {
        throw progressResult.reason;
      }

      const progressData = progressResult.value;
      const baselineData =
        baselineResult.status === "fulfilled" ? baselineResult.value : [];

      setSiteProgress(progressData);
      setBaselines(baselineData);

      if (progressData.baselines_count === 0) {
        setShowEmpty(true);
        setSnapshotsByMetric({});
        return;
      }

      const { start, end } = toIsoDateRange(period);
      const snapshotResults = await Promise.allSettled(
        progressData.progress.map((item) =>
          getSnapshots(DEFAULT_SITE_ID, item.metric, start, end),
        ),
      );

      const nextSnapshots: Partial<Record<KPIMetricName, SnapshotResponse[]>> =
        {};
      snapshotResults.forEach((result, index) => {
        const metric = progressData.progress[index]?.metric;
        if (!metric) {
          return;
        }
        if (result.status === "fulfilled") {
          nextSnapshots[metric] = result.value;
        }
      });
      setSnapshotsByMetric(nextSnapshots);
    } catch (err) {
      setError(toFriendlyErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [period]);

  useEffect(() => {
    void loadKPIData();
  }, [loadKPIData]);

  useEffect(() => {
    const onRerun = (event: Event) => {
      const detail = (event as CustomEvent<OnboardingRerunDetail>).detail;
      if (detail && shouldOpenOnboardingForScope(detail.scope, "kpi")) {
        setOnboardingOpen(true);
      }
    };
    window.addEventListener(ONBOARDING_RERUN_EVENT, onRerun);
    return () => window.removeEventListener(ONBOARDING_RERUN_EVENT, onRerun);
  }, []);

  const progressMap = useMemo(() => {
    const map = new Map<string, KPIProgressItem>();
    for (const item of siteProgress?.progress ?? []) {
      map.set(item.metric, item);
    }
    return map;
  }, [siteProgress?.progress]);

  const latestUpdatedAt = useMemo(
    () => getLatestCurrentDate(siteProgress?.progress ?? []),
    [siteProgress?.progress],
  );

  const periodAwareProgressMap = useMemo(
    () => buildPeriodAwareProgressMap(progressMap, snapshotsByMetric),
    [progressMap, snapshotsByMetric],
  );

  return (
    <section className="space-y-5">
      <header
        className="brand-hero relative overflow-hidden rounded-2xl p-6"
        data-onboarding-target="kpi-header"
      >
        <div className="pointer-events-none absolute -right-12 -top-14 h-36 w-36 rounded-full bg-cyan-300/35 blur-3xl dark:bg-cyan-400/15" />
        <div className="pointer-events-none absolute -bottom-16 left-10 h-28 w-28 rounded-full bg-emerald-300/30 blur-2xl dark:bg-emerald-400/15" />
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <p className="m-0 brand-title-gradient text-xs font-bold uppercase tracking-[0.14em]">
              WASABI KPI Tracking
            </p>
            <h2 className="m-0 mt-1 text-2xl font-semibold text-slate-900 dark:text-slate-100">
              KPI Dashboard
            </h2>
            <p className="m-0 mt-2 text-sm text-slate-600 dark:text-slate-400">
              Monitor pilot performance for energy, material efficiency, and
              CO2-eq targets.
            </p>
            <p className="m-0 mt-2 text-sm font-semibold text-slate-700 dark:text-slate-300">
              Targets met: {siteProgress?.targets_met ?? 0} /{" "}
              {siteProgress?.targets_total ?? 0}
            </p>
          </div>

          <div className="flex w-full flex-col gap-2 sm:w-auto sm:items-end">
            <label className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              Measurement period
            </label>
            <select
              value={period}
              onChange={(event) =>
                setPeriod(event.target.value as PeriodOption)
              }
              data-onboarding-target="kpi-period-selector"
              className="btn-brand-subtle w-full rounded-lg px-3 py-2 text-sm font-medium text-slate-900 outline-none ring-sky-200 focus:ring-2 sm:w-auto dark:text-slate-100"
            >
              {PERIOD_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <p className="m-0 text-xs text-slate-500 dark:text-slate-400">
              Last updated: {formatDateTime(latestUpdatedAt)}
            </p>
          </div>
        </div>
      </header>

      {loading && (
        <div className="brand-surface-muted rounded-xl px-4 py-3 opacity-50">
          <LoadingSpinner label="Loading KPI progress..." size="sm" />
        </div>
      )}

      {!loading && error && (
        <ErrorMessage
          title="Unable to load KPI dashboard"
          message={error}
          onRetry={() => void loadKPIData()}
        />
      )}

      {!loading && !error && showEmpty && (
        <EmptyState
          title="No KPI baseline data"
          message="Record KPI baselines to start tracking progress"
          actionLabel="Go to Settings"
          onAction={() => navigate("/settings")}
        />
      )}

      {!loading && !error && !showEmpty && (
        <>
          <div
            className="brand-panel rounded-2xl p-4"
            data-onboarding-target="kpi-target-cards"
          >
            <div className="mb-3 flex items-center justify-between">
              <h3 className="m-0 text-base font-semibold text-slate-900 dark:text-slate-100">
                Target Progress
              </h3>
              <p className="m-0 text-xs text-slate-500 dark:text-slate-400">
                Site: {siteProgress?.site_id ?? DEFAULT_SITE_ID}
              </p>
            </div>
            <div className="reveal-stagger grid grid-cols-1 items-stretch gap-4 lg:grid-cols-2 2xl:grid-cols-3">
              {KPI_METRICS.map((meta) => (
                <div key={meta.metric} className="h-full">
                  <KPITargetCard
                    metricLabel={meta.label}
                    metricHint={meta.hint}
                    targetPercent={meta.targetPercent}
                    progress={periodAwareProgressMap.get(meta.metric) ?? null}
                  />
                </div>
              ))}
            </div>
          </div>

          <div
            className="space-y-4 reveal-stagger"
            data-onboarding-target="kpi-trend-charts"
          >
            {KPI_METRICS.map((meta) => {
              const metricProgress = progressMap.get(meta.metric);
              const baseline = metricProgress?.baseline_value ?? 0;
              const targetLine = getTargetLineValue(meta, baseline);
              const snapshots = snapshotsByMetric[meta.metric] ?? [];

              return (
                <article
                  key={`${meta.metric}-chart`}
                  className="brand-panel rounded-2xl p-4"
                >
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <h3 className="m-0 text-base font-semibold text-slate-900 dark:text-slate-100">
                      {meta.label} Trend
                    </h3>
                    <p className="m-0 text-xs text-slate-500 dark:text-slate-400">
                      Baseline records:{" "}
                      {
                        baselines.filter((item) => item.metric === meta.metric)
                          .length
                      }
                    </p>
                  </div>

                  <div className="overflow-hidden">
                    <KPITrendChart
                      metricLabel={meta.label}
                      unit={metricProgress?.unit ?? "--"}
                      snapshots={snapshots}
                      baselineValue={baseline}
                      targetValue={targetLine}
                    />
                  </div>
                  {snapshots.length === 1 && (
                    <p className="mb-0 mt-2 text-xs text-slate-500 dark:text-slate-400">
                      Only one data point is available in this period.
                    </p>
                  )}
                </article>
              );
            })}
          </div>
        </>
      )}

      <OnboardingOverlay
        open={onboardingOpen}
        steps={[
          {
            title: "KPI Dashboard Overview",
            description:
              "This page tracks WASABI KPI performance for the selected site.",
            selector: '[data-onboarding-target="kpi-header"]',
          },
          {
            title: "Target Cards",
            description:
              "Review current baseline vs current values and target attainment per KPI.",
            selector: '[data-onboarding-target="kpi-target-cards"]',
          },
          {
            title: "Period Filter",
            description:
              "Change the period to load snapshots for different time windows.",
            selector: '[data-onboarding-target="kpi-period-selector"]',
          },
          {
            title: "Trend Charts",
            description:
              "Inspect historical progression with baseline and target reference lines.",
            selector: '[data-onboarding-target="kpi-trend-charts"]',
          },
        ]}
        onClose={() => setOnboardingOpen(false)}
      />
    </section>
  );
}
