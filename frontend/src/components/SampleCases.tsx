/**
 * SampleCases component — displays pre-built sample cases for quick loading.
 *
 * Fetches sample cases from GET /api/cases/samples on mount and renders
 * a list of clickable cards. Selecting a card populates the case text
 * input via the Zustand store.
 *
 * Requirements: 6.1, 6.2
 */

import { useEffect, useState } from 'react';
import axios from 'axios';
import { useCaseStore } from '../store/caseStore';
import { apiUrl } from '@/lib/api';
import type { SampleCase } from '../types';

/** Color mapping for specialty badges. */
const SPECIALTY_COLORS: Record<string, string> = {
  cardiology: 'bg-red-100 text-red-700',
  radiology: 'bg-blue-100 text-blue-700',
  oncology: 'bg-purple-100 text-purple-700',
  pharmacy: 'bg-green-100 text-green-700',
};

/** Fallback color for unknown specialties. */
const DEFAULT_BADGE_COLOR = 'bg-gray-100 text-gray-700';

function SpecialtyBadge({ specialty }: { specialty: string }) {
  const colorClass = SPECIALTY_COLORS[specialty.toLowerCase()] ?? DEFAULT_BADGE_COLOR;
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium capitalize ${colorClass}`}
    >
      {specialty}
    </span>
  );
}

export function SampleCases() {
  const [samples, setSamples] = useState<SampleCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const setCaseText = useCaseStore((state) => state.setCaseText);

  useEffect(() => {
    let cancelled = false;

    async function fetchSamples() {
      try {
        const response = await axios.get<SampleCase[]>(apiUrl('/api/cases/samples'));
        if (!cancelled) {
          const data = response.data;
          setSamples(Array.isArray(data) ? data : []);
        }
      } catch (err) {
        if (!cancelled) {
          setError('Failed to load sample cases.');
          console.error('SampleCases fetch error:', err);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    fetchSamples();

    return () => {
      cancelled = true;
    };
  }, []);

  function handleSelect(sample: SampleCase) {
    setSelectedId(sample.id);
    setCaseText(sample.text);
  }

  if (loading) {
    return (
      <div className="space-y-2 p-2" aria-label="Loading sample cases">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="h-16 animate-pulse rounded-lg bg-gray-100"
            aria-hidden="true"
          />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <p className="p-2 text-sm text-red-600" role="alert">
        {error}
      </p>
    );
  }

  if (samples.length === 0) {
    return (
      <p className="p-2 text-sm text-gray-500">No sample cases available.</p>
    );
  }

  return (
    <section aria-label="Sample cases">
      <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-500">
        Sample Cases
      </h2>
      <ul className="space-y-2" role="list">
        {samples.map((sample) => (
          <li key={sample.id}>
            <button
              type="button"
              onClick={() => handleSelect(sample)}
              aria-label={`Load sample case: ${sample.title}`}
              aria-pressed={selectedId === sample.id}
              className={`w-full rounded-lg border p-3 text-left transition-colors hover:bg-blue-50 focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                selectedId === sample.id
                  ? 'border-blue-400 bg-blue-50'
                  : 'border-gray-200 bg-white'
              }`}
            >
              <p className="mb-1.5 text-sm font-medium text-gray-800">
                {sample.title}
              </p>
              <div className="flex flex-wrap gap-1">
                {sample.specialties.map((specialty) => (
                  <SpecialtyBadge key={specialty} specialty={specialty} />
                ))}
              </div>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default SampleCases;
