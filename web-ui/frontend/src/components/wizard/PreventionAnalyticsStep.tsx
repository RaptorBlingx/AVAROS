import { useCallback, useEffect, useMemo, useState } from "react";

import {
  getPreventionConfig,
  savePreventionConfig,
  testPreventionConnection,
  toFriendlyErrorMessage,
} from "../../api/client";
import type {
  PreventionConfigResponse,
  PreventionTestResponse,
} from "../../api/types";
import ErrorMessage from "../common/ErrorMessage";
import LoadingSpinner from "../common/LoadingSpinner";
import Tooltip from "../common/Tooltip";

type PreventionAnalyticsStepProps = {
  onComplete: () => void;
  onSkip: () => void;
};

function normalizeState(value: string): string {
  return value ? value.replace(/_/g, " ") : "unknown";
}

function stateTone(value: string): string {
  const state = value.toLowerCase();
  if (state === "healthy" || state === "fresh") {
    return "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200";
  }
  if (state === "disabled" || state === "missing" || state === "unknown") {
    return "border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-300";
  }
  return "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200";
}

export default function PreventionAnalyticsStep({
  onComplete,
  onSkip,
}: PreventionAnalyticsStepProps) {
  const [config, setConfig] = useState<PreventionConfigResponse | null>(null);
  const [enabled, setEnabled] = useState(false);
  const [endpointUrl, setEndpointUrl] = useState("");
  const [authMode, setAuthMode] = useState<
    "none" | "bearer" | "keycloak_client_credentials"
  >("none");
  const [authToken, setAuthToken] = useState("");
  const [authTokenDirty, setAuthTokenDirty] = useState(false);
  const [keycloakTokenUrl, setKeycloakTokenUrl] = useState("");
  const [keycloakClientId, setKeycloakClientId] = useState("");
  const [keycloakClientSecret, setKeycloakClientSecret] = useState("");
  const [keycloakClientSecretDirty, setKeycloakClientSecretDirty] = useState(false);
  const [keycloakScope, setKeycloakScope] = useState("");
  const [dataMaxAgeMinutes, setDataMaxAgeMinutes] = useState("1440");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState("");
  const [testResult, setTestResult] = useState<PreventionTestResponse | null>(
    null,
  );

  const loadConfig = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await getPreventionConfig();
      setConfig(response);
      setEnabled(response.enabled);
      setEndpointUrl(response.endpoint_url ?? "");
      setAuthMode(
        response.auth_mode === "bearer" ||
          response.auth_mode === "keycloak_client_credentials"
          ? response.auth_mode
          : "none",
      );
      setDataMaxAgeMinutes(String(response.data_max_age_minutes || 1440));
      setAuthToken("");
      setAuthTokenDirty(false);
      setKeycloakTokenUrl(response.keycloak_token_url ?? "");
      setKeycloakClientId(response.keycloak_client_id ?? "");
      setKeycloakClientSecret("");
      setKeycloakClientSecretDirty(false);
      setKeycloakScope(response.keycloak_scope ?? "");
    } catch (err: unknown) {
      setError(toFriendlyErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadConfig();
  }, [loadConfig]);

  const validationError = useMemo(() => {
    const freshness = Number(dataMaxAgeMinutes);
    if (!Number.isInteger(freshness) || freshness < 1) {
      return "Data freshness limit must be a whole number greater than zero.";
    }
    if (!enabled) {
      return "";
    }
    const normalizedUrl = endpointUrl.trim();
    if (!normalizedUrl) {
      return "PREVENTION endpoint URL is required when analytics are enabled.";
    }
    if (!/^https?:\/\//i.test(normalizedUrl)) {
      return "PREVENTION endpoint URL must start with http:// or https://.";
    }
    if (
      authMode === "bearer" &&
      !authToken.trim() &&
      !config?.auth_token_configured
    ) {
      return "Auth token is required when Bearer token authentication is selected.";
    }
    if (authMode === "keycloak_client_credentials") {
      if (!keycloakTokenUrl.trim()) {
        return "Keycloak token URL is required for Keycloak authentication.";
      }
      if (!/^https?:\/\//i.test(keycloakTokenUrl.trim())) {
        return "Keycloak token URL must start with http:// or https://.";
      }
      if (!keycloakClientId.trim()) {
        return "Keycloak client ID is required for Keycloak authentication.";
      }
      if (
        !keycloakClientSecret.trim() &&
        !config?.keycloak_client_secret_configured
      ) {
        return "Keycloak client secret is required for Keycloak authentication.";
      }
    }
    return "";
  }, [
    authMode,
    authToken,
    config?.auth_token_configured,
    config?.keycloak_client_secret_configured,
    dataMaxAgeMinutes,
    enabled,
    endpointUrl,
    keycloakClientId,
    keycloakClientSecret,
    keycloakTokenUrl,
  ]);

  const buildPayload = useCallback(
    (nextEnabled: boolean) => {
      const payload: {
        enabled: boolean;
        endpoint_url: string;
        data_max_age_minutes: number;
        auth_mode: "none" | "bearer" | "keycloak_client_credentials";
        auth_token?: string | null;
        clear_auth_token?: boolean;
        keycloak_token_url?: string;
        keycloak_client_id?: string;
        keycloak_client_secret?: string | null;
        clear_keycloak_client_secret?: boolean;
        keycloak_scope?: string;
      } = {
        enabled: nextEnabled,
        endpoint_url: nextEnabled ? endpointUrl.trim() : "",
        data_max_age_minutes: Number(dataMaxAgeMinutes),
        auth_mode: nextEnabled ? authMode : "none",
      };
      if (payload.auth_mode === "bearer" && authTokenDirty) {
        const token = authToken.trim();
        if (token) {
          payload.auth_token = token;
        } else {
          payload.clear_auth_token = true;
        }
      }
      if (payload.auth_mode === "keycloak_client_credentials") {
        payload.keycloak_token_url = keycloakTokenUrl.trim();
        payload.keycloak_client_id = keycloakClientId.trim();
        payload.keycloak_scope = keycloakScope.trim();
        if (keycloakClientSecretDirty) {
          const secret = keycloakClientSecret.trim();
          if (secret) {
            payload.keycloak_client_secret = secret;
          } else {
            payload.clear_keycloak_client_secret = true;
          }
        }
      }
      return payload;
    },
    [
      authMode,
      authToken,
      authTokenDirty,
      dataMaxAgeMinutes,
      endpointUrl,
      keycloakClientId,
      keycloakClientSecret,
      keycloakClientSecretDirty,
      keycloakScope,
      keycloakTokenUrl,
    ],
  );

  const handleTest = useCallback(async () => {
    setError(validationError);
    setTestResult(null);
    if (validationError) {
      return;
    }
    setTesting(true);
    try {
      const response = await testPreventionConnection({
        endpoint_url: endpointUrl.trim(),
        auth_mode: authMode,
        auth_token: authMode === "bearer" ? authToken.trim() : "",
        keycloak_token_url:
          authMode === "keycloak_client_credentials"
            ? keycloakTokenUrl.trim()
            : "",
        keycloak_client_id:
          authMode === "keycloak_client_credentials"
            ? keycloakClientId.trim()
            : "",
        keycloak_client_secret:
          authMode === "keycloak_client_credentials"
            ? keycloakClientSecret.trim()
            : "",
        keycloak_scope:
          authMode === "keycloak_client_credentials"
            ? keycloakScope.trim()
            : "",
      });
      setTestResult(response);
    } catch (err: unknown) {
      setError(toFriendlyErrorMessage(err));
    } finally {
      setTesting(false);
    }
  }, [
    authMode,
    authToken,
    endpointUrl,
    keycloakClientId,
    keycloakClientSecret,
    keycloakScope,
    keycloakTokenUrl,
    validationError,
  ]);

  const handleSave = useCallback(async () => {
    setError(validationError);
    if (validationError) {
      return;
    }
    setSaving(true);
    try {
      await savePreventionConfig(buildPayload(enabled));
      onComplete();
    } catch (err: unknown) {
      setError(toFriendlyErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }, [buildPayload, enabled, onComplete, validationError]);

  const handleSkip = useCallback(async () => {
    setSaving(true);
    setError("");
    try {
      await savePreventionConfig(buildPayload(false));
      onSkip();
    } catch (err: unknown) {
      setError(toFriendlyErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }, [buildPayload, onSkip]);

  return (
    <section className="space-y-4">
      <header className="brand-hero rounded-2xl p-6 backdrop-blur-sm">
        <p className="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-sky-700 dark:text-sky-300">
          Step 5 of 7
        </p>
        <div className="mt-2 inline-flex items-center gap-2">
          <h2 className="m-0 text-2xl font-semibold text-slate-900 dark:text-slate-100">
            PREVENTION Analytics
          </h2>
          <Tooltip
            content="PREVENTION is an optional external analytics service. Enable this only when a PREVENTION deployment is running and reachable from AVAROS."
            ariaLabel="Why PREVENTION analytics is needed"
          />
        </div>
        <p className="m-0 mt-2 text-sm text-slate-600 dark:text-slate-300">
          Connect AVAROS to a PREVENTION analytics service after metric mapping so anomaly and drift insights can use the configured time-series data.
        </p>
        <p className="m-0 mt-2 text-xs text-slate-500 dark:text-slate-400">
          If your AVAROS package was delivered without a PREVENTION runtime, leave this disabled unless your site administrator provides a PREVENTION endpoint.
        </p>
      </header>

      <div className="brand-hero rounded-2xl p-6 backdrop-blur-sm">
        {loading ? (
          <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900 opacity-50">
            <LoadingSpinner label="Loading PREVENTION settings..." size="sm" />
          </div>
        ) : (
          <div className="space-y-5">
            {error && (
              <ErrorMessage
                title="PREVENTION configuration error"
                message={error}
                onRetry={() => void loadConfig()}
              />
            )}

            {config?.env_override && (
              <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
                PREVENTION_URL is set in the service environment, so runtime traffic uses that endpoint until the environment override is removed.
              </div>
            )}

            {config && (
              <div className="grid gap-3 sm:grid-cols-2">
                <div className={`rounded-xl border px-4 py-3 ${stateTone(config.state)}`}>
                  <div className="flex items-center gap-2">
                    <p className="m-0 text-xs font-semibold uppercase">Connection</p>
                    <Tooltip
                      content="Shows whether AVAROS can reach the PREVENTION HTTP/GraphQL service at the configured endpoint."
                      ariaLabel="What PREVENTION connection status means"
                    />
                  </div>
                  <p className="m-0 mt-1 text-base font-semibold capitalize">
                    {normalizeState(config.state)}
                  </p>
                  <p className="m-0 mt-1 text-xs">{config.message}</p>
                </div>
                <div className={`rounded-xl border px-4 py-3 ${stateTone(config.data_state)}`}>
                  <div className="flex items-center gap-2">
                    <p className="m-0 text-xs font-semibold uppercase">Data Feed</p>
                    <Tooltip
                      content="Shows whether AVAROS has generated the export manifest and metric files that PREVENTION loads for analysis. Missing means no export has been created yet."
                      ariaLabel="What PREVENTION data feed status means"
                    />
                  </div>
                  <p className="m-0 mt-1 text-base font-semibold capitalize">
                    {normalizeState(config.data_state)}
                  </p>
                  <p className="m-0 mt-1 text-xs">{config.data_message}</p>
                </div>
              </div>
            )}

            <div className="rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900 dark:border-sky-800 dark:bg-sky-950/40 dark:text-sky-100">
              <p className="m-0 font-semibold">When should this be enabled?</p>
              <p className="m-0 mt-1">
                Enable PREVENTION only when your deployment includes a running PREVENTION service. The endpoint URL and optional token usually come from the PREVENTION administrator, the local Docker/compose deployment, or the consortium-provided platform owner.
              </p>
              <p className="m-0 mt-2 text-xs">
                Current AVAROS support covers PREVENTION-backed anomaly detection and drift monitoring. Predictive or prescriptive workflows require a provider-supplied PREVENTION model/API contract and are not enabled here automatically.
              </p>
            </div>

            <label className="flex items-start gap-3 rounded-xl border border-slate-200 bg-white/70 p-4 dark:border-slate-700 dark:bg-slate-900/60">
              <input
                type="checkbox"
                checked={enabled}
                onChange={(event) => setEnabled(event.target.checked)}
                className="mt-1 h-4 w-4"
              />
              <span>
                <span className="block text-sm font-semibold text-slate-900 dark:text-slate-100">
                  Enable PREVENTION analytics
                  <Tooltip
                    content="Turn this on only when PREVENTION is installed and reachable. If not, keep it off; AVAROS still works without PREVENTION, but anomaly and drift analytics will be unavailable."
                    ariaLabel="When to enable PREVENTION analytics"
                    className="ml-2 align-middle"
                  />
                </span>
                <span className="block text-xs text-slate-600 dark:text-slate-300">
                  Enables anomaly and drift intents when a PREVENTION endpoint is reachable.
                </span>
              </span>
            </label>

            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">
                PREVENTION Endpoint URL
                <Tooltip
                  content="The base URL for the PREVENTION service, for example http://prevention:8081 inside Docker or an HTTPS URL supplied by the platform owner."
                  ariaLabel="Where to get the PREVENTION endpoint URL"
                  className="ml-2 align-middle"
                />
                <input
                  type="url"
                  value={endpointUrl}
                  onChange={(event) => setEndpointUrl(event.target.value)}
                  disabled={!enabled}
                  placeholder="http://prevention:8081"
                  className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                />
              </label>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">
                Data Freshness Limit
                <Tooltip
                  content="Maximum age, in minutes, for AVAROS data exported to PREVENTION. If the latest export is older than this, AVAROS reports the data feed as stale."
                  ariaLabel="What PREVENTION data freshness limit means"
                  className="ml-2 align-middle"
                />
                <input
                  type="number"
                  min={1}
                  value={dataMaxAgeMinutes}
                  onChange={(event) => setDataMaxAgeMinutes(event.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                />
              </label>
            </div>

            <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">
              PREVENTION Auth Mode
              <Tooltip
                content="Use No authentication for local no-auth PREVENTION, Bearer token for a pre-issued token, or Keycloak/OIDC when the PREVENTION administrator gives AVAROS client-credentials details."
                ariaLabel="How to choose PREVENTION authentication mode"
                className="ml-2 align-middle"
              />
              <select
                value={authMode}
                onChange={(event) =>
                  setAuthMode(
                    event.target.value as
                      | "none"
                      | "bearer"
                      | "keycloak_client_credentials",
                  )
                }
                disabled={!enabled}
                className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
              >
                <option value="none">No authentication</option>
                <option value="bearer">Bearer token</option>
                <option value="keycloak_client_credentials">
                  Keycloak/OIDC client credentials
                </option>
              </select>
            </label>

            {authMode === "bearer" && (
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">
                Auth Token Optional
                <Tooltip
                  content="Optional pre-issued bearer token for secured PREVENTION deployments. The platform owner or PREVENTION administrator provides this. Leave blank when a masked token is already configured and should be kept."
                  ariaLabel="Where to get the PREVENTION auth token"
                  className="ml-2 align-middle"
                />
                <input
                  type="password"
                  value={authToken}
                  onChange={(event) => {
                    setAuthToken(event.target.value);
                    setAuthTokenDirty(true);
                  }}
                  disabled={!enabled}
                  placeholder={
                    config?.auth_token_configured
                      ? `${config.auth_token_masked} configured; leave blank to keep`
                      : "Bearer token for protected deployments"
                  }
                  className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                />
              </label>
            )}

            {authMode === "keycloak_client_credentials" && (
              <div className="rounded-xl border border-slate-200 bg-white/70 p-4 dark:border-slate-700 dark:bg-slate-900/60">
                <div className="flex items-center gap-2">
                  <p className="m-0 text-sm font-semibold text-slate-900 dark:text-slate-100">
                    Keycloak/OIDC Client Credentials
                  </p>
                  <Tooltip
                    content="These values come from the PREVENTION or Keycloak administrator. AVAROS exchanges them for a short-lived access token before calling PREVENTION GraphQL."
                    ariaLabel="What Keycloak client credentials do"
                  />
                </div>
                <div className="mt-4 grid gap-4 sm:grid-cols-2">
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">
                    Keycloak Token URL
                    <input
                      type="url"
                      value={keycloakTokenUrl}
                      onChange={(event) => setKeycloakTokenUrl(event.target.value)}
                      disabled={!enabled}
                      placeholder="https://keycloak.example.com/realms/wasabi/protocol/openid-connect/token"
                      className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                    />
                  </label>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">
                    Keycloak Client ID
                    <input
                      type="text"
                      value={keycloakClientId}
                      onChange={(event) => setKeycloakClientId(event.target.value)}
                      disabled={!enabled}
                      placeholder="avaros-prevention-client"
                      className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                    />
                  </label>
                </div>
                <div className="mt-4 grid gap-4 sm:grid-cols-2">
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">
                    Keycloak Client Secret
                    <input
                      type="password"
                      value={keycloakClientSecret}
                      onChange={(event) => {
                        setKeycloakClientSecret(event.target.value);
                        setKeycloakClientSecretDirty(true);
                      }}
                      disabled={!enabled}
                      placeholder={
                        config?.keycloak_client_secret_configured
                          ? `${config.keycloak_client_secret_masked} configured; leave blank to keep`
                          : "Client secret"
                      }
                      className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                    />
                  </label>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">
                    Keycloak Scope Optional
                    <input
                      type="text"
                      value={keycloakScope}
                      onChange={(event) => setKeycloakScope(event.target.value)}
                      disabled={!enabled}
                      placeholder="openid"
                      className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                    />
                  </label>
                </div>
              </div>
            )}

            {testResult && (
              <div className={`rounded-xl border px-4 py-3 text-sm ${stateTone(testResult.state)}`}>
                <p className="m-0 font-semibold">
                  Test {testResult.success ? "passed" : "failed"}: {normalizeState(testResult.state)}
                </p>
                <p className="m-0 mt-1">{testResult.message}</p>
              </div>
            )}

            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                className="btn-brand-subtle inline-flex items-center rounded-lg px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
                onClick={handleSkip}
                disabled={saving || testing}
              >
                Skip
              </button>
              <button
                type="button"
                className="btn-brand-subtle inline-flex items-center rounded-lg px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
                onClick={() => void handleTest()}
                disabled={!enabled || saving || testing}
              >
                {testing ? "Testing..." : "Test Connection"}
              </button>
              <button
                type="button"
                className="btn-brand-primary inline-flex items-center rounded-lg px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
                onClick={() => void handleSave()}
                disabled={saving || testing}
              >
                {saving ? "Saving..." : "Save & Continue"}
              </button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
