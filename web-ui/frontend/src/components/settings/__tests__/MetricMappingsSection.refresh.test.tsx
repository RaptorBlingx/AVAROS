// @vitest-environment jsdom

import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mockApi = vi.hoisted(() => ({
  listMetricMappings: vi.fn(),
  createMetricMapping: vi.fn(),
  updateMetricMapping: vi.fn(),
  deleteMetricMapping: vi.fn(),
  toFriendlyErrorMessage: vi.fn(() => "error"),
}));

vi.mock("../../../api/client", () => mockApi);

vi.mock("../../common/ThemeProvider", () => ({
  useTheme: () => ({ isDark: false }),
}));

import MetricMappingsSection from "../MetricMappingsSection";

describe("MetricMappingsSection profile refresh", () => {
  beforeEach(() => {
    mockApi.listMetricMappings.mockReset();
    mockApi.createMetricMapping.mockReset();
    mockApi.updateMetricMapping.mockReset();
    mockApi.deleteMetricMapping.mockReset();
    mockApi.listMetricMappings.mockResolvedValue([
      {
        canonical_metric: "energy_per_unit",
        endpoint: "/api/v1/kpis/energy",
        json_path: "$.data.value",
        unit: "kWh/unit",
        transform: null,
      },
    ]);
  });

  it("test_metric_mappings_refetches_on_refresh_key_change", async () => {
    const notify = vi.fn();
    const { rerender } = render(
      <MetricMappingsSection onNotify={notify} refreshKey={0} activeProfile="reneryo" />,
    );

    await waitFor(() => {
      expect(mockApi.listMetricMappings).toHaveBeenCalledTimes(1);
    });

    rerender(
      <MetricMappingsSection onNotify={notify} refreshKey={1} activeProfile="reneryo" />,
    );

    await waitFor(() => {
      expect(mockApi.listMetricMappings).toHaveBeenCalledTimes(2);
    });
  });

  it("test_unconfigured_profile_shows_read_only_hint_and_disables_save_buttons", async () => {
    render(
      <MetricMappingsSection onNotify={vi.fn()} refreshKey={0} activeProfile="unconfigured" />,
    );

    await waitFor(() => {
      expect(
        screen.getByText(
          "Unconfigured profile uses built-in demo data. Metric mappings are not configurable.",
        ),
      ).toBeTruthy();
    });

    const addButton = screen.getByRole("button", { name: "Add Mapping" });
    expect(addButton.hasAttribute("disabled")).toBe(true);

    const saveCreateButtons = screen.getAllByRole("button", {
      name: /Save|Create/i,
    });
    expect(saveCreateButtons.every((button) => button.hasAttribute("disabled"))).toBe(true);
  });
});
