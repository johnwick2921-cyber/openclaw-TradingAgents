import { useState } from 'react';
import { api } from '../hooks/useApi';
import SignalBadge from './SignalBadge';

export default function WatchlistPanel({ watchlist, onUpdate }) {
  const [newTicker, setNewTicker] = useState('');

  const handleAdd = async () => {
    if (!newTicker.trim()) return;
    try {
      const result = await api('/api/trading/watchlist', { method: 'PUT', body: { action: 'add', ticker: newTicker.trim() } });
      onUpdate(result.watchlist);
      setNewTicker('');
    } catch (err) { console.error('Add failed:', err); }
  };

  const handleRemove = async (ticker) => {
    try {
      const result = await api('/api/trading/watchlist', { method: 'PUT', body: { action: 'remove', ticker } });
      onUpdate(result.watchlist);
    } catch (err) { console.error('Remove failed:', err); }
  };

  return (
    <div>
      <div className="flex gap-2 mb-3">
        <input type="text" value={newTicker} onChange={(e) => setNewTicker(e.target.value.toUpperCase())}
          onKeyDown={(e) => e.key === 'Enter' && handleAdd()} placeholder="Add ticker (e.g. NVDA)"
          className="flex-1 px-3 py-1.5 rounded-lg text-sm border outline-none focus:ring-2"
          style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border)', color: 'var(--text-primary)' }} />
        <button onClick={handleAdd} className="px-3 py-1.5 rounded-lg text-sm font-semibold text-white" style={{ backgroundColor: 'var(--accent)' }}>Add</button>
      </div>
      {(!watchlist || watchlist.length === 0) ? (
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>No tickers — add one above</p>
      ) : (
        <table className="w-full text-sm">
          <thead><tr style={{ color: 'var(--text-secondary)' }}>
            <th className="text-left py-1.5">Ticker</th><th className="text-left py-1.5">Signal</th>
            <th className="text-left py-1.5">Date</th><th className="text-left py-1.5">Status</th>
            <th className="text-center py-1.5">Correct?</th><th className="text-right py-1.5"></th>
          </tr></thead>
          <tbody>
            {watchlist.map((item) => (
              <tr key={item.ticker} className="border-t" style={{ borderColor: 'var(--border)' }}>
                <td className="py-2 font-semibold" style={{ color: 'var(--text-primary)' }}>{item.ticker}</td>
                <td className="py-2">{item.signal ? <SignalBadge signal={item.signal} /> : '—'}</td>
                <td className="py-2" style={{ color: 'var(--text-secondary)' }}>{item.date || '—'}</td>
                <td className="py-2" style={{ color: 'var(--text-secondary)' }}>{item.status || '—'}</td>
                <td className="py-2 text-center">{item.correct === true ? '✓' : item.correct === false ? '✗' : '—'}</td>
                <td className="py-2 text-right"><button onClick={() => handleRemove(item.ticker)} className="text-xs px-2 py-0.5 rounded" style={{ color: 'var(--danger)' }}>Remove</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
