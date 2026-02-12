import { Component, type ErrorInfo, type ReactNode } from "react";

type ErrorBoundaryProps = {
  children: ReactNode;
};

type ErrorBoundaryState = {
  hasError: boolean;
};

export default class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error("Unhandled UI error:", error, errorInfo);
  }

  handleReload = (): void => {
    window.location.reload();
  };

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className="brand-app-bg brand-app-bg--light dark:brand-app-bg--dark flex min-h-screen items-center justify-center p-6">
          <div className="brand-surface w-full max-w-md rounded-2xl p-6 shadow-sm">
            <h2 className="m-0 text-xl font-semibold text-slate-900 dark:text-slate-100">Unexpected error</h2>
            <p className="m-0 mt-2 text-sm text-slate-600 dark:text-slate-300">
              AVAROS UI hit an unexpected issue. Please reload the page.
            </p>
            <button
              type="button"
              onClick={this.handleReload}
              className="btn-brand-primary mt-4 rounded-lg px-4 py-2 text-sm font-semibold"
            >
              Reload
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
