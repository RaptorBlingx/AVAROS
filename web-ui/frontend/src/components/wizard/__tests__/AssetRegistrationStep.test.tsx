// @vitest-environment jsdom

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mockApi = vi.hoisted(() => ({
  discoverAssets: vi.fn(),
  getConfiguredAssets: vi.fn(),
  saveConfiguredAssets: vi.fn(),
  toFriendlyErrorMessage: vi.fn(() => "error"),
}));

vi.mock("../../../api/client", () => mockApi);

import AssetRegistrationStep from "../AssetRegistrationStep";

describe("AssetRegistrationStep", () => {
  beforeEach(() => {
    mockApi.discoverAssets.mockReset();
    mockApi.getConfiguredAssets.mockReset();
    mockApi.saveConfiguredAssets.mockReset();

    mockApi.getConfiguredAssets.mockResolvedValue({
      asset_mappings: {
        "line-1": {
          asset_type: "line",
          aliases: ["line one"],
        },
      },
    });
    mockApi.discoverAssets.mockResolvedValue({
      supports_discovery: true,
      assets: [
        {
          asset_id: "line-2",
          display_name: "Line 2",
          asset_type: "line",
          aliases: ["line two"],
          metadata: {},
        },
      ],
      existing_mappings: {},
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

  it("loads configured rows and discovery suggestions for asset registration", async () => {
    render(
      <AssetRegistrationStep
        platformType="reneryo"
        onComplete={vi.fn()}
        onSkip={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(mockApi.getConfiguredAssets).toHaveBeenCalledTimes(1);
    });

    expect(mockApi.discoverAssets).toHaveBeenCalledTimes(1);
    expect(screen.getByDisplayValue("line-1")).toBeTruthy();
    expect(screen.getByDisplayValue("Line 1")).toBeTruthy();
    expect(screen.getByDisplayValue("line-2")).toBeTruthy();
    expect(screen.getByDisplayValue("Line 2")).toBeTruthy();
    const existingAssetIdInput = screen.getByDisplayValue("line-1") as HTMLInputElement;
    const suggestedAssetIdInput = screen.getByDisplayValue("line-2") as HTMLInputElement;
    expect(existingAssetIdInput.disabled).toBe(true);
    expect(suggestedAssetIdInput.disabled).toBe(false);
    expect(
      screen.queryByRole("button", { name: "Import Mapping" }),
    ).toBeNull();
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
      "line-2": {
        aliases: ["line two"],
        asset_type: "line",
        display_name: "Line 2",
      },
    });
    expect(onComplete).toHaveBeenCalledTimes(1);
  });
});
