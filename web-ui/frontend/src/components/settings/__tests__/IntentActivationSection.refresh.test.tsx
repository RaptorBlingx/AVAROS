// @vitest-environment jsdom

import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mockApi = vi.hoisted(() => ({
  getIntents: vi.fn(),
  listMetricMappings: vi.fn(),
  setIntentActive: vi.fn(),
  toFriendlyErrorMessage: vi.fn(() => "error"),
}));

vi.mock("../../../api/client", () => mockApi);

vi.mock("../../common/ThemeProvider", () => ({
  useTheme: () => ({ isDark: false }),
}));

import IntentActivationSection from "../IntentActivationSection";

describe("IntentActivationSection profile refresh", () => {
  beforeEach(() => {
    mockApi.getIntents.mockReset();
    mockApi.listMetricMappings.mockReset();
    mockApi.setIntentActive.mockReset();

    mockApi.getIntents.mockResolvedValue([
      {
        intent_name: "kpi.oee",
        active: true,
        required_metrics: ["oee"],
        metrics_mapped: true,
        category: "kpi",
      },
    ]);
    mockApi.listMetricMappings.mockResolvedValue([
      {
        canonical_metric: "oee",
        endpoint: "/api/oee",
        json_path: "$.value",
        unit: "%",
        transform: null,
      },
    ]);
  });

  it("test_intent_activation_refetches_on_refresh_key_change", async () => {
    const notify = vi.fn();
    const { rerender } = render(
      <IntentActivationSection onNotify={notify} refreshKey={0} activeProfile="reneryo" />,
    );

    await waitFor(() => {
      expect(mockApi.getIntents).toHaveBeenCalledTimes(1);
      expect(mockApi.listMetricMappings).toHaveBeenCalledTimes(1);
    });

    rerender(
      <IntentActivationSection onNotify={notify} refreshKey={1} activeProfile="reneryo" />,
    );

    await waitFor(() => {
      expect(mockApi.getIntents).toHaveBeenCalledTimes(2);
      expect(mockApi.listMetricMappings).toHaveBeenCalledTimes(2);
    });
  });

  it("test_unconfigured_profile_shows_read_only_hint_and_disables_save_buttons", async () => {
    render(
      <IntentActivationSection onNotify={vi.fn()} refreshKey={0} activeProfile="unconfigured" />,
    );

    await waitFor(() => {
      expect(
        screen.getByText(
          "Unconfigured profile uses built-in demo data. Intent activation is not configurable.",
        ),
      ).toBeTruthy();
    });

    expect(screen.getByRole("button", { name: "Enable All" }).hasAttribute("disabled")).toBe(true);
    expect(screen.getByRole("button", { name: "Disable All" }).hasAttribute("disabled")).toBe(true);

    const switchButton = screen.getByRole("switch");
    expect(switchButton.hasAttribute("disabled")).toBe(true);
  });

  it("test_enable_all_skips_unmapped_kpi_intents", async () => {
    mockApi.getIntents.mockResolvedValue([
      {
        intent_name: "kpi.oee",
        active: false,
        required_metrics: ["oee"],
        metrics_mapped: true,
        category: "kpi",
      },
      {
        intent_name: "kpi.energy.total",
        active: false,
        required_metrics: ["energy_total"],
        metrics_mapped: false,
        category: "kpi",
      },
      {
        intent_name: "control.device.turn_on",
        active: false,
        required_metrics: [],
        metrics_mapped: true,
        category: "action",
      },
      {
        intent_name: "status.system.show",
        active: false,
        required_metrics: [],
        metrics_mapped: true,
        category: "system",
      },
    ]);
    mockApi.listMetricMappings.mockResolvedValue([
      {
        canonical_metric: "oee",
        endpoint: "/api/oee",
        json_path: "$.value",
        unit: "%",
        transform: null,
      },
    ]);
    mockApi.setIntentActive.mockResolvedValue({
      intent_name: "kpi.oee",
      active: true,
      required_metrics: ["oee"],
      metrics_mapped: true,
      category: "kpi",
    });
    const notify = vi.fn();

    render(
      <IntentActivationSection onNotify={notify} refreshKey={0} activeProfile="reneryo" />,
    );

    await waitFor(() => {
      expect(mockApi.getIntents).toHaveBeenCalledTimes(1);
    });

    const enableAllBtn = await screen.findByRole("button", { name: "Enable All" });
    enableAllBtn.click();

    await waitFor(() => {
      expect(mockApi.setIntentActive).toHaveBeenCalledTimes(3);
    });

    const updatedIntents = mockApi.setIntentActive.mock.calls.map((call) => call[0]);
    expect(updatedIntents).toContain("kpi.oee");
    expect(updatedIntents).toContain("control.device.turn_on");
    expect(updatedIntents).toContain("status.system.show");
    expect(updatedIntents).not.toContain("kpi.energy.total");
    expect(notify).toHaveBeenCalledWith(
      "success",
      "Enabled eligible intents. 1 KPI intents still need metric mappings.",
    );
  });
});
