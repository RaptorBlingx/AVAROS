type ErrorMessageProps = {
  title?: string;
  message: string;
  onRetry?: () => void;
};

export default function ErrorMessage({
  title = "Something went wrong",
  message,
  onRetry,
}: ErrorMessageProps) {
  return (
    <div className="brand-surface mt-3 rounded-xl px-4 py-3" role="alert">
      <div className="flex items-start gap-3">
        <span className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-rose-300/70 bg-rose-100/80 text-rose-700 dark:border-rose-500/40 dark:bg-rose-950/40 dark:text-rose-300">
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor">
            <path d="M12 8v5m0 3h.01M5 19h14L12 4 5 19z" strokeWidth="2" strokeLinecap="round" />
          </svg>
        </span>
        <div>
          <p className="m-0 text-sm font-semibold text-rose-700 dark:text-rose-300">{title}</p>
          <p className="m-0 mt-1 text-sm text-rose-700/90 dark:text-rose-200/90">{message}</p>
        </div>
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="btn-brand-subtle mt-3 rounded-lg px-3 py-1.5 text-xs font-semibold"
        >
          Retry
        </button>
      )}
    </div>
  );
}
