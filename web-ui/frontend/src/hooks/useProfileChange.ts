import { useEffect, useState } from "react";

export const ACTIVE_PROFILE_CHANGED_EVENT = "avaros:active-profile-changed";

export type ActiveProfileChangedDetail = {
  profileName: string;
  previousProfileName?: string;
};

/** Notify all mounted browser views that the active backend profile changed. */
export function emitActiveProfileChanged(
  detail: ActiveProfileChangedDetail,
): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(
    new CustomEvent<ActiveProfileChangedDetail>(
      ACTIVE_PROFILE_CHANGED_EVENT,
      { detail },
    ),
  );
}

/** Return a monotonically increasing revision whenever the profile changes. */
export function useProfileRevision(): number {
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    const handleProfileChanged = () => {
      setRevision((current) => current + 1);
    };
    window.addEventListener(
      ACTIVE_PROFILE_CHANGED_EVENT,
      handleProfileChanged,
    );
    return () => {
      window.removeEventListener(
        ACTIVE_PROFILE_CHANGED_EVENT,
        handleProfileChanged,
      );
    };
  }, []);

  return revision;
}
