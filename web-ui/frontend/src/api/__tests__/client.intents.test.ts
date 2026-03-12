// @vitest-environment jsdom

import { beforeEach, describe, expect, it, vi } from "vitest";

import { getIntents } from "../client";

function okJsonResponse(body: unknown): Response {
  return {
    ok: true,
    status: 200,
    json: async () => body,
  } as Response;
}

describe("getIntents category normalization", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("defaults missing category to kpi for array responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        okJsonResponse([
          {
            intent_name: "kpi.oee",
            active: true,
            display_name: "OEE",
            required_metrics: ["oee"],
            metrics_mapped: true,
          },
        ]),
      ),
    );

    const intents = await getIntents();

    expect(intents).toHaveLength(1);
    expect(intents[0].category).toBe("kpi");
  });

  it("defaults unknown category to kpi for wrapped responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        okJsonResponse({
          intents: [
            {
              intent_name: "status.system.show",
              active: true,
              display_name: "System Status",
              required_metrics: [],
              metrics_mapped: true,
              category: "legacy",
            },
          ],
        }),
      ),
    );

    const intents = await getIntents();

    expect(intents).toHaveLength(1);
    expect(intents[0].category).toBe("kpi");
  });
});
