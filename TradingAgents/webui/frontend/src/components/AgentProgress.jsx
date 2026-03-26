const STATUS_ICON = {
  pending: { icon: '\u2B1C', className: '' },
  running: { icon: '\uD83D\uDD04', className: 'inline-block animate-spin' },
  completed: { icon: '\u2705', className: '' },
  failed: { icon: '\u274C', className: '' },
};

export default function AgentProgress({ agents = [] }) {
  return (
    <div
      className="rounded-xl border p-4"
      style={{
        backgroundColor: 'var(--bg-secondary)',
        borderColor: 'var(--border)',
      }}
    >
      <h3
        className="text-sm font-semibold uppercase tracking-wider mb-3"
        style={{ color: 'var(--text-secondary)' }}
      >
        Agent Progress
      </h3>

      {agents.length === 0 && (
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
          Waiting for agents...
        </p>
      )}

      <div className="flex flex-col gap-2">
        {agents.map((agent) => {
          const cfg = STATUS_ICON[agent.status] || STATUS_ICON.pending;
          return (
            <div
              key={agent.name}
              className="flex items-center gap-3 px-3 py-2 rounded-lg"
              style={{ backgroundColor: 'var(--bg-tertiary)' }}
            >
              <span className={cfg.className} role="img" aria-label={agent.status}>
                {cfg.icon}
              </span>
              <span
                className="flex-1 text-sm font-medium truncate"
                style={{ color: 'var(--text-primary)' }}
              >
                {agent.name}
              </span>
              {agent.status === 'completed' && agent.duration != null && (
                <span
                  className="text-xs tabular-nums"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  {typeof agent.duration === 'number'
                    ? `${agent.duration.toFixed(1)}s`
                    : agent.duration}
                </span>
              )}
              {agent.status === 'running' && (
                <span
                  className="text-xs"
                  style={{ color: 'var(--accent)' }}
                >
                  running
                </span>
              )}
              {agent.status === 'failed' && (
                <span
                  className="text-xs"
                  style={{ color: 'var(--danger)' }}
                >
                  failed
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
