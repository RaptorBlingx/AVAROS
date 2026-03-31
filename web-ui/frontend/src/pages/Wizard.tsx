import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import {
  createPlatformConfig,
  getPlatformConfig,
  getStatus,
  testConnection,
  toFriendlyErrorMessage,
} from "../api/client";
import type {
  ConnectionTestResponse,
  PlatformConfigRequest,
  SystemStatusResponse,
} from "../api/types";
import AssetMetricLinkingStep from "../components/wizard/AssetMetricLinkingStep";
import AssetRegistrationStep from "../components/wizard/AssetRegistrationStep";
import IntentActivationStep from "../components/wizard/IntentActivationStep";
import MetricMappingStep from "../components/wizard/MetricMappingStep";
import PlatformSetupStep from "../components/wizard/PlatformSetupStep";
import SuccessScreen from "../components/wizard/SuccessScreen";
import OnboardingOverlay from "../components/common/OnboardingOverlay";
import Tooltip from "../components/common/Tooltip";
import {
  ONBOARDING_RERUN_EVENT,
  shouldOpenOnboardingForScope,
  type OnboardingRerunDetail,
} from "../components/common/onboarding";

type StepNumber = 1 | 2 | 3 | 4 | 5 | 6;

type WizardState = {
  currentStep: StepNumber;
  authType: "api_key" | "cookie" | "none";
  apiUrl: string;
  apiKey: string;
};

type IntegrationPreset = "mock" | null;
const MOCK_PRESET_URL =
  (import.meta.env.VITE_MOCK_PRESET_URL || "http://reneryo-data-generator-api:8090").trim();

function normalizeUrl(url: string): string {
  return url.trim().replace(/\/+$/, "");
}

function isMockPresetUrl(url: string): boolean {
  return normalizeUrl(url) === normalizeUrl(MOCK_PRESET_URL);
}

function fromBackendAuthType(authType: string | undefined): WizardState["authType"] {
  if (authType === "cookie") {
    return "cookie";
  }
  if (authType === "none") {
    return "none";
  }
  return "api_key";
}

function buildPayload(
  state: WizardState,
  integrationPreset: IntegrationPreset,
): PlatformConfigRequest {
  if (integrationPreset === "mock") {
    return {
      platform_type: "custom_rest",
      api_url: MOCK_PRESET_URL,
      api_key: "",
      extra_settings: {
        auth_type: "none",
      },
    };
  }
  return {
    platform_type: "custom_rest",
    api_url: state.apiUrl.trim(),
    api_key: state.authType === "none" ? "" : state.apiKey.trim(),
    extra_settings: {
      auth_type:
        state.authType === "cookie"
          ? "cookie"
          : state.authType === "none"
          ? "none"
          : "bearer",
    },
  };
}

function enableDashboardBypass(): void {
  sessionStorage.setItem(
    "avaros_skip_wizard_until",
    String(Date.now() + 15000),
  );
}

function validateConnection(
  state: WizardState,
  integrationPreset: IntegrationPreset,
): string {
  if (integrationPreset === "mock") {
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
  if (state.authType !== "none" && !key) {
    return state.authType === "cookie"
      ? "Session cookie is required for this platform."
      : "API key is required for this platform.";
  }
  return "";
}

export default function Wizard() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const forceWizard = searchParams.get("force") === "1";

  const [state, setState] = useState<WizardState>({
    currentStep: 1,
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
  const [completedSteps, setCompletedSteps] = useState<Set<StepNumber>>(
    new Set(),
  );
  const [onboardingOpen, setOnboardingOpen] = useState(false);
  const [integrationPreset, setIntegrationPreset] = useState<IntegrationPreset>(null);
  const effectiveIntegrationPreset: IntegrationPreset = useMemo(
    () => (integrationPreset === "mock" ? "mock" : null),
    [integrationPreset],
  );

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
    const hydrateConnectionForm = async () => {
      try {
        const config = await getPlatformConfig();
        if (config.platform_type === "unconfigured") {
          return;
        }
        setState((prev) => ({
          ...prev,
          apiUrl: config.api_url ?? "",
          authType: fromBackendAuthType(
            typeof config.extra_settings?.auth_type === "string"
              ? config.extra_settings.auth_type
              : undefined,
          ),
          apiKey: "",
        }));
        if (
          isMockPresetUrl(config.api_url ?? "") &&
          fromBackendAuthType(
            typeof config.extra_settings?.auth_type === "string"
              ? config.extra_settings.auth_type
              : undefined,
          ) === "none"
        ) {
          setIntegrationPreset("mock");
        }
      } catch {
        // Wizard can still continue with manual entry when preload fails.
      }
    };

    void hydrateConnectionForm();
  }, []);

  useEffect(() => {
    setHeaderError("");
  }, [state.currentStep]);

  useEffect(() => {
    const onRerun = (event: Event) => {
      const detail = (event as CustomEvent<OnboardingRerunDetail>).detail;
      if (detail && shouldOpenOnboardingForScope(detail.scope, "wizard")) {
        setOnboardingOpen(true);
      }
    };
    window.addEventListener(ONBOARDING_RERUN_EVENT, onRerun);
    return () => window.removeEventListener(ONBOARDING_RERUN_EVENT, onRerun);
  }, []);

  const stepLabel = useMemo(() => {
    if (state.currentStep === 1) return "Platform Setup";
    if (state.currentStep === 2) return "Asset Registration";
    if (state.currentStep === 3) return "Metric Mapping";
    if (state.currentStep === 4) return "Asset-Metric Linking";
    if (state.currentStep === 5) return "Intent Activation";
    return "Complete";
  }, [state.currentStep]);

  const stepItems = useMemo(
    () => [
      "Platform Setup",
      "Asset Registration",
      "Metric Mapping",
      "Asset-Metric Linking",
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
      triggerBlockedNext("Complete platform setup in this step to continue.");
      return;
    }

    if (state.currentStep === 2) {
      triggerBlockedNext("Complete or skip asset registration to continue.");
      return;
    }

    if (state.currentStep === 3) {
      triggerBlockedNext("Complete or skip metric mapping to continue.");
      return;
    }

    if (state.currentStep === 4) {
      triggerBlockedNext("Complete or skip asset-metric linking to continue.");
      return;
    }

    if (state.currentStep === 5) {
      triggerBlockedNext("Complete or skip intent activation to continue.");
      return;
    }
  }, [
    state.currentStep,
    triggerBlockedNext,
  ]);

  const handleTestConnection = useCallback(async () => {
    const validationError = validateConnection(state, effectiveIntegrationPreset);
    setFormError(validationError);
    setTestError("");
    setTestResult(null);
    if (validationError) {
      return;
    }
    setIsTesting(true);
    try {
      const result = await testConnection(
        buildPayload(state, effectiveIntegrationPreset),
      );
      setTestResult(result);
    } catch (error: unknown) {
      setTestError(toFriendlyErrorMessage(error));
    } finally {
      setIsTesting(false);
    }
  }, [effectiveIntegrationPreset, state]);

  const handleSaveConnection = useCallback(async () => {
    const validationError = validateConnection(state, effectiveIntegrationPreset);
    setFormError(validationError);
    setTestError("");
    if (validationError) {
      return;
    }

    setIsSaving(true);
    try {
      await createPlatformConfig(buildPayload(state, effectiveIntegrationPreset));
      markStepComplete(1);
      goToStep(2);
    } catch (error: unknown) {
      setFormError(toFriendlyErrorMessage(error));
    } finally {
      setIsSaving(false);
    }
  }, [effectiveIntegrationPreset, goToStep, markStepComplete, state]);

  const handleAssetRegistrationStepComplete = useCallback(() => {
    markStepComplete(2);
    goToStep(3);
  }, [goToStep, markStepComplete]);

  const handleMetricStepComplete = useCallback(() => {
    markStepComplete(3);
    goToStep(4);
  }, [goToStep, markStepComplete]);

  const handleLinkingStepComplete = useCallback(() => {
    markStepComplete(4);
    goToStep(5);
  }, [goToStep, markStepComplete]);

  const finalizeWizard = useCallback(async () => {
    setHeaderError("");
    try {
      const latestStatus = await getStatus();
      if (!latestStatus.configured) {
        enableDashboardBypass();
      }
      setSuccessStatus(latestStatus);
      markStepComplete(5);
      goToStep(6);
    } catch (error: unknown) {
      setFormError(toFriendlyErrorMessage(error));
    }
  }, [goToStep, markStepComplete]);

  const content = useMemo(() => {
    if (state.currentStep === 1) {
      return (
        <PlatformSetupStep
          status={status}
          statusLoading={loadingStatus}
          statusError={statusError}
          platformType={"custom_rest"}
          isMockPresetActive={effectiveIntegrationPreset === "mock"}
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
          onUseMockQuickAction={() => {
            setIntegrationPreset("mock");
            setFormError("");
            setTestError("");
            setTestResult(null);
            setState((prev) => ({
              ...prev,
              authType: "none",
              apiUrl: MOCK_PRESET_URL,
              apiKey: "",
            }));
          }}
          onUseApiMode={() => {
            setIntegrationPreset(null);
            setFormError("");
            setTestError("");
            setTestResult(null);
            setState((prev) => ({
              ...prev,
              authType: prev.authType === "none" ? "api_key" : prev.authType,
              apiUrl: isMockPresetUrl(prev.apiUrl) ? "" : prev.apiUrl,
              apiKey: "",
            }));
          }}
          onTestConnection={handleTestConnection}
          onSaveAndContinue={handleSaveConnection}
        />
      );
    }

    if (state.currentStep === 2) {
      return (
        <AssetRegistrationStep
          platformType={"custom_rest"}
          integrationPreset={effectiveIntegrationPreset}
          onComplete={handleAssetRegistrationStepComplete}
          onSkip={handleAssetRegistrationStepComplete}
        />
      );
    }

    if (state.currentStep === 3) {
      return (
        <MetricMappingStep
          integrationPreset={effectiveIntegrationPreset}
          onComplete={handleMetricStepComplete}
          onSkip={handleMetricStepComplete}
        />
      );
    }

    if (state.currentStep === 4) {
      return (
        <AssetMetricLinkingStep
          onComplete={handleLinkingStepComplete}
          onSkip={handleLinkingStepComplete}
        />
      );
    }

    if (state.currentStep === 5) {
      return (
        <IntentActivationStep
          onComplete={() => void finalizeWizard()}
          onSkip={() => void finalizeWizard()}
        />
      );
    }

    return (
      <SuccessScreen
        status={successStatus}
        onGoToDashboard={() => {
          if (successStatus && !successStatus.configured) {
            enableDashboardBypass();
          }
          navigate("/", { replace: true });
        }}
      />
    );
  }, [
    finalizeWizard,
    formError,
    handleAssetRegistrationStepComplete,
    handleLinkingStepComplete,
    handleMetricStepComplete,
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
    effectiveIntegrationPreset,
    status,
    statusError,
    successStatus,
    testError,
    testResult,
  ]);

  return (
    <section className="mx-auto w-full max-w-4xl space-y-4">
      <div
        className="brand-hero rounded-xl px-4 py-3 text-sm text-slate-600 backdrop-blur-sm dark:text-slate-300"
        data-onboarding-target="wizard-header"
      >
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

        <div
          className="mt-3 overflow-x-auto"
          data-onboarding-target="wizard-stepper"
        >
          <div className="flex min-w-[640px] gap-2 sm:min-w-0 sm:grid sm:grid-cols-3 lg:grid-cols-5">
            {stepItems.map((item, index) => {
              const stepNumber = (index + 1) as StepNumber;
              const isActive = state.currentStep === stepNumber;
              const isDone = completedSteps.has(stepNumber);
              return (
                <div key={item} className="space-y-1 text-left">
                  <div className="wizard-step-track h-1.5 w-full overflow-hidden rounded-full">
                    <div
                      className={`h-full ${
                        isDone || isActive
                          ? "wizard-step-fill w-full"
                          : "w-0 bg-transparent"
                      } transition-all duration-500 ease-out`}
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

      <div data-onboarding-target="wizard-content">{content}</div>

      <OnboardingOverlay
        open={onboardingOpen}
        steps={[
          {
            title: "Wizard Overview",
            description:
              "Use this guided flow to configure AVAROS end-to-end in a safe order.",
            selector: '[data-onboarding-target="wizard-header"]',
          },
          {
            title: "Progress Stepper",
            description:
              "Track your position and navigate between setup steps with Back and Next controls.",
            selector: '[data-onboarding-target="wizard-stepper"]',
          },
          {
            title: "Step Content",
            description:
              "Each panel collects one required configuration area before activation.",
            selector: '[data-onboarding-target="wizard-content"]',
          },
        ]}
        onClose={() => setOnboardingOpen(false)}
      />
    </section>
  );
}
