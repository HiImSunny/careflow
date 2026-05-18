/**
 * Tests for AgentChat component.
 *
 * Includes:
 *  - Unit tests for specific rendering scenarios
 *  - Property 8: Agent Message Rendering Completeness
 *
 * **Validates: Requirements 5.2**
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import '@testing-library/jest-dom';
import * as fc from 'fast-check';
import { AgentChat } from './AgentChat';
import type { AgentMessage } from '@/types';
import { useCaseStore } from '@/store/caseStore';

// ── Mock the Zustand store ────────────────────────────────────────────────

vi.mock('@/store/caseStore', () => ({
  useCaseStore: vi.fn(),
}));

const mockUseCaseStore = vi.mocked(useCaseStore);

interface MockStoreState {
  carePlan: { case_id: string } | null;
  agentMessages: AgentMessage[];
  addAgentMessage: (msg: AgentMessage) => void;
}

function setupStore(state: Partial<MockStoreState> = {}) {
  const defaults: MockStoreState = {
    carePlan: null,
    agentMessages: [],
    addAgentMessage: vi.fn(),
  };
  const merged = { ...defaults, ...state };
  mockUseCaseStore.mockImplementation((selector: (s: MockStoreState) => unknown) => {
    return selector(merged);
  });
}

// ── Helpers ───────────────────────────────────────────────────────────────

function makeMessage(overrides: Partial<AgentMessage> = {}): AgentMessage {
  return {
    agent: 'Orchestrator',
    content: 'Decomposing case and identifying relevant specialties…',
    timestamp: '2024-01-01T10:00:00.000Z',
    ...overrides,
  };
}

// ── Unit tests ────────────────────────────────────────────────────────────

describe('AgentChat — unit tests', () => {
  beforeEach(() => {
    setupStore();
  });

  afterEach(() => {
    cleanup();
  });

  it('renders a placeholder when there are no messages', () => {
    render(<AgentChat messages={[]} />);
    expect(screen.getByLabelText('Agent chat placeholder')).toBeInTheDocument();
  });

  it('renders a message with agent name, content, and timestamp', () => {
    const msg = makeMessage();
    render(<AgentChat messages={[msg]} />);

    expect(screen.getByTestId('agent-name')).toHaveTextContent('Orchestrator');
    expect(screen.getByTestId('agent-content')).toHaveTextContent(
      'Decomposing case and identifying relevant specialties…'
    );
    expect(screen.getByTestId('agent-timestamp')).toBeInTheDocument();
  });

  it('renders multiple messages', () => {
    const messages = [
      makeMessage({ agent: 'Orchestrator', content: 'Starting analysis.' }),
      makeMessage({ agent: 'Cardiology', content: 'Reviewing cardiac findings.' }),
      makeMessage({ agent: 'Coordinator', content: 'Reconciling findings.' }),
    ];
    render(<AgentChat messages={messages} />);

    const items = screen.getAllByTestId('agent-message');
    expect(items).toHaveLength(3);
  });

  it('renders agent name in each message item', () => {
    const messages = [
      makeMessage({ agent: 'Radiology', content: 'Imaging analysis complete.' }),
      makeMessage({ agent: 'Pharmacy', content: 'Drug interaction check done.' }),
    ];
    render(<AgentChat messages={messages} />);

    const names = screen.getAllByTestId('agent-name');
    expect(names[0]).toHaveTextContent('Radiology');
    expect(names[1]).toHaveTextContent('Pharmacy');
  });

  it('renders the agent messages list with aria-live for accessibility', () => {
    const messages = [makeMessage()];
    render(<AgentChat messages={messages} />);

    const list = screen.getByRole('list', { name: 'Agent messages' });
    expect(list).toHaveAttribute('aria-live', 'polite');
  });

  it('renders the panel header', () => {
    render(<AgentChat messages={[]} />);
    expect(screen.getByText('Agent Chat')).toBeInTheDocument();
  });
});

// ── Property 8: Agent Message Rendering Completeness ─────────────────────
//
// For any AgentMessage object, the rendered AgentChat entry SHALL contain
// the agent name, the message content, and the timestamp as visible text.
//
// **Validates: Requirements 5.2**
// Tag: Feature: careflow-orchestrator, Property 8: Agent Message Rendering Completeness

describe('Property 8: Agent Message Rendering Completeness', () => {
  beforeEach(() => {
    setupStore();
  });

  afterEach(() => {
    cleanup();
  });

  // Non-empty, non-whitespace string arbitrary
  const nonBlankStringArb = fc
    .string({ minLength: 1, maxLength: 80 })
    .filter((s) => s.trim().length > 0);

  // Arbitrary for agent names (realistic set + random strings)
  const agentNameArb = fc.oneof(
    fc.constantFrom(
      'Orchestrator',
      'Coordinator',
      'Cardiology',
      'Radiology',
      'Oncology',
      'Pharmacy',
      'system'
    ),
    nonBlankStringArb
  );

  // Arbitrary for ISO timestamp strings
  const timestampArb = fc
    .date({ min: new Date('2020-01-01'), max: new Date('2030-12-31') })
    .map((d) => d.toISOString());

  // Arbitrary for a single AgentMessage
  const agentMessageArb = fc.record<AgentMessage>({
    agent: agentNameArb,
    content: nonBlankStringArb,
    timestamp: timestampArb,
  });

  // Arbitrary for a non-empty array of AgentMessages (1–10 messages)
  const agentMessagesArb = fc.array(agentMessageArb, { minLength: 1, maxLength: 10 });

  it('each rendered message contains the agent name as visible text', () => {
    fc.assert(
      fc.property(agentMessagesArb, (messages) => {
        cleanup();
        setupStore({ agentMessages: messages });
        const { unmount } = render(<AgentChat messages={messages} />);

        const renderedNames = screen.getAllByTestId('agent-name');
        expect(renderedNames).toHaveLength(messages.length);

        messages.forEach((msg, i) => {
          expect(renderedNames[i].textContent).toContain(msg.agent);
        });

        unmount();
        cleanup();
      }),
      { numRuns: 100 }
    );
  });

  it('each rendered message contains the content as visible text', () => {
    fc.assert(
      fc.property(agentMessagesArb, (messages) => {
        cleanup();
        setupStore({ agentMessages: messages });
        const { unmount } = render(<AgentChat messages={messages} />);

        const renderedContents = screen.getAllByTestId('agent-content');
        expect(renderedContents).toHaveLength(messages.length);

        messages.forEach((msg, i) => {
          expect(renderedContents[i].textContent).toContain(msg.content.trim());
        });

        unmount();
        cleanup();
      }),
      { numRuns: 100 }
    );
  });

  it('each rendered message contains a timestamp element', () => {
    fc.assert(
      fc.property(agentMessagesArb, (messages) => {
        cleanup();
        setupStore({ agentMessages: messages });
        const { unmount } = render(<AgentChat messages={messages} />);

        const renderedTimestamps = screen.getAllByTestId('agent-timestamp');
        expect(renderedTimestamps).toHaveLength(messages.length);

        // Each timestamp element should have a non-empty dateTime attribute
        // matching the original ISO timestamp.
        messages.forEach((msg, i) => {
          expect(renderedTimestamps[i]).toHaveAttribute('dateTime', msg.timestamp);
        });

        unmount();
        cleanup();
      }),
      { numRuns: 100 }
    );
  });

  it('renders exactly N message items for N messages', () => {
    fc.assert(
      fc.property(agentMessagesArb, (messages) => {
        cleanup();
        setupStore({ agentMessages: messages });
        const { unmount } = render(<AgentChat messages={messages} />);

        const items = screen.getAllByTestId('agent-message');
        expect(items).toHaveLength(messages.length);

        unmount();
        cleanup();
      }),
      { numRuns: 100 }
    );
  });
});
