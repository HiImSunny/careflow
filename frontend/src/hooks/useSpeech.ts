/**
 * useSpeech — real-time speech-to-text hook with automatic fallback.
 *
 * Strategy:
 *  1. Try the backend WebSocket → Speechmatics pipeline first.
 *  2. If the WebSocket fails to open OR the backend signals it has no
 *     Speechmatics key (sends {"type":"done"} immediately with no text),
 *     automatically fall back to the browser's Web Speech API.
 *  3. If the browser doesn't support Web Speech API either, surface an error.
 *
 * Requirements: 9.1, 9.3, 9.4, 9.5
 */

import { useCallback, useRef, useState } from 'react';
import { useCaseStore } from '@/store/caseStore';
import { wsUrl } from '@/lib/api';

export interface UseSpeechResult {
  isRecording: boolean;
  startRecording: () => void;
  stopRecording: () => void;
  transcript: string;
  error: string | null;
  /** Which engine is currently active */
  engine: 'speechmatics' | 'webspeech' | 'mock' | null;
}

const AUDIO_MIME_TYPE = 'audio/webm';
const WS_ENDPOINT = '/api/speech/transcribe';

// ── Web Speech API type declarations (not in all TS libs) ─────────────────

interface SpeechRecognitionEvent extends Event {
  results: SpeechRecognitionResultList;
  resultIndex: number;
}

interface SpeechRecognitionErrorEvent extends Event {
  error: string;
}

interface SpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((e: SpeechRecognitionEvent) => void) | null;
  onerror: ((e: SpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

declare global {
  interface Window {
    SpeechRecognition?: new () => SpeechRecognition;
    webkitSpeechRecognition?: new () => SpeechRecognition;
  }
}

function getSpeechRecognition(): (new () => SpeechRecognition) | null {
  return window.SpeechRecognition ?? window.webkitSpeechRecognition ?? null;
}

// ── Hook ──────────────────────────────────────────────────────────────────

export function useSpeech(): UseSpeechResult {
  const { caseText, setCaseText } = useCaseStore();

  const [isRecording, setIsRecording] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [engine, setEngine] = useState<UseSpeechResult['engine']>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const recognitionRef = useRef<SpeechRecognition | null>(null);

  const caseTextRef = useRef(caseText);
  caseTextRef.current = caseText;

  // ── Append helper ────────────────────────────────────────────────────────

  const appendText = useCallback(
    (newText: string) => {
      if (!newText) return;
      setTranscript((prev) => prev + newText);
      setCaseText(caseTextRef.current + newText);
    },
    [setCaseText],
  );

  // ── Stop (works for both engines) ────────────────────────────────────────

  const stopRecording = useCallback(() => {
    // Stop MediaRecorder
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    mediaRecorderRef.current = null;

    // Release mic stream
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }

    // Close WebSocket
    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }

    // Stop Web Speech API
    if (recognitionRef.current) {
      recognitionRef.current.abort();
      recognitionRef.current = null;
    }

    setIsRecording(false);
    setEngine(null);
  }, []);

  // ── Web Speech API fallback ───────────────────────────────────────────────

  const startWebSpeech = useCallback(() => {
    const SpeechRecognitionCtor = getSpeechRecognition();
    if (!SpeechRecognitionCtor) {
      setError(
        'Speech recognition is not supported in this browser. ' +
          'Please use Chrome or Edge, or provide a Speechmatics API key.',
      );
      setIsRecording(false);
      return;
    }

    const recognition = new SpeechRecognitionCtor();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-US';
    recognitionRef.current = recognition;

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let interim = '';
      let final = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) {
          final += result[0].transcript;
        } else {
          interim += result[0].transcript;
        }
      }
      if (final) appendText(final);
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      if (event.error !== 'aborted') {
        setError(`Speech recognition error: ${event.error}`);
      }
      stopRecording();
    };

    recognition.onend = () => {
      setIsRecording(false);
      setEngine(null);
    };

    recognition.start();
    setEngine('webspeech');
    setIsRecording(true);
  }, [appendText, stopRecording]);

  // ── Speechmatics via WebSocket ────────────────────────────────────────────

  const startSpeechmatics = useCallback(
    async (stream: MediaStream) => {
      let socket: WebSocket;
      try {
        socket = new WebSocket(wsUrl(WS_ENDPOINT));
      } catch {
        // WebSocket constructor failed — fall back immediately
        stream.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
        startWebSpeech();
        return;
      }
      socketRef.current = socket;

      // Track whether we received any real transcript text
      let receivedText = false;

      // Timeout: if socket doesn't open within 3 s, fall back
      const openTimeout = setTimeout(() => {
        if (socket.readyState !== WebSocket.OPEN) {
          socket.close();
          stream.getTracks().forEach((t) => t.stop());
          streamRef.current = null;
          startWebSpeech();
        }
      }, 3000);

      socket.onopen = () => {
        clearTimeout(openTimeout);

        const mimeType = MediaRecorder.isTypeSupported(AUDIO_MIME_TYPE)
          ? AUDIO_MIME_TYPE
          : '';
        const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
        mediaRecorderRef.current = recorder;

        recorder.ondataavailable = (event: BlobEvent) => {
          if (event.data.size > 0 && socketRef.current?.readyState === WebSocket.OPEN) {
            socketRef.current.send(event.data);
          }
        };

        recorder.start(250);
        setEngine('speechmatics');
        setIsRecording(true);
      };

      socket.onmessage = (event: MessageEvent) => {
        if (typeof event.data === 'string') {
          try {
            const parsed = JSON.parse(event.data) as Record<string, unknown>;

            // Backend signals done with no real transcription → mock mode
            // Fall back to Web Speech API for a better UX
            if (parsed.type === 'done' && !receivedText) {
              stopRecording();
              startWebSpeech();
              return;
            }

            if (parsed.type === 'error') {
              // Backend Speechmatics error → fall back
              stopRecording();
              startWebSpeech();
              return;
            }

            const text =
              typeof parsed.transcript === 'string'
                ? parsed.transcript
                : typeof parsed.text === 'string'
                  ? parsed.text
                  : null;

            if (text) {
              receivedText = true;
              appendText(text);
            }
          } catch {
            // Plain text transcript
            if (event.data.trim()) {
              receivedText = true;
              appendText(event.data);
            }
          }
        }
      };

      socket.onerror = () => {
        clearTimeout(openTimeout);
        // WebSocket error → fall back to Web Speech API
        stopRecording();
        startWebSpeech();
      };

      socket.onclose = (event: CloseEvent) => {
        clearTimeout(openTimeout);
        if (!event.wasClean && event.code !== 1000 && !receivedText) {
          // Closed without any transcript → fall back
          startWebSpeech();
        }
        setIsRecording(false);
      };
    },
    [appendText, startWebSpeech, stopRecording],
  );

  // ── Public startRecording ─────────────────────────────────────────────────

  const startRecording = useCallback(async () => {
    setError(null);

    // Request mic permission
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      // Mic denied → try Web Speech API (it handles its own permission)
      startWebSpeech();
      return;
    }
    streamRef.current = stream;

    // Try Speechmatics first; it will fall back to Web Speech API on failure
    await startSpeechmatics(stream);
  }, [startSpeechmatics, startWebSpeech]);

  return { isRecording, startRecording, stopRecording, transcript, error, engine };
}
