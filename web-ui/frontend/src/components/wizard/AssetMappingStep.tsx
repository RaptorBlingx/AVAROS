import AssetManagementSection from "../settings/AssetManagementSection";
import Tooltip from "../common/Tooltip";
import type { PlatformType } from "../../api/types";

type AssetMappingStepProps = {
  platformType: PlatformType | null;
  onComplete: () => void;
  onSkip: () => void;
};

export default function AssetMappingStep({
  platformType,
  onComplete,
  onSkip,
}: AssetMappingStepProps) {
  return (
    <section className="space-y-4">
      <header className="brand-hero rounded-2xl p-6 backdrop-blur-sm">
        <p className="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-sky-700 dark:text-sky-300">
          Step 4 of 7
        </p>
        <div className="mt-2 inline-flex items-center gap-2">
          <h2 className="m-0 text-2xl font-semibold text-slate-900 dark:text-slate-100">
            Asset Mapping
          </h2>
          <Tooltip
            content="Configure assets for the selected platform. RENERYO uses discovery, custom REST uses manual mapping, unconfigured is read-only."
            ariaLabel="Why asset mapping is needed"
          />
        </div>
      </header>

      <div className="brand-hero rounded-2xl p-6 backdrop-blur-sm">
        <AssetManagementSection
          mode="wizard"
          platformType={platformType}
          onComplete={onComplete}
          onSkip={onSkip}
        />
      </div>
    </section>
  );
}
