import { useEffect, useRef, useState } from 'react';

const AGENT_COLORS = [
  '#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#22c55e',
  '#06b6d4', '#f97316', '#6366f1', '#14b8a6', '#e11d48',
];

function agentColor(name) {
  if (!name) return 'var(--text-secondary)';
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return AGENT_COLORS[Math.abs(hash) % AGENT_COLORS.length];
}

function formatTimestamp(ts) {
  if (!ts) return '';
  try {
    const d = new Date(ts);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return String(ts);
  }
}

export default function LiveMessages({ messages = [] }) {
  const containerRef = useRef(null);
  const [autoScroll, setAutoScroll] = useState(true);

  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [messages, autoScroll]);

  const handleScroll = () => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    const atBottom = scrollHeight - scrollTop - clientHeight < 40;
    if (autoScroll && !atBottom) {
      setAutoScroll(false);
    }
  };

  return (
    <div
      className="rounded-xl border flex flex-col"
      style={{
        backgroundColor: 'var(--bg-secondary)',
        borderColor: 'var(--border)',
        maxHeight: '600px',
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-2 border-b"
        style={{ borderColor: 'var(--border)' }}
      >
        <h3
          className="text-sm font-semibold uppercase tracking-wider"
          style={{ color: 'var(--text-secondary)' }}
        >
          Live Messages
        </h3>
        <button
          onClick={() => {
            setAutoScroll((prev) => !prev);
            if (!autoScroll && containerRef.current) {
              containerRef.current.scrollTop = containerRef.current.scrollHeight;
            }
          }}
          className="text-xs px-2 py-1 rounded-md transition-colors"
          style={{
            color: autoScroll ? 'var(--accent)' : 'var(--text-secondary)',
            backgroundColor: autoScroll
              ? 'color-mix(in srgb, var(--accent) 12%, transparent)'
              : 'var(--bg-tertiary)',
          }}
        >
          {autoScroll ? 'Auto-scroll ON' : 'Auto-scroll OFF'}
        </button>
      </div>

      {/* Messages */}
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto p-3 space-y-1"
        style={{ minHeight: '200px' }}
      >
        {messages.length === 0 && (
          <p className="text-sm text-center py-8" style={{ color: 'var(--text-secondary)' }}>
            Waiting for messages...
          </p>
        )}

        {messages.map((msg, idx) => {
          const isToolCall = msg.type === 'tool_call';
          const isWarning = msg.type === 'warning';
          const isError = msg.type === 'error';

          let textColor = 'var(--text-primary)';
          let bgColor = 'transparent';
          if (isWarning) {
            textColor = 'var(--warning)';
            bgColor = 'color-mix(in srgb, var(--warning) 8%, transparent)';
          } else if (isError) {
            textColor = 'var(--danger)';
            bgColor = 'color-mix(in srgb, var(--danger) 8%, transparent)';
          }

          return (
            <div
              key={msg._id ?? idx}
              className="rounded-md px-2 py-1 text-sm"
              style={{ backgroundColor: bgColor }}
            >
              <span
                className="text-xs tabular-nums mr-2"
                style={{ color: 'var(--text-secondary)' }}
              >
                {formatTimestamp(msg.timestamp)}
              </span>
              {msg.agent && (
                <span
                  className="font-semibold mr-2 text-xs"
                  style={{ color: agentColor(msg.agent) }}
                >
                  [{msg.agent}]
                </span>
              )}
              <span
                className={isToolCall ? 'font-mono text-xs' : ''}
                style={{ color: textColor }}
              >
                {msg.content}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
