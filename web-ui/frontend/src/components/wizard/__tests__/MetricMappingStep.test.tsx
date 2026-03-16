// @vitest-environment jsdom

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mockApi = vi.hoisted(() => ({
  createMetricMapping: vi.fn(),
  deleteMetricMapping: vi.fn(),
  getAssetLinkingSummary: vi.fn(),
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

  it("renders read-only reneryo coverage summary and continues", async () => {
    const onComplete = vi.fn();
    render(
      <MetricMappingStep
        platformType="reneryo"
        onComplete={onComplete}
        onSkip={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(mockApi.getAssetLinkingSummary).toHaveBeenCalledTimes(1);
    });

    expect(screen.getByText("changeover_time")).toBeTruthy();
    expect(screen.getByText("Linked assets: 1/1")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Add Mapping" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(onComplete).toHaveBeenCalledTimes(1);
  });
});
