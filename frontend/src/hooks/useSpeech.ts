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
import { wsUrl } from '@/lib/api';

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
 * Builds the WebSocket URL, using VITE_API_URL in production or
 * deriving from the current page origin in development.
 */
function buildWsUrl(): string {
  return wsUrl(WS_ENDPOINT);
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

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const caseTextRef = useRef(caseText);
  caseTextRef.current = caseText;

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    mediaRecorderRef.current = null;

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }

    setIsRecording(false);
  }, []);

  const startRecording = useCallback(async () => {
    setError(null);

    // 1. Request microphone permission
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

    // 2. Open WebSocket connection
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
      // 3. Start MediaRecorder once the socket is open
      const mimeType = MediaRecorder.isTypeSupported(AUDIO_MIME_TYPE) ? AUDIO_MIME_TYPE : '';
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (event: BlobEvent) => {
        if (event.data.size > 0 && socketRef.current?.readyState === WebSocket.OPEN) {
          socketRef.current.send(event.data);
        }
      };

      recorder.start(250);
      setIsRecording(true);
    };

    // 4. Handle incoming transcription messages
    socket.onmessage = (event: MessageEvent) => {
      let newText = '';

      if (typeof event.data === 'string') {
        try {
          const parsed = JSON.parse(event.data) as Record<string, unknown>;
          if (typeof parsed.transcript === 'string') {
            newText = parsed.transcript;
          } else if (typeof parsed.text === 'string') {
            newText = parsed.text;
          } else {
            newText = event.data;
          }
        } catch {
          newText = event.data;
        }
      }

      if (newText) {
        setTranscript((prev) => prev + newText);
        setCaseText(caseTextRef.current + newText);
      }
    };

    // 5. Handle WebSocket errors
    socket.onerror = () => {
      setError('Speech service connection error. Please try again.');
      stopRecording();
    };

    socket.onclose = (event: CloseEvent) => {
      if (!event.wasClean && event.code !== 1000 && isRecording) {
        setError('Speech service connection closed unexpectedly.');
      }
      setIsRecording(false);
    };
  }, [setCaseText, stopRecording]);

  return { isRecording, startRecording, stopRecording, transcript, error };
}
