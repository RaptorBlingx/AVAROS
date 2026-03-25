// @vitest-environment jsdom

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mockApi = vi.hoisted(() => ({
  getAssetDiscovery: vi.fn(),
  getConfiguredAssets: vi.fn(),
  getGeneratorAssetPreview: vi.fn(),
  saveConfiguredAssets: vi.fn(),
  toFriendlyErrorMessage: vi.fn(() => "error"),
}));

vi.mock("../../../api/client", () => mockApi);

import AssetRegistrationStep from "../AssetRegistrationStep";

describe("AssetRegistrationStep", () => {
  beforeEach(() => {
    mockApi.getAssetDiscovery.mockReset();
    mockApi.getConfiguredAssets.mockReset();
    mockApi.getGeneratorAssetPreview.mockReset();
    mockApi.saveConfiguredAssets.mockReset();
    mockApi.getAssetDiscovery.mockResolvedValue({
      platform_type: "custom_rest",
      supports_discovery: false,
      assets: [],
      existing_mappings: {},
    });
    mockApi.getGeneratorAssetPreview.mockResolvedValue({
      available: true,
      source_path: "/tmp/mapping_output.json",
      imported_metrics: 0,
      assets: [],
      error: "",
    });

    mockApi.getConfiguredAssets.mockResolvedValue({
      asset_mappings: {
        "line-1": {
          asset_type: "line",
          aliases: ["line one"],
        },
      },
    });
    mockApi.saveConfiguredAssets.mockResolvedValue({
      asset_mappings: {
        "line-1": {
          display_name: "Line 1",
          asset_type: "line",
          aliases: ["line one"],
        },
      },
    });
  });

  it("loads configured rows for manual asset registration without live discovery", async () => {
    render(
      <AssetRegistrationStep
        platformType="custom_rest"
        onComplete={vi.fn()}
        onSkip={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(mockApi.getConfiguredAssets).toHaveBeenCalledTimes(1);
    });
    expect(mockApi.getAssetDiscovery).toHaveBeenCalledTimes(0);

    expect(screen.getByDisplayValue("line-1")).toBeTruthy();
    expect(screen.getByDisplayValue("Line 1")).toBeTruthy();
    const existingAssetIdInput = screen.getByDisplayValue("line-1") as HTMLInputElement;
    expect(existingAssetIdInput.disabled).toBe(true);
    expect(
      screen.queryByRole("button", { name: "Import Mapping" }),
    ).toBeNull();
  });

  it("does not call discovery when mock preset is active", async () => {
    render(
      <AssetRegistrationStep
        platformType="custom_rest"
        integrationPreset="mock"
        onComplete={vi.fn()}
        onSkip={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(mockApi.getConfiguredAssets).toHaveBeenCalledTimes(1);
    });
    expect(mockApi.getAssetDiscovery).toHaveBeenCalledTimes(0);
    expect(mockApi.getGeneratorAssetPreview).toHaveBeenCalledTimes(0);
    expect(screen.queryByText("Live Asset Suggestions")).toBeNull();
  });

  it("renders generator and live sections for reneryo preset", async () => {
    mockApi.getConfiguredAssets.mockResolvedValueOnce({ asset_mappings: {} });
    mockApi.getGeneratorAssetPreview.mockResolvedValueOnce({
      available: true,
      source_path: "/tmp/mapping_output.json",
      imported_metrics: 1,
      assets: [
        {
          asset_id: "Line-1",
          display_name: "Line 1",
          asset_type: "line",
          metric_count: 19,
          metrics: ["energy_total"],
          source: "generator",
        },
      ],
      error: "",
    });
    mockApi.getAssetDiscovery.mockResolvedValueOnce({
      platform_type: "custom_rest",
      supports_discovery: true,
      assets: [
        {
          asset_id: "8e7a03ca-2992-4ca1-aea4-2cdcfc911c5d",
          display_name: "Seu 4 for reporting",
          asset_type: "machine",
          aliases: [],
        },
      ],
      existing_mappings: {},
    });

    render(
      <AssetRegistrationStep
        platformType="custom_rest"
        integrationPreset="reneryo"
        onComplete={vi.fn()}
        onSkip={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(mockApi.getGeneratorAssetPreview).toHaveBeenCalledTimes(1);
      expect(mockApi.getAssetDiscovery).toHaveBeenCalledTimes(1);
    });

    expect(screen.getByText("KPI-ready Generator Assets")).toBeTruthy();
    expect(screen.getByText("Live RENERYO Resources")).toBeTruthy();
    expect(screen.getByText("Line 1")).toBeTruthy();
    expect(screen.getByText("Seu 4 for reporting")).toBeTruthy();
  });

  it("saves edited registration rows", async () => {
    const onComplete = vi.fn();
    render(
      <AssetRegistrationStep
        platformType="custom_rest"
        onComplete={onComplete}
        onSkip={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(mockApi.getConfiguredAssets).toHaveBeenCalledTimes(1);
    });

    const saveBtn = await screen.findByRole("button", { name: "Save & Continue" });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(mockApi.saveConfiguredAssets).toHaveBeenCalledTimes(1);
    });
    expect(mockApi.saveConfiguredAssets).toHaveBeenCalledWith({
      "line-1": {
        asset_type: "line",
        aliases: ["line one"],
        capability_mode: "full_kpi",
        display_name: "Line 1",
        mapping_source: "manual",
        native_metric_bindings: {},
      },
    });
    expect(onComplete).toHaveBeenCalledTimes(1);
  });

  it("upgrades discovered SEU rows to energy-only mode", async () => {
    mockApi.getConfiguredAssets.mockResolvedValueOnce({
      asset_mappings: {
        "8e7a03ca-2992-4ca1-aea4-2cdcfc911c5d": {
          display_name: "Seu 4 for reporting",
          asset_type: "machine",
          aliases: ["seu 4 for reporting"],
          mapping_source: "manual",
          capability_mode: "full_kpi",
        },
      },
    });
    mockApi.getAssetDiscovery.mockResolvedValueOnce({
      platform_type: "custom_rest",
      supports_discovery: true,
      assets: [
        {
          asset_id: "8e7a03ca-2992-4ca1-aea4-2cdcfc911c5d",
          display_name: "Seu 4 for reporting",
          asset_type: "machine",
          aliases: [],
        },
      ],
      existing_mappings: {},
    });
    mockApi.saveConfiguredAssets.mockResolvedValueOnce({
      asset_mappings: {
        "8e7a03ca-2992-4ca1-aea4-2cdcfc911c5d": {
          display_name: "Seu 4 for reporting",
          asset_type: "machine",
          aliases: ["seu 4 for reporting"],
          mapping_source: "live_discovery",
          capability_mode: "energy_only",
          native_metric_bindings: {
            energy_total: {
              strategy: "asset_consumption_total",
              unit: "kWh",
              trend_supported: false,
              compare_supported: false,
              default_period_mode: "aggregate_total",
              aggregate_start_iso: "2021-02-01T00:00:00.000Z",
            },
          },
        },
      },
    });

    render(
      <AssetRegistrationStep
        platformType="custom_rest"
        integrationPreset="reneryo"
        onComplete={vi.fn()}
        onSkip={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(mockApi.getAssetDiscovery).toHaveBeenCalledTimes(1);
    });
    await waitFor(() => {
      expect(
        screen.getByText("Mode: Energy only (compatibility)"),
      ).toBeTruthy();
    });

    fireEvent.click(await screen.findByRole("button", { name: "Save & Continue" }));

    await waitFor(() => {
      expect(mockApi.saveConfiguredAssets).toHaveBeenCalledTimes(1);
    });
    expect(mockApi.saveConfiguredAssets).toHaveBeenCalledWith({
      "8e7a03ca-2992-4ca1-aea4-2cdcfc911c5d": {
        display_name: "Seu 4 for reporting",
        asset_type: "machine",
        aliases: ["seu 4 for reporting"],
        mapping_source: "live_discovery",
        capability_mode: "energy_only",
        native_metric_bindings: {
          energy_total: {
            strategy: "asset_consumption_total",
            unit: "kWh",
            trend_supported: false,
            compare_supported: false,
            default_period_mode: "aggregate_total",
            aggregate_start_iso: "2021-02-01T00:00:00.000Z",
          },
        },
      },
    });
  });
});
