/**
 * useSpeech — real-time speech-to-text hook via WebSocket + MediaRecorder.
 *
 * Behaviour:
 * - `startRecording()`: requests microphone permission, opens a WebSocket to
 *   `/api/speech/transcribe`, and streams audio/webm chunks via MediaRecorder.
 * - `stopRecording()`: stops the MediaRecorder, closes the WebSocket, and
 *   sets `isRecording` to false.
 * - Each transcription message received over the WebSocket is appended to the
 *   local `transcript` state and also appended to `caseText` in the Zustand
 *   store via `setCaseText`.
 * - WebSocket errors set the `error` state and revert `isRecording` to false.
 *
 * Requirements: 9.1, 9.3, 9.4, 9.5
 */

import { useCallback, useRef, useState } from 'react';
import { useCaseStore } from '@/store/caseStore';

/** Return type of the useSpeech hook. */
export interface UseSpeechResult {
  isRecording: boolean;
  startRecording: () => void;
  stopRecording: () => void;
  transcript: string;
  error: string | null;
}

/** MIME type used for MediaRecorder audio chunks. */
const AUDIO_MIME_TYPE = 'audio/webm';

/** WebSocket endpoint for real-time transcription. */
const WS_ENDPOINT = '/api/speech/transcribe';

/**
 * Builds the WebSocket URL from the current page origin.
 * Converts http(s) → ws(s) so the hook works in both dev and prod.
 */
function buildWsUrl(): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  return `${protocol}//${host}${WS_ENDPOINT}`;
}

/**
 * Real implementation of the speech hook.
 * Manages microphone access, MediaRecorder lifecycle, and WebSocket connection.
 */
export function useSpeech(): UseSpeechResult {
  const { caseText, setCaseText } = useCaseStore();

  const [isRecording, setIsRecording] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [error, setError] = useState<string | null>(null);

  // Refs so that stopRecording() can access the live instances without
  // needing them in the dependency array of useCallback.
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // Keep a ref to the latest caseText so the transcription handler always
  // appends to the current value without stale closure issues.
  const caseTextRef = useRef(caseText);
  caseTextRef.current = caseText;

  const stopRecording = useCallback(() => {
    // Stop MediaRecorder
    if (
      mediaRecorderRef.current &&
      mediaRecorderRef.current.state !== 'inactive'
    ) {
      mediaRecorderRef.current.stop();
    }
    mediaRecorderRef.current = null;

    // Stop all microphone tracks
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    // Close WebSocket
    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }

    setIsRecording(false);
  }, []);

  const startRecording = useCallback(async () => {
    // Clear any previous error
    setError(null);

    // ── 1. Request microphone permission ──────────────────────────────────
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : 'Microphone access denied. Please allow microphone access and try again.';
      setError(message);
      return;
    }
    streamRef.current = stream;

    // ── 2. Open WebSocket connection ──────────────────────────────────────
    let socket: WebSocket;
    try {
      socket = new WebSocket(buildWsUrl());
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to open speech service connection.';
      setError(message);
      stream.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      return;
    }
    socketRef.current = socket;

    socket.onopen = () => {
      // ── 3. Start MediaRecorder once the socket is open ──────────────────
      const mimeType = MediaRecorder.isTypeSupported(AUDIO_MIME_TYPE)
        ? AUDIO_MIME_TYPE
        : '';

      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (event: BlobEvent) => {
        if (
          event.data.size > 0 &&
          socketRef.current?.readyState === WebSocket.OPEN
        ) {
          socketRef.current.send(event.data);
        }
      };

      // Emit chunks every 250 ms for low-latency streaming
      recorder.start(250);
      setIsRecording(true);
    };

    // ── 4. Handle incoming transcription messages ─────────────────────────
    socket.onmessage = (event: MessageEvent) => {
      let newText = '';

      if (typeof event.data === 'string') {
        try {
          // The server may send JSON like { "transcript": "..." }
          const parsed = JSON.parse(event.data) as Record<string, unknown>;
          if (typeof parsed.transcript === 'string') {
            newText = parsed.transcript;
          } else if (typeof parsed.text === 'string') {
            newText = parsed.text;
          } else {
            // Fallback: treat the whole string as plain text
            newText = event.data;
          }
        } catch {
          // Not JSON — treat as plain transcription text
          newText = event.data;
        }
      }

      if (newText) {
        // Append to local transcript state
        setTranscript((prev) => prev + newText);

        // Append to Zustand caseText (using ref to avoid stale closure)
        setCaseText(caseTextRef.current + newText);
      }
    };

    // ── 5. Handle WebSocket errors ────────────────────────────────────────
    socket.onerror = () => {
      setError('Speech service connection error. Please try again.');
      stopRecording();
    };

    socket.onclose = (event: CloseEvent) => {
      // Only treat unexpected closes as errors (code 1000 = normal closure)
      if (!event.wasClean && event.code !== 1000 && isRecording) {
        setError('Speech service connection closed unexpectedly.');
      }
      setIsRecording(false);
    };
  }, [setCaseText, stopRecording]);

  return { isRecording, startRecording, stopRecording, transcript, error };
}
