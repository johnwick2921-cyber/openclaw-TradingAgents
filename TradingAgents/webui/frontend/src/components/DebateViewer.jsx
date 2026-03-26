import { useState } from 'react';

export default function DebateViewer({ exchanges = [], judgeDecision }) {
  const [expanded, setExpanded] = useState(true);

  if (exchanges.length === 0 && !judgeDecision) return null;

  return (
    <div
      className="rounded-xl border overflow-hidden"
      style={{
        backgroundColor: 'var(--bg-secondary)',
        borderColor: 'var(--border)',
      }}
    >
      {/* Header */}
      <div
        className="flex items-center gap-2 px-4 py-3 cursor-pointer select-none"
        style={{ borderBottom: expanded ? '1px solid var(--border)' : 'none' }}
        onClick={() => setExpanded((prev) => !prev)}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className={`h-4 w-4 transition-transform ${expanded ? 'rotate-90' : ''}`}
          style={{ color: 'var(--text-secondary)' }}
          viewBox="0 0 20 20"
          fill="currentColor"
        >
          <path
            fillRule="evenodd"
            d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
            clipRule="evenodd"
          />
        </svg>
        <h3
          className="text-sm font-semibold"
          style={{ color: 'var(--text-primary)' }}
        >
          Debate Exchanges ({exchanges.length})
        </h3>
      </div>

      {expanded && (
        <div className="px-4 py-3 space-y-3">
          {/* Exchanges as chat bubbles */}
          {exchanges.map((exchange, idx) => {
            const isLeft = idx % 2 === 0;
            return (
              <div
                key={idx}
                className={`flex flex-col ${isLeft ? 'items-start' : 'items-end'}`}
                style={{ maxWidth: '85%', marginLeft: isLeft ? '0' : 'auto', marginRight: isLeft ? 'auto' : '0' }}
              >
                <span
                  className="text-xs font-semibold mb-1 px-1"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  {exchange.speaker}
                </span>
                <div
                  className="rounded-xl px-3 py-2 text-sm leading-relaxed"
                  style={{
                    backgroundColor: isLeft
                      ? 'var(--bg-tertiary)'
                      : 'color-mix(in srgb, var(--accent) 12%, transparent)',
                    color: 'var(--text-primary)',
                    borderBottomLeftRadius: isLeft ? '4px' : undefined,
                    borderBottomRightRadius: isLeft ? undefined : '4px',
                  }}
                >
                  {exchange.content}
                </div>
              </div>
            );
          })}

          {/* Judge Decision */}
          {judgeDecision && (
            <div
              className="mt-4 rounded-lg px-4 py-3 border"
              style={{
                backgroundColor: 'color-mix(in srgb, var(--accent) 8%, transparent)',
                borderColor: 'color-mix(in srgb, var(--accent) 25%, transparent)',
              }}
            >
              <p
                className="text-xs font-semibold uppercase tracking-wider mb-1"
                style={{ color: 'var(--accent)' }}
              >
                Judge Decision
              </p>
              <p
                className="text-sm leading-relaxed"
                style={{ color: 'var(--text-primary)' }}
              >
                {judgeDecision}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
