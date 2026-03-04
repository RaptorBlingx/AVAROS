// @vitest-environment jsdom

import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ThemeProvider } from "../../components/common/ThemeProvider";
import Dashboard from "../Dashboard";

vi.mock("../../components/common/OnboardingOverlay", () => ({
  default: () => null,
}));

vi.mock("../../api/client", () => ({
  ApiError: class ApiError extends Error {
    status: number;

    constructor(message: string, status: number) {
      super(message);
      this.status = status;
    }
  },
  DEFAULT_SITE_ID: "pilot-1",
  getHealth: vi.fn(),
  getStatus: vi.fn(),
  getSiteProgress: vi.fn(),
  toFriendlyErrorMessage: () => "Request failed",
}));

import { getHealth, getSiteProgress, getStatus } from "../../api/client";

function renderDashboard(): void {
  render(
    <MemoryRouter>
      <ThemeProvider>
        <Dashboard />
      </ThemeProvider>
    </MemoryRouter>,
  );
}

describe("Dashboard KPI summary", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.mocked(getHealth).mockResolvedValue({ status: "ok", version: "1.0.0" });
    vi.mocked(getStatus).mockResolvedValue({
      configured: true,
      active_adapter: "mock",
      platform_type: "mock",
      loaded_intents: 12,
      database_connected: true,
      version: "1.0.0",
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders empty KPI state with settings link when no progress exists", async () => {
    vi.mocked(getSiteProgress).mockResolvedValue({
      site_id: "pilot-1",
      baselines_count: 0,
      targets_met: 0,
      targets_total: 0,
      progress: [],
    });

    renderDashboard();

    await waitFor(() => {
      expect(
        screen.getByText(
          "No KPI data available — configure a platform and record a baseline.",
        ),
      ).toBeTruthy();
    });

    expect(screen.getByRole("link", { name: "Configure in Settings" })).toBeTruthy();
    expect(screen.queryByText(/placeholders/i)).toBeNull();
  });

  it("renders live KPI values when progress data exists", async () => {
    vi.mocked(getSiteProgress).mockResolvedValue({
      site_id: "pilot-1",
      baselines_count: 3,
      targets_met: 2,
      targets_total: 3,
      progress: [
        {
          metric: "energy_per_unit",
          site_id: "pilot-1",
          baseline_value: 50,
          current_value: 42,
          target_percent: 8,
          improvement_percent: 16,
          target_met: true,
          unit: "kWh/unit",
          baseline_date: "2026-02-01T00:00:00Z",
          current_date: "2026-03-01T00:00:00Z",
          direction: "improving",
        },
        {
          metric: "material_efficiency",
          site_id: "pilot-1",
          baseline_value: 65,
          current_value: 70,
          target_percent: 5,
          improvement_percent: 7.7,
          target_met: true,
          unit: "%",
          baseline_date: "2026-02-01T00:00:00Z",
          current_date: "2026-03-01T00:00:00Z",
          direction: "improving",
        },
        {
          metric: "co2_total",
          site_id: "pilot-1",
          baseline_value: 1200,
          current_value: 1100,
          target_percent: 10,
          improvement_percent: 8.3,
          target_met: false,
          unit: "kg",
          baseline_date: "2026-02-01T00:00:00Z",
          current_date: "2026-03-01T00:00:00Z",
          direction: "improving",
        },
      ],
    });

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText("42 kWh/unit")).toBeTruthy();
    });

    expect(screen.getByText("70 %")).toBeTruthy();
    expect(screen.getByText("1100 kg")).toBeTruthy();
    expect(screen.getByText("+16.0% vs baseline")).toBeTruthy();
  });
});
