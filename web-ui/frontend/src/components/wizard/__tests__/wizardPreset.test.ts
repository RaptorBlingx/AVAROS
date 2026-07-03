import { afterEach, describe, expect, it, vi } from "vitest";

import {
  clearPresetCache,
  hasWizardPreset,
  loadWizardPreset,
} from "../wizardPreset";

const VALID_PRESET = {
  platform: {
    api_url: "https://example.test",
    auth_type: "none",
    credential: "",
  },
  assets: [],
  metrics: {
    endpoint: "/metrics",
    json_path: "$.value",
    mappings: [],
  },
  linking: {},
};

afterEach(() => {
  clearPresetCache();
  vi.unstubAllGlobals();
});

describe("wizard preset loading", () => {
  it("rejects the SPA HTML fallback with a useful message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("<!doctype html><html></html>", {
          status: 200,
          headers: { "content-type": "text/html" },
        }),
      ),
    );

    await expect(loadWizardPreset("reneryo")).rejects.toThrow(
      'No bundled preset is available for profile "reneryo"',
    );
    await expect(hasWizardPreset("reneryo")).resolves.toBe(false);
  });

  it("loads and caches a valid JSON preset", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(VALID_PRESET), {
        status: 200,
        headers: { "content-type": "application/json; charset=utf-8" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(loadWizardPreset("demo")).resolves.toEqual(VALID_PRESET);
    await expect(hasWizardPreset("demo")).resolves.toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("rejects JSON that is not a wizard preset", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ message: "not a preset" }), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
      ),
    );

    await expect(loadWizardPreset("broken")).rejects.toThrow("invalid structure");
  });
});
