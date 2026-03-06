import type { AssetRecord } from "../../api/types";
import type { AssetRow } from "./assetManagementSection.helpers";
import { TYPE_OPTIONS } from "./assetManagementSection.helpers";

type AssetManagementRowsProps = {
  rows: AssetRow[];
  isCustomRest: boolean;
  seuOptions: AssetRecord[];
  onChange: <K extends keyof AssetRow>(index: number, key: K, value: AssetRow[K]) => void;
  onDelete: (index: number) => void;
};

export default function AssetManagementRows({
  rows,
  isCustomRest,
  seuOptions,
  onChange,
  onDelete,
}: AssetManagementRowsProps) {
  return (
    <div className="space-y-3">
      {rows.map((row, index) => (
        <div
          key={row.rowId}
          className="grid gap-2 rounded-xl border border-slate-300 bg-white p-3 dark:border-slate-600 dark:bg-slate-800 md:grid-cols-5"
        >
          <input
            type="text"
            value={row.assetId}
            placeholder="asset id (optional)"
            onChange={(event) => onChange(index, "assetId", event.target.value)}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-900"
          />
          <input
            type="text"
            value={row.displayName}
            placeholder="asset name"
            onChange={(event) => onChange(index, "displayName", event.target.value)}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-900"
          />

          {isCustomRest ? (
            <select
              value={row.assetType}
              onChange={(event) =>
                onChange(
                  index,
                  "assetType",
                  event.target.value as AssetRow["assetType"],
                )
              }
              className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-900"
            >
              {TYPE_OPTIONS.filter((type) => type !== "seu").map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
          ) : (
            <select
              value={row.seuId}
              onChange={(event) => onChange(index, "seuId", event.target.value)}
              className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-900"
            >
              <option value="">Select SEU</option>
              {seuOptions.map((asset) => (
                <option key={asset.asset_id} value={asset.asset_id}>
                  {asset.display_name} ({asset.asset_id})
                </option>
              ))}
            </select>
          )}

          <input
            type="text"
            value={isCustomRest ? row.endpointTemplate : row.aliases}
            placeholder={isCustomRest ? "/api/metrics/{asset_id}" : "aliases (comma-separated)"}
            onChange={(event) =>
              onChange(
                index,
                isCustomRest ? "endpointTemplate" : "aliases",
                event.target.value,
              )
            }
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-900"
          />

          <div className="flex items-center gap-2">
            {isCustomRest ? (
              <input
                type="text"
                value={row.aliases}
                placeholder="aliases (comma-separated)"
                onChange={(event) => onChange(index, "aliases", event.target.value)}
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-900"
              />
            ) : null}
            <button
              type="button"
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold dark:border-slate-600"
              onClick={() => onDelete(index)}
            >
              Delete
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
