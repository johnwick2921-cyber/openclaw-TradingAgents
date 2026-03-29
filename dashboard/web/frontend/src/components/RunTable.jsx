import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import SignalBadge from './SignalBadge';

function formatDuration(seconds) {
  if (seconds == null) return '--';
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  if (m === 0) return `${s}s`;
  return `${m}m ${s}s`;
}

function relativeTime(dateStr) {
  if (!dateStr) return '--';
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diff = Math.max(0, Math.floor((now - then) / 1000));

  if (diff < 60) return 'just now';
  if (diff < 3600) {
    const mins = Math.floor(diff / 60);
    return `${mins} min${mins > 1 ? 's' : ''} ago`;
  }
  if (diff < 86400) {
    const hrs = Math.floor(diff / 3600);
    return `${hrs} hr${hrs > 1 ? 's' : ''} ago`;
  }
  const days = Math.floor(diff / 86400);
  return `${days} day${days > 1 ? 's' : ''} ago`;
}

const COLUMNS = [
  { key: 'ticker', label: 'Ticker', sortable: true },
  { key: 'trade_date', label: 'Date', sortable: true },
  { key: 'signal', label: 'Signal', sortable: true },
  { key: 'provider', label: 'Provider', sortable: true },
  { key: 'duration', label: 'Duration', sortable: true },
  { key: 'created_at', label: 'Created', sortable: true },
  { key: 'actions', label: 'Actions', sortable: false },
];

function SkeletonRow() {
  return (
    <tr>
      {/* checkbox */}
      <td className="px-4 py-3">
        <div className="h-4 w-4 rounded" style={{ backgroundColor: 'var(--bg-tertiary)' }} />
      </td>
      {COLUMNS.map((col) => (
        <td key={col.key} className="px-4 py-3">
          <div
            className="h-4 rounded animate-pulse"
            style={{
              backgroundColor: 'var(--bg-tertiary)',
              width: col.key === 'actions' ? '5rem' : '4rem',
            }}
          />
        </td>
      ))}
    </tr>
  );
}

export default function RunTable({
  runs = [],
  total = 0,
  page = 1,
  perPage = 20,
  onPageChange,
  onSort,
  onDelete,
  loading,
}) {
  const navigate = useNavigate();
  const [sortCol, setSortCol] = useState('created_at');
  const [sortOrder, setSortOrder] = useState('desc');
  const [selected, setSelected] = useState(new Set());

  const totalPages = Math.max(1, Math.ceil(total / perPage));

  const handleSort = (key) => {
    const col = COLUMNS.find((c) => c.key === key);
    if (!col?.sortable) return;

    let newOrder = 'asc';
    if (sortCol === key && sortOrder === 'asc') newOrder = 'desc';
    setSortCol(key);
    setSortOrder(newOrder);
    onSort?.(key, newOrder);
  };

  const toggleAll = () => {
    if (selected.size === runs.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(runs.map((r) => r.id)));
    }
  };

  const toggleOne = (id) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleDeleteSelected = () => {
    for (const id of selected) {
      onDelete?.(id);
    }
    setSelected(new Set());
  };

  const SortArrow = ({ colKey }) => {
    if (sortCol !== colKey) return null;
    return (
      <span className="ml-1 text-xs" style={{ color: 'var(--accent)' }}>
        {sortOrder === 'asc' ? '\u25B2' : '\u25BC'}
      </span>
    );
  };

  return (
    <div>
      {/* Bulk actions */}
      {selected.size > 0 && (
        <div className="flex items-center gap-3 mb-3">
          <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>
            {selected.size} selected
          </span>
          <button
            onClick={handleDeleteSelected}
            className="px-3 py-1.5 rounded-lg text-xs font-medium text-white transition-colors"
            style={{ backgroundColor: 'var(--danger)' }}
          >
            Delete Selected
          </button>
        </div>
      )}

      <div className="overflow-x-auto rounded-lg border" style={{ borderColor: 'var(--border)' }}>
        <table className="w-full text-sm" style={{ color: 'var(--text-primary)' }}>
          <thead>
            <tr style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border)' }}>
              {/* Checkbox header */}
              <th className="px-4 py-3 text-left w-10">
                <input
                  type="checkbox"
                  checked={runs.length > 0 && selected.size === runs.length}
                  onChange={toggleAll}
                  style={{ accentColor: 'var(--accent)' }}
                />
              </th>
              {COLUMNS.map((col) => (
                <th
                  key={col.key}
                  className={`px-4 py-3 text-left font-medium text-xs uppercase tracking-wider ${
                    col.sortable ? 'cursor-pointer select-none' : ''
                  }`}
                  style={{ color: 'var(--text-secondary)' }}
                  onClick={() => handleSort(col.key)}
                >
                  {col.label}
                  {col.sortable && <SortArrow colKey={col.key} />}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <>
                <SkeletonRow />
                <SkeletonRow />
                <SkeletonRow />
                <SkeletonRow />
                <SkeletonRow />
              </>
            ) : runs.length === 0 ? (
              <tr>
                <td
                  colSpan={COLUMNS.length + 1}
                  className="px-4 py-12 text-center text-sm"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  No runs yet. Start your first analysis above.
                </td>
              </tr>
            ) : (
              runs.map((run) => (
                <tr
                  key={run.id}
                  className="border-t transition-colors"
                  style={{ borderColor: 'var(--border)' }}
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.backgroundColor = 'var(--bg-secondary)')
                  }
                  onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                >
                  {/* Checkbox */}
                  <td className="px-4 py-3">
                    <input
                      type="checkbox"
                      checked={selected.has(run.id)}
                      onChange={() => toggleOne(run.id)}
                      style={{ accentColor: 'var(--accent)' }}
                    />
                  </td>
                  {/* Ticker */}
                  <td className="px-4 py-3 font-semibold">{run.ticker}</td>
                  {/* Date */}
                  <td className="px-4 py-3" style={{ color: 'var(--text-secondary)' }}>
                    {run.trade_date || '--'}
                  </td>
                  {/* Signal */}
                  <td className="px-4 py-3">
                    {run.signal ? <SignalBadge signal={run.signal} /> : '--'}
                  </td>
                  {/* Provider */}
                  <td className="px-4 py-3" style={{ color: 'var(--text-secondary)' }}>
                    {run.provider || '--'}
                  </td>
                  {/* Duration */}
                  <td className="px-4 py-3" style={{ color: 'var(--text-secondary)' }}>
                    {formatDuration(run.duration)}
                  </td>
                  {/* Created */}
                  <td className="px-4 py-3" style={{ color: 'var(--text-secondary)' }}>
                    {relativeTime(run.created_at)}
                  </td>
                  {/* Actions */}
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => navigate(`/runs/${run.id}`)}
                        className="px-2.5 py-1 rounded text-xs font-medium transition-colors"
                        style={{
                          backgroundColor: 'color-mix(in srgb, var(--accent) 12%, transparent)',
                          color: 'var(--accent)',
                        }}
                      >
                        View
                      </button>
                      <button
                        onClick={() => onDelete?.(run.id)}
                        className="px-2.5 py-1 rounded text-xs font-medium transition-colors"
                        style={{
                          backgroundColor: 'color-mix(in srgb, var(--danger) 12%, transparent)',
                          color: 'var(--danger)',
                        }}
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>
            Page {page} of {totalPages} ({total} total)
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => onPageChange?.(page - 1)}
              disabled={page <= 1}
              className="px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              style={{
                borderColor: 'var(--border)',
                color: 'var(--text-primary)',
                backgroundColor: 'var(--bg-secondary)',
              }}
            >
              Previous
            </button>
            {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
              // Show pages around current page
              let p;
              if (totalPages <= 5) {
                p = i + 1;
              } else if (page <= 3) {
                p = i + 1;
              } else if (page >= totalPages - 2) {
                p = totalPages - 4 + i;
              } else {
                p = page - 2 + i;
              }
              return (
                <button
                  key={p}
                  onClick={() => onPageChange?.(p)}
                  className="px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors"
                  style={{
                    borderColor: p === page ? 'var(--accent)' : 'var(--border)',
                    color: p === page ? 'var(--accent)' : 'var(--text-primary)',
                    backgroundColor: p === page
                      ? 'color-mix(in srgb, var(--accent) 10%, transparent)'
                      : 'var(--bg-secondary)',
                  }}
                >
                  {p}
                </button>
              );
            })}
            <button
              onClick={() => onPageChange?.(page + 1)}
              disabled={page >= totalPages}
              className="px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              style={{
                borderColor: 'var(--border)',
                color: 'var(--text-primary)',
                backgroundColor: 'var(--bg-secondary)',
              }}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
