import type { ReactNode } from "react";

type EmptyStateProps = {
  title: string;
  message: string;
  actionLabel?: string;
  onAction?: () => void;
  icon?: ReactNode;
};

export default function EmptyState({
  title,
  message,
  actionLabel,
  onAction,
  icon,
}: EmptyStateProps) {
  return (
    <div className="rounded-xl border border-sky-200 bg-sky-50/70 px-5 py-6 text-center">
      <div className="mx-auto mb-2 inline-flex h-10 w-10 items-center justify-center rounded-full border border-slate-300 bg-white text-slate-500">
        {icon ?? (
          <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor">
            <path d="M5 12h14M12 5v14" strokeWidth="2" strokeLinecap="round" />
          </svg>
        )}
      </div>
      <h4 className="m-0 text-sm font-semibold text-slate-900">{title}</h4>
      <p className="m-0 mt-1 text-sm text-slate-600">{message}</p>
      {actionLabel && onAction && (
        <button
          type="button"
          onClick={onAction}
          className="mt-3 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:bg-slate-100"
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}
