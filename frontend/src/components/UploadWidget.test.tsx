/**
 * Unit tests for UploadWidget component.
 * Requirements: 1.1, 1.2, 1.4, 1.5, 1.6
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { UploadWidget } from './UploadWidget';
import { useCaseStore } from '@/store/caseStore';

// ── Mock hooks ────────────────────────────────────────────────────────────────

const mockOrchestrate = vi.fn();
vi.mock('@/hooks/useOrchestrate', () => ({
  useOrchestrate: () => ({
    orchestrate: mockOrchestrate,
    loading: false,
    error: null,
  }),
}));

vi.mock('@/hooks/useSpeech', () => ({
  useSpeech: () => ({
    isRecording: false,
    startRecording: vi.fn(),
    stopRecording: vi.fn(),
    transcript: '',
    error: null,
  }),
}));

// ── Helpers ───────────────────────────────────────────────────────────────────

function resetStore() {
  useCaseStore.setState({
    caseText: '',
    caseImage: null,
    carePlan: null,
    agentMessages: [],
    loading: false,
    error: null,
  });
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('UploadWidget', () => {
  beforeEach(() => {
    resetStore();
    mockOrchestrate.mockReset();
  });

  // Requirement 1.5 — validation error when no input
  it('shows a validation error when submit is clicked with no input', async () => {
    render(<UploadWidget />);
    const submitBtn = screen.getByRole('button', { name: /submit case/i });
    // Button should be disabled when no input
    expect(submitBtn).toBeDisabled();
  });

  it('displays a validation error message when form is submitted programmatically with no input', async () => {
    render(<UploadWidget />);
    const form = screen.getByRole('form', { hidden: true }) ??
      document.querySelector('form');
    // Simulate form submit with no input by firing submit event directly
    if (form) {
      fireEvent.submit(form);
    }
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  // Requirement 1.4 — submit button disabled when no input
  it('disables submit button when caseText is empty and no image', () => {
    render(<UploadWidget />);
    expect(
      screen.getByRole('button', { name: /submit case/i })
    ).toBeDisabled();
  });

  it('enables submit button when caseText has content', async () => {
    render(<UploadWidget />);
    const textarea = screen.getByRole('textbox', { name: /case notes/i });
    await userEvent.type(textarea, 'Patient has chest pain');
    expect(
      screen.getByRole('button', { name: /submit case/i })
    ).not.toBeDisabled();
  });

  it('disables submit button when caseText is only whitespace', async () => {
    render(<UploadWidget />);
    const textarea = screen.getByRole('textbox', { name: /case notes/i });
    await userEvent.type(textarea, '   ');
    expect(
      screen.getByRole('button', { name: /submit case/i })
    ).toBeDisabled();
  });

  // Requirement 1.1 — calls orchestrate on submit
  it('calls orchestrate with caseText on submit', async () => {
    render(<UploadWidget />);
    const textarea = screen.getByRole('textbox', { name: /case notes/i });
    await userEvent.type(textarea, 'Patient has chest pain');
    const submitBtn = screen.getByRole('button', { name: /submit case/i });
    await userEvent.click(submitBtn);
    expect(mockOrchestrate).toHaveBeenCalledWith({
      text: 'Patient has chest pain',
    });
  });

  // Requirement 1.6 — drag-and-drop zone renders
  it('renders the drag-and-drop upload zone', () => {
    render(<UploadWidget />);
    expect(
      screen.getByRole('button', { name: /drag and drop image upload zone/i })
    ).toBeInTheDocument();
  });

  // Requirement 1.6 — file drop sets image and displays file name
  it('accepts a dropped file and displays its name', async () => {
    render(<UploadWidget />);
    const dropZone = screen.getByRole('button', {
      name: /drag and drop image upload zone/i,
    });

    const file = new File(['(image data)'], 'xray.jpg', { type: 'image/jpeg' });
    const dataTransfer = {
      files: [file],
      items: [],
      types: [],
    };

    fireEvent.dragOver(dropZone, { dataTransfer });
    fireEvent.drop(dropZone, { dataTransfer });

    await waitFor(() => {
      expect(screen.getAllByText('xray.jpg').length).toBeGreaterThan(0);
    });
  });

  // Requirement 1.2 — image enables submit button
  it('enables submit button when an image is present', async () => {
    render(<UploadWidget />);
    const dropZone = screen.getByRole('button', {
      name: /drag and drop image upload zone/i,
    });

    const file = new File(['(image data)'], 'scan.png', { type: 'image/png' });
    fireEvent.drop(dropZone, {
      dataTransfer: { files: [file] },
    });

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /submit case/i })
      ).not.toBeDisabled();
    });
  });

  // Microphone button renders
  it('renders the microphone button', () => {
    render(<UploadWidget />);
    expect(
      screen.getByRole('button', { name: /start recording/i })
    ).toBeInTheDocument();
  });

  // Remove image button
  it('shows a remove button after a file is dropped and removes the file on click', async () => {
    render(<UploadWidget />);
    const dropZone = screen.getByRole('button', {
      name: /drag and drop image upload zone/i,
    });

    const file = new File(['(image data)'], 'ct.jpg', { type: 'image/jpeg' });
    fireEvent.drop(dropZone, { dataTransfer: { files: [file] } });

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /remove uploaded image/i })
      ).toBeInTheDocument();
    });

    await userEvent.click(
      screen.getByRole('button', { name: /remove uploaded image/i })
    );

    await waitFor(() => {
      expect(
        screen.queryByRole('button', { name: /remove uploaded image/i })
      ).not.toBeInTheDocument();
    });
  });
});
