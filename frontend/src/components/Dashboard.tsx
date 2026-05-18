/**
 * Dashboard — three-panel layout for the CareFlow Orchestrator.
 *
 * Layout:
 *   Left  (320 px) : UploadWidget + SampleCases
 *   Center (flex-1): loading spinner | error + retry | TimelineView + CarePlanPanel
 *   Right  (320 px): AgentChat stub (Phase 3)
 *
 * Requirements: 4.4, 4.5
 */

import React from 'react';
import { Loader2, AlertCircle, RefreshCw } from 'lucide-react';
import { useCaseStore } from '@/store/caseStore';
import { UploadWidget } from './UploadWidget';
import { SampleCases } from './SampleCases';
import { TimelineView } from './TimelineView';
import { CarePlanPanel } from './CarePlanPanel';
import { AgentChat } from './AgentChat';
import { ExportBar } from './ExportBar';

// ── Loading spinner ────────────────────────────────────────────────────────

function LoadingState() {
  return (
    <div
      className="flex flex-col items-center justify-center gap-3 py-20"
      role="status"
      aria-label="Analysing case"
    >
      <Loader2
        className="h-10 w-10 animate-spin text-blue-500"
        aria-hidden="true"
      />
      <p className="text-sm text-slate-500">Analysing case across specialties…</p>
    </div>
  );
}

// ── Error state ────────────────────────────────────────────────────────────

interface ErrorStateProps {
  message: string;
  onRetry: () => void;
}

function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div
      className="flex flex-col items-center justify-center gap-4 rounded-lg border border-red-200 bg-red-50 px-6 py-10 text-center"
      role="alert"
      aria-label="Orchestration error"
    >
      <AlertCircle className="h-8 w-8 text-red-500" aria-hidden="true" />
      <div>
        <p className="mb-1 text-sm font-semibold text-red-700">
          Something went wrong
        </p>
        <p className="text-sm text-red-600">{message}</p>
      </div>
      <button
        type="button"
        onClick={onRetry}
        className="flex items-center gap-2 rounded-md border border-red-300 bg-white px-4 py-2 text-sm font-medium text-red-700 shadow-sm hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-1 transition-colors"
        aria-label="Retry case submission"
      >
        <RefreshCw className="h-4 w-4" aria-hidden="true" />
        Retry
      </button>
    </div>
  );
}

// ── Center panel content ───────────────────────────────────────────────────

function CenterPanel() {
  const { loading, error, setError } = useCaseStore();

  const handleRetry = () => {
    setError(null);
  };

  if (loading) {
    return <LoadingState />;
  }

  if (error) {
    return <ErrorState message={error} onRetry={handleRetry} />;
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          Care Plan
        </h2>
        <ExportBar />
      </div>
      <TimelineView />
      <CarePlanPanel />
    </div>
  );
}

// ── Dashboard ──────────────────────────────────────────────────────────────

/**
 * Root layout component. Renders the three-panel CSS Grid dashboard.
 */
export function Dashboard(): React.ReactElement {
  return (
    <div className="min-h-screen bg-slate-100">
      {/* Header */}
      <header className="border-b border-slate-200 bg-white px-6 py-4 shadow-sm">
        <h1 className="text-lg font-bold text-slate-800">
          CareFlow Orchestrator
        </h1>
        <p className="text-xs text-slate-500">
          Multi-specialty clinical decision support
        </p>
      </header>

      {/* Three-panel grid */}
      <main
        className="mx-auto grid h-[calc(100vh-73px)] max-w-[1600px] grid-cols-[320px_1fr_320px] gap-0 overflow-hidden"
        aria-label="Dashboard layout"
      >
        {/* Left panel */}
        <aside
          className="flex flex-col gap-6 overflow-y-auto border-r border-slate-200 bg-white p-4"
          aria-label="Input panel"
        >
          <UploadWidget />
          <hr className="border-slate-200" />
          <SampleCases />
        </aside>

        {/* Center panel */}
        <section
          className="overflow-y-auto bg-slate-50 p-6"
          aria-label="Care plan panel"
        >
          <CenterPanel />
        </section>

        {/* Right panel */}
        <aside
          className="flex flex-col overflow-y-auto border-l border-slate-200 bg-white p-4"
          aria-label="Agent chat panel"
        >
          <AgentChat />
        </aside>
      </main>
    </div>
  );
}

export default Dashboard;
