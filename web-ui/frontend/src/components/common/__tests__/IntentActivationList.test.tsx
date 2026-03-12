// @vitest-environment jsdom

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../ThemeProvider", () => ({
  useTheme: () => ({ isDark: false }),
}));

import IntentActivationList, { type IntentViewModel } from "../IntentActivationList";

function renderList(intents: IntentViewModel[]) {
  const onToggle = vi.fn();
  render(
    <IntentActivationList
      intents={intents}
      savingIntent={null}
      bulkAction={null}
      onEnableAll={vi.fn()}
      onDisableAll={vi.fn()}
      onToggle={onToggle}
    />,
  );
  return { onToggle };
}

describe("IntentActivationList", () => {
  it("renders category sections and disables unmapped KPI toggle", () => {
    const intents: IntentViewModel[] = [
      {
        intent_name: "kpi.oee",
        active: false,
        required_metrics: ["oee"],
        metrics_mapped: false,
        category: "kpi",
        allMapped: false,
      },
      {
        intent_name: "control.device.turn_on",
        active: false,
        required_metrics: [],
        metrics_mapped: true,
        category: "action",
        allMapped: true,
      },
      {
        intent_name: "status.system.show",
        active: false,
        required_metrics: [],
        metrics_mapped: true,
        category: "system",
        allMapped: true,
      },
    ];

    renderList(intents);

    expect(screen.getByText("KPI Queries (1)")).toBeTruthy();
    expect(screen.getByText("Device Control (1)")).toBeTruthy();
    expect(screen.getByText("System (1)")).toBeTruthy();
    expect(screen.getByText("Needs Mapping")).toBeTruthy();
    expect(screen.getAllByText("Built-in").length).toBe(2);

    const switches = screen.getAllByRole("switch");
    expect(switches[0].hasAttribute("disabled")).toBe(true);
    expect(switches[0].getAttribute("title")).toBe("Map required metrics first");
  });

  it("allows toggling mapped KPI intent", () => {
    const intents: IntentViewModel[] = [
      {
        intent_name: "kpi.energy.per_unit",
        active: false,
        required_metrics: ["energy_per_unit"],
        metrics_mapped: true,
        category: "kpi",
        allMapped: true,
      },
    ];
    const { onToggle } = renderList(intents);

    const switchButton = screen.getByRole("switch");
    expect(switchButton.hasAttribute("disabled")).toBe(false);
    expect(screen.getByText("Mapped")).toBeTruthy();
    fireEvent.click(switchButton);

    expect(onToggle).toHaveBeenCalledWith("kpi.energy.per_unit", true);
  });
});
