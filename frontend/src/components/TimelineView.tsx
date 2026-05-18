/**
 * TimelineView — renders the care plan timeline as a vertical list.
 *
 * Each entry shows a color-coded specialty badge, a formatted timestamp,
 * and the description text. When the timeline is empty, a placeholder
 * message is shown. While `loading` is true in the Zustand store, a
 * skeleton loading state is rendered instead.
 *
 * Requirements: 4.1, 4.4
 */

import React from 'react';
import { useCaseStore } from '@/store/caseStore';
import { Skeleton } from '@/components/ui/skeleton';
import type { TimelineEntry } from '@/types';

// ── Specialty badge colours ────────────────────────────────────────────────

const SPECIALTY_COLORS: Record<string, string> = {
  cardiology: 'bg-red-100 text-red-700 border-red-200',
  radiology: 'bg-blue-100 text-blue-700 border-blue-200',
  oncology: 'bg-purple-100 text-purple-700 border-purple-200',
  pharmacy: 'bg-green-100 text-green-700 border-green-200',
};

const DEFAULT_BADGE_COLOR = 'bg-gray-100 text-gray-700 border-gray-200';

/** Dot colour on the timeline spine, matching the badge colour. */
const SPECIALTY_DOT_COLORS: Record<string, string> = {
  cardiology: 'bg-red-400',
  radiology: 'bg-blue-400',
  oncology: 'bg-purple-400',
  pharmacy: 'bg-green-400',
};

const DEFAULT_DOT_COLOR = 'bg-gray-400';

// ── Sub-components ─────────────────────────────────────────────────────────

function SpecialtyBadge({ specialty }: { specialty: string }) {
  const key = specialty.toLowerCase();
  const colorClass = SPECIALTY_COLORS[key] ?? DEFAULT_BADGE_COLOR;
  return (
    <span
      className={`inline-block rounded-full border px-2 py-0.5 text-xs font-semibold capitalize ${colorClass}`}
    >
      {specialty}
    </span>
  );
}

/** Formats an ISO timestamp string into a human-readable date/time. */
function formatTimestamp(ts: string): string {
  try {
    return new Intl.DateTimeFormat('en-US', {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(new Date(ts));
  } catch {
    return ts;
  }
}

// ── Skeleton loading state ─────────────────────────────────────────────────

function TimelineSkeleton(): React.ReactElement {
  return (
    <section aria-label="Loading timeline" aria-busy="true">
      <Skeleton className="mb-4 h-5 w-24" />
      <ol className="space-y-0" aria-label="Loading timeline entries">
        {[0, 1, 2].map((i) => (
          <li key={i} className="relative flex gap-4 pb-6">
            {/* Dot placeholder */}
            <Skeleton className="relative z-10 mt-1 h-6 w-6 flex-shrink-0 rounded-full" />
            {/* Content placeholder */}
            <div className="flex-1 space-y-2">
              <div className="flex items-center gap-2">
                <Skeleton className="h-4 w-20 rounded-full" />
                <Skeleton className="h-3 w-28" />
              </div>
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-3/4" />
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

// ── Main component ─────────────────────────────────────────────────────────

export interface TimelineViewProps {
  /** Optional explicit timeline prop; falls back to Zustand store if omitted. */
  timeline?: TimelineEntry[];
}

/**
 * Renders a vertical timeline of care plan entries.
 * Accepts an optional `timeline` prop; if not provided, reads from the
 * Zustand store so it can be used standalone inside Dashboard.
 * Shows a skeleton loading state while `loading` is true in the store.
 */
export function TimelineView({ timeline: timelineProp }: TimelineViewProps = {}): React.ReactElement {
  const storeTimeline = useCaseStore((state) => state.carePlan?.timeline ?? []);
  const loading = useCaseStore((state) => state.loading);
  const rawTimeline = timelineProp ?? storeTimeline;
  // Defensive: ensure it's actually an array
  const timeline = Array.isArray(rawTimeline) ? rawTimeline : [];

  if (loading) {
    return <TimelineSkeleton />;
  }

  if (timeline.length === 0) {
    return (
      <div
        className="flex flex-col items-center justify-center rounded-lg border border-dashed border-slate-300 bg-slate-50 py-12 text-center"
        aria-label="Timeline placeholder"
      >
        <p className="text-sm text-slate-500">
          No timeline entries yet. Submit a case to see the care plan timeline.
        </p>
      </div>
    );
  }

  return (
    <section aria-label="Care plan timeline">
      <h2 className="mb-4 text-base font-semibold text-slate-800">Timeline</h2>
      <ol className="relative space-y-0" aria-label="Timeline entries">
        {timeline.map((entry, index) => {
          const key = entry.specialty.toLowerCase();
          const dotColor = SPECIALTY_DOT_COLORS[key] ?? DEFAULT_DOT_COLOR;
          const isLast = index === timeline.length - 1;

          return (
            <li
              key={`${entry.timestamp}-${index}`}
              className="relative flex gap-4 pb-6"
              data-testid="timeline-item"
            >
              {/* Vertical spine line */}
              {!isLast && (
                <div
                  className="absolute left-[11px] top-5 h-full w-0.5 bg-slate-200"
                  aria-hidden="true"
                />
              )}

              {/* Dot */}
              <div
                className={`relative z-10 mt-1 h-6 w-6 flex-shrink-0 rounded-full ${dotColor} flex items-center justify-center`}
                aria-hidden="true"
              >
                <div className="h-2 w-2 rounded-full bg-white" />
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <div className="mb-1 flex flex-wrap items-center gap-2">
                  <SpecialtyBadge specialty={entry.specialty} />
                  <time
                    dateTime={entry.timestamp}
                    className="text-xs text-slate-500"
                  >
                    {formatTimestamp(entry.timestamp)}
                  </time>
                </div>
                <p className="text-sm text-slate-700">{entry.description}</p>
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

export default TimelineView;
