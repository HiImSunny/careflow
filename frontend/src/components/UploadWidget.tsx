/**
 * UploadWidget — primary case submission component.
 *
 * Features:
 * - Textarea bound to `caseText` in the Zustand store
 * - Drag-and-drop image upload zone
 * - Microphone button (stub until Phase 3)
 * - Submit button disabled when no input is present
 * - Inline validation error when submit is attempted with no input
 *
 * Requirements: 1.1, 1.2, 1.4, 1.5, 1.6
 */

import React, { useRef, useState } from 'react';
import { Mic, MicOff, Upload, X } from 'lucide-react';
import { useCaseStore } from '@/store/caseStore';
import { useOrchestrate } from '@/hooks/useOrchestrate';
import { useSpeech } from '@/hooks/useSpeech';

/** Returns true when the string is non-null and contains at least one non-whitespace character. */
function hasContent(value: string | null | undefined): boolean {
  return typeof value === 'string' && value.trim().length > 0;
}

export function UploadWidget(): React.ReactElement {
  const { caseText, caseImage, setCaseText, setCaseImage } = useCaseStore();
  const { orchestrate, loading } = useOrchestrate();
  const { isRecording, startRecording, stopRecording, error: speechError, engine } =
    useSpeech();

  const [dragOver, setDragOver] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── Derived state ──────────────────────────────────────────────────────────

  /** True when the user has provided at least one form of input. */
  const hasInput = hasContent(caseText) || caseImage !== null;

  // ── Handlers ───────────────────────────────────────────────────────────────

  const handleTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setCaseText(e.target.value);
    if (validationError) setValidationError(null);
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
  };

  const acceptFile = (file: File) => {
    setCaseImage(file);
    if (validationError) setValidationError(null);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);

    const file = e.dataTransfer.files?.[0];
    if (file) {
      acceptFile(file);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      acceptFile(file);
    }
    // Reset input so the same file can be re-selected
    e.target.value = '';
  };

  const handleRemoveImage = () => {
    setCaseImage(null);
  };

  const handleMicToggle = () => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!hasInput) {
      setValidationError(
        'Please enter case notes, upload an image, or record audio before submitting.'
      );
      return;
    }

    setValidationError(null);
    await orchestrate({ text: caseText || undefined });
  };

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col gap-4"
      aria-label="Case submission form"
    >
      {/* ── Case notes textarea ── */}
      <div className="flex flex-col gap-1">
        <label
          htmlFor="case-text"
          className="text-sm font-medium text-slate-700"
        >
          Case Notes
        </label>
        <textarea
          id="case-text"
          value={caseText}
          onChange={handleTextChange}
          placeholder="Enter patient case notes here…"
          rows={6}
          className="w-full resize-y rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder-slate-400 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
          disabled={loading}
          aria-label="Case notes text input"
        />
      </div>

      {/* ── Drag-and-drop file zone ── */}
      <div
        role="button"
        tabIndex={0}
        aria-label="Drag and drop image upload zone"
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            fileInputRef.current?.click();
          }
        }}
        className={[
          'flex cursor-pointer flex-col items-center justify-center gap-2 rounded-md border-2 border-dashed px-4 py-6 text-sm transition-colors',
          dragOver
            ? 'border-blue-500 bg-blue-50 text-blue-700'
            : 'border-slate-300 bg-slate-50 text-slate-500 hover:border-slate-400 hover:bg-slate-100',
          loading ? 'pointer-events-none opacity-50' : '',
        ]
          .filter(Boolean)
          .join(' ')}
      >
        <Upload className="h-5 w-5" aria-hidden="true" />
        {caseImage ? (
          <span className="font-medium text-slate-700">{caseImage.name}</span>
        ) : (
          <span>
            Drag &amp; drop an image here, or{' '}
            <span className="font-medium text-blue-600">browse</span>
          </span>
        )}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={handleFileInputChange}
          aria-label="File input for image upload"
          tabIndex={-1}
        />
      </div>

      {/* ── Accepted file name + remove button ── */}
      {caseImage && (
        <div className="flex items-center justify-between rounded-md border border-slate-200 bg-white px-3 py-2 text-sm">
          <span className="truncate text-slate-700" title={caseImage.name}>
            {caseImage.name}
          </span>
          <button
            type="button"
            onClick={handleRemoveImage}
            className="ml-2 flex-shrink-0 rounded p-0.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 focus:outline-none focus:ring-1 focus:ring-blue-500"
            aria-label="Remove uploaded image"
            disabled={loading}
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      )}

      {/* ── Controls row: mic + submit ── */}
      <div className="flex items-center gap-3">
        {/* Microphone button */}
        <button
          type="button"
          onClick={handleMicToggle}
          disabled={loading}
          aria-label={isRecording ? 'Stop recording' : 'Start recording'}
          aria-pressed={isRecording}
          className={[
            'flex h-10 flex-shrink-0 items-center justify-center gap-1.5 rounded-full border px-3 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1',
            isRecording
              ? 'border-red-500 bg-red-50 text-red-600 hover:bg-red-100'
              : 'border-slate-300 bg-white text-slate-600 hover:bg-slate-50',
            loading ? 'opacity-50 cursor-not-allowed' : '',
          ]
            .filter(Boolean)
            .join(' ')}
        >
          {isRecording ? (
            <MicOff className="h-4 w-4" aria-hidden="true" />
          ) : (
            <Mic className="h-4 w-4" aria-hidden="true" />
          )}
          {isRecording && engine === 'webspeech' && (
            <span className="text-xs font-medium">Browser</span>
          )}
          {isRecording && engine === 'speechmatics' && (
            <span className="text-xs font-medium">Speechmatics</span>
          )}
        </button>
        {/* Submit button */}
        <button
          type="submit"
          disabled={!hasInput || loading}
          aria-label="Submit case for analysis"
          className="flex-1 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? 'Analysing…' : 'Submit Case'}
        </button>
      </div>

      {/* ── Validation error ── */}
      {validationError && (
        <p
          role="alert"
          className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
        >
          {validationError}
        </p>
      )}

      {/* ── Speech error ── */}
      {speechError && (
        <p
          role="alert"
          className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700"
        >
          Microphone error: {speechError}
        </p>
      )}
    </form>
  );
}

export default UploadWidget;
