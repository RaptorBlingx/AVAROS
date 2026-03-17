import type { ConnectionTestResponse, PlatformType } from "../../api/types";
import Tooltip from "../common/Tooltip";
import ConnectionTestResult from "../common/ConnectionTestResult";

type AuthType = "api_key" | "cookie" | "none";

type ConnectionSetupStepProps = {
  platformType: PlatformType;
  authType: AuthType;
  apiUrl: string;
  apiKey: string;
  formError: string;
  testResult: ConnectionTestResponse | null;
  testError: string;
  isTesting: boolean;
  isSaving: boolean;
  onAuthTypeChange: (value: AuthType) => void;
  onApiUrlChange: (value: string) => void;
  onApiKeyChange: (value: string) => void;
  onTestConnection: () => void;
  onSave: () => void;
};

export default function ConnectionSetupStep({
  platformType,
  authType,
  apiUrl,
  apiKey,
  formError,
  testResult,
  testError,
  isTesting,
  isSaving,
  onAuthTypeChange,
  onApiUrlChange,
  onApiKeyChange,
  onTestConnection,
  onSave,
}: ConnectionSetupStepProps) {
  const isUnconfigured = platformType === "unconfigured";
  const adapterTarget =
    platformType === "reneryo"
      ? "RENERYO"
      : platformType === "custom_rest"
      ? "Custom REST"
      : "Unconfigured";

  return (
    <section className="space-y-4">
      <header className="brand-hero rounded-2xl p-6 backdrop-blur-sm">
        <p className="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-sky-700 dark:text-sky-300">
          Step 3 of 7
        </p>
        <div className="mt-2 inline-flex items-center gap-2">
          <h2 className="m-0 text-2xl font-semibold text-slate-900 dark:text-slate-100">
            Connection Setup
          </h2>
          <Tooltip
            content="Why is this needed? AVAROS must validate endpoint reachability and credentials before activation."
            ariaLabel="Why connection setup is needed"
          />
        </div>
      </header>

      <div className="brand-hero rounded-2xl p-6 backdrop-blur-sm">
        {isUnconfigured ? (
          <div className="rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900 dark:border-sky-500/40 dark:bg-sky-900/30 dark:text-sky-200">
            Unconfigured mode. No connection details are required.
          </div>
        ) : (
          <div className="space-y-4">
            <label className="block">
              <span className="mb-1 block text-sm font-semibold text-slate-700 dark:text-slate-300">
                API URL
              </span>
              <input
                type="url"
                value={apiUrl}
                onChange={(event) => onApiUrlChange(event.target.value)}
                placeholder="https://api.example.com"
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none ring-sky-200 focus:ring-2 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
              />
            </label>

            <label className="block">
              <span className="mb-1 block text-sm font-semibold text-slate-700 dark:text-slate-300">
                Auth Type
              </span>
              <select
                value={authType}
                onChange={(event) =>
                  onAuthTypeChange(event.target.value as AuthType)
                }
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none ring-sky-200 focus:ring-2 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
              >
                <option value="api_key">API Key</option>
                <option value="cookie">Session Cookie</option>
                <option value="none">No Authentication</option>
              </select>
            </label>

            {authType !== "none" && (
              <label className="block">
                <span className="mb-1 block text-sm font-semibold text-slate-700 dark:text-slate-300">
                  {authType === "cookie" ? "Session Cookie Value" : "API Key"}
                </span>
                <input
                  type="password"
                  value={apiKey}
                  onChange={(event) => onApiKeyChange(event.target.value)}
                  placeholder={
                    authType === "cookie"
                      ? "Paste session cookie (S=...)"
                      : "Enter your API key"
                  }
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none ring-sky-200 focus:ring-2 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                />
              </label>
            )}
          </div>
        )}

        {formError && (
          <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900 dark:border-red-500/40 dark:bg-red-900/40 dark:text-red-200">
            {formError}
          </div>
        )}

        {testError && (
          <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900 dark:border-red-500/40 dark:bg-red-900/40 dark:text-red-200">
            {testError}
          </div>
        )}

        {testResult && <ConnectionTestResult result={testResult} />}

        <div className="mt-6 flex flex-wrap gap-3">
          {!isUnconfigured && (
            <button
              type="button"
              className="btn-brand-subtle inline-flex items-center rounded-lg px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
              onClick={onTestConnection}
              disabled={isTesting || isSaving}
            >
              {isTesting ? (
                <span className="inline-flex items-center gap-2">
                  <svg
                    className="h-4 w-4 animate-spin"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                  >
                    <path
                      d="M21 12a9 9 0 10-9 9"
                      strokeWidth="2"
                      strokeLinecap="round"
                    />
                  </svg>
                  Testing connection to {adapterTarget}...
                </span>
              ) : (
                "Test Connection"
              )}
            </button>
          )}
          <button
            type="button"
            className="btn-brand-primary inline-flex items-center rounded-lg px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
            onClick={onSave}
            disabled={isSaving || isTesting}
          >
            {isSaving ? "Saving..." : "Save & Continue"}
          </button>
        </div>
      </div>
    </section>
  );
}
