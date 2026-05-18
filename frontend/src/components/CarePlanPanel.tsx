/**
 * CarePlanPanel — displays the full care plan: findings by specialty,
 * recommendations, and alerts.
 *
 * Reads `carePlan` from the Zustand store. When null, renders a placeholder.
 * While `loading` is true, renders a skeleton loading state.
 * Findings are grouped by specialty using a Radix UI Accordion.
 * Alerts are rendered with a red/amber visual treatment.
 *
 * Requirements: 4.2, 4.3, 4.4
 */

import React from 'react';
import * as Accordion from '@radix-ui/react-accordion';
import { AlertTriangle, ChevronDown, CheckCircle2, ClipboardList } from 'lucide-react';
import { useCaseStore } from '@/store/caseStore';
import { Skeleton } from '@/components/ui/skeleton';
import type { CarePlan } from '@/types';

// ── Specialty badge colours (shared with TimelineView) ─────────────────────

const SPECIALTY_COLORS: Record<string, string> = {
  cardiology: 'bg-red-100 text-red-700',
  radiology: 'bg-blue-100 text-blue-700',
  oncology: 'bg-purple-100 text-purple-700',
  pharmacy: 'bg-green-100 text-green-700',
};

const DEFAULT_BADGE_COLOR = 'bg-gray-100 text-gray-700';

// ── Sub-components ─────────────────────────────────────────────────────────

function SpecialtyBadge({ specialty }: { specialty: string }) {
  const key = specialty.toLowerCase();
  const colorClass = SPECIALTY_COLORS[key] ?? DEFAULT_BADGE_COLOR;
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-semibold capitalize ${colorClass}`}
    >
      {specialty}
    </span>
  );
}

// ── Findings accordion ─────────────────────────────────────────────────────

interface FindingsSectionProps {
  carePlan: CarePlan;
}

function FindingsSection({ carePlan }: FindingsSectionProps) {
  const specialties = Object.keys(carePlan.findings);

  if (specialties.length === 0) {
    return (
      <p className="text-sm text-slate-500 italic">No specialty findings available.</p>
    );
  }

  return (
    <Accordion.Root
      type="multiple"
      defaultValue={specialties}
      className="space-y-2"
    >
      {specialties.map((specialty) => {
        const findings = carePlan.findings[specialty];
        return (
          <Accordion.Item
            key={specialty}
            value={specialty}
            className="rounded-lg border border-slate-200 bg-white overflow-hidden"
          >
            <Accordion.Header>
              <Accordion.Trigger
                className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-blue-500 transition-colors group"
                aria-label={`${specialty} findings`}
              >
                <div className="flex items-center gap-2">
                  <SpecialtyBadge specialty={specialty} />
                  <span className="text-sm font-medium text-slate-700 capitalize">
                    {specialty}
                  </span>
                </div>
                <ChevronDown
                  className="h-4 w-4 text-slate-400 transition-transform duration-200 group-data-[state=open]:rotate-180"
                  aria-hidden="true"
                />
              </Accordion.Trigger>
            </Accordion.Header>
            <Accordion.Content className="px-4 pb-4 pt-2 data-[state=closed]:animate-none">
              <p className="mb-3 text-sm text-slate-600">{findings.summary}</p>
              {findings.action_items.length > 0 && (
                <div>
                  <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Action Items
                  </p>
                  <ul className="space-y-1" role="list">
                    {findings.action_items.map((item, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                        <CheckCircle2
                          className="mt-0.5 h-4 w-4 flex-shrink-0 text-green-500"
                          aria-hidden="true"
                        />
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </Accordion.Content>
          </Accordion.Item>
        );
      })}
    </Accordion.Root>
  );
}

// ── Recommendations section ────────────────────────────────────────────────

function RecommendationsSection({ recommendations }: { recommendations: string[] }) {
  if (recommendations.length === 0) {
    return (
      <p className="text-sm text-slate-500 italic">No recommendations.</p>
    );
  }

  return (
    <ul className="space-y-2" role="list" aria-label="Recommendations">
      {recommendations.map((rec, i) => (
        <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
          <ClipboardList
            className="mt-0.5 h-4 w-4 flex-shrink-0 text-blue-500"
            aria-hidden="true"
          />
          <span>{rec}</span>
        </li>
      ))}
    </ul>
  );
}

// ── Alerts section ─────────────────────────────────────────────────────────

function AlertsSection({ alerts }: { alerts: string[] }) {
  if (alerts.length === 0) {
    return (
      <p className="text-sm text-slate-500 italic">No alerts.</p>
    );
  }

  return (
    <ul className="space-y-2" role="list" aria-label="Alerts">
      {alerts.map((alert, i) => (
        <li
          key={i}
          className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800"
          role="alert"
        >
          <AlertTriangle
            className="mt-0.5 h-4 w-4 flex-shrink-0 text-red-500"
            aria-hidden="true"
          />
          <span>{alert}</span>
        </li>
      ))}
    </ul>
  );
}

// ── Skeleton loading state ─────────────────────────────────────────────────

function CarePlanSkeleton(): React.ReactElement {
  return (
    <section aria-label="Loading care plan" aria-busy="true" className="space-y-6">
      {/* Alerts skeleton */}
      <div>
        <Skeleton className="mb-3 h-4 w-16" />
        <div className="space-y-2">
          <Skeleton className="h-10 w-full rounded-md" />
        </div>
      </div>

      {/* Findings skeleton */}
      <div>
        <Skeleton className="mb-3 h-4 w-36" />
        <div className="space-y-2">
          {[0, 1, 2].map((i) => (
            <div key={i} className="rounded-lg border border-slate-200 bg-white overflow-hidden">
              <div className="flex items-center justify-between px-4 py-3">
                <div className="flex items-center gap-2">
                  <Skeleton className="h-5 w-20 rounded-full" />
                  <Skeleton className="h-4 w-24" />
                </div>
                <Skeleton className="h-4 w-4" />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Recommendations skeleton */}
      <div>
        <Skeleton className="mb-3 h-4 w-32" />
        <div className="space-y-2">
          {[0, 1, 2].map((i) => (
            <div key={i} className="flex items-start gap-2">
              <Skeleton className="mt-0.5 h-4 w-4 flex-shrink-0" />
              <Skeleton className="h-4 flex-1" />
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ── Placeholder ────────────────────────────────────────────────────────────

function CarePlanPlaceholder() {
  return (
    <div
      className="flex flex-col items-center justify-center rounded-lg border border-dashed border-slate-300 bg-slate-50 py-12 text-center"
      aria-label="Care plan placeholder"
    >
      <p className="text-sm text-slate-500">
        No care plan loaded. Submit a case to generate a care plan.
      </p>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────

/**
 * Renders the full care plan panel: findings accordion, recommendations list,
 * and alerts list. Reads from the Zustand store.
 * Shows a skeleton loading state while `loading` is true.
 */
export function CarePlanPanel(): React.ReactElement {
  const carePlan = useCaseStore((state) => state.carePlan);
  const loading = useCaseStore((state) => state.loading);

  if (loading) {
    return <CarePlanSkeleton />;
  }

  if (!carePlan) {
    return <CarePlanPlaceholder />;
  }

  // Defensive: ensure arrays are actually arrays (API may return unexpected shapes)
  const alerts = Array.isArray(carePlan.alerts) ? carePlan.alerts : [];
  const recommendations = Array.isArray(carePlan.recommendations) ? carePlan.recommendations : [];
  const findings = carePlan.findings && typeof carePlan.findings === 'object' ? carePlan.findings : {};
  const safePlan = { ...carePlan, alerts, recommendations, findings };

  return (
    <section aria-label="Care plan panel" className="space-y-6">
      {/* Alerts — shown first so critical info is immediately visible */}
      {safePlan.alerts.length > 0 && (
        <div>
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-red-600">
            Alerts
          </h3>
          <AlertsSection alerts={safePlan.alerts} />
        </div>
      )}

      {/* Findings by specialty */}
      <div>
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
          Findings by Specialty
        </h3>
        <FindingsSection carePlan={safePlan} />
      </div>

      {/* Recommendations */}
      <div>
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
          Recommendations
        </h3>
        <RecommendationsSection recommendations={safePlan.recommendations} />
      </div>
    </section>
  );
}

export default CarePlanPanel;
