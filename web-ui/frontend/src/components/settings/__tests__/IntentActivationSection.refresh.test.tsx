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

  it("test_mock_profile_shows_read_only_hint_and_disables_save_buttons", async () => {
    render(
      <IntentActivationSection onNotify={vi.fn()} refreshKey={0} activeProfile="mock" />,
    );

    await waitFor(() => {
      expect(
        screen.getByText(
          "Mock profile uses built-in demo data. Intent activation is not configurable.",
        ),
      ).toBeTruthy();
    });

    expect(screen.getByRole("button", { name: "Enable All" }).hasAttribute("disabled")).toBe(true);
    expect(screen.getByRole("button", { name: "Disable All" }).hasAttribute("disabled")).toBe(true);

    const switchButton = screen.getByRole("switch");
    expect(switchButton.hasAttribute("disabled")).toBe(true);
  });
});
