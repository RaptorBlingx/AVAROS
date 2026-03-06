// @vitest-environment jsdom

import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mockApi = vi.hoisted(() => ({
  discoverAssets: vi.fn(),
  getConfiguredAssets: vi.fn(),
  getPlatformConfig: vi.fn(),
  saveConfiguredAssets: vi.fn(),
  toFriendlyErrorMessage: vi.fn(() => "error"),
}));

vi.mock("../../../api/client", () => mockApi);

import AssetMappingStep from "../AssetMappingStep";

describe("AssetMappingStep platform rendering", () => {
  beforeEach(() => {
    mockApi.discoverAssets.mockReset();
    mockApi.getConfiguredAssets.mockReset();
    mockApi.getPlatformConfig.mockReset();
    mockApi.saveConfiguredAssets.mockReset();

    mockApi.getConfiguredAssets.mockResolvedValue({ asset_mappings: {} });
    mockApi.discoverAssets.mockResolvedValue({
      platform_type: "mock",
      supports_discovery: true,
      assets: [
        {
          asset_id: "Line-1",
          display_name: "Line 1",
          asset_type: "line",
          aliases: ["line one"],
          metadata: {},
        },
      ],
      existing_mappings: {},
    });
  });

  it("renders manual entry fields for custom_rest", async () => {
    render(
      <AssetMappingStep
        platformType="custom_rest"
        onComplete={vi.fn()}
        onSkip={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(mockApi.getConfiguredAssets).toHaveBeenCalled();
    });

    expect(screen.getByPlaceholderText(/asset name/i)).toBeTruthy();
    expect(screen.getByPlaceholderText("/api/metrics/{asset_id}")).toBeTruthy();
    expect(screen.queryByText("These are demo assets")).toBeNull();
  });

  it("renders read-only demo assets for mock", async () => {
    render(
      <AssetMappingStep
        platformType="mock"
        onComplete={vi.fn()}
        onSkip={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(mockApi.discoverAssets).toHaveBeenCalled();
    });

    expect(
      screen.getByText(/These are demo assets\. Connect a real platform/i),
    ).toBeTruthy();
    expect(screen.getByText("Line 1")).toBeTruthy();
    expect(screen.queryByText("Add Asset")).toBeNull();
  });
});
