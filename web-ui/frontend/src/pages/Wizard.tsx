import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import {
  createPlatformConfig,
  getStatus,
  testConnection,
  toFriendlyErrorMessage,
} from "../api/client";
import type {
  ConnectionTestResponse,
  PlatformConfigRequest,
  PlatformType,
  SystemStatusResponse,
} from "../api/types";
import ConnectionSetupStep from "../components/wizard/ConnectionSetupStep";
import IntentActivationStep from "../components/wizard/IntentActivationStep";
import MetricMappingStep from "../components/wizard/MetricMappingStep";
import PlatformSelectStep from "../components/wizard/PlatformSelectStep";
import SuccessScreen from "../components/wizard/SuccessScreen";
import WelcomeStep from "../components/wizard/WelcomeStep";
import Tooltip from "../components/common/Tooltip";

type StepNumber = 1 | 2 | 3 | 4 | 5 | 6;

type WizardState = {
  currentStep: StepNumber;
  platformType: PlatformType | null;
  authType: "api_key";
  apiUrl: string;
  apiKey: string;
};

function buildPayload(state: WizardState): PlatformConfigRequest {
  const platformType = state.platformType ?? "mock";
  return {
    platform_type: platformType,
    api_url: platformType === "mock" ? "" : state.apiUrl.trim(),
    api_key: platformType === "mock" ? "" : state.apiKey.trim(),
    extra_settings: {},
  };
}

function enableDashboardBypass(): void {
  sessionStorage.setItem("avaros_skip_wizard_until", String(Date.now() + 15000));
}

function validateConnection(state: WizardState): string {
  if (!state.platformType) {
    return "Please select a platform first.";
  }
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
    platformType: null,
    authType: "api_key",
    apiUrl: "",
    apiKey: "",
  });
  const [status, setStatus] = useState<SystemStatusResponse | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [statusError, setStatusError] = useState("");
  const [formError, setFormError] = useState("");
  const [testResult, setTestResult] = useState<ConnectionTestResponse | null>(null);
  const [testError, setTestError] = useState("");
  const [isTesting, setIsTesting] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [successStatus, setSuccessStatus] = useState<SystemStatusResponse | null>(null);
  const [completedSteps, setCompletedSteps] = useState<Set<StepNumber>>(new Set());

  const [headerError, setHeaderError] = useState("");
  const [nextBlocked, setNextBlocked] = useState(false);
  const nextButtonRef = useRef<HTMLButtonElement | null>(null);

  const triggerBlockedNext = useCallback((message: string) => {
    setHeaderError(message);
    setNextBlocked(true);
    nextButtonRef.current?.animate(
      [
        { transform: "translateX(0)" },
        { transform: "translateX(-5px)" },
        { transform: "translateX(5px)" },
        { transform: "translateX(-3px)" },
        { transform: "translateX(3px)" },
        { transform: "translateX(0)" },
      ],
      { duration: 320, iterations: 1, easing: "ease-in-out" },
    );
    window.setTimeout(() => setNextBlocked(false), 420);
  }, []);

  const markStepComplete = useCallback((step: StepNumber) => {
    setCompletedSteps((prev) => {
      const next = new Set(prev);
      next.add(step);
      return next;
    });
  }, []);

  const goToStep = useCallback((step: StepNumber) => {
    setState((prev) => ({ ...prev, currentStep: step }));
  }, []);

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
      setStatusError(toFriendlyErrorMessage(error));
    } finally {
      setLoadingStatus(false);
    }
  }, [forceWizard, navigate]);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  useEffect(() => {
    setHeaderError("");
  }, [state.currentStep]);

  const stepLabel = useMemo(() => {
    if (state.currentStep === 1) return "Setup";
    if (state.currentStep === 2) return "Platform Selection";
    if (state.currentStep === 3) return "Connection Setup";
    if (state.currentStep === 4) return "Metric Mapping";
    if (state.currentStep === 5) return "Intent Activation";
    return "Complete";
  }, [state.currentStep]);

  const stepItems = useMemo(
    () => [
      "Get Started",
      "Platform",
      "Connection",
      "Metric Mapping",
      "Intent Activation",
      "Success",
    ],
    [],
  );

  const goBackStep = useCallback(() => {
    setHeaderError("");
    if (state.currentStep === 1) {
      return;
    }
    goToStep((state.currentStep - 1) as StepNumber);
  }, [goToStep, state.currentStep]);

  const goForwardStep = useCallback(() => {
    setHeaderError("");

    if (state.currentStep === 6) {
      return;
    }

    if (state.currentStep === 1) {
      markStepComplete(1);
      goToStep(2);
      return;
    }

    if (state.currentStep === 2) {
      if (!state.platformType) {
        triggerBlockedNext("Select a platform to continue.");
        return;
      }
      markStepComplete(2);
      goToStep(3);
      return;
    }

    if (state.currentStep === 3) {
      triggerBlockedNext("Complete connection setup in this step to continue.");
      return;
    }

    if (state.currentStep === 4) {
      triggerBlockedNext("Complete or skip metric mapping to continue.");
      return;
    }

    if (state.currentStep === 5) {
      triggerBlockedNext("Complete or skip intent activation to continue.");
      return;
    }
  }, [goToStep, markStepComplete, state.currentStep, state.platformType, triggerBlockedNext]);

  const handlePlatformChange = useCallback((platformType: PlatformType) => {
    setState((prev) => ({ ...prev, platformType }));
    setHeaderError("");
    setFormError("");
    setTestError("");
    setTestResult(null);
  }, []);

  const handlePlatformConfirm = useCallback(() => {
    setHeaderError("");
    if (!state.platformType) {
      triggerBlockedNext("Select a platform to continue.");
      return;
    }
    markStepComplete(2);
    goToStep(3);
  }, [goToStep, markStepComplete, state.platformType, triggerBlockedNext]);

  const handleTestConnection = useCallback(async () => {
    const validationError = validateConnection(state);
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
      setTestError(toFriendlyErrorMessage(error));
    } finally {
      setIsTesting(false);
    }
  }, [state]);

  const handleSaveConnection = useCallback(async () => {
    const validationError = validateConnection(state);
    setFormError(validationError);
    setTestError("");
    if (validationError) {
      return;
    }

    setIsSaving(true);
    try {
      await createPlatformConfig(buildPayload(state));
      markStepComplete(3);
      goToStep(4);
    } catch (error: unknown) {
      setFormError(toFriendlyErrorMessage(error));
    } finally {
      setIsSaving(false);
    }
  }, [goToStep, markStepComplete, state]);

  const handleMetricStepComplete = useCallback(() => {
    markStepComplete(4);
    goToStep(5);
  }, [goToStep, markStepComplete]);

  const finalizeWizard = useCallback(async () => {
    setHeaderError("");
    try {
      const latestStatus = await getStatus();
      if (state.platformType === "mock" || !latestStatus.configured) {
        enableDashboardBypass();
      }
      setSuccessStatus(latestStatus);
      markStepComplete(5);
      goToStep(6);
    } catch (error: unknown) {
      setFormError(toFriendlyErrorMessage(error));
    }
  }, [goToStep, markStepComplete, state.platformType]);

  const content = useMemo(() => {
    if (state.currentStep === 1) {
      return (
        <WelcomeStep
          status={status}
          loading={loadingStatus}
          error={statusError}
          onNext={goForwardStep}
        />
      );
    }

    if (state.currentStep === 2) {
      return (
        <PlatformSelectStep
          value={state.platformType}
          onChange={handlePlatformChange}
          onConfirm={handlePlatformConfirm}
        />
      );
    }

    if (state.currentStep === 3) {
      return (
        <ConnectionSetupStep
          platformType={state.platformType ?? "mock"}
          authType={state.authType}
          apiUrl={state.apiUrl}
          apiKey={state.apiKey}
          formError={formError}
          testResult={testResult}
          testError={testError}
          isTesting={isTesting}
          isSaving={isSaving}
          onAuthTypeChange={(value) => setState((prev) => ({ ...prev, authType: value }))}
          onApiUrlChange={(value) => setState((prev) => ({ ...prev, apiUrl: value }))}
          onApiKeyChange={(value) => setState((prev) => ({ ...prev, apiKey: value }))}
          onTestConnection={handleTestConnection}
          onSave={handleSaveConnection}
        />
      );
    }

    if (state.currentStep === 4) {
      return <MetricMappingStep onComplete={handleMetricStepComplete} onSkip={handleMetricStepComplete} />;
    }

    if (state.currentStep === 5) {
      return <IntentActivationStep onComplete={() => void finalizeWizard()} onSkip={() => void finalizeWizard()} />;
    }

    return (
      <SuccessScreen
        status={successStatus}
        onGoToDashboard={() => {
          if (state.platformType === "mock" || (successStatus && !successStatus.configured)) {
            enableDashboardBypass();
          }
          navigate("/", { replace: true });
        }}
      />
    );
  }, [
    finalizeWizard,
    formError,
    goForwardStep,
    handleMetricStepComplete,
    handlePlatformChange,
    handlePlatformConfirm,
    handleSaveConnection,
    handleTestConnection,
    isSaving,
    isTesting,
    loadingStatus,
    navigate,
    state.apiKey,
    state.apiUrl,
    state.authType,
    state.currentStep,
    state.platformType,
    status,
    statusError,
    successStatus,
    testError,
    testResult,
  ]);

  return (
    <section className="mx-auto w-full max-w-4xl space-y-4">
      <div className="brand-hero rounded-xl px-4 py-3 text-sm text-slate-600 backdrop-blur-sm dark:text-slate-300">
        <div className="flex items-center justify-between gap-3">
          <p className="m-0 inline-flex items-center gap-2">
            <span className="font-semibold text-slate-900 dark:text-slate-100">
              Current Step:
            </span>{" "}
            {stepLabel}
            <Tooltip
              content="Why is this needed? Each step captures required setup inputs so AVAROS can run reliably in your factory."
              ariaLabel="Why this wizard step is needed"
            />
          </p>
          <div className="flex items-center gap-2">
            <p className="m-0 text-xs font-medium text-slate-500 dark:text-slate-400">
              {state.currentStep} / 6
            </p>
            <button
              type="button"
              onClick={goBackStep}
              disabled={state.currentStep === 1}
              className="btn-brand-subtle rounded-lg px-3 py-1.5 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-50"
            >
              Back
            </button>
            <button
              ref={nextButtonRef}
              type="button"
              onClick={goForwardStep}
              disabled={state.currentStep === 6}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-all disabled:cursor-not-allowed disabled:opacity-50 ${
                nextBlocked
                  ? "border border-rose-400 bg-rose-50 text-rose-700 dark:border-rose-500 dark:bg-rose-900/40 dark:text-rose-200"
                  : "btn-brand-primary"
              }`}
            >
              Next
            </button>
          </div>
        </div>

        {headerError && (
          <p className="m-0 mt-2 text-xs font-medium text-rose-700 dark:text-rose-300">
            {headerError}
          </p>
        )}

        <div className="mt-3 overflow-x-auto">
          <div className="flex min-w-[640px] gap-2 sm:min-w-0 sm:grid sm:grid-cols-3 lg:grid-cols-6">
          {stepItems.map((item, index) => {
            const stepNumber = (index + 1) as StepNumber;
            const isActive = state.currentStep === stepNumber;
            const isDone = completedSteps.has(stepNumber);
            return (
              <div key={item} className="space-y-1 text-left">
                <div className="wizard-step-track h-1.5 w-full overflow-hidden rounded-full">
                  <div
                    className={`h-full ${isDone || isActive ? "wizard-step-fill w-full" : "w-0 bg-transparent"} transition-all duration-500 ease-out`}
                  />
                </div>
                <p
                  className={`m-0 text-[10px] ${
                    isActive
                      ? "font-semibold text-sky-700 dark:text-sky-300"
                      : "text-slate-500 dark:text-slate-400"
                  }`}
                >
                  {item}
                </p>
              </div>
            );
          })}
          </div>
        </div>
      </div>

      {content}
    </section>
  );
}
