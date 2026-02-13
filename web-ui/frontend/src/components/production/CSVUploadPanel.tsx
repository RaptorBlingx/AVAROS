import { useCallback, useMemo, useState } from "react";

import {
  downloadCSVTemplate,
  toFriendlyErrorMessage,
  uploadProductionCSV,
} from "../../api/client";
import type { CSVUploadResponse } from "../../api/types";
import ErrorMessage from "../common/ErrorMessage";
import LoadingSpinner from "../common/LoadingSpinner";

type UploadHistoryItem = {
  id: number;
  fileName: string;
  uploadedAt: string;
  inserted: number;
};

type CSVUploadPanelProps = {
  onUploadComplete: () => void;
  onNotify: (type: "success" | "error", message: string) => void;
};

function parseCsvPreview(fileText: string): string[][] {
  const rows: string[][] = [];
  let currentRow: string[] = [];
  let currentCell = "";
  let insideQuotes = false;

  const text = fileText.replace(/\r\n/g, "\n");
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const nextChar = text[index + 1];

    if (char === '"') {
      if (insideQuotes && nextChar === '"') {
        currentCell += '"';
        index += 1;
      } else {
        insideQuotes = !insideQuotes;
      }
      continue;
    }

    if (char === "," && !insideQuotes) {
      currentRow.push(currentCell.trim());
      currentCell = "";
      continue;
    }

    if (char === "\n" && !insideQuotes) {
      currentRow.push(currentCell.trim());
      const hasContent = currentRow.some((cell) => cell.length > 0);
      if (hasContent) {
        rows.push(currentRow);
      }
      currentRow = [];
      currentCell = "";
      if (rows.length >= 6) {
        break;
      }
      continue;
    }

    currentCell += char;
  }

  if (rows.length < 6 && (currentCell.length > 0 || currentRow.length > 0)) {
    currentRow.push(currentCell.trim());
    const hasContent = currentRow.some((cell) => cell.length > 0);
    if (hasContent) {
      rows.push(currentRow);
    }
  }

  return rows.slice(0, 6);
}

export default function CSVUploadPanel({
  onUploadComplete,
  onNotify,
}: CSVUploadPanelProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewRows, setPreviewRows] = useState<string[][]>([]);
  const [uploadResult, setUploadResult] = useState<CSVUploadResponse | null>(
    null,
  );
  const [uploadError, setUploadError] = useState<string>("");
  const [isUploading, setIsUploading] = useState(false);
  const [history, setHistory] = useState<UploadHistoryItem[]>([]);

  const validateFile = useCallback((file: File): string | null => {
    if (!file.name.toLowerCase().endsWith(".csv")) {
      return "Only CSV files are allowed.";
    }
    const maxBytes = 5 * 1024 * 1024;
    if (file.size > maxBytes) {
      return "File is too large. Maximum allowed size is 5MB.";
    }
    return null;
  }, []);

  const readPreview = useCallback(async (file: File) => {
    const text = await file.text();
    setPreviewRows(parseCsvPreview(text));
  }, []);

  const handleFileSelection = useCallback(
    async (file: File | null) => {
      setUploadError("");
      setUploadResult(null);
      if (!file) {
        setSelectedFile(null);
        setPreviewRows([]);
        return;
      }

      const validationError = validateFile(file);
      if (validationError) {
        setSelectedFile(null);
        setPreviewRows([]);
        setUploadError(validationError);
        onNotify("error", validationError);
        return;
      }

      setSelectedFile(file);
      await readPreview(file);
    },
    [onNotify, readPreview, validateFile],
  );

  const handleDrop = useCallback(
    async (event: React.DragEvent<HTMLLabelElement>) => {
      event.preventDefault();
      const file = event.dataTransfer.files?.[0] ?? null;
      await handleFileSelection(file);
    },
    [handleFileSelection],
  );

  const handleUpload = useCallback(async () => {
    if (!selectedFile) {
      return;
    }

    setIsUploading(true);
    setUploadError("");

    try {
      const result = await uploadProductionCSV(selectedFile);
      setUploadResult(result);
      setHistory((prev) => [
        {
          id: Date.now(),
          fileName: selectedFile.name,
          uploadedAt: new Date().toISOString(),
          inserted: result.inserted,
        },
        ...prev,
      ]);
      onUploadComplete();
      onNotify(
        "success",
        `Upload completed. Inserted ${result.inserted} row(s).`,
      );
    } catch (error) {
      const message = toFriendlyErrorMessage(error);
      setUploadError(message);
      onNotify("error", message);
    } finally {
      setIsUploading(false);
    }
  }, [onNotify, onUploadComplete, selectedFile]);

  const handleDownloadTemplate = useCallback(async () => {
    try {
      const blob = await downloadCSVTemplate();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "production_data_template.csv";
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      URL.revokeObjectURL(url);
      onNotify("success", "Template downloaded.");
    } catch (error) {
      onNotify("error", toFriendlyErrorMessage(error));
    }
  }, [onNotify]);

  const previewHeader = useMemo(() => previewRows[0] ?? [], [previewRows]);
  const previewBody = useMemo(() => previewRows.slice(1), [previewRows]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="m-0 text-sm text-slate-600 dark:text-slate-300">
          Upload production records using CSV export from MES/ERP.
        </p>
        <button
          type="button"
          onClick={() => void handleDownloadTemplate()}
          className="btn-brand-subtle rounded-lg px-3 py-1.5 text-xs font-semibold"
        >
          Download Template
        </button>
      </div>

      <label
        htmlFor="production-csv-file"
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => void handleDrop(event)}
        className="brand-surface flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-cyan-300 px-4 py-8 text-center transition hover:bg-cyan-50/50 dark:border-cyan-700 dark:hover:bg-slate-800/50"
      >
        <input
          id="production-csv-file"
          type="file"
          accept=".csv"
          className="hidden"
          onChange={(event) =>
            void handleFileSelection(event.target.files?.[0] ?? null)
          }
        />
        <p className="m-0 text-sm font-semibold text-slate-900 dark:text-slate-100">
          Drag & drop CSV here or click to browse
        </p>
        <p className="m-0 mt-1 text-xs text-slate-500 dark:text-slate-400">
          CSV only, max 5MB
        </p>
        {selectedFile && (
          <p className="m-0 mt-3 text-xs font-medium text-sky-700 dark:text-sky-300">
            Selected: {selectedFile.name}
          </p>
        )}
      </label>

      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => void handleUpload()}
          disabled={!selectedFile || isUploading}
          className="btn-brand-primary rounded-lg px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
        >
          Upload
        </button>
        {isUploading && (
          <LoadingSpinner size="sm" label="Uploading CSV..." className="opacity-80" />
        )}
      </div>

      {uploadError && <ErrorMessage message={uploadError} />}

      {previewRows.length > 0 && (
        <section className="brand-surface rounded-xl p-4">
          <h4 className="m-0 text-sm font-semibold text-slate-900 dark:text-slate-100">
            Preview (first 5 rows)
          </h4>
          <div className="mt-3 overflow-x-auto">
            <table className="min-w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-700">
                  {previewHeader.map((header, index) => (
                    <th
                      key={`${header}-${index}`}
                      className="px-2 py-2 font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300"
                    >
                      {header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {previewBody.map((row, rowIndex) => (
                  <tr key={`preview-row-${rowIndex}`} className="border-b border-slate-100 dark:border-slate-800">
                    {row.map((value, cellIndex) => (
                      <td
                        key={`preview-cell-${rowIndex}-${cellIndex}`}
                        className="px-2 py-2 text-slate-700 dark:text-slate-200"
                      >
                        {value}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {uploadResult && (
        <section className="brand-surface rounded-xl p-4">
          <h4 className="m-0 text-sm font-semibold text-slate-900 dark:text-slate-100">
            Upload Result
          </h4>
          <div className="mt-3 grid gap-2 text-sm text-slate-700 dark:text-slate-200 sm:grid-cols-3">
            <p className="m-0">Total Rows: {uploadResult.total_rows}</p>
            <p className="m-0">Valid Rows: {uploadResult.valid_rows}</p>
            <p className="m-0">Inserted: {uploadResult.inserted}</p>
          </div>
          {uploadResult.errors.length > 0 && (
            <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50/70 p-3 text-xs text-amber-800 dark:border-amber-500/40 dark:bg-amber-950/30 dark:text-amber-200">
              <p className="m-0 font-semibold">Row errors:</p>
              <ul className="m-0 mt-2 list-disc pl-4">
                {uploadResult.errors.map((error, index) => (
                  <li key={`${error.row}-${error.column}-${index}`}>
                    Row {error.row}, {error.column}: {error.message}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}

      {history.length > 0 && (
        <section className="brand-surface rounded-xl p-4">
          <h4 className="m-0 text-sm font-semibold text-slate-900 dark:text-slate-100">
            Recent Uploads
          </h4>
          <ul className="m-0 mt-3 space-y-2 p-0 text-xs text-slate-600 dark:text-slate-300">
            {history.map((item) => (
              <li
                key={item.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 px-3 py-2 dark:border-slate-700"
              >
                <span className="font-medium text-slate-700 dark:text-slate-200">
                  {item.fileName}
                </span>
                <span>{new Date(item.uploadedAt).toLocaleString()}</span>
                <span>Inserted: {item.inserted}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
