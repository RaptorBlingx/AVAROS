import type { CanonicalMetricName, MetricMappingSource } from "../../api/types";

export type MetricOption = {
  value: CanonicalMetricName;
  label: string;
  category: "Energy" | "Material" | "Production" | "Carbon" | "Supplier";
};

export type MetricMappingRow = {
  id: string;
  canonical_metric: CanonicalMetricName;
  endpoint: string;
  json_path: string;
  unit: string;
  transform: string;
  source: MetricMappingSource;
};

export type MetricRowError = {
  canonical_metric?: string;
  endpoint?: string;
  json_path?: string;
  unit?: string;
};

export const METRIC_OPTIONS: MetricOption[] = [
  { value: "energy_per_unit", label: "Energy Per Unit", category: "Energy" },
  { value: "energy_total", label: "Energy Total", category: "Energy" },
  { value: "peak_demand", label: "Peak Demand", category: "Energy" },
  {
    value: "peak_tariff_exposure",
    label: "Peak Tariff Exposure",
    category: "Energy"
  },
  { value: "scrap_rate", label: "Scrap Rate", category: "Material" },
  { value: "rework_rate", label: "Rework Rate", category: "Material" },
  {
    value: "material_efficiency",
    label: "Material Efficiency",
    category: "Material"
  },
  {
    value: "recycled_content",
    label: "Recycled Content",
    category: "Material"
  },
  { value: "oee", label: "OEE", category: "Production" },
  { value: "throughput", label: "Throughput", category: "Production" },
  { value: "cycle_time", label: "Cycle Time", category: "Production" },
  {
    value: "changeover_time",
    label: "Changeover Time",
    category: "Production"
  },
  { value: "co2_per_unit", label: "CO₂ Per Unit", category: "Carbon" },
  { value: "co2_total", label: "CO₂ Total", category: "Carbon" },
  { value: "co2_per_batch", label: "CO₂ Per Batch", category: "Carbon" },
  {
    value: "supplier_lead_time",
    label: "Supplier Lead Time",
    category: "Supplier"
  },
  {
    value: "supplier_defect_rate",
    label: "Supplier Defect Rate",
    category: "Supplier"
  },
  {
    value: "supplier_on_time",
    label: "Supplier On-Time",
    category: "Supplier"
  },
  {
    value: "supplier_co2_per_kg",
    label: "Supplier CO₂ Per kg",
    category: "Supplier"
  }
];

export function groupMetricOptions(): Record<MetricOption["category"], MetricOption[]> {
  const groups: Record<MetricOption["category"], MetricOption[]> = {
    Energy: [],
    Material: [],
    Production: [],
    Carbon: [],
    Supplier: []
  };
  for (const option of METRIC_OPTIONS) {
    groups[option.category].push(option);
  }
  return groups;
}
