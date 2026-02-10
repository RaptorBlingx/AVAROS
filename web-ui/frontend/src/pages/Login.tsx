import { useState } from "react";

import { getStatus } from "../api/client";
import { setStoredApiKey } from "../api/client";

type LoginProps = {
  onAuthenticated: () => void;
};

export default function Login({ onAuthenticated }: LoginProps) {
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    // Temporarily store the key so the client sends it
    setStoredApiKey(apiKey);

    try {
      // Attempt an authenticated request to validate the key
      await getStatus();
      onAuthenticated();
    } catch {
      setStoredApiKey("");
      setError("Invalid API key. Check the server logs for the generated key.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-100 via-sky-50 to-slate-200">
      <div className="w-full max-w-md rounded-xl bg-white p-8 shadow-lg">
        <div className="mb-6 text-center">
          <h1 className="text-2xl font-bold text-slate-800">AVAROS</h1>
          <p className="mt-1 text-sm text-slate-500">
            Enter your API key to access the Web UI
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="api-key"
              className="block text-sm font-medium text-slate-700"
            >
              API Key
            </label>
            <input
              id="api-key"
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Paste your AVAROS_WEB_API_KEY"
              className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
              autoFocus
              required
            />
          </div>

          {error && (
            <p className="text-sm text-red-600">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading || !apiKey}
            className="w-full rounded-lg bg-sky-600 px-4 py-2 text-sm font-semibold text-white shadow hover:bg-sky-700 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? "Verifying…" : "Sign In"}
          </button>
        </form>

        <p className="mt-4 text-center text-xs text-slate-400">
          The API key is shown in server logs on first startup when{" "}
          <code className="rounded bg-slate-100 px-1">AVAROS_WEB_API_KEY</code>{" "}
          is not set.
        </p>
      </div>
    </div>
  );
}
