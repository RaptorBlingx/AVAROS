// @vitest-environment jsdom

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { PlatformType, SystemStatusResponse } from "../../../api/types";
import PlatformSetupStep from "../PlatformSetupStep";

vi.mock("../../common/Tooltip", () => ({
  default: () => null,
}));

vi.mock("../../common/ConnectionTestResult", () => ({
  default: () => null,
}));

vi.mock("../../common/ErrorMessage", () => ({
  default: ({ message }: { message: string }) => <div>{message}</div>,
}));

vi.mock("../../common/LoadingSpinner", () => ({
  default: () => null,
}));

const STATUS: SystemStatusResponse = {
  configured: false,
  active_adapter: "custom_rest",
  platform_type: "custom_rest",
  loaded_intents: 0,
  database_connected: true,
  version: "0.1.0",
};

function renderStep(options?: {
  platformType?: PlatformType;
  isMockPresetActive?: boolean;
}) {
  const platformType = options?.platformType ?? "custom_rest";
  const isMockPresetActive = options?.isMockPresetActive ?? false;
  const onUseReneryoQuickAction = vi.fn();
  const onUseMockQuickAction = vi.fn();
  const onUseApiMode = vi.fn();
  render(
    <PlatformSetupStep
      status={STATUS}
      statusLoading={false}
      statusError=""
      platformType={platformType}
      isMockPresetActive={isMockPresetActive}
      authType="api_key"
      apiUrl=""
      apiKey=""
      formError=""
      testResult={null}
      testError=""
      isTesting={false}
      isSaving={false}
      onUseMockQuickAction={onUseMockQuickAction}
      onUseReneryoQuickAction={onUseReneryoQuickAction}
      onUseApiMode={onUseApiMode}
      onAuthTypeChange={vi.fn()}
      onApiUrlChange={vi.fn()}
      onApiKeyChange={vi.fn()}
      onTestConnection={vi.fn()}
      onSaveAndContinue={vi.fn()}
    />,
  );
  return { onUseReneryoQuickAction, onUseMockQuickAction, onUseApiMode };
}

describe("PlatformSetupStep", () => {
  it("always renders the RENERYO preset action", () => {
    renderStep();
    expect(screen.getByRole("button", { name: "Use RENERYO" })).toBeTruthy();
  });

  it("always renders the Mock preset action", () => {
    renderStep();
    expect(screen.getByRole("button", { name: "Use Mock" })).toBeTruthy();
  });

  it("triggers preset callback when RENERYO action is clicked", () => {
    const { onUseReneryoQuickAction } = renderStep();
    fireEvent.click(screen.getByRole("button", { name: "Use RENERYO" }));
    expect(onUseReneryoQuickAction).toHaveBeenCalledTimes(1);
  });

  it("triggers preset callback when Mock action is clicked", () => {
    const { onUseMockQuickAction } = renderStep();
    fireEvent.click(screen.getByRole("button", { name: "Use Mock" }));
    expect(onUseMockQuickAction).toHaveBeenCalledTimes(1);
  });

  it("triggers callback when Use API is clicked", () => {
    const { onUseApiMode } = renderStep();
    fireEvent.click(screen.getByRole("button", { name: "Use API" }));
    expect(onUseApiMode).toHaveBeenCalledTimes(1);
  });

  it("hides API form controls while mock preset is active", () => {
    renderStep({ isMockPresetActive: true });
    expect(screen.queryByLabelText("API URL")).toBeNull();
    expect(screen.queryByRole("button", { name: "Test Connection" })).toBeNull();
  });
});
