import type { KPIProgressItem, KPIMetricName, SnapshotResponse } from "../../api/types";

export type PeriodOption = "7d" | "30d" | "90d" | "all";

export type MetricMeta = {
  metric: KPIMetricName;
  label: string;
  targetPercent: number;
  direction: "reduction" | "increase";
  hint: string;
};

export const KPI_METRICS: MetricMeta[] = [
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
    label: "CO₂-eq",
    targetPercent: 10,
    direction: "reduction",
    hint: "Target: >=10% CO₂-eq reduction",
  },
];

export const PERIOD_OPTIONS: Array<{ value: PeriodOption; label: string }> = [
  { value: "7d", label: "Last 7 days" },
  { value: "30d", label: "Last 30 days" },
  { value: "90d", label: "Last 90 days" },
  { value: "all", label: "All time" },
];

export function toIsoDateRange(period: PeriodOption): { start?: string; end?: string } {
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

export function formatDateTime(value?: string): string {
  if (!value) {
    return "--";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "--";
  }
  return date.toLocaleString();
}

export function getTargetLineValue(meta: MetricMeta, baselineValue: number): number {
  if (meta.direction === "reduction") {
    return baselineValue * (1 - meta.targetPercent / 100);
  }
  return baselineValue * (1 + meta.targetPercent / 100);
}

export function computeImprovementPercent(
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

export function getLatestCurrentDate(items: KPIProgressItem[]): string {
  const dates = items.map((item) => item.current_date);
  if (dates.length === 0) {
    return "";
  }
  const sorted = [...dates].sort();
  return sorted[sorted.length - 1] ?? "";
}

export function buildPeriodAwareProgressMap(
  progressMap: Map<string, KPIProgressItem>,
  snapshotsByMetric: Partial<Record<KPIMetricName, SnapshotResponse[]>>
): Map<string, KPIProgressItem | null> {
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
}
