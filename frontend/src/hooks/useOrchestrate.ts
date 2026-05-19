/**
 * Custom hook for submitting cases to the orchestration API.
 *
 * Flow:
 * 1. POST /api/orchestrate → receives {case_id, status: "processing"} (202)
 * 2. Sets pendingCaseId so AgentChat connects to SSE immediately
 * 3. When SSE emits type:"complete", fetches /api/orchestrate/{case_id}/result
 * 4. Calls setCarePlan() and setLoading(false)
 *
 * Includes 1 automatic retry on network errors before surfacing the error
 * to the user. API error responses are converted to user-friendly messages
 * (never raw JSON).
 *
 * Requirements: 1.1, 1.2, 4.4, 4.5, 1.5
 */

import { useEffect, useRef } from 'react';
import axios from 'axios';
import { useCaseStore } from '@/store/caseStore';
import { apiUrl } from '@/lib/api';
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
 *
 * After receiving the case_id (202), it opens an SSE connection to watch
 * agent messages stream in real-time. When the SSE "complete" event fires,
 * it fetches the full care plan from /api/orchestrate/{case_id}/result.
 */
export function useOrchestrate(): UseOrchestrateResult {
  const { loading, error, caseImage, setCarePlan, setLoading, setError, setPendingCaseId } =
    useCaseStore();
  const clearMessages = () => useCaseStore.setState({ agentMessages: [], carePlan: null });

  // Track the active SSE connection so we can close it on unmount or new submission.
  const sseRef = useRef<EventSource | null>(null);

  // Clean up SSE on unmount.
  useEffect(() => {
    return () => {
      sseRef.current?.close();
    };
  }, []);

  const orchestrate = async (input: OrchestrateInput): Promise<void> => {
    // Close any previous SSE connection.
    sseRef.current?.close();
    sseRef.current = null;

    setLoading(true);
    setError(null);
    clearMessages();

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
    let case_id: string | null = null;

    // ------------------------------------------------------------------
    // Step 1: POST to /api/orchestrate — get case_id back immediately (202)
    // ------------------------------------------------------------------
    for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
      try {
        const response = await axios.post<{ case_id: string; status: string }>(
          apiUrl('/api/orchestrate'),
          payload,
        );
        case_id = response.data.case_id;
        break;
      } catch (err: unknown) {
        lastError = err;
        if (attempt < MAX_RETRIES && isNetworkError(err)) {
          await new Promise((resolve) => setTimeout(resolve, 500));
          continue;
        }
        setError(extractErrorMessage(lastError));
        setLoading(false);
        return;
      }
    }

    if (!case_id) {
      setError('Failed to start orchestration. Please try again.');
      setLoading(false);
      return;
    }

    // ------------------------------------------------------------------
    // Step 2: Set pendingCaseId so AgentChat connects to SSE
    // ------------------------------------------------------------------
    setPendingCaseId(case_id);

    // ------------------------------------------------------------------
    // Step 3: Open SSE connection and wait for "complete" event
    // ------------------------------------------------------------------
    const capturedCaseId = case_id;
    const sse = new EventSource(apiUrl(`/api/chat/${capturedCaseId}`));
    sseRef.current = sse;

    sse.onmessage = async (event: MessageEvent) => {
      try {
        const msg = JSON.parse(event.data as string) as {
          type?: string;
          agent?: string;
          content?: string;
          timestamp?: string;
        };

        if (msg.type === 'complete') {
          // Step 4: Fetch the full care plan result
          sse.close();
          sseRef.current = null;

          try {
            const resultResponse = await axios.get<CarePlan>(
              apiUrl(`/api/orchestrate/${capturedCaseId}/result`),
            );
            setCarePlan(resultResponse.data);
          } catch (fetchErr) {
            setError(extractErrorMessage(fetchErr));
          } finally {
            setLoading(false);
            setPendingCaseId(null);
          }
        } else if (msg.type === 'error') {
          sse.close();
          sseRef.current = null;
          setError(msg.content ?? 'Orchestration failed. Please try again.');
          setLoading(false);
          setPendingCaseId(null);
        }
        // Regular agent messages are handled by AgentChat via its own SSE listener.
      } catch {
        // Ignore parse errors on keep-alive comments.
      }
    };

    sse.onerror = () => {
      // Only surface an error if we're still loading (not already completed).
      if (useCaseStore.getState().loading) {
        sse.close();
        sseRef.current = null;
        setError('Lost connection to the server. Please try again.');
        setLoading(false);
        setPendingCaseId(null);
      }
    };
  };

  return { orchestrate, loading, error };
}
