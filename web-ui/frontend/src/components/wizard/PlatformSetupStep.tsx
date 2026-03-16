import type {
  ConnectionTestResponse,
  PlatformType,
  SystemStatusResponse,
} from "../../api/types";
import ConnectionTestResult from "../common/ConnectionTestResult";
import ErrorMessage from "../common/ErrorMessage";
import LoadingSpinner from "../common/LoadingSpinner";
import Tooltip from "../common/Tooltip";

type AuthType = "api_key" | "cookie" | "none";

type PlatformSetupStepProps = {
  status: SystemStatusResponse | null;
  statusLoading: boolean;
  statusError: string;
  platformType: PlatformType | null;
  authType: AuthType;
  apiUrl: string;
  apiKey: string;
  formError: string;
  testResult: ConnectionTestResponse | null;
  testError: string;
  isTesting: boolean;
  isSaving: boolean;
  onChooseExternalApi: () => void;
  onUseMockQuickAction: () => void;
  onUseReneryoQuickAction: () => void;
  onAuthTypeChange: (value: AuthType) => void;
  onApiUrlChange: (value: string) => void;
  onApiKeyChange: (value: string) => void;
  onTestConnection: () => void;
  onSaveAndContinue: () => void;
};

export default function PlatformSetupStep({
  status,
  statusLoading,
  statusError,
  platformType,
  authType,
  apiUrl,
  apiKey,
  formError,
  testResult,
  testError,
  isTesting,
  isSaving,
  onChooseExternalApi,
  onUseMockQuickAction,
  onUseReneryoQuickAction,
  onAuthTypeChange,
  onApiUrlChange,
  onApiKeyChange,
  onTestConnection,
  onSaveAndContinue,
}: PlatformSetupStepProps) {
  const showDevQuickActions =
    import.meta.env.DEV ||
    import.meta.env.VITE_ENABLE_DEV_QUICK_ACTIONS === "true";
  const resolvedPlatform = platformType ?? "custom_rest";
  const isMock = resolvedPlatform === "mock";
  const isReneryo = resolvedPlatform === "reneryo";
  const isExternalApi = resolvedPlatform === "custom_rest";
  const adapterTarget = isReneryo ? "RENERYO" : "External API";

  return (
    <section className="space-y-4">
      <header className="brand-hero rounded-2xl p-6 backdrop-blur-sm">
        <p className="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-sky-700 dark:text-sky-300">
          Step 1 of 6
        </p>
        <div className="mt-2 inline-flex items-center gap-2">
          <h2 className="m-0 text-2xl font-semibold text-slate-900 dark:text-slate-100">
            Platform Setup
          </h2>
          <Tooltip
            content="Choose your production integration path and validate connection settings."
            ariaLabel="Why platform setup is needed"
          />
        </div>
        <p className="mb-0 mt-2 text-sm text-slate-600 dark:text-slate-300">
          Configure your production data source, then continue with asset and metric setup.
        </p>
      </header>

      <div className="brand-hero rounded-2xl p-6 backdrop-blur-sm">
        {statusLoading && (
          <div className="mb-4 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900 opacity-50">
            <LoadingSpinner label="Loading current system status..." size="sm" />
          </div>
        )}
        {!statusLoading && statusError && (
          <div className="mb-4">
            <ErrorMessage title="Status unavailable" message={statusError} />
          </div>
        )}
        {!statusLoading && !statusError && status && (
          <div className="mb-4 grid gap-3 sm:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-sky-100/20 p-4 dark:border-slate-700 dark:bg-slate-800">
              <p className="m-0 text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
                Configured
              </p>
              <p className="m-0 mt-2 text-lg font-semibold text-slate-900 dark:text-slate-100">
                {status.configured ? "Yes" : "No"}
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-sky-100/20 p-4 dark:border-slate-700 dark:bg-slate-800">
              <p className="m-0 text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
                Database
              </p>
              <p className="m-0 mt-2 text-lg font-semibold text-slate-900 dark:text-slate-100">
                {status.database_connected ? "Connected" : "Disconnected"}
              </p>
            </div>
          </div>
        )}

        <div className="space-y-3">
          <button
            type="button"
            onClick={onChooseExternalApi}
            className={`w-full rounded-xl border p-4 text-left transition ${
              isExternalApi
                ? "border-cyan-300 bg-gradient-to-r from-sky-50/90 via-white to-emerald-50/70 shadow-sm dark:border-cyan-500/50 dark:from-sky-900/50 dark:via-slate-900/90 dark:to-emerald-900/35"
                : "border-slate-200 bg-white/90 hover:bg-gradient-to-r hover:from-sky-50 hover:to-emerald-50 dark:border-slate-700 dark:bg-slate-800/85 dark:hover:from-slate-800 dark:hover:via-slate-800 dark:hover:to-slate-700/90"
            }`}
          >
            <p className="m-0 text-sm font-semibold text-slate-900 dark:text-slate-100">
              Connect via API
            </p>
            <p className="m-0 mt-1 text-sm text-slate-600 dark:text-slate-300">
              Primary production path. Connect to your platform API endpoint.
            </p>
          </button>

          {showDevQuickActions && (
            <div className="rounded-xl border border-dashed border-slate-300 p-3 dark:border-slate-600">
              <p className="m-0 text-xs font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400">
                Developer Quick Actions
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                <button
                  type="button"
                  className={`rounded-lg px-3 py-2 text-sm font-semibold ${
                    isMock
                      ? "bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300"
                      : "btn-brand-subtle"
                  }`}
                  onClick={onUseMockQuickAction}
                >
                  Use Mock
                </button>
                <button
                  type="button"
                  className={`rounded-lg px-3 py-2 text-sm font-semibold ${
                    isReneryo
                      ? "bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300"
                      : "btn-brand-subtle"
                  }`}
                  onClick={onUseReneryoQuickAction}
                >
                  Use RENERYO
                </button>
              </div>
            </div>
          )}
        </div>

        {isMock ? (
          <div className="mt-4 rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900 dark:border-sky-500/40 dark:bg-sky-900/30 dark:text-sky-200">
            Mock mode selected. No connection details are required.
          </div>
        ) : (
          <div className="mt-4 space-y-4">
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
          {!isMock && (
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
            onClick={onSaveAndContinue}
            disabled={isSaving || isTesting}
          >
            {isSaving
              ? "Saving..."
              : isMock
                ? "Continue with Demo Data"
                : "Save & Continue"}
          </button>
        </div>
      </div>
    </section>
  );
}
