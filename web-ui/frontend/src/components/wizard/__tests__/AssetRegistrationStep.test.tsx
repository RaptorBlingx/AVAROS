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
      platform_type: "reneryo",
      supports_discovery: true,
      discovery_source: "adapter",
      assets: [
        {
          asset_id: "line-2",
          display_name: "Line 2",
          asset_type: "line",
          aliases: ["line two"],
          metadata: {},
        },
      ],
      registered_assets: [],
      discovery_error: "",
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

  it("shows registered logical rows for reneryo and keeps discovery as guidance only", async () => {
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
    expect(screen.queryByDisplayValue("line-2")).toBeNull();
    expect(
      screen.getByText(/Use Resource Linking to validate and map them/i),
    ).toBeTruthy();
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
    await waitFor(() => {
      expect(screen.getByDisplayValue("line-2")).toBeTruthy();
    });

    fireEvent.click(screen.getByRole("button", { name: "Save & Continue" }));

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

  it("shows a reneryo notice when live discovery is unavailable", async () => {
    mockApi.discoverAssets.mockResolvedValue({
      platform_type: "reneryo",
      supports_discovery: false,
      discovery_source: "registered",
      assets: [],
      registered_assets: [
        {
          asset_id: "line-1",
          display_name: "Line 1",
          asset_type: "line",
          aliases: ["line one"],
          metadata: {},
        },
      ],
      discovery_error: "",
      existing_mappings: {},
    });

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

    expect(
      screen.getByText(/Live RENERYO discovery is unavailable/i),
    ).toBeTruthy();
    expect(screen.getByDisplayValue("line-1")).toBeTruthy();
    expect(
      screen.queryByText(/Discovered assets were pre-filled/i),
    ).toBeNull();
  });

  it("preserves hidden registered mappings on save for reneryo", async () => {
    const onComplete = vi.fn();
    render(
      <AssetRegistrationStep
        platformType="reneryo"
        onComplete={onComplete}
        onSkip={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(mockApi.getConfiguredAssets).toHaveBeenCalledTimes(1);
    });

    fireEvent.click(screen.getByRole("button", { name: "Save & Continue" }));

    await waitFor(() => {
      expect(mockApi.saveConfiguredAssets).toHaveBeenCalledTimes(1);
    });
    expect(mockApi.saveConfiguredAssets).toHaveBeenCalledWith({
      "line-1": {
        display_name: "Line 1",
        asset_type: "line",
        aliases: ["line one"],
      },
    });
    expect(onComplete).toHaveBeenCalledTimes(1);
  });

  it("hides technical seu UUID rows from primary reneryo registration list", async () => {
    mockApi.getConfiguredAssets.mockResolvedValue({
      asset_mappings: {
        "line-1": {
          display_name: "Line 1",
          asset_type: "line",
          aliases: ["line one"],
        },
        "00b4057f-59bc-4fe2-9eda-ad904f21b689": {
          display_name: "Seu 4 for reporting",
          asset_type: "machine",
          aliases: ["seu 4 for reporting"],
        },
      },
    });

    render(
      <AssetRegistrationStep
        platformType="reneryo"
        onComplete={vi.fn()}
        onSkip={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByDisplayValue("line-1")).toBeTruthy();
    });

    expect(
      screen.queryByDisplayValue("00b4057f-59bc-4fe2-9eda-ad904f21b689"),
    ).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Save & Continue" }));

    await waitFor(() => {
      expect(mockApi.saveConfiguredAssets).toHaveBeenCalledTimes(1);
    });
    expect(mockApi.saveConfiguredAssets).toHaveBeenCalledWith({
      "line-1": {
        display_name: "Line 1",
        asset_type: "line",
        aliases: ["line one"],
      },
      "00b4057f-59bc-4fe2-9eda-ad904f21b689": {
        display_name: "Seu 4 for reporting",
        asset_type: "machine",
        aliases: ["seu 4 for reporting"],
      },
    });
  });
});
