import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import {
  ApiError,
  createPlatformConfig,
  getStatus,
  testConnection,
} from "../api/client";
import type {
  ConnectionTestResponse,
  PlatformConfigRequest,
  PlatformType,
  SystemStatusResponse,
} from "../api/types";
import ConnectionSetupStep from "../components/wizard/ConnectionSetupStep";
import MetricMappingStep from "../components/wizard/MetricMappingStep";
import PlatformSelectStep from "../components/wizard/PlatformSelectStep";
import SuccessScreen from "../components/wizard/SuccessScreen";
import WelcomeStep from "../components/wizard/WelcomeStep";

type WizardState = {
  currentStep: 1 | 2 | 3 | 4 | 5;
  platformType: PlatformType;
  authType: "api_key";
  apiUrl: string;
  apiKey: string;
};

function toUserMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Something went wrong. Please try again.";
}

function buildPayload(state: WizardState): PlatformConfigRequest {
  return {
    platform_type: state.platformType,
    api_url: state.platformType === "mock" ? "" : state.apiUrl.trim(),
    api_key: state.platformType === "mock" ? "" : state.apiKey.trim(),
    extra_settings: {},
  };
}

function enableDashboardBypass(): void {
  sessionStorage.setItem(
    "avaros_skip_wizard_until",
    String(Date.now() + 15000),
  );
}

function validate(state: WizardState): string {
  if (state.platformType === "mock") {
    return "";
  }
  const url = state.apiUrl.trim();
  const key = state.apiKey.trim();
  if (!url) {
    return "URL is required for this platform.";
  }
  if (!/^https?:\/\//i.test(url)) {
    return "URL must start with http:// or https://.";
  }
  if (!key) {
    return "API key is required for this platform.";
  }
  return "";
}

export default function Wizard() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const forceWizard = searchParams.get("force") === "1";
  const [state, setState] = useState<WizardState>({
    currentStep: 1,
    platformType: "mock",
    authType: "api_key",
    apiUrl: "",
    apiKey: "",
  });
  const [status, setStatus] = useState<SystemStatusResponse | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [statusError, setStatusError] = useState("");
  const [formError, setFormError] = useState("");
  const [testResult, setTestResult] = useState<ConnectionTestResponse | null>(
    null,
  );
  const [testError, setTestError] = useState("");
  const [isTesting, setIsTesting] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [successStatus, setSuccessStatus] =
    useState<SystemStatusResponse | null>(null);

  const loadStatus = useCallback(async () => {
    setLoadingStatus(true);
    setStatusError("");
    try {
      const data = await getStatus();
      if (data.configured && !forceWizard) {
        navigate("/", { replace: true });
        return;
      }
      setStatus(data);
    } catch (error: unknown) {
      setStatusError(toUserMessage(error));
    } finally {
      setLoadingStatus(false);
    }
  }, [forceWizard, navigate]);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  const stepLabel = useMemo(() => {
    if (state.currentStep === 1) {
      return "Setup";
    }
    if (state.currentStep === 2) {
      return "Platform Selection";
    }
    if (state.currentStep === 3) {
      return "Connection Setup";
    }
    if (state.currentStep === 4) {
      return "Metric Mapping";
    }
    return "Complete";
  }, [state.currentStep]);

  const stepItems = useMemo(
    () => [
      "Get Started",
      "Platform",
      "Connection",
      "Metric Mapping",
      "Success",
    ],
    [],
  );

  const goNextStep = useCallback(() => {
    setState((prev) => {
      if (prev.currentStep === 1) {
        return { ...prev, currentStep: 2 };
      }
      if (prev.currentStep === 2) {
        return { ...prev, currentStep: 3 };
      }
      return prev;
    });
  }, []);

  const handlePlatformChange = useCallback((platformType: PlatformType) => {
    setState((prev) => ({
      ...prev,
      platformType,
    }));
    setFormError("");
    setTestError("");
    setTestResult(null);
  }, []);

  const handleTestConnection = useCallback(async () => {
    const validationError = validate(state);
    setFormError(validationError);
    setTestError("");
    setTestResult(null);
    if (validationError) {
      return;
    }
    setIsTesting(true);
    try {
      const result = await testConnection(buildPayload(state));
      setTestResult(result);
    } catch (error: unknown) {
      setTestError(toUserMessage(error));
    } finally {
      setIsTesting(false);
    }
  }, [state]);

  const handleSave = useCallback(async () => {
    const validationError = validate(state);
    setFormError(validationError);
    setTestError("");
    if (validationError) {
      return;
    }
    setIsSaving(true);
    try {
      await createPlatformConfig(buildPayload(state));
      setState((prev) => ({ ...prev, currentStep: 4 }));
    } catch (error: unknown) {
      setFormError(toUserMessage(error));
    } finally {
      setIsSaving(false);
    }
  }, [state]);

  const handleMetricStepComplete = useCallback(async () => {
    try {
      const latestStatus = await getStatus();
      if (state.platformType === "mock" || !latestStatus.configured) {
        enableDashboardBypass();
      }
      setSuccessStatus(latestStatus);
      setState((prev) => ({ ...prev, currentStep: 5 }));
    } catch (error: unknown) {
      setFormError(toUserMessage(error));
    }
  }, [state.platformType]);

  const handleMetricStepSkip = useCallback(async () => {
    await handleMetricStepComplete();
  }, [handleMetricStepComplete]);

  const content = useMemo(() => {
    if (state.currentStep === 1) {
      return (
        <WelcomeStep
          status={status}
          loading={loadingStatus}
          error={statusError}
          onNext={goNextStep}
        />
      );
    }
    if (state.currentStep === 2) {
      return (
        <PlatformSelectStep
          value={state.platformType}
          onChange={handlePlatformChange}
          onNext={goNextStep}
        />
      );
    }
    if (state.currentStep === 3) {
      return (
        <ConnectionSetupStep
          platformType={state.platformType}
          authType={state.authType}
          apiUrl={state.apiUrl}
          apiKey={state.apiKey}
          formError={formError}
          testResult={testResult}
          testError={testError}
          isTesting={isTesting}
          isSaving={isSaving}
          onAuthTypeChange={(value) =>
            setState((prev) => ({ ...prev, authType: value }))
          }
          onApiUrlChange={(value) =>
            setState((prev) => ({ ...prev, apiUrl: value }))
          }
          onApiKeyChange={(value) =>
            setState((prev) => ({ ...prev, apiKey: value }))
          }
          onTestConnection={handleTestConnection}
          onSave={handleSave}
        />
      );
    }
    if (state.currentStep === 4) {
      return (
        <MetricMappingStep
          onComplete={() => void handleMetricStepComplete()}
          onSkip={() => void handleMetricStepSkip()}
        />
      );
    }
    return (
      <SuccessScreen
        status={successStatus}
        onGoToDashboard={() => {
          if (
            state.platformType === "mock" ||
            (successStatus && !successStatus.configured)
          ) {
            enableDashboardBypass();
          }
          navigate("/", { replace: true });
        }}
      />
    );
  }, [
    formError,
    goNextStep,
    handleMetricStepComplete,
    handleMetricStepSkip,
    handlePlatformChange,
    handleSave,
    handleTestConnection,
    isSaving,
    isTesting,
    loadingStatus,
    navigate,
    state.platformType,
    state.apiUrl,
    state.authType,
    state.currentStep,
    state.apiKey,
    status,
    statusError,
    successStatus,
    testError,
    testResult,
  ]);

  return (
    <section className="mx-auto w-full max-w-4xl space-y-4">
      <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600 shadow-sm">
        <div className="flex items-center justify-between gap-3">
          <p className="m-0">
            <span className="font-semibold text-slate-900">Current Step:</span>{" "}
            {stepLabel}
          </p>
          <p className="m-0 text-xs font-medium text-slate-500">
            {state.currentStep} / 5
          </p>
        </div>
        <div className="mt-3 grid grid-cols-5 gap-2">
          {stepItems.map((item, index) => {
            const stepNumber = index + 1;
            const isActive = state.currentStep === stepNumber;
            const isDone = state.currentStep > stepNumber;
            return (
              <div key={item} className="space-y-1">
                <div
                  className={`h-1.5 rounded-full ${
                    isDone || isActive ? "bg-sky-500" : "bg-slate-200"
                  }`}
                />
                <p
                  className={`m-0 text-[10px] ${
                    isActive ? "font-semibold text-sky-700" : "text-slate-500"
                  }`}
                >
                  {item}
                </p>
              </div>
            );
          })}
        </div>
      </div>
      {content}
    </section>
  );
}
