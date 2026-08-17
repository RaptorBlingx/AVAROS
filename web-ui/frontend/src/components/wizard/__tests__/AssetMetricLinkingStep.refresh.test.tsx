// @vitest-environment jsdom

import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mockApi = vi.hoisted(() => ({
  getConfiguredAssets: vi.fn(),
  listMetricMappings: vi.fn(),
  saveConfiguredAssets: vi.fn(),
  toFriendlyErrorMessage: vi.fn(() => "error"),
}));

vi.mock("../../../api/client", () => mockApi);

vi.mock("../wizardPreset", () => ({
  hasWizardPreset: vi.fn().mockResolvedValue(false),
  loadWizardPreset: vi.fn(),
}));

import AssetMetricLinkingStep from "../AssetMetricLinkingStep";

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });
  return { promise, resolve, reject };
}

const metricMapping = {
  canonical_metric: "oee" as const,
  endpoint: "/kpis/{resource_id}/oee",
  json_path: "$.value",
  unit: "%",
  transform: null,
  source: "manual" as const,
};

describe("AssetMetricLinkingStep profile refresh", () => {
  beforeEach(() => {
    mockApi.getConfiguredAssets.mockReset();
    mockApi.listMetricMappings.mockReset();
    mockApi.saveConfiguredAssets.mockReset();
    mockApi.toFriendlyErrorMessage.mockReset();
    mockApi.toFriendlyErrorMessage.mockReturnValue("error");
  });

  it("keeps the newly selected profile when the previous load finishes later", async () => {
    const oldAssets = deferred<{
      asset_mappings: Record<string, {
        display_name: string;
        metric_resources: Record<string, string>;
      }>;
    }>();
    const oldMetrics = deferred<Array<typeof metricMapping>>();
    const newAssets = deferred<{
      asset_mappings: Record<string, {
        display_name: string;
        metric_resources: Record<string, string>;
      }>;
    }>();
    const newMetrics = deferred<Array<typeof metricMapping>>();

    mockApi.getConfiguredAssets
      .mockReturnValueOnce(oldAssets.promise)
      .mockReturnValueOnce(newAssets.promise);
    mockApi.listMetricMappings
      .mockReturnValueOnce(oldMetrics.promise)
      .mockReturnValueOnce(newMetrics.promise);

    const { rerender } = render(
      <AssetMetricLinkingStep
        onComplete={vi.fn()}
        mode="settings"
        profileName="profile-old"
        refreshKey={0}
      />,
    );

    await waitFor(() => {
      expect(mockApi.getConfiguredAssets).toHaveBeenCalledTimes(1);
      expect(mockApi.listMetricMappings).toHaveBeenCalledTimes(1);
    });

    rerender(
      <AssetMetricLinkingStep
        onComplete={vi.fn()}
        mode="settings"
        profileName="profile-new"
        refreshKey={1}
      />,
    );

    await waitFor(() => {
      expect(mockApi.getConfiguredAssets).toHaveBeenCalledTimes(2);
      expect(mockApi.listMetricMappings).toHaveBeenCalledTimes(2);
    });

    newAssets.resolve({
      asset_mappings: {
        "line-new": {
          display_name: "Line New",
          metric_resources: { oee: "new-resource" },
        },
      },
    });
    newMetrics.resolve([metricMapping]);

    await waitFor(() => {
      expect(screen.getByText("Line New")).toBeTruthy();
    });

    // The old profile response arrives after the new profile response.
    oldAssets.resolve({
      asset_mappings: {
        "line-old": {
          display_name: "Line Old",
          metric_resources: { oee: "old-resource" },
        },
      },
    });
    oldMetrics.resolve([metricMapping]);
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(screen.getByText("Line New")).toBeTruthy();
    expect(screen.queryByText("Line Old")).toBeNull();
  });
});
