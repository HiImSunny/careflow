/**
 * Custom hook for submitting cases to the orchestration API.
 *
 * Includes 1 automatic retry on network errors before surfacing the error
 * to the user. API error responses are converted to user-friendly messages
 * (never raw JSON).
 *
 * Requirements: 1.1, 1.2, 4.4, 4.5, 1.5
 */

import axios from 'axios';
import { useCaseStore } from '@/store/caseStore';
import type { OrchestrateInput, CarePlan } from '@/types';

/** Return type of the useOrchestrate hook. */
export interface UseOrchestrateResult {
  orchestrate: (input: OrchestrateInput) => Promise<void>;
  loading: boolean;
  error: string | null;
}

/** Maximum number of automatic retries on network error before surfacing to user. */
const MAX_RETRIES = 1;

/**
 * Converts a File object to a base64-encoded string (without the data URL prefix).
 */
async function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      // Strip the "data:<mime>;base64," prefix
      const base64 = result.split(',')[1];
      resolve(base64);
    };
    reader.onerror = () => reject(new Error('Failed to read file'));
    reader.readAsDataURL(file);
  });
}

/**
 * Returns true when the error is a network-level failure (no response received),
 * which is a candidate for automatic retry.
 */
function isNetworkError(err: unknown): boolean {
  return axios.isAxiosError(err) && !err.response;
}

/**
 * Extracts a user-friendly error message from an Axios or generic error.
 * Never returns raw JSON — always a readable string.
 */
function extractErrorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const data = err.response?.data;

    if (data) {
      // Prefer explicit error/detail fields over raw JSON
      if (typeof data === 'string') {
        // Avoid surfacing raw JSON strings
        try {
          const parsed = JSON.parse(data) as Record<string, unknown>;
          return (
            (typeof parsed.detail === 'string' ? parsed.detail : null) ??
            (typeof parsed.error === 'string' ? parsed.error : null) ??
            (typeof parsed.message === 'string' ? parsed.message : null) ??
            'The server returned an unexpected error. Please try again.'
          );
        } catch {
          // Not JSON — return as-is if it looks like a plain message
          return data.length < 200 ? data : 'The server returned an unexpected error. Please try again.';
        }
      }

      if (typeof data === 'object') {
        const d = data as Record<string, unknown>;
        return (
          (typeof d.detail === 'string' ? d.detail : null) ??
          (typeof d.error === 'string' ? d.error : null) ??
          (typeof d.message === 'string' ? d.message : null) ??
          'The server returned an unexpected error. Please try again.'
        );
      }
    }

    // Network-level errors
    if (!err.response) {
      return 'Unable to reach the server. Please check your connection and try again.';
    }

    // HTTP status-based fallbacks
    const status = err.response.status;
    if (status === 422) return 'Invalid input. Please provide case notes, an image, or audio before submitting.';
    if (status === 502) return 'The AI service is temporarily unavailable. Please try again in a moment.';
    if (status === 503) return 'A required service is unavailable. Please try again later.';
    if (status >= 500) return 'A server error occurred. Please try again.';
    if (status === 404) return 'The requested resource was not found.';

    return err.message ?? 'An unexpected error occurred.';
  }

  if (err instanceof Error) {
    return err.message;
  }

  return 'An unexpected error occurred.';
}

/**
 * Hook that wraps the POST /api/orchestrate call.
 * Manages loading and error state via the Zustand store.
 * Automatically retries once on network errors before surfacing to the user.
 */
export function useOrchestrate(): UseOrchestrateResult {
  const { loading, error, caseImage, setCarePlan, setLoading, setError } =
    useCaseStore();

  const orchestrate = async (input: OrchestrateInput): Promise<void> => {
    setLoading(true);
    setError(null);

    // Convert image File to base64 once (before retry loop)
    let image_b64: string | undefined = input.image_b64;
    if (!image_b64 && caseImage) {
      try {
        image_b64 = await fileToBase64(caseImage);
      } catch {
        setError('Failed to process the uploaded image. Please try again.');
        setLoading(false);
        return;
      }
    }

    const payload: OrchestrateInput = { ...input, image_b64 };

    let lastError: unknown = null;

    for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
      try {
        const response = await axios.post<CarePlan>('/api/orchestrate', payload);
        setCarePlan(response.data);
        setLoading(false);
        return;
      } catch (err: unknown) {
        lastError = err;

        // Only retry on network errors (no response received); for HTTP errors
        // (4xx/5xx) surface immediately — retrying won't help.
        if (attempt < MAX_RETRIES && isNetworkError(err)) {
          // Brief pause before retry to avoid hammering the server
          await new Promise((resolve) => setTimeout(resolve, 500));
          continue;
        }

        // Either not a network error, or we've exhausted retries
        break;
      }
    }

    setError(extractErrorMessage(lastError));
    setLoading(false);
  };

  return { orchestrate, loading, error };
}
