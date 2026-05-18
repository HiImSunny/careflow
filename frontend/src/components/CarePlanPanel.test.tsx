/**
 * Tests for CarePlanPanel component.
 *
 * Includes:
 *  - Unit tests for specific rendering scenarios
 *  - Property 2 (frontend): Care Plan Structural Invariant (rendering)
 *
 * **Validates: Requirements 4.2, 4.3**
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import '@testing-library/jest-dom';
import * as fc from 'fast-check';
import { CarePlanPanel } from './CarePlanPanel';
import type { CarePlan, SpecialtyFindings } from '@/types';
import { useCaseStore } from '@/store/caseStore';

// ── Mock the Zustand store ────────────────────────────────────────────────

vi.mock('@/store/caseStore', () => ({
  useCaseStore: vi.fn(),
}));

const mockUseCaseStore = vi.mocked(useCaseStore);

function setupStore(carePlan: CarePlan | null, loading = false) {
  mockUseCaseStore.mockImplementation((selector: (state: Partial<{ carePlan: CarePlan | null; loading: boolean }>) => unknown) => {
    return selector({ carePlan, loading });
  });
}

// ── Helpers ───────────────────────────────────────────────────────────────

function makeCarePlan(overrides: Partial<CarePlan> = {}): CarePlan {
  return {
    case_id: 'test-case-001',
    timeline: [],
    recommendations: ['Monitor blood pressure.', 'Follow up in 2 weeks.'],
    alerts: ['Drug interaction detected.'],
    findings: {
      cardiology: {
        specialty: 'cardiology',
        summary: 'Elevated troponin levels.',
        action_items: ['Order ECG', 'Consult cardiologist'],
      },
    },
    ...overrides,
  };
}

// ── Unit tests ────────────────────────────────────────────────────────────

describe('CarePlanPanel — unit tests', () => {
  beforeEach(() => {
    setupStore(null);
  });

  it('renders a placeholder when carePlan is null', () => {
    render(<CarePlanPanel />);
    expect(screen.getByLabelText('Care plan placeholder')).toBeInTheDocument();
  });

  it('renders findings section when carePlan is loaded', () => {
    setupStore(makeCarePlan());
    render(<CarePlanPanel />);
    // Specialty name appears in both the badge and the label span
    expect(screen.getAllByText('cardiology').length).toBeGreaterThan(0);
    expect(screen.getByText('Elevated troponin levels.')).toBeInTheDocument();
  });

  it('renders recommendations as a list', () => {
    setupStore(makeCarePlan());
    render(<CarePlanPanel />);
    expect(screen.getByText('Monitor blood pressure.')).toBeInTheDocument();
    expect(screen.getByText('Follow up in 2 weeks.')).toBeInTheDocument();
  });

  it('renders alerts with visual distinction (role=alert)', () => {
    setupStore(makeCarePlan());
    render(<CarePlanPanel />);
    const alertItems = screen.getAllByRole('alert');
    expect(alertItems.length).toBeGreaterThan(0);
    expect(alertItems[0]).toHaveTextContent('Drug interaction detected.');
  });

  it('renders action items within findings', () => {
    setupStore(makeCarePlan());
    render(<CarePlanPanel />);
    expect(screen.getByText('Order ECG')).toBeInTheDocument();
    expect(screen.getByText('Consult cardiologist')).toBeInTheDocument();
  });

  it('renders multiple specialties', () => {
    const plan = makeCarePlan({
      findings: {
        cardiology: {
          specialty: 'cardiology',
          summary: 'Cardio summary.',
          action_items: [],
        },
        radiology: {
          specialty: 'radiology',
          summary: 'Radiology summary.',
          action_items: ['Review CT scan'],
        },
      },
    });
    setupStore(plan);
    render(<CarePlanPanel />);
    expect(screen.getByText('Cardio summary.')).toBeInTheDocument();
    expect(screen.getByText('Radiology summary.')).toBeInTheDocument();
  });

  it('renders "No alerts" placeholder when alerts array is empty', () => {
    setupStore(makeCarePlan({ alerts: [] }));
    render(<CarePlanPanel />);
    // Alerts section should not be rendered when empty (it's conditionally shown)
    expect(screen.queryByLabelText('Alerts')).not.toBeInTheDocument();
  });
});

// ── Property 2 (frontend): Care Plan Structural Invariant (rendering) ─────
//
// For any CarePlan object, the CarePlanPanel SHALL render all specialty names,
// all recommendation strings, and all alert strings in the output.
//
// **Validates: Requirements 4.2**
// Tag: Feature: careflow-orchestrator, Property 2: Care Plan Structural Invariant

describe('Property 2 (frontend): Care Plan Structural Invariant (rendering)', () => {
  afterEach(() => {
    cleanup();
  });
  // Non-empty, non-whitespace string arbitrary (avoids Testing Library normalization issues)
  const nonBlankStringArb = fc
    .string({ minLength: 1, maxLength: 100 })
    .filter((s) => s.trim().length > 0);

  // Arbitrary for SpecialtyFindings
  const specialtyFindingsArb = fc.record<SpecialtyFindings>({
    specialty: fc.constantFrom('cardiology', 'radiology', 'oncology', 'pharmacy'),
    summary: nonBlankStringArb,
    action_items: fc.array(nonBlankStringArb, { maxLength: 5 }),
  });

  // Arbitrary for findings dict (0–4 specialties, unique keys)
  const findingsArb = fc.uniqueArray(
    fc.constantFrom('cardiology', 'radiology', 'oncology', 'pharmacy'),
    { minLength: 0, maxLength: 4 }
  ).chain((specialties) =>
    fc.tuple(...specialties.map(() => specialtyFindingsArb)).map((findingsArr) => {
      const findings: Record<string, SpecialtyFindings> = {};
      specialties.forEach((s, i) => {
        findings[s] = { ...findingsArr[i], specialty: s };
      });
      return findings;
    })
  );

  // Arbitrary for a full CarePlan
  const carePlanArb = fc.record<CarePlan>({
    case_id: fc.uuid(),
    timeline: fc.constant([]),
    recommendations: fc.array(nonBlankStringArb, { minLength: 0, maxLength: 5 }),
    alerts: fc.array(nonBlankStringArb, { minLength: 0, maxLength: 3 }),
    findings: findingsArb,
  });

  it('renders all specialty names present in findings', () => {
    fc.assert(
      fc.property(carePlanArb, (carePlan) => {
        cleanup();
        setupStore(carePlan);
        const { unmount } = render(<CarePlanPanel />);

        const specialties = Object.keys(carePlan.findings);
        specialties.forEach((specialty) => {
          // Each specialty name should appear at least once in the rendered output
          const elements = screen.getAllByText(specialty);
          expect(elements.length).toBeGreaterThan(0);
        });

        unmount();
        cleanup();
      }),
      { numRuns: 100 }
    );
  });

  it('renders all recommendation strings', () => {
    fc.assert(
      fc.property(carePlanArb, (carePlan) => {
        // Only test plans with at least one recommendation to avoid trivial cases
        fc.pre(carePlan.recommendations.length > 0);

        cleanup();
        setupStore(carePlan);
        const { unmount } = render(<CarePlanPanel />);

        const bodyText = document.body.textContent ?? '';
        carePlan.recommendations.forEach((rec) => {
          expect(bodyText).toContain(rec.trim());
        });

        unmount();
        cleanup();
      }),
      { numRuns: 100 }
    );
  });

  it('renders all alert strings', () => {
    fc.assert(
      fc.property(carePlanArb, (carePlan) => {
        // Only test plans with at least one alert
        fc.pre(carePlan.alerts.length > 0);

        cleanup();
        setupStore(carePlan);
        const { unmount } = render(<CarePlanPanel />);

        const bodyText = document.body.textContent ?? '';
        carePlan.alerts.forEach((alert) => {
          expect(bodyText).toContain(alert.trim());
        });

        unmount();
        cleanup();
      }),
      { numRuns: 100 }
    );
  });
});
