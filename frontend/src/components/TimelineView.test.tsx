/**
 * Tests for TimelineView component.
 *
 * Includes:
 *  - Unit tests for specific rendering scenarios
 *  - Property 9: Timeline Rendering Completeness
 *
 * **Validates: Requirements 4.1**
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, within, cleanup } from '@testing-library/react';
import '@testing-library/jest-dom';
import * as fc from 'fast-check';
import { TimelineView } from './TimelineView';
import type { TimelineEntry } from '@/types';
import { useCaseStore } from '@/store/caseStore';

// ── Mock the Zustand store so tests are isolated ──────────────────────────

vi.mock('@/store/caseStore', () => ({
  useCaseStore: vi.fn(),
}));

const mockUseCaseStore = vi.mocked(useCaseStore);

function setupStore(timeline: TimelineEntry[] = [], loading = false) {
  // useCaseStore is called with a selector function; simulate that
  mockUseCaseStore.mockImplementation((selector: (state: Partial<{ carePlan: { timeline: TimelineEntry[] } | null; loading: boolean }>) => unknown) => {
    return selector({ carePlan: timeline.length > 0 ? { timeline } : null, loading });
  });
}

// ── Helpers ───────────────────────────────────────────────────────────────

function makeEntry(overrides: Partial<TimelineEntry> = {}): TimelineEntry {
  return {
    timestamp: '2024-01-15T10:30:00Z',
    specialty: 'cardiology',
    description: 'Patient presents with chest pain.',
    ...overrides,
  };
}

// ── Unit tests ────────────────────────────────────────────────────────────

describe('TimelineView — unit tests', () => {
  beforeEach(() => {
    setupStore([]);
  });

  it('renders a placeholder when timeline prop is empty', () => {
    render(<TimelineView timeline={[]} />);
    expect(screen.getByLabelText('Timeline placeholder')).toBeInTheDocument();
  });

  it('renders a placeholder when no prop is given and store has no carePlan', () => {
    render(<TimelineView />);
    expect(screen.getByLabelText('Timeline placeholder')).toBeInTheDocument();
  });

  it('renders the correct number of timeline items', () => {
    const entries: TimelineEntry[] = [
      makeEntry({ specialty: 'cardiology', description: 'Chest pain noted.' }),
      makeEntry({ specialty: 'radiology', description: 'X-ray ordered.' }),
      makeEntry({ specialty: 'pharmacy', description: 'Medication review.' }),
    ];
    render(<TimelineView timeline={entries} />);
    const items = screen.getAllByTestId('timeline-item');
    expect(items).toHaveLength(3);
  });

  it('renders specialty badge text for each entry', () => {
    const entries: TimelineEntry[] = [
      makeEntry({ specialty: 'cardiology', description: 'Cardio finding.' }),
      makeEntry({ specialty: 'oncology', description: 'Oncology finding.' }),
    ];
    render(<TimelineView timeline={entries} />);
    expect(screen.getByText('cardiology')).toBeInTheDocument();
    expect(screen.getByText('oncology')).toBeInTheDocument();
  });

  it('renders description text for each entry', () => {
    const entries: TimelineEntry[] = [
      makeEntry({ description: 'Unique description alpha.' }),
      makeEntry({ description: 'Unique description beta.' }),
    ];
    render(<TimelineView timeline={entries} />);
    expect(screen.getByText('Unique description alpha.')).toBeInTheDocument();
    expect(screen.getByText('Unique description beta.')).toBeInTheDocument();
  });

  it('renders a formatted timestamp', () => {
    const entry = makeEntry({ timestamp: '2024-06-01T09:00:00Z' });
    render(<TimelineView timeline={[entry]} />);
    // The time element should be present with the ISO timestamp as dateTime
    const timeEl = document.querySelector('time');
    expect(timeEl).toBeInTheDocument();
    expect(timeEl?.getAttribute('dateTime')).toBe('2024-06-01T09:00:00Z');
  });

  it('reads timeline from the Zustand store when no prop is given', () => {
    const storeEntries: TimelineEntry[] = [
      makeEntry({ description: 'From store.' }),
    ];
    setupStore(storeEntries);
    render(<TimelineView />);
    expect(screen.getByText('From store.')).toBeInTheDocument();
  });
});

// ── Property 9: Timeline Rendering Completeness ───────────────────────────
//
// For any Care Plan with N timeline entries, the TimelineView SHALL render
// exactly N timeline items, each containing the specialty badge text and
// description text from the corresponding entry.
//
// **Validates: Requirements 4.1**
// Tag: Feature: careflow-orchestrator, Property 9: Timeline Rendering Completeness

describe('Property 9: Timeline Rendering Completeness', () => {
  beforeEach(() => {
    setupStore([]);
  });

  afterEach(() => {
    cleanup();
  });

  // Arbitrary for a single TimelineEntry — description must be non-blank so
  // Testing Library can find it (whitespace-only strings normalize to empty).
  const timelineEntryArb = fc.record<TimelineEntry>({
    timestamp: fc.date({ min: new Date('2020-01-01'), max: new Date('2030-12-31') })
      .map((d) => d.toISOString()),
    specialty: fc.constantFrom('cardiology', 'radiology', 'oncology', 'pharmacy', 'unknown'),
    description: fc
      .string({ minLength: 1, maxLength: 200 })
      .filter((s) => s.trim().length > 0),
  });

  // Arbitrary for an array of 0–20 entries
  const timelineArb = fc.array(timelineEntryArb, { minLength: 0, maxLength: 20 });

  it('renders exactly N timeline items for any array of N entries', () => {
    fc.assert(
      fc.property(timelineArb, (entries) => {
        cleanup(); // ensure clean DOM before each iteration
        const { unmount } = render(<TimelineView timeline={entries} />);

        if (entries.length === 0) {
          // Empty case: placeholder shown, no timeline items
          expect(screen.getByLabelText('Timeline placeholder')).toBeInTheDocument();
          expect(screen.queryAllByTestId('timeline-item')).toHaveLength(0);
        } else {
          const items = screen.getAllByTestId('timeline-item');
          expect(items).toHaveLength(entries.length);
        }

        unmount();
        cleanup();
      }),
      { numRuns: 100 }
    );
  });

  it('each rendered item contains the specialty and description from the corresponding entry', () => {
    fc.assert(
      fc.property(
        fc.array(timelineEntryArb, { minLength: 1, maxLength: 10 }),
        (entries) => {
          cleanup(); // ensure clean DOM before each iteration
          const { unmount } = render(<TimelineView timeline={entries} />);
          const items = screen.getAllByTestId('timeline-item');

          expect(items).toHaveLength(entries.length);

          entries.forEach((entry, i) => {
            const item = items[i];
            // Specialty badge text should appear within the item
            expect(within(item).getAllByText(entry.specialty).length).toBeGreaterThan(0);
            // Description text should appear within the item using textContent
            expect(item.textContent).toContain(entry.description.trim());
          });

          unmount();
          cleanup();
        }
      ),
      { numRuns: 100 }
    );
  });
});
