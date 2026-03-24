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
    expect(screen.getByRole("button", { name: "Add Mapping" })).toBeTruthy();
  });
});
