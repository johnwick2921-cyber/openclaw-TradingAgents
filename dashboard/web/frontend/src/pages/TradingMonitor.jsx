import { useState, useEffect, useCallback } from 'react';
import { api } from '../hooks/useApi';
import ErrorBanner from '../components/ErrorBanner';
import HaltSwitch from '../components/HaltSwitch';
import BiasControl from '../components/BiasControl';
import WatchlistPanel from '../components/WatchlistPanel';
import PipelineStatus from '../components/PipelineStatus';
import RiskPanel from '../components/RiskPanel';
import SignalBadge from '../components/SignalBadge';

function Card({ title, children }) {
  return (
    <div className="rounded-xl border p-5" style={{ backgroundColor: 'var(--bg-primary)', borderColor: 'var(--border)' }}>
      {title && <h3 className="text-base font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>{title}</h3>}
      {children}
    </div>
  );
}

const PHASE_LABELS = { pre: 'Pre-Session', open: 'Market Open', midday: 'Midday', close: 'Near Close', post: 'Post-Session', closed: 'Market Closed' };

export default function TradingMonitor() {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchStatus = useCallback(async () => {
    try { const data = await api('/api/trading/status'); setStatus(data); setError(null); }
    catch (err) { setError(err.message); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  if (loading) return <div className="flex items-center justify-center h-64"><p style={{ color: 'var(--text-secondary)' }}>Loading...</p></div>;

  const s = status || {};
  const phase = PHASE_LABELS[s.market_phase] || s.market_phase || 'Unknown';

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold" style={{ color: 'var(--text-primary)' }}>Trading Monitor</h2>
          <p className="text-sm mt-0.5" style={{ color: 'var(--text-secondary)' }}>{s.strategy?.toUpperCase()} | {phase}</p>
        </div>
        <HaltSwitch halted={s.state === 'halted'} onToggle={() => fetchStatus()} />
      </div>
      {error && <ErrorBanner message={error} type="error" onDismiss={() => setError(null)} />}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card title="Market Bias"><BiasControl bias={s.bias} onUpdate={(bias) => setStatus((p) => ({ ...p, bias }))} /></Card>
        <Card title="Last Run">
          {s.last_run ? (
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>{s.last_run.ticker}</span>
                {s.last_run.signal && <SignalBadge signal={s.last_run.signal} />}
              </div>
              <div className="text-xs space-y-0.5" style={{ color: 'var(--text-secondary)' }}>
                <div>Date: {s.last_run.trade_date} | Strategy: {s.last_run.strategy}</div>
                <div>Duration: {s.last_run.duration_seconds?.toFixed(1)}s | Status: {s.last_run.status}</div>
              </div>
            </div>
          ) : <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>No runs yet</p>}
        </Card>
      </div>
      <Card title="Watchlist"><WatchlistPanel watchlist={s.watchlist} onUpdate={() => fetchStatus()} /></Card>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card title="Pipeline"><PipelineStatus analysis={s.analysis} strategy={s.strategy} /></Card>
        <Card title="Risk Parameters"><RiskPanel risk={s.risk} jadecap={s.jadecap} /></Card>
      </div>
      {s.memory_stats?.length > 0 && (
        <Card title="Memory Stats">
          <div className="flex flex-wrap gap-3">
            {s.memory_stats.map(({ agent, count }) => (
              <div key={agent} className="px-3 py-1.5 rounded-lg text-xs" style={{ backgroundColor: 'var(--bg-secondary)', color: 'var(--text-primary)' }}>
                <span className="font-medium">{agent}</span> <span style={{ color: 'var(--text-secondary)' }}>({count})</span>
              </div>
            ))}
          </div>
        </Card>
      )}
      <Card title="LLM Configuration">
        <div className="grid grid-cols-3 gap-2 text-sm">
          {[['Default', s.llm?.default || 'gpt-4o'], ['Deep Think', s.llm?.deep_think || 'claude-opus-4-6'], ['Quick Think', s.llm?.quick_think || 'gpt-4o-mini']].map(([label, val]) => (
            <div key={label} className="px-3 py-2 rounded-lg" style={{ backgroundColor: 'var(--bg-secondary)' }}>
              <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>{label}</div>
              <div className="font-medium" style={{ color: 'var(--text-primary)' }}>{val}</div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
