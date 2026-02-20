export const ONBOARDING_STORAGE_KEY = "avaros_onboarding_complete";
export const ONBOARDING_RERUN_EVENT = "avaros:rerun-onboarding";
export const ONBOARDING_VOICE_FOCUS_EVENT = "avaros:onboarding-voice-focus";

export type OnboardingScope =
  | "dashboard"
  | "settings"
  | "wizard"
  | "kpi"
  | "production"
  | "all";

export type OnboardingRerunDetail = {
  scope: OnboardingScope;
};

export type OnboardingVoiceFocusDetail = {
  expanded: boolean;
};

export function resolveOnboardingScope(pathname: string): OnboardingScope {
  if (pathname === "/") {
    return "dashboard";
  }
  if (pathname.startsWith("/settings")) {
    return "settings";
  }
  if (pathname.startsWith("/wizard")) {
    return "wizard";
  }
  if (pathname.startsWith("/kpi")) {
    return "kpi";
  }
  if (pathname.startsWith("/production-data")) {
    return "production";
  }
  return "all";
}

export function shouldOpenOnboardingForScope(
  eventScope: OnboardingScope,
  pageScope: Exclude<OnboardingScope, "all">,
): boolean {
  return eventScope === "all" || eventScope === pageScope;
}

export function dispatchOnboardingRerun(scope: OnboardingScope): void {
  window.dispatchEvent(
    new CustomEvent<OnboardingRerunDetail>(ONBOARDING_RERUN_EVENT, {
      detail: { scope },
    }),
  );
}

export function dispatchOnboardingVoiceFocus(expanded: boolean): void {
  window.dispatchEvent(
    new CustomEvent<OnboardingVoiceFocusDetail>(ONBOARDING_VOICE_FOCUS_EVENT, {
      detail: { expanded },
    }),
  );
}
