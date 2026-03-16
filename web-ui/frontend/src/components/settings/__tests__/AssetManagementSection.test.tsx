// @vitest-environment jsdom

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mockApi = vi.hoisted(() => ({
  discoverAssets: vi.fn(),
  getAssetLinkingSummary: vi.fn(),
  getConfiguredAssets: vi.fn(),
  getPlatformConfig: vi.fn(),
  saveConfiguredAssets: vi.fn(),
  toFriendlyErrorMessage: vi.fn(() => "error"),
}));

vi.mock("../../../api/client", () => mockApi);

import AssetManagementSection from "../AssetManagementSection";

function renderWithRouter(node: ReactNode) {
  return render(<MemoryRouter>{node}</MemoryRouter>);
}

describe("AssetManagementSection", () => {
  beforeEach(() => {
    mockApi.discoverAssets.mockReset();
    mockApi.getAssetLinkingSummary.mockReset();
    mockApi.getConfiguredAssets.mockReset();
    mockApi.getPlatformConfig.mockReset();
    mockApi.saveConfiguredAssets.mockReset();

    mockApi.getConfiguredAssets.mockResolvedValue({ asset_mappings: {} });
    mockApi.saveConfiguredAssets.mockResolvedValue({ asset_mappings: {} });
    mockApi.discoverAssets.mockResolvedValue({
      platform_type: "custom_rest",
      supports_discovery: false,
      discovery_source: "none",
      assets: [],
      registered_assets: [],
      discovery_error: "",
      existing_mappings: {},
    });
    mockApi.getAssetLinkingSummary.mockResolvedValue({
      platform_type: "reneryo",
      supports_discovery: true,
      discovery_source: "adapter",
      discovery_error: "",
      canonical_metrics: [],
      imported_assets: [],
      unlinked_assets: [],
      discovered_assets: [],
      metric_coverage: [],
    });
  });

  it("saves manual custom_rest assets via /api/v1/config/assets client call", async () => {
    const onNotify = vi.fn();
    renderWithRouter(
      <AssetManagementSection
        mode="settings"
        platformType="custom_rest"
        onNotify={onNotify}
      />,
    );

    await waitFor(() => {
      expect(mockApi.getConfiguredAssets).toHaveBeenCalled();
    });

    fireEvent.change(screen.getByPlaceholderText(/asset name/i), {
      target: { value: "Mixer A" },
    });
    fireEvent.change(screen.getByPlaceholderText("/api/metrics/{asset_id}"), {
      target: { value: "/v1/energy/{asset_id}" },
    });
    fireEvent.change(screen.getByPlaceholderText(/aliases/i), {
      target: { value: "mixer-a, mixer alpha" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Save Assets" }));

    await waitFor(() => {
      expect(mockApi.saveConfiguredAssets).toHaveBeenCalledTimes(1);
    });

    expect(mockApi.saveConfiguredAssets).toHaveBeenCalledWith({
      "mixer-a": {
        display_name: "Mixer A",
        asset_type: "machine",
        aliases: ["mixer-a", "mixer alpha"],
        endpoint_template: "/v1/energy/{asset_id}",
      },
    });
    expect(onNotify).toHaveBeenCalledWith("success", "Assets saved.");
  });

  it("hides Discover Assets button for custom_rest when discovery is unsupported", async () => {
    renderWithRouter(<AssetManagementSection mode="settings" platformType="custom_rest" />);

    await waitFor(() => {
      expect(mockApi.discoverAssets).toHaveBeenCalled();
    });

    await waitFor(() => {
      expect(screen.queryByRole("button", { name: "Discover Assets" })).toBeNull();
    });
  });

  it("shows Discover Assets button for mock when discovery is supported", async () => {
    mockApi.discoverAssets.mockResolvedValue({
      platform_type: "mock",
      supports_discovery: true,
      discovery_source: "adapter",
      assets: [],
      registered_assets: [],
      discovery_error: "",
      existing_mappings: {},
    });

    renderWithRouter(<AssetManagementSection mode="settings" platformType="mock" />);

    await waitFor(() => {
      expect(mockApi.discoverAssets).toHaveBeenCalled();
    });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Discover Assets" })).toBeTruthy();
    });
  });

  it("keeps Discover Assets button visible after discovery fetch failure on mock", async () => {
    mockApi.discoverAssets.mockRejectedValue(new Error("network down"));

    renderWithRouter(<AssetManagementSection mode="settings" platformType="mock" />);

    await waitFor(() => {
      expect(mockApi.discoverAssets).toHaveBeenCalled();
    });

    expect(screen.getByRole("button", { name: "Discover Assets" })).toBeTruthy();
  });
});
