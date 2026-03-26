import { useState } from 'react';

function SkeletonCard() {
  return (
    <div
      className="rounded-lg border p-4 animate-pulse"
      style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border)' }}
    >
      <div className="h-4 rounded w-3/4 mb-3" style={{ backgroundColor: 'var(--bg-tertiary)' }} />
      <div className="h-3 rounded w-full mb-2" style={{ backgroundColor: 'var(--bg-tertiary)' }} />
      <div className="h-3 rounded w-5/6 mb-4" style={{ backgroundColor: 'var(--bg-tertiary)' }} />
      <div className="flex gap-3">
        <div className="h-3 rounded w-20" style={{ backgroundColor: 'var(--bg-tertiary)' }} />
        <div className="h-3 rounded w-24" style={{ backgroundColor: 'var(--bg-tertiary)' }} />
      </div>
    </div>
  );
}

function MemoryCard({ memory, onDelete }) {
  const [expanded, setExpanded] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const situation = memory.situation || '';
  const truncated = situation.length > 180;
  const displaySituation = expanded ? situation : situation.slice(0, 180) + (truncated ? '...' : '');

  const createdAt = memory.created_at
    ? new Date(memory.created_at).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    : null;

  const handleDelete = () => {
    if (confirmDelete) {
      onDelete(memory.id);
      setConfirmDelete(false);
    } else {
      setConfirmDelete(true);
      setTimeout(() => setConfirmDelete(false), 3000);
    }
  };

  return (
    <div
      className="rounded-lg border p-4 transition-colors"
      style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border)' }}
    >
      {/* Situation */}
      <div className="mb-2">
        <span
          className="text-xs font-semibold uppercase tracking-wider"
          style={{ color: 'var(--text-secondary)' }}
        >
          Situation
        </span>
        <p
          className="text-sm mt-1 leading-relaxed cursor-pointer"
          style={{ color: 'var(--text-primary)' }}
          onClick={() => setExpanded(!expanded)}
          title={truncated ? (expanded ? 'Click to collapse' : 'Click to expand') : undefined}
        >
          {displaySituation}
          {truncated && (
            <button
              className="ml-1 text-xs font-medium"
              style={{ color: 'var(--accent)' }}
              onClick={(e) => {
                e.stopPropagation();
                setExpanded(!expanded);
              }}
            >
              {expanded ? 'Show less' : 'Show more'}
            </button>
          )}
        </p>
      </div>

      {/* Lesson / Recommendation */}
      {memory.lesson && (
        <div className="mb-3">
          <span
            className="text-xs font-semibold uppercase tracking-wider"
            style={{ color: 'var(--text-secondary)' }}
          >
            Lesson
          </span>
          <p className="text-sm mt-1 leading-relaxed" style={{ color: 'var(--text-primary)' }}>
            {memory.lesson}
          </p>
        </div>
      )}

      {/* Footer: run info + delete */}
      <div className="flex items-center justify-between mt-3 pt-3 border-t" style={{ borderColor: 'var(--border)' }}>
        <div className="flex items-center gap-3 text-xs" style={{ color: 'var(--text-secondary)' }}>
          {memory.run_id && (
            <span className="flex items-center gap-1">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M6 2a2 2 0 00-2 2v12a2 2 0 002 2h8a2 2 0 002-2V7.414A2 2 0 0015.414 6L12 2.586A2 2 0 0010.586 2H6zm5 6a1 1 0 10-2 0v3.586l-1.293-1.293a1 1 0 10-1.414 1.414l3 3a1 1 0 001.414 0l3-3a1 1 0 00-1.414-1.414L11 11.586V8z" clipRule="evenodd" />
              </svg>
              Run {memory.run_id.toString().slice(0, 8)}
            </span>
          )}
          {createdAt && (
            <span className="flex items-center gap-1">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clipRule="evenodd" />
              </svg>
              {createdAt}
            </span>
          )}
        </div>
        <button
          onClick={handleDelete}
          className="flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors"
          style={{
            color: confirmDelete ? '#fff' : 'var(--danger)',
            backgroundColor: confirmDelete
              ? 'var(--danger)'
              : 'color-mix(in srgb, var(--danger) 10%, transparent)',
          }}
          title={confirmDelete ? 'Click again to confirm' : 'Delete memory'}
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
          </svg>
          {confirmDelete ? 'Confirm' : 'Delete'}
        </button>
      </div>
    </div>
  );
}

export default function MemoryExplorer({ memories, onDelete, onClearAll, loading }) {
  if (loading) {
    return (
      <div className="grid gap-4">
        {[1, 2, 3].map((i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    );
  }

  if (!memories || memories.length === 0) {
    return (
      <div
        className="rounded-lg border p-8 text-center"
        style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border)' }}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="h-12 w-12 mx-auto mb-3"
          style={{ color: 'var(--text-secondary)' }}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
          />
        </svg>
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
          No memories yet. Run an analysis and reflect to build agent memory.
        </p>
      </div>
    );
  }

  return (
    <div className="grid gap-4">
      {memories.map((memory) => (
        <MemoryCard key={memory.id} memory={memory} onDelete={onDelete} />
      ))}
    </div>
  );
}
