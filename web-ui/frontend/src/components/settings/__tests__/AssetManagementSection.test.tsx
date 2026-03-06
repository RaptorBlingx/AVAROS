// @vitest-environment jsdom

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mockApi = vi.hoisted(() => ({
  discoverAssets: vi.fn(),
  getConfiguredAssets: vi.fn(),
  getPlatformConfig: vi.fn(),
  saveConfiguredAssets: vi.fn(),
  toFriendlyErrorMessage: vi.fn(() => "error"),
}));

vi.mock("../../../api/client", () => mockApi);

import AssetManagementSection from "../AssetManagementSection";

describe("AssetManagementSection", () => {
  beforeEach(() => {
    mockApi.discoverAssets.mockReset();
    mockApi.getConfiguredAssets.mockReset();
    mockApi.getPlatformConfig.mockReset();
    mockApi.saveConfiguredAssets.mockReset();

    mockApi.getConfiguredAssets.mockResolvedValue({ asset_mappings: {} });
    mockApi.saveConfiguredAssets.mockResolvedValue({ asset_mappings: {} });
    mockApi.discoverAssets.mockResolvedValue({
      platform_type: "custom_rest",
      supports_discovery: false,
      assets: [],
      existing_mappings: {},
    });
  });

  it("saves manual custom_rest assets via /api/v1/config/assets client call", async () => {
    const onNotify = vi.fn();
    render(
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
});
