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
  active_adapter: "mock",
  platform_type: "mock",
  loaded_intents: 0,
  database_connected: true,
  version: "0.1.0",
};

function renderStep(platformType: PlatformType = "custom_rest") {
  const onUseReneryoQuickAction = vi.fn();
  render(
    <PlatformSetupStep
      status={STATUS}
      statusLoading={false}
      statusError=""
      platformType={platformType}
      authType="api_key"
      apiUrl=""
      apiKey=""
      formError=""
      testResult={null}
      testError=""
      isTesting={false}
      isSaving={false}
      onChooseExternalApi={vi.fn()}
      onUseMockQuickAction={vi.fn()}
      onUseReneryoQuickAction={onUseReneryoQuickAction}
      onAuthTypeChange={vi.fn()}
      onApiUrlChange={vi.fn()}
      onApiKeyChange={vi.fn()}
      onTestConnection={vi.fn()}
      onSaveAndContinue={vi.fn()}
    />,
  );
  return { onUseReneryoQuickAction };
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
});
