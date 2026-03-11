import type { CanonicalMetricName, MetricMapping } from "../../api/types";
import type { MetricMappingRow } from "../common/metricMapping";

export type SettingsMetricRow = MetricMappingRow & {
  persisted: boolean;
  originalMetric: CanonicalMetricName | null;
};

export const EMPTY_SETTINGS_ROW_DEFAULTS: Omit<
  SettingsMetricRow,
  "id" | "canonical_metric" | "persisted" | "originalMetric"
> = {
  endpoint: "",
  json_path: "",
  unit: "",
  transform: "",
  source: "manual",
};

export function createSettingsRow(mapping: MetricMapping): SettingsMetricRow {
  return {
    id: `${mapping.canonical_metric}-${Math.random().toString(36).slice(2, 9)}`,
    canonical_metric: mapping.canonical_metric,
    endpoint: mapping.endpoint,
    json_path: mapping.json_path,
    unit: mapping.unit,
    transform: mapping.transform ?? "",
    source: mapping.source ?? "manual",
    persisted: true,
    originalMetric: mapping.canonical_metric,
  };
}

