// @vitest-environment jsdom

import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mockApi = vi.hoisted(() => ({
  listEmissionFactors: vi.fn(),
  listEmissionFactorPresets: vi.fn(),
  createEmissionFactor: vi.fn(),
  deleteEmissionFactor: vi.fn(),
  toFriendlyErrorMessage: vi.fn(() => "error"),
}));

vi.mock("../../../api/client", () => mockApi);

vi.mock("../../common/ThemeProvider", () => ({
  useTheme: () => ({ isDark: false }),
}));

import EmissionFactorsSection from "../EmissionFactorsSection";

describe("EmissionFactorsSection profile refresh", () => {
  beforeEach(() => {
    mockApi.listEmissionFactors.mockReset();
    mockApi.listEmissionFactorPresets.mockReset();
    mockApi.createEmissionFactor.mockReset();
    mockApi.deleteEmissionFactor.mockReset();

    mockApi.listEmissionFactors.mockResolvedValue({
      factors: [
        {
          energy_source: "electricity",
          factor: 0.48,
          country: "TR",
          source: "IEA",
          year: 2024,
        },
      ],
    });
    mockApi.listEmissionFactorPresets.mockResolvedValue([
      {
        country: "TR",
        energy_source: "electricity",
        factor: 0.48,
        source: "IEA",
        year: 2024,
      },
    ]);
  });

  it("test_emission_factors_refetches_on_refresh_key_change", async () => {
    const notify = vi.fn();
    const { rerender } = render(
      <EmissionFactorsSection onNotify={notify} refreshKey={0} activeProfile="custom_rest" />,
    );

    await waitFor(() => {
      expect(mockApi.listEmissionFactors).toHaveBeenCalledTimes(1);
      expect(mockApi.listEmissionFactorPresets).toHaveBeenCalledTimes(1);
    });

    rerender(
      <EmissionFactorsSection onNotify={notify} refreshKey={1} activeProfile="custom_rest" />,
    );

    await waitFor(() => {
      expect(mockApi.listEmissionFactors).toHaveBeenCalledTimes(2);
      expect(mockApi.listEmissionFactorPresets).toHaveBeenCalledTimes(2);
    });
  });

  it("test_unconfigured_profile_stays_editable_without_demo_hint", async () => {
    render(
      <EmissionFactorsSection onNotify={vi.fn()} refreshKey={0} activeProfile="unconfigured" />,
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Apply TR Preset/i })).toBeTruthy();
    });

    expect(
      screen.getByRole("button", { name: /Apply TR Preset/i }).hasAttribute(
        "disabled",
      ),
    ).toBe(false);
    expect(
      screen
        .getByRole("button", { name: /Add Custom Factor/i })
        .hasAttribute("disabled"),
    ).toBe(false);

    const deleteButtons = screen.getAllByRole("button", { name: "Delete" });
    expect(deleteButtons.every((button) => button.hasAttribute("disabled"))).toBe(false);
    expect(screen.queryByText(/built-in demo data/i)).toBeNull();
  });
});
