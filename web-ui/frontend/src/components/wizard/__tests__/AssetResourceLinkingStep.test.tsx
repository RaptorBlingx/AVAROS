// @vitest-environment jsdom

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mockApi = vi.hoisted(() => ({
  getConfiguredAssets: vi.fn(),
  importGeneratorMapping: vi.fn(),
  saveConfiguredAssets: vi.fn(),
  toFriendlyErrorMessage: vi.fn(() => "error"),
}));

vi.mock("../../../api/client", () => mockApi);

import AssetResourceLinkingStep from "../AssetResourceLinkingStep";

describe("AssetResourceLinkingStep", () => {
  beforeEach(() => {
    mockApi.getConfiguredAssets.mockReset();
    mockApi.importGeneratorMapping.mockReset();
    mockApi.saveConfiguredAssets.mockReset();

    mockApi.getConfiguredAssets.mockResolvedValue({
      asset_mappings: {
        "line-1": {
          display_name: "Line 1",
          asset_type: "line",
          metric_resources: {
            energy_total: "uuid-1",
          },
        },
      },
    });
    mockApi.saveConfiguredAssets.mockResolvedValue({ asset_mappings: {} });
    mockApi.importGeneratorMapping.mockResolvedValue({
      imported_metrics: 1,
      imported_resources: 19,
      asset_mappings: {
        "line-1": {
          display_name: "Line 1",
          asset_type: "line",
          metric_resources: {
            energy_per_unit: "1",
            energy_total: "2",
            peak_demand: "3",
            peak_tariff_exposure: "4",
            scrap_rate: "5",
            rework_rate: "6",
            material_efficiency: "7",
            recycled_content: "8",
            supplier_lead_time: "9",
            supplier_defect_rate: "10",
            supplier_on_time: "11",
            supplier_co2_per_kg: "12",
            oee: "13",
            throughput: "14",
            cycle_time: "15",
            changeover_time: "16",
            co2_per_unit: "17",
            co2_total: "18",
            co2_per_batch: "19",
          },
        },
      },
    });
  });

  it("saves endpoint template links for custom_rest", async () => {
    const onComplete = vi.fn();
    render(
      <AssetResourceLinkingStep
        platformType="custom_rest"
        onComplete={onComplete}
        onSkip={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(mockApi.getConfiguredAssets).toHaveBeenCalledTimes(1);
    });

    const endpointInput = await screen.findByPlaceholderText(
      "/api/metrics/{asset_id}",
    );

    fireEvent.change(endpointInput, {
      target: { value: "/v1/metrics/{asset_id}" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Save & Continue" }));

    await waitFor(() => {
      expect(mockApi.saveConfiguredAssets).toHaveBeenCalledTimes(1);
    });

    expect(mockApi.saveConfiguredAssets).toHaveBeenCalledWith({
      "line-1": {
        display_name: "Line 1",
        asset_type: "line",
        metric_resources: {
          energy_total: "uuid-1",
        },
        endpoint_template: "/v1/metrics/{asset_id}",
      },
    });
    expect(onComplete).toHaveBeenCalledTimes(1);
  });

  it("shows reneryo metric coverage and imports generator mapping", async () => {
    const onComplete = vi.fn();
    render(
      <AssetResourceLinkingStep
        platformType="reneryo"
        onComplete={onComplete}
        onSkip={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(mockApi.getConfiguredAssets).toHaveBeenCalledTimes(1);
    });
    expect(screen.getByText("1/19 metrics linked")).toBeTruthy();
    expect(screen.getByText("Partial")).toBeTruthy();

    fireEvent.change(
      screen.getByPlaceholderText('{"mapping": {"energy_total": {"line-1": "uuid-1"}}}'),
      {
        target: { value: '{"mapping":{"energy_total":{"line-1":"uuid-1"}}}' },
      },
    );
    fireEvent.click(screen.getByRole("button", { name: "Import Mapping" }));

    await waitFor(() => {
      expect(mockApi.importGeneratorMapping).toHaveBeenCalledTimes(1);
    });
    expect(mockApi.importGeneratorMapping).toHaveBeenCalledWith({
      energy_total: { "line-1": "uuid-1" },
    });
    expect(screen.getByText("Ready")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(onComplete).toHaveBeenCalledTimes(1);

    expect(mockApi.saveConfiguredAssets).not.toHaveBeenCalled();
  });
});
