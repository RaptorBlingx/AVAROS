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
import KPITrendChart from "../components/kpi/KPITrendChart";
import KPITargetCard from "../components/kpi/KPITargetCard";

type PeriodOption = "7d" | "30d" | "90d" | "all";

type MetricMeta = {
  metric: KPIMetricName;
  label: string;
  targetPercent: number;
  direction: "reduction" | "increase";
  hint: string;
};

const KPI_METRICS: MetricMeta[] = [
  {
    metric: "energy_per_unit",
    label: "Energy per Unit",
    targetPercent: 8,
    direction: "reduction",
    hint: "Target: >=8% electricity per unit reduction",
  },
  {
    metric: "material_efficiency",
    label: "Material Efficiency",
    targetPercent: 5,
    direction: "increase",
    hint: "Target: >=5% material efficiency improvement",
  },
  {
    metric: "co2_total",
    label: "CO2-eq",
    targetPercent: 10,
    direction: "reduction",
    hint: "Target: >=10% CO2-eq reduction",
  },
];

const PERIOD_OPTIONS: Array<{ value: PeriodOption; label: string }> = [
  { value: "7d", label: "Last 7 days" },
  { value: "30d", label: "Last 30 days" },
  { value: "90d", label: "Last 90 days" },
  { value: "all", label: "All time" },
];

function toIsoDateRange(period: PeriodOption): { start?: string; end?: string } {
  if (period === "all") {
    return {};
  }

  const end = new Date();
  const start = new Date(end);
  if (period === "7d") {
    start.setDate(end.getDate() - 7);
  } else if (period === "30d") {
    start.setDate(end.getDate() - 30);
  } else {
    start.setDate(end.getDate() - 90);
  }

  return {
    start: start.toISOString().slice(0, 10),
    end: end.toISOString().slice(0, 10),
  };
}

function formatDateTime(value?: string): string {
  if (!value) {
    return "--";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "--";
  }
  return date.toLocaleString();
}

function getTargetLineValue(meta: MetricMeta, baselineValue: number): number {
  if (meta.direction === "reduction") {
    return baselineValue * (1 - meta.targetPercent / 100);
  }
  return baselineValue * (1 + meta.targetPercent / 100);
}

function computeImprovementPercent(
  baseline: number,
  current: number,
  direction: "reduction" | "increase"
): number {
  if (baseline === 0) {
    return 0;
  }
  if (direction === "reduction") {
    return ((baseline - current) / baseline) * 100;
  }
  return ((current - baseline) / baseline) * 100;
}

export default function KPIDashboard() {
  const navigate = useNavigate();

  const [period, setPeriod] = useState<PeriodOption>("30d");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showEmpty, setShowEmpty] = useState(false);

  const [siteProgress, setSiteProgress] = useState<SiteProgressResponse | null>(null);
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
          getSnapshots(DEFAULT_SITE_ID, item.metric, start, end)
        )
      );

      const nextSnapshots: Partial<Record<KPIMetricName, SnapshotResponse[]>> = {};
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

  const progressMap = useMemo(() => {
    const map = new Map<string, KPIProgressItem>();
    for (const item of siteProgress?.progress ?? []) {
      map.set(item.metric, item);
    }
    return map;
  }, [siteProgress?.progress]);

  const latestUpdatedAt = useMemo(() => {
    const dates = (siteProgress?.progress ?? []).map((item) => item.current_date);
    if (dates.length === 0) {
      return "";
    }
    const sorted = [...dates].sort();
    return sorted[sorted.length - 1] ?? "";
  }, [siteProgress?.progress]);

  const periodAwareProgressMap = useMemo(() => {
    const map = new Map<string, KPIProgressItem | null>();

    for (const meta of KPI_METRICS) {
      const baseProgress = progressMap.get(meta.metric);
      if (!baseProgress) {
        map.set(meta.metric, null);
        continue;
      }

      const metricSnapshots = snapshotsByMetric[meta.metric] ?? [];
      if (metricSnapshots.length === 0) {
        map.set(meta.metric, null);
        continue;
      }

      const sortedSnapshots = [...metricSnapshots].sort((a, b) =>
        new Date(a.measured_at).getTime() - new Date(b.measured_at).getTime()
      );
      const latestSnapshot = sortedSnapshots[sortedSnapshots.length - 1];
      const improvementPercent = computeImprovementPercent(
        baseProgress.baseline_value,
        latestSnapshot.value,
        meta.direction
      );

      map.set(meta.metric, {
        ...baseProgress,
        current_value: latestSnapshot.value,
        unit: latestSnapshot.unit,
        current_date: latestSnapshot.measured_at,
        improvement_percent: Number(improvementPercent.toFixed(2)),
        target_met: improvementPercent >= meta.targetPercent,
      });
    }

    return map;
  }, [progressMap, snapshotsByMetric]);

  return (
    <section className="space-y-5">
      <header className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900/40">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="m-0 text-xs font-bold uppercase tracking-[0.14em] text-sky-600 dark:text-sky-300">
              WASABI KPI Tracking
            </p>
            <h2 className="m-0 mt-1 text-2xl font-semibold text-slate-900 dark:text-slate-100">
              KPI Dashboard
            </h2>
            <p className="m-0 mt-2 text-sm text-slate-600 dark:text-slate-400">
              Monitor pilot performance for energy, material efficiency, and CO2-eq targets.
            </p>
            <p className="m-0 mt-2 text-sm font-semibold text-slate-700 dark:text-slate-300">
              Targets met: {siteProgress?.targets_met ?? 0} / {siteProgress?.targets_total ?? 0}
            </p>
          </div>

          <div className="flex flex-col gap-2 sm:items-end">
            <label className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              Measurement period
            </label>
            <select
              value={period}
              onChange={(event) => setPeriod(event.target.value as PeriodOption)}
              className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none ring-sky-200 focus:ring-2 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
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
        <div className="rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 opacity-50 dark:border-slate-700 dark:bg-slate-900/40">
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
          <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
            {KPI_METRICS.map((meta) => (
              <KPITargetCard
                key={meta.metric}
                metricLabel={meta.label}
                metricHint={meta.hint}
                targetPercent={meta.targetPercent}
                progress={periodAwareProgressMap.get(meta.metric) ?? null}
              />
            ))}
          </div>

          <div className="space-y-4">
            {KPI_METRICS.map((meta) => {
              const metricProgress = progressMap.get(meta.metric);
              const baseline = metricProgress?.baseline_value ?? 0;
              const targetLine = getTargetLineValue(meta, baseline);
              const snapshots = snapshotsByMetric[meta.metric] ?? [];

              return (
                <article
                  key={`${meta.metric}-chart`}
                  className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900/40"
                >
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <h3 className="m-0 text-base font-semibold text-slate-900 dark:text-slate-100">
                      {meta.label} Trend
                    </h3>
                    <p className="m-0 text-xs text-slate-500 dark:text-slate-400">
                      Baseline records: {baselines.filter((item) => item.metric === meta.metric).length}
                    </p>
                  </div>

                  <div className="overflow-x-auto">
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
    </section>
  );
}
