import type { AssetMappingItem, PlatformType } from "../../api/types";

export type AssetRow = {
  rowId: string;
  assetId: string;
  displayName: string;
  assetType: "machine" | "line" | "sensor" | "seu";
  aliases: string;
  endpointTemplate: string;
  seuId: string;
};

export const TYPE_OPTIONS: Array<AssetRow["assetType"]> = [
  "machine",
  "line",
  "sensor",
  "seu",
];

function createRowId(seed?: string): string {
  const base = seed ? seed.replace(/[^a-zA-Z0-9_-]/g, "") : "row";
  return `${base}-${Math.random().toString(36).slice(2, 10)}`;
}

export function toAssetId(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export function csvToAliases(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function aliasesToCsv(aliases?: string[]): string {
  if (!Array.isArray(aliases) || aliases.length === 0) {
    return "";
  }
  return aliases.join(", ");
}

export function createEmptyRow(): AssetRow {
  return {
    rowId: createRowId(),
    assetId: "",
    displayName: "",
    assetType: "machine",
    aliases: "",
    endpointTemplate: "",
    seuId: "",
  };
}

export function toRows(mappings: Record<string, AssetMappingItem>): AssetRow[] {
  const rows = Object.entries(mappings).map(([assetId, item]) => {
    const displayName = String(item.display_name ?? assetId);
    const rawType = String(item.asset_type ?? "machine").toLowerCase();
    const assetType = TYPE_OPTIONS.includes(rawType as AssetRow["assetType"])
      ? (rawType as AssetRow["assetType"])
      : "machine";
    return {
      rowId: createRowId(assetId),
      assetId,
      displayName,
      assetType,
      aliases: aliasesToCsv(item.aliases),
      endpointTemplate: String(item.endpoint_template ?? ""),
      seuId: String(item.seu_id ?? ""),
    };
  });
  return rows.length > 0 ? rows : [createEmptyRow()];
}

export function toPayload(
  rows: AssetRow[],
  platformType: PlatformType,
): Record<string, AssetMappingItem> {
  return rows.reduce<Record<string, AssetMappingItem>>((acc, row) => {
    const resolvedId = row.assetId.trim() || toAssetId(row.displayName);
    if (!resolvedId) {
      return acc;
    }
    const payload: AssetMappingItem = {
      display_name: row.displayName.trim() || resolvedId,
      asset_type: platformType === "reneryo" ? "seu" : row.assetType,
      aliases: csvToAliases(row.aliases),
    };
    if (platformType === "custom_rest") {
      payload.endpoint_template = row.endpointTemplate.trim();
    }
    if (platformType === "reneryo") {
      payload.seu_id = row.seuId.trim();
    }
    acc[resolvedId] = payload;
    return acc;
  }, {});
}
