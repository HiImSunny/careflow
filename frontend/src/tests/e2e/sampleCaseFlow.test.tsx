/**
 * End-to-end flow tests for sample case selection and CarePlanPanel rendering.
 *
 * Simulates:
 * 1. Selecting a sample case (populating the Zustand store via setCaseText)
 * 2. Submitting the case (setting carePlan in the store)
 * 3. Verifying that CarePlanPanel renders the expected findings
 *
 * Uses vitest + @testing-library/react.
 * Validates: Requirements 6.1, 6.2, 6.3
 */

import React from 'react';
import { render, screen, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { CarePlanPanel } from '@/components/CarePlanPanel';
import { useCaseStore } from '@/store/caseStore';
import type { CarePlan, SampleCase } from '@/types';

// ---------------------------------------------------------------------------
// Sample case data (mirrors backend/data/sample_cases.json)
// ---------------------------------------------------------------------------

const SAMPLE_CASES: SampleCase[] = [
  {
    id: 'sample-1',
    title: 'Chest Pain with Imaging',
    specialties: ['cardiology', 'radiology'],
    text: '65-year-old male with a 2-hour history of crushing substernal chest pain radiating to the left arm, associated with diaphoresis and mild dyspnea.',
  },
  {
    id: 'sample-2',
    title: 'Lung Mass with Medication Review',
    specialties: ['radiology', 'oncology', 'pharmacy'],
    text: '58-year-old female referred for evaluation of an incidental 3.2 cm spiculated right upper lobe lung mass.',
  },
  {
    id: 'sample-3',
    title: 'Multi-Specialty Complex Case',
    specialties: ['cardiology', 'oncology', 'pharmacy', 'radiology'],
    text: '72-year-old male with a complex medical history presenting for multidisciplinary evaluation.',
  },
];

// ---------------------------------------------------------------------------
// Care plan fixtures — one per sample case
// ---------------------------------------------------------------------------

function makeMockCarePlan(caseId: string, specialties: string[]): CarePlan {
  const findings: CarePlan['findings'] = {};
  for (const specialty of specialties) {
    findings[specialty] = {
      specialty,
      summary: `Mock ${specialty} summary for ${caseId}.`,
      action_items: [`Action 1 for ${specialty}`, `Action 2 for ${specialty}`],
    };
  }
  return {
    case_id: caseId,
    timeline: specialties.map((s) => ({
      timestamp: '2024-01-01T10:00:00Z',
      specialty: s,
      description: `Mock ${s} finding.`,
    })),
    recommendations: specialties.map((s) => `Recommendation for ${s}`),
    alerts: ['Mock alert: review all findings carefully.'],
    findings,
  };
}

const MOCK_CARE_PLANS: Record<string, CarePlan> = {
  'sample-1': makeMockCarePlan('sample-1', ['cardiology', 'radiology']),
  'sample-2': makeMockCarePlan('sample-2', ['radiology', 'oncology', 'pharmacy']),
  'sample-3': makeMockCarePlan('sample-3', ['cardiology', 'oncology', 'pharmacy', 'radiology']),
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Reset the Zustand store to its initial state before each test. */
function resetStore() {
  useCaseStore.getState().reset();
}

/** Simulate selecting a sample case and receiving a care plan. */
function simulateSampleCaseFlow(sampleCase: SampleCase): void {
  const store = useCaseStore.getState();
  // Step 1: user selects a sample case → store gets the text
  store.setCaseText(sampleCase.text);
  // Step 2: orchestration completes → store gets the care plan
  store.setCarePlan(MOCK_CARE_PLANS[sampleCase.id]);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Sample Case Flow — CarePlanPanel rendering', () => {
  beforeEach(() => {
    resetStore();
  });

  // ── Requirement 6.1: sample cases are available ──────────────────────────

  it('should have at least 3 sample cases available', () => {
    expect(SAMPLE_CASES.length).toBeGreaterThanOrEqual(3);
  });

  it('each sample case should have id, title, specialties, and text', () => {
    for (const sc of SAMPLE_CASES) {
      expect(sc.id).toBeTruthy();
      expect(sc.title).toBeTruthy();
      expect(sc.specialties.length).toBeGreaterThanOrEqual(1);
      expect(sc.text.trim().length).toBeGreaterThan(0);
    }
  });

  it('sample cases should cover different specialty combinations', () => {
    const sets = SAMPLE_CASES.map((sc) => JSON.stringify([...sc.specialties].sort()));
    const unique = new Set(sets);
    expect(unique.size).toBeGreaterThanOrEqual(2);
  });

  // ── Requirement 6.2: selecting a sample case populates the store ─────────

  it('selecting sample-1 populates caseText in the store', () => {
    const sc = SAMPLE_CASES[0];
    act(() => {
      useCaseStore.getState().setCaseText(sc.text);
    });
    expect(useCaseStore.getState().caseText).toBe(sc.text);
  });

  it('selecting sample-2 populates caseText in the store', () => {
    const sc = SAMPLE_CASES[1];
    act(() => {
      useCaseStore.getState().setCaseText(sc.text);
    });
    expect(useCaseStore.getState().caseText).toBe(sc.text);
  });

  it('selecting sample-3 populates caseText in the store', () => {
    const sc = SAMPLE_CASES[2];
    act(() => {
      useCaseStore.getState().setCaseText(sc.text);
    });
    expect(useCaseStore.getState().caseText).toBe(sc.text);
  });

  // ── CarePlanPanel renders placeholder when no plan is loaded ─────────────

  it('renders placeholder when no care plan is loaded', () => {
    render(<CarePlanPanel />);
    expect(
      screen.getByText(/no care plan loaded/i)
    ).toBeInTheDocument();
  });

  // ── Sample case 1: Chest Pain with Imaging ───────────────────────────────

  it('renders CarePlanPanel findings for sample-1 (cardiology + radiology)', () => {
    act(() => {
      simulateSampleCaseFlow(SAMPLE_CASES[0]);
    });

    render(<CarePlanPanel />);

    // Findings section heading
    expect(screen.getByText(/findings by specialty/i)).toBeInTheDocument();

    // Specialty badges / headings — multiple elements expected (badge + heading + content)
    expect(screen.getAllByText(/cardiology/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/radiology/i).length).toBeGreaterThan(0);

    // Recommendations
    expect(screen.getByText(/recommendation for cardiology/i)).toBeInTheDocument();
    expect(screen.getByText(/recommendation for radiology/i)).toBeInTheDocument();

    // Alert
    expect(screen.getByText(/mock alert/i)).toBeInTheDocument();
  });

  it('renders action items for sample-1 findings', () => {
    act(() => {
      simulateSampleCaseFlow(SAMPLE_CASES[0]);
    });

    render(<CarePlanPanel />);

    expect(screen.getByText(/action 1 for cardiology/i)).toBeInTheDocument();
    expect(screen.getByText(/action 1 for radiology/i)).toBeInTheDocument();
  });

  // ── Sample case 2: Lung Mass with Medication Review ──────────────────────

  it('renders CarePlanPanel findings for sample-2 (radiology + oncology + pharmacy)', () => {
    act(() => {
      simulateSampleCaseFlow(SAMPLE_CASES[1]);
    });

    render(<CarePlanPanel />);

    expect(screen.getByText(/findings by specialty/i)).toBeInTheDocument();
    expect(screen.getAllByText(/radiology/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/oncology/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/pharmacy/i).length).toBeGreaterThan(0);

    expect(screen.getByText(/recommendation for radiology/i)).toBeInTheDocument();
    expect(screen.getByText(/recommendation for oncology/i)).toBeInTheDocument();
    expect(screen.getByText(/recommendation for pharmacy/i)).toBeInTheDocument();
  });

  it('renders action items for sample-2 findings', () => {
    act(() => {
      simulateSampleCaseFlow(SAMPLE_CASES[1]);
    });

    render(<CarePlanPanel />);

    expect(screen.getByText(/action 1 for oncology/i)).toBeInTheDocument();
    expect(screen.getByText(/action 1 for pharmacy/i)).toBeInTheDocument();
  });

  // ── Sample case 3: Multi-Specialty Complex Case ───────────────────────────

  it('renders CarePlanPanel findings for sample-3 (all four specialties)', () => {
    act(() => {
      simulateSampleCaseFlow(SAMPLE_CASES[2]);
    });

    render(<CarePlanPanel />);

    expect(screen.getByText(/findings by specialty/i)).toBeInTheDocument();
    expect(screen.getAllByText(/cardiology/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/oncology/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/pharmacy/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/radiology/i).length).toBeGreaterThan(0);
  });

  it('renders all four specialty summaries for sample-3', () => {
    act(() => {
      simulateSampleCaseFlow(SAMPLE_CASES[2]);
    });

    render(<CarePlanPanel />);

    for (const specialty of ['cardiology', 'oncology', 'pharmacy', 'radiology']) {
      expect(
        screen.getByText(new RegExp(`mock ${specialty} summary`, 'i'))
      ).toBeInTheDocument();
    }
  });

  it('renders recommendations for all four specialties in sample-3', () => {
    act(() => {
      simulateSampleCaseFlow(SAMPLE_CASES[2]);
    });

    render(<CarePlanPanel />);

    for (const specialty of ['cardiology', 'oncology', 'pharmacy', 'radiology']) {
      expect(
        screen.getByText(new RegExp(`recommendation for ${specialty}`, 'i'))
      ).toBeInTheDocument();
    }
  });

  // ── Structural validity checks ────────────────────────────────────────────

  it('CarePlanPanel renders alerts section when alerts are present', () => {
    act(() => {
      simulateSampleCaseFlow(SAMPLE_CASES[0]);
    });

    render(<CarePlanPanel />);

    // The alerts heading should be visible
    expect(screen.getByText(/alerts/i)).toBeInTheDocument();
    // The alert content should be visible
    expect(screen.getByText(/mock alert/i)).toBeInTheDocument();
  });

  it('CarePlanPanel renders recommendations section', () => {
    act(() => {
      simulateSampleCaseFlow(SAMPLE_CASES[0]);
    });

    render(<CarePlanPanel />);

    expect(screen.getByText(/recommendations/i)).toBeInTheDocument();
  });

  it('care plan panel has correct aria-label', () => {
    act(() => {
      simulateSampleCaseFlow(SAMPLE_CASES[0]);
    });

    render(<CarePlanPanel />);

    expect(screen.getByRole('region', { name: /care plan panel/i })).toBeInTheDocument();
  });

  // ── Loading state ─────────────────────────────────────────────────────────

  it('renders loading skeleton when loading is true', () => {
    act(() => {
      useCaseStore.getState().setLoading(true);
    });

    render(<CarePlanPanel />);

    expect(screen.getByRole('region', { name: /loading care plan/i })).toBeInTheDocument();
  });

  // ── Store state transitions ───────────────────────────────────────────────

  it('transitions from placeholder to care plan after setCarePlan is called', () => {
    const { rerender } = render(<CarePlanPanel />);

    // Initially shows placeholder
    expect(screen.getByText(/no care plan loaded/i)).toBeInTheDocument();

    // Simulate orchestration completing
    act(() => {
      useCaseStore.getState().setCarePlan(MOCK_CARE_PLANS['sample-1']);
    });

    rerender(<CarePlanPanel />);

    // Now shows care plan
    expect(screen.queryByText(/no care plan loaded/i)).not.toBeInTheDocument();
    expect(screen.getByText(/findings by specialty/i)).toBeInTheDocument();
  });
});
