/**
 * ExportBar — provides "Export PDF" and "Export EMR" download actions.
 *
 * Both buttons are disabled when no care plan is loaded, and a tooltip
 * explains why. On click, the respective backend endpoint is fetched and
 * the browser is triggered to download the resulting file.
 *
 * Requirements: 7.1, 7.2, 7.3, 7.4, 7.5
 */

import React, { useState } from 'react';
import * as Tooltip from '@radix-ui/react-tooltip';
import { FileText, FileDown, Loader2 } from 'lucide-react';
import { useCaseStore } from '@/store/caseStore';
import { apiUrl } from '@/lib/api';

// ── Types ──────────────────────────────────────────────────────────────────

type ExportFormat = 'pdf' | 'emr';

// ── Download helper ────────────────────────────────────────────────────────

/**
 * Fetch the export endpoint and trigger a browser file download.
 * Returns an error message string on failure, or null on success.
 */
async function triggerDownload(
  caseId: string,
  format: ExportFormat,
): Promise<string | null> {
  const url = apiUrl(`/api/export/${format}/${encodeURIComponent(caseId)}`);
  try {
    const response = await fetch(url);
    if (!response.ok) {
      const text = await response.text().catch(() => response.statusText);
      return `Export failed (${response.status}): ${text}`;
    }

    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);

    const anchor = document.createElement('a');
    anchor.href = objectUrl;
    anchor.download =
      format === 'pdf'
        ? `careplan_${caseId}.pdf`
        : `careplan_${caseId}.txt`;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(objectUrl);

    return null;
  } catch (err) {
    return err instanceof Error ? err.message : 'Unknown export error';
  }
}

// ── ExportButton ───────────────────────────────────────────────────────────

interface ExportButtonProps {
  label: string;
  icon: React.ReactNode;
  disabled: boolean;
  loading: boolean;
  onClick: () => void;
  ariaLabel: string;
}

function ExportButton({
  label,
  icon,
  disabled,
  loading,
  onClick,
  ariaLabel,
}: ExportButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || loading}
      aria-label={ariaLabel}
      aria-disabled={disabled || loading}
      className={[
        'flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm font-medium shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1',
        disabled || loading
          ? 'cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400'
          : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-50 hover:border-slate-400',
      ].join(' ')}
    >
      {loading ? (
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
      ) : (
        <span aria-hidden="true">{icon}</span>
      )}
      {label}
    </button>
  );
}

// ── ExportBar ──────────────────────────────────────────────────────────────

/**
 * Renders the export action bar. Reads `carePlan` from the Zustand store.
 * When no plan is loaded, both buttons are disabled with a tooltip.
 */
export function ExportBar(): React.ReactElement {
  const carePlan = useCaseStore((state) => state.carePlan);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [emrLoading, setEmrLoading] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  const isDisabled = carePlan === null;

  const handleExport = async (format: ExportFormat) => {
    if (!carePlan) return;
    setExportError(null);

    if (format === 'pdf') {
      setPdfLoading(true);
    } else {
      setEmrLoading(true);
    }

    const error = await triggerDownload(carePlan.case_id, format);

    if (format === 'pdf') {
      setPdfLoading(false);
    } else {
      setEmrLoading(false);
    }

    if (error) {
      setExportError(error);
    }
  };

  const buttons = (
    <div className="flex items-center gap-2">
      <ExportButton
        label="Export PDF"
        icon={<FileDown className="h-4 w-4" />}
        disabled={isDisabled}
        loading={pdfLoading}
        onClick={() => handleExport('pdf')}
        ariaLabel="Export care plan as PDF"
      />
      <ExportButton
        label="Export EMR"
        icon={<FileText className="h-4 w-4" />}
        disabled={isDisabled}
        loading={emrLoading}
        onClick={() => handleExport('emr')}
        ariaLabel="Export care plan as EMR text file"
      />
    </div>
  );

  return (
    <div className="flex flex-col gap-1">
      {isDisabled ? (
        <Tooltip.Provider delayDuration={200}>
          <Tooltip.Root>
            <Tooltip.Trigger asChild>
              {/* Wrap in a span so the tooltip works on disabled buttons */}
              <span className="inline-flex">{buttons}</span>
            </Tooltip.Trigger>
            <Tooltip.Portal>
              <Tooltip.Content
                className="z-50 rounded-md bg-slate-800 px-3 py-1.5 text-xs text-white shadow-md"
                sideOffset={6}
                role="tooltip"
              >
                No care plan loaded
                <Tooltip.Arrow className="fill-slate-800" />
              </Tooltip.Content>
            </Tooltip.Portal>
          </Tooltip.Root>
        </Tooltip.Provider>
      ) : (
        buttons
      )}

      {exportError && (
        <p className="text-xs text-red-600" role="alert">
          {exportError}
        </p>
      )}
    </div>
  );
}

export default ExportBar;
