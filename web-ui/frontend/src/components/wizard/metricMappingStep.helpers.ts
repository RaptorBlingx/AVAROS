import type {
  MetricMapping,
  MetricMappingRequest,
} from "../../api/types";
import type { MetricMappingRow } from "../common/metricMapping";

export const EMPTY_WIZARD_ROW_DEFAULTS: Omit<MetricMappingRow, "id" | "canonical_metric"> = {
  endpoint: "",
  json_path: "",
  unit: "",
  transform: "",
  source: "manual",
};

export function createWizardRow(mapping: MetricMapping): MetricMappingRow {
  return {
    id: `${mapping.canonical_metric}-${Math.random().toString(36).slice(2, 9)}`,
    canonical_metric: mapping.canonical_metric,
    endpoint: mapping.endpoint,
    json_path: mapping.json_path,
    unit: mapping.unit,
    transform: mapping.transform ?? "",
    source: mapping.source ?? "manual",
  };
}

export function toMappingRequestPayload(
  row: MetricMappingRow,
): MetricMappingRequest {
  return {
    canonical_metric: row.canonical_metric,
    endpoint: row.endpoint.trim(),
    json_path: row.json_path.trim(),
    unit: row.unit.trim(),
    transform: row.transform.trim() || null,
  };
}

