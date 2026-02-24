// @vitest-environment jsdom

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mockApi = vi.hoisted(() => ({
  listMetricMappings: vi.fn(),
  createMetricMapping: vi.fn(),
  updateMetricMapping: vi.fn(),
  deleteMetricMapping: vi.fn(),
  getPlatformConfig: vi.fn(),
  testMetricMapping: vi.fn(),
  toFriendlyErrorMessage: vi.fn(() => "error"),
}));

vi.mock("../../../api/client", () => mockApi);

vi.mock("../../common/ThemeProvider", () => ({
  useTheme: () => ({ isDark: false }),
}));

import MetricMappingsSection from "../MetricMappingsSection";

describe("MetricMappingsSection mapping test action", () => {
  beforeEach(() => {
    mockApi.listMetricMappings.mockReset();
    mockApi.createMetricMapping.mockReset();
    mockApi.updateMetricMapping.mockReset();
    mockApi.deleteMetricMapping.mockReset();
    mockApi.getPlatformConfig.mockReset();
    mockApi.testMetricMapping.mockReset();

    mockApi.listMetricMappings.mockResolvedValue([
      {
        canonical_metric: "energy_per_unit",
        endpoint: "/api/v1/kpis/energy",
        json_path: "$.data.value",
        unit: "kWh/unit",
        transform: null,
      },
    ]);

    mockApi.getPlatformConfig.mockResolvedValue({
      platform_type: "reneryo",
      api_url: "https://api.example.com",
      api_key: "****1234",
      extra_settings: { auth_type: "bearer" },
    });
  });

  it("shows loading then success when mapping test passes", async () => {
    let resolveTest:
      | ((value: {
          success: boolean;
          value: number | null;
          raw_response_preview: string;
          error: string | null;
        }) => void)
      | undefined;
    mockApi.testMetricMapping.mockReturnValue(
      new Promise((resolve) => {
        resolveTest = resolve;
      }),
    );

    render(
      <MetricMappingsSection onNotify={vi.fn()} refreshKey={0} activeProfile="reneryo" />,
    );

    await waitFor(() => {
      expect(mockApi.listMetricMappings).toHaveBeenCalledTimes(1);
    });

    const testButtons = screen.getAllByRole("button", {
      name: /test mapping for energy_per_unit/i,
    });
    fireEvent.click(testButtons[0]);

    await waitFor(() => {
      expect(screen.getAllByText("Testing...").length).toBeGreaterThan(0);
    });

    if (!resolveTest) {
      throw new Error("resolveTest was not set");
    }
    resolveTest({
      success: true,
      value: 42.5,
      raw_response_preview: '{"data":{"value":42.5}}',
      error: null,
    });

    await waitFor(() => {
      expect(screen.getAllByText("✓").length).toBeGreaterThan(0);
    });

    const updatedButtons = screen.getAllByRole("button", {
      name: /test mapping for energy_per_unit/i,
    });
    expect(updatedButtons[0].getAttribute("title")).toBe("Value: 42.5");
  });

  it("shows error icon and tooltip when mapping test fails", async () => {
    mockApi.testMetricMapping.mockResolvedValue({
      success: false,
      value: null,
      raw_response_preview: "{}",
      error: "JSONPath did not resolve to a value",
    });

    render(
      <MetricMappingsSection onNotify={vi.fn()} refreshKey={0} activeProfile="reneryo" />,
    );

    await waitFor(() => {
      expect(mockApi.listMetricMappings).toHaveBeenCalledTimes(1);
    });

    const testButtons = screen.getAllByRole("button", {
      name: /test mapping for energy_per_unit/i,
    });
    fireEvent.click(testButtons[0]);

    await waitFor(() => {
      expect(screen.getAllByText("✕").length).toBeGreaterThan(0);
    });

    const updatedButtons = screen.getAllByRole("button", {
      name: /test mapping for energy_per_unit/i,
    });
    expect(updatedButtons[0].getAttribute("title")).toBe(
      "JSONPath did not resolve to a value",
    );
  });

  it("resets mapping test state when endpoint is edited", async () => {
    mockApi.testMetricMapping.mockResolvedValue({
      success: true,
      value: 21,
      raw_response_preview: '{"data":{"value":21}}',
      error: null,
    });

    render(
      <MetricMappingsSection onNotify={vi.fn()} refreshKey={0} activeProfile="reneryo" />,
    );

    await waitFor(() => {
      expect(mockApi.listMetricMappings).toHaveBeenCalledTimes(1);
    });

    const testButtons = screen.getAllByRole("button", {
      name: /test mapping for energy_per_unit/i,
    });
    fireEvent.click(testButtons[0]);

    await waitFor(() => {
      expect(screen.getAllByText("✓").length).toBeGreaterThan(0);
    });

    const endpointInputs = screen.getAllByDisplayValue("/api/v1/kpis/energy");
    fireEvent.change(endpointInputs[0], {
      target: { value: "/api/v2/kpis/energy" },
    });

    await waitFor(() => {
      expect(screen.getAllByText("Test").length).toBeGreaterThan(0);
    });
  });
});
