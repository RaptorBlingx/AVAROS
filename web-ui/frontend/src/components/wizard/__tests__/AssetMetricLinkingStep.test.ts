import { describe, expect, it } from "vitest";

import {
  applyPresetLinking,
  mergeNativeBindingsForMetricResources,
} from "../AssetMetricLinkingStep";

describe("applyPresetLinking", () => {
  it("replaces preset links and clears obsolete metric resources", () => {
    const rows = [
      {
        assetId: "Meter-1",
        displayName: "Meter 1",
        resources: {
          energy_per_unit: "obsolete-resource",
          energy_total: "old-resource",
        },
      },
      {
        assetId: "Meter-2",
        displayName: "Meter 2",
        resources: {
          energy_per_unit: "obsolete-resource",
          energy_total: "obsolete-resource",
        },
      },
    ];

    expect(
      applyPresetLinking(rows, {
        "Meter-1": { energy_total: "current-resource" },
      }),
    ).toEqual([
      {
        ...rows[0],
        resources: {
          energy_per_unit: "",
          energy_total: "current-resource",
        },
      },
      {
        ...rows[1],
        resources: {
          energy_per_unit: "",
          energy_total: "",
        },
      },
    ]);
  });

  it("does not infer platform-specific native bindings from resource IDs", () => {
    expect(
      mergeNativeBindingsForMetricResources(
        "Electric-Main-Meter",
        {
          native_metric_bindings: {
            oee: { strategy: "custom_native" },
          },
        },
        {
          energy_total: "525c5133-80eb-4c95-8f0c-06e56d2854fe",
        },
      ),
    ).toEqual({
      oee: { strategy: "custom_native" },
    });
  });
});
