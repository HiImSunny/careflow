/**
 * Tests for ExportBar component.
 *
 * Validates: Requirements 7.1, 7.2, 7.5
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { ExportBar } from './ExportBar';
import { useCaseStore } from '@/store/caseStore';
import type { CarePlan } from '@/types';
import type { CaseStore } from '@/store/caseStore';

// ── Mock the Zustand store ────────────────────────────────────────────────

vi.mock('@/store/caseStore', () => ({
  useCaseStore: vi.fn(),
}));

const mockUseCaseStore = vi.mocked(useCaseStore);

function setupStore(carePlan: CarePlan | null) {
  mockUseCaseStore.mockImplementation((selector: (state: CaseStore) => unknown) => {
    return selector({ carePlan } as CaseStore);
  });
}

// ── Helpers ───────────────────────────────────────────────────────────────

function makeCarePlan(): CarePlan {
  return {
    case_id: 'test-case-001',
    timeline: [],
    recommendations: ['Monitor blood pressure.'],
    alerts: [],
    findings: {},
  };
}

// ── Tests ─────────────────────────────────────────────────────────────────

describe('ExportBar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders Export PDF and Export EMR buttons', () => {
    setupStore(makeCarePlan());
    render(<ExportBar />);
    // Buttons are identified by their aria-label
    expect(screen.getByRole('button', { name: /export care plan as pdf/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /export care plan as emr/i })).toBeInTheDocument();
  });

  it('disables both buttons when carePlan is null', () => {
    setupStore(null);
    render(<ExportBar />);
    const pdfButton = screen.getByRole('button', { name: /export care plan as pdf/i });
    const emrButton = screen.getByRole('button', { name: /export care plan as emr/i });
    expect(pdfButton).toBeDisabled();
    expect(emrButton).toBeDisabled();
  });

  it('enables both buttons when carePlan is loaded', () => {
    setupStore(makeCarePlan());
    render(<ExportBar />);
    const pdfButton = screen.getByRole('button', { name: /export care plan as pdf/i });
    const emrButton = screen.getByRole('button', { name: /export care plan as emr/i });
    expect(pdfButton).not.toBeDisabled();
    expect(emrButton).not.toBeDisabled();
  });

  it('renders tooltip trigger wrapper when carePlan is null', () => {
    setupStore(null);
    render(<ExportBar />);
    // When disabled, buttons are wrapped in a span for tooltip support
    const pdfButton = screen.getByRole('button', { name: /export care plan as pdf/i });
    expect(pdfButton.closest('span')).toBeInTheDocument();
  });

  it('does not wrap buttons in tooltip span when carePlan is loaded', () => {
    setupStore(makeCarePlan());
    render(<ExportBar />);
    // When enabled, buttons are rendered directly without tooltip wrapper span
    const pdfButton = screen.getByRole('button', { name: /export care plan as pdf/i });
    // The button should not be inside a tooltip trigger span
    expect(pdfButton.closest('[data-state]')).toBeNull();
  });

  it('shows visible button text "Export PDF" and "Export EMR"', () => {
    setupStore(makeCarePlan());
    render(<ExportBar />);
    expect(screen.getByText('Export PDF')).toBeInTheDocument();
    expect(screen.getByText('Export EMR')).toBeInTheDocument();
  });
});
