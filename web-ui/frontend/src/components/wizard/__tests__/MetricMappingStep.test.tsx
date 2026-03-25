// @vitest-environment jsdom

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mockApi = vi.hoisted(() => ({
  createMetricMapping: vi.fn(),
  deleteMetricMapping: vi.fn(),
  getAssetLinkingSummary: vi.fn(),
  importGeneratorMapping: vi.fn(),
  listMetricMappings: vi.fn(),
  toFriendlyErrorMessage: vi.fn((error: unknown) =>
    error instanceof Error ? error.message : "error",
  ),
  updateMetricMapping: vi.fn(),
}));

const mockMetricTestHook = vi.hoisted(() => ({
  testStateByRow: {},
  testRowMapping: vi.fn(),
  resetRowTestState: vi.fn(),
  clearAllTestState: vi.fn(),
}));

vi.mock("../../../api/client", () => mockApi);
vi.mock("../../../hooks/useMetricMappingTest", () => ({
  default: () => mockMetricTestHook,
}));

import MetricMappingStep from "../MetricMappingStep";

describe("MetricMappingStep", () => {
  beforeEach(() => {
    mockApi.createMetricMapping.mockReset();
    mockApi.deleteMetricMapping.mockReset();
    mockApi.getAssetLinkingSummary.mockReset();
    mockApi.importGeneratorMapping.mockReset();
    mockApi.listMetricMappings.mockReset();
    mockApi.updateMetricMapping.mockReset();

    mockApi.listMetricMappings.mockResolvedValue([
      {
        canonical_metric: "changeover_time",
        endpoint: "/api/u/measurement/metric/resource/id/values",
        json_path: "$.records[*].value",
        unit: "min",
        transform: null,
        source: "manual",
      },
    ]);
    mockApi.createMetricMapping.mockResolvedValue({});
    mockApi.deleteMetricMapping.mockResolvedValue(undefined);
    mockApi.importGeneratorMapping.mockResolvedValue({
      imported_metrics: 1,
      imported_resources: 1,
      asset_mappings: {},
    });
    mockApi.getAssetLinkingSummary.mockResolvedValue({
      imported_assets: [
        {
          asset_id: "Line-1",
          display_name: "Line 1",
          asset_type: "line",
          aliases: [],
          source: "imported",
          mapping_mode: "full_kpi",
          mapping_source: "generator",
          linked_metrics: ["changeover_time"],
          native_metrics: [],
          supported_metrics: ["changeover_time"],
          missing_metrics: [],
          linked_metric_count: 1,
          total_metrics: 1,
        },
      ],
      unlinked_assets: [],
      discovered_assets: [
        {
          asset_id: "620aa6a4-c1b3-431b-8bec-dc82ac0cd6b4",
          display_name: "Seu",
          asset_type: "machine",
          aliases: [],
          source: "discovered",
          mapping_mode: "registration_only",
          mapping_source: "live_discovery",
          linked_metrics: [],
          native_metrics: [],
          supported_metrics: [],
          missing_metrics: [],
          linked_metric_count: 0,
          total_metrics: 19,
        },
      ],
      metric_coverage: [
        {
          metric_name: "changeover_time",
          linked_assets: 1,
          total_assets: 1,
          missing_assets: [],
        },
      ],
    });
  });

  it("falls back to create when update returns metric mapping not found", async () => {
    const onComplete = vi.fn();
    mockApi.updateMetricMapping.mockRejectedValue({
      status: 404,
      message: "Metric mapping not found: changeover_time",
    });

    render(<MetricMappingStep onComplete={onComplete} onSkip={vi.fn()} />);

    await waitFor(() => {
      expect(mockApi.listMetricMappings).toHaveBeenCalledTimes(1);
    });

    fireEvent.click(
      screen.getByRole("button", { name: "Save Mappings & Continue" }),
    );

    await waitFor(() => {
      expect(mockApi.updateMetricMapping).toHaveBeenCalledTimes(1);
    });
    await waitFor(() => {
      expect(mockApi.createMetricMapping).toHaveBeenCalledTimes(1);
    });

    expect(mockApi.createMetricMapping).toHaveBeenCalledWith({
      canonical_metric: "changeover_time",
      endpoint: "/api/u/measurement/metric/resource/id/values",
      json_path: "$.records[*].value",
      unit: "min",
      transform: null,
    });
    expect(onComplete).toHaveBeenCalledTimes(1);
  });

  it("renders RENERYO helper coverage while keeping manual mapping editable", async () => {
    render(
      <MetricMappingStep
        integrationPreset="reneryo"
        onComplete={vi.fn()}
        onSkip={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(mockApi.getAssetLinkingSummary).toHaveBeenCalledTimes(1);
    });

    expect(screen.getByText("RENERYO Helper")).toBeTruthy();
    expect(screen.getByText("changeover_time")).toBeTruthy();
    expect(screen.getByText("Linked assets: 1/1")).toBeTruthy();
    expect(screen.getByText("KPI-ready Assets (Full KPI)")).toBeTruthy();
    expect(screen.getByText("Line 1")).toBeTruthy();
    expect(screen.getByText("Live RENERYO Resources (Discovered)")).toBeTruthy();
    expect(screen.getByText("620aa6a4-c1b3-431b-8bec-dc82ac0cd6b4 · machine")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Add Mapping" })).toBeTruthy();
  });
});
