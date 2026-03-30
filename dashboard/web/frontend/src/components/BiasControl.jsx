import { useState } from 'react';
import { api } from '../hooks/useApi';

const DIRECTIONS = ['bullish', 'neutral', 'bearish'];
const CONFIDENCES = ['low', 'medium', 'high'];
const DIR_STYLES = {
  bullish: { color: 'var(--success)', bg: 'color-mix(in srgb, var(--success) 15%, transparent)' },
  neutral: { color: 'var(--text-secondary)', bg: 'color-mix(in srgb, var(--text-secondary) 10%, transparent)' },
  bearish: { color: 'var(--danger)', bg: 'color-mix(in srgb, var(--danger) 15%, transparent)' },
};

export default function BiasControl({ bias, onUpdate }) {
  const [reason, setReason] = useState(bias?.reason || '');
  const [saving, setSaving] = useState(false);
  const dir = bias?.direction || 'neutral';
  const conf = bias?.confidence || 'medium';
  const style = DIR_STYLES[dir] || DIR_STYLES.neutral;

  const save = async (updates) => {
    setSaving(true);
    try {
      const body = { direction: dir, reason, confidence: conf, ...updates };
      const result = await api('/api/trading/bias', { method: 'PUT', body });
      onUpdate(result.bias);
      if (updates.reason !== undefined) setReason(updates.reason);
    } catch (err) { console.error('Bias update failed:', err); }
    finally { setSaving(false); }
  };

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        {DIRECTIONS.map((d) => {
          const s = DIR_STYLES[d];
          const active = dir === d;
          return (
            <button key={d} onClick={() => save({ direction: d })} disabled={saving}
              className="flex-1 py-2 px-3 rounded-lg text-sm font-semibold transition-all capitalize"
              style={{ backgroundColor: active ? s.bg : 'transparent', color: active ? s.color : 'var(--text-secondary)', border: `1.5px solid ${active ? s.color : 'var(--border)'}`, opacity: saving ? 0.5 : 1 }}>
              {d}
            </button>
          );
        })}
      </div>
      <div className="flex gap-2 items-center">
        <span className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Confidence:</span>
        {CONFIDENCES.map((c) => (
          <button key={c} onClick={() => save({ confidence: c })} disabled={saving}
            className="px-2 py-0.5 rounded text-xs font-medium transition-all capitalize"
            style={{ backgroundColor: conf === c ? style.bg : 'transparent', color: conf === c ? style.color : 'var(--text-secondary)', border: `1px solid ${conf === c ? style.color : 'var(--border)'}` }}>
            {c}
          </button>
        ))}
      </div>
      <input type="text" value={reason} onChange={(e) => setReason(e.target.value)}
        onBlur={() => save({ reason })} onKeyDown={(e) => e.key === 'Enter' && save({ reason })}
        placeholder="Bias reason (e.g. NQ displacement above midnight open)"
        className="w-full px-3 py-1.5 rounded-lg text-sm border outline-none focus:ring-2"
        style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border)', color: 'var(--text-primary)' }} />
    </div>
  );
}
