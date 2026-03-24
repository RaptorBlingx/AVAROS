// @vitest-environment jsdom

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mockApi = vi.hoisted(() => ({
  getAssetDiscovery: vi.fn(),
  getConfiguredAssets: vi.fn(),
  saveConfiguredAssets: vi.fn(),
  toFriendlyErrorMessage: vi.fn(() => "error"),
}));

vi.mock("../../../api/client", () => mockApi);

import AssetRegistrationStep from "../AssetRegistrationStep";

describe("AssetRegistrationStep", () => {
  beforeEach(() => {
    mockApi.getAssetDiscovery.mockReset();
    mockApi.getConfiguredAssets.mockReset();
    mockApi.saveConfiguredAssets.mockReset();
    mockApi.getAssetDiscovery.mockResolvedValue({
      platform_type: "custom_rest",
      supports_discovery: false,
      assets: [],
      existing_mappings: {},
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

  it("loads configured rows for manual asset registration", async () => {
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
    await waitFor(() => {
      expect(mockApi.getAssetDiscovery).toHaveBeenCalledTimes(1);
    });

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
    expect(screen.queryByText("Live Asset Suggestions")).toBeNull();
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
        display_name: "Line 1",
      },
    });
    expect(onComplete).toHaveBeenCalledTimes(1);
  });
});
