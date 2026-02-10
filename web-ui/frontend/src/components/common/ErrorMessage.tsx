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
    <div
      className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-rose-900"
      role="alert"
    >
      <p className="m-0 text-sm font-semibold">{title}</p>
      <p className="m-0 mt-1 text-sm">{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-2 rounded border border-rose-300 bg-white px-3 py-1 text-xs font-semibold text-rose-700"
        >
          Retry
        </button>
      )}
    </div>
  );
}
