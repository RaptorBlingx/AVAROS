import type { ReactNode } from "react";

type LoadingSpinnerProps = {
  label?: string;
  size?: "sm" | "md" | "lg";
  className?: string;
  icon?: ReactNode;
};

export default function LoadingSpinner({
  label = "Loading...",
  size = "md",
  className = "",
  icon,
}: LoadingSpinnerProps) {
  const spinnerSizeClass =
    size === "sm" ? "h-4 w-4" : size === "lg" ? "h-8 w-8" : "h-6 w-6";

  return (
    <div
      className={`inline-flex items-center gap-2 text-slate-600 dark:text-slate-300 ${className}`}
      role="status"
      aria-live="polite"
    >
      {icon ?? (
        <span
          className={`${spinnerSizeClass} inline-block animate-spin rounded-full border-2 border-slate-300 border-t-sky-500`}
          aria-hidden="true"
        />
      )}
      <span className="text-sm font-medium">{label}</span>
    </div>
  );
}
