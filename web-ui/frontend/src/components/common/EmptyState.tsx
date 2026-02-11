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
    <div className="brand-surface rounded-xl px-5 py-6 text-center">
      <div className="mx-auto mb-2 inline-flex h-10 w-10 items-center justify-center rounded-full border border-slate-300 bg-white/90 text-slate-500 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300">
        {icon ?? (
          <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor">
            <path d="M5 12h14M12 5v14" strokeWidth="2" strokeLinecap="round" />
          </svg>
        )}
      </div>
      <h4 className="m-0 text-sm font-semibold text-slate-900 dark:text-slate-100">{title}</h4>
      <p className="m-0 mt-1 text-sm text-slate-600 dark:text-slate-300">{message}</p>
      {actionLabel && onAction && (
        <button
          type="button"
          onClick={onAction}
          className="btn-brand-subtle mt-3 rounded-lg px-3 py-1.5 text-xs font-semibold"
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}
