/**
 * AgentChat — streams real-time agent messages during orchestration.
 *
 * Opens an EventSource to /api/chat/{case_id} when a case_id is available.
 * Renders each received message showing agent name, content, and timestamp.
 * Displays a "Care plan ready" completion message when orchestration finishes.
 *
 * Requirements: 5.1, 5.2, 5.3, 5.4
 */

import React, { useEffect, useRef, useState } from 'react';
import { Bot, CheckCircle2, Loader2 } from 'lucide-react';
import { useCaseStore } from '@/store/caseStore';
import { apiUrl } from '@/lib/api';
import type { AgentMessage } from '@/types';

// ── Agent badge colours ────────────────────────────────────────────────────

const AGENT_COLORS: Record<string, string> = {
  orchestrator: 'bg-indigo-100 text-indigo-700',
  coordinator: 'bg-teal-100 text-teal-700',
  cardiology: 'bg-red-100 text-red-700',
  radiology: 'bg-blue-100 text-blue-700',
  oncology: 'bg-purple-100 text-purple-700',
  pharmacy: 'bg-green-100 text-green-700',
  system: 'bg-slate-100 text-slate-700',
};

const DEFAULT_AGENT_COLOR = 'bg-gray-100 text-gray-700';

function agentColorClass(agent: string): string {
  return AGENT_COLORS[agent.toLowerCase()] ?? DEFAULT_AGENT_COLOR;
}

// ── Timestamp formatter ────────────────────────────────────────────────────

function formatTimestamp(ts: string): string {
  try {
    return new Intl.DateTimeFormat('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    }).format(new Date(ts));
  } catch {
    return ts;
  }
}

// ── Message item ───────────────────────────────────────────────────────────

interface MessageItemProps {
  message: AgentMessage;
  isComplete?: boolean;
}

function MessageItem({ message, isComplete }: MessageItemProps) {
  const colorClass = agentColorClass(message.agent);

  return (
    <li
      className="flex flex-col gap-1 rounded-md border border-slate-100 bg-white p-3 shadow-sm"
      data-testid="agent-message"
    >
      <div className="flex items-center justify-between gap-2">
        <span
          className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold capitalize ${colorClass}`}
          data-testid="agent-name"
        >
          {isComplete ? (
            <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
          ) : (
            <Bot className="h-3 w-3" aria-hidden="true" />
          )}
          {message.agent}
        </span>
        <time
          dateTime={message.timestamp}
          className="text-xs text-slate-400"
          data-testid="agent-timestamp"
        >
          {formatTimestamp(message.timestamp)}
        </time>
      </div>
      <p
        className={`text-sm ${isComplete ? 'font-semibold text-teal-700' : 'text-slate-700'}`}
        data-testid="agent-content"
      >
        {message.content}
      </p>
    </li>
  );
}

// ── Placeholder ────────────────────────────────────────────────────────────

function AgentChatPlaceholder() {
  return (
    <div
      className="flex flex-1 flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-slate-300 bg-slate-50 py-10 text-center"
      aria-label="Agent chat placeholder"
    >
      <Bot className="h-8 w-8 text-slate-300" aria-hidden="true" />
      <p className="text-xs text-slate-400">
        Agent messages will appear here during orchestration.
      </p>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────

/**
 * Renders the agent chat panel. Connects to the SSE endpoint when a case_id
 * is available and streams agent messages in real time.
 *
 * Requirements: 5.1, 5.2, 5.3, 5.4
 */
export interface AgentChatProps {
  /** Optional explicit messages prop (used in tests / Storybook). */
  messages?: AgentMessage[];
  /** Optional explicit case_id prop (overrides store value). */
  caseId?: string;
}

export function AgentChat({ messages: messagesProp, caseId: caseIdProp }: AgentChatProps = {}): React.ReactElement {
  const storeCaseId = useCaseStore((state) => state.carePlan?.case_id ?? null);
  const addAgentMessage = useCaseStore((state) => state.addAgentMessage);
  const storeMessages = useCaseStore((state) => state.agentMessages);

  // Use prop overrides when provided (for testing / controlled usage).
  const caseId = caseIdProp ?? storeCaseId;
  const messages = messagesProp ?? storeMessages;

  const [isStreaming, setIsStreaming] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  // Auto-scroll to bottom when new messages arrive.
  useEffect(() => {
    if (bottomRef.current && typeof bottomRef.current.scrollIntoView === 'function') {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  // Open SSE connection when caseId becomes available.
  useEffect(() => {
    if (!caseId) {
      return;
    }

    // Close any existing connection.
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    setIsStreaming(true);
    setIsComplete(false);

    const es = new EventSource(apiUrl(`/api/chat/${caseId}`));
    eventSourceRef.current = es;

    es.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data as string) as AgentMessage & { type?: string };

        if (data.type === 'complete') {
          // Final completion event — display "Care plan ready" message.
          addAgentMessage({
            agent: data.agent,
            content: data.content,
            timestamp: data.timestamp,
          });
          setIsComplete(true);
          setIsStreaming(false);
          es.close();
          eventSourceRef.current = null;
          return;
        }

        addAgentMessage({
          agent: data.agent,
          content: data.content,
          timestamp: data.timestamp,
        });
      } catch (err) {
        // Ignore malformed events.
      }
    };

    es.onerror = () => {
      setIsStreaming(false);
      es.close();
      eventSourceRef.current = null;
    };

    return () => {
      es.close();
      eventSourceRef.current = null;
    };
  }, [caseId, addAgentMessage]);

  return (
    <div
      className="flex h-full flex-col"
      aria-label="Agent chat panel"
    >
      {/* Header */}
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          Agent Chat
        </h2>
        {isStreaming && (
          <span
            className="flex items-center gap-1 text-xs text-blue-500"
            aria-label="Streaming agent messages"
          >
            <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
            Live
          </span>
        )}
        {isComplete && (
          <span
            className="flex items-center gap-1 text-xs text-teal-600"
            aria-label="Orchestration complete"
          >
            <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
            Done
          </span>
        )}
      </div>

      {/* Message list or placeholder */}
      {messages.length === 0 ? (
        <AgentChatPlaceholder />
      ) : (
        <div className="flex-1 overflow-y-auto">
          <ul
            className="space-y-2"
            aria-label="Agent messages"
            aria-live="polite"
            aria-atomic="false"
          >
            {messages.map((msg, index) => {
              const isLastAndComplete = isComplete && index === messages.length - 1;
              return (
                <MessageItem
                  key={`${msg.timestamp}-${index}`}
                  message={msg}
                  isComplete={isLastAndComplete}
                />
              );
            })}
          </ul>
          <div ref={bottomRef} />
        </div>
      )}
    </div>
  );
}

export default AgentChat;
