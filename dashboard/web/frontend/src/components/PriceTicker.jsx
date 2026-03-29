import { useState, useEffect, useRef, useCallback } from 'react';
import { api } from '../hooks/useApi';

export default function PriceTicker({ symbol = 'NQ' }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [flash, setFlash] = useState(null); // 'up' | 'down' | null
  const prevPrice = useRef(null);
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);

  const applyTick = useCallback((tick) => {
    if (!tick || tick.price == null) return;

    // Flash green/red on price change
    if (prevPrice.current !== null) {
      if (tick.price > prevPrice.current) setFlash('up');
      else if (tick.price < prevPrice.current) setFlash('down');
    }
    prevPrice.current = tick.price;
    setData(tick);
    setLoading(false);

    // Clear flash after animation
    setTimeout(() => setFlash(null), 400);
  }, []);

  useEffect(() => {
    let active = true;

    // Try WebSocket first for real-time ticks
    const connectWs = () => {
      if (!active) return;
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/ws/prices/${symbol}`;
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        // WebSocket connected — ticks will stream in
      };

      ws.onmessage = (evt) => {
        try {
          const tick = JSON.parse(evt.data);
          if (active) applyTick(tick);
        } catch { /* ignore */ }
      };

      ws.onclose = () => {
        // Reconnect after 5s
        if (active) {
          reconnectTimer.current = setTimeout(connectWs, 5000);
        }
      };

      ws.onerror = () => { /* onclose will fire */ };

      wsRef.current = ws;
    };

    connectWs();

    // Also fetch once via REST as initial fallback (in case WS takes a moment)
    (async () => {
      try {
        const result = await api(`/api/prices/${symbol}`);
        if (active && result.price != null && !prevPrice.current) {
          applyTick(result);
        }
      } catch { /* ignore */ }
    })();

    return () => {
      active = false;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [symbol, applyTick]);

  if (loading && !data) {
    return (
      <div
        className="flex items-center gap-3 px-4 py-3 rounded-xl border animate-pulse"
        style={{ backgroundColor: 'var(--bg-primary)', borderColor: 'var(--border)' }}
      >
        <div className="h-4 w-20 rounded" style={{ backgroundColor: 'var(--bg-secondary)' }} />
        <div className="h-6 w-28 rounded" style={{ backgroundColor: 'var(--bg-secondary)' }} />
      </div>
    );
  }

  if (!data || data.price == null) {
    return null;
  }

  const isUp = data.change >= 0;
  const changeColor = isUp ? '#22c55e' : '#ef4444';
  const arrow = isUp ? '▲' : '▼';

  const flashBg =
    flash === 'up' ? 'rgba(34,197,94,0.15)' :
    flash === 'down' ? 'rgba(239,68,68,0.15)' :
    'var(--bg-primary)';

  const sourceLabel = data.source?.includes('databento') ? 'Live' :
    data.source?.includes('yfinance') ? 'Delayed' : data.source || '';

  return (
    <div
      className="flex items-center gap-4 px-5 py-3 rounded-xl border transition-colors duration-200"
      style={{
        backgroundColor: flashBg,
        borderColor: 'var(--border)',
      }}
    >
      {/* Symbol */}
      <div className="flex flex-col">
        <span className="text-xs font-medium tracking-wide" style={{ color: 'var(--text-secondary)' }}>
          {data.symbol}
        </span>
        <span className="text-xs" style={{ color: sourceLabel === 'Live' ? '#22c55e' : 'var(--text-secondary)', opacity: sourceLabel === 'Live' ? 1 : 0.6 }}>
          {sourceLabel}
        </span>
      </div>

      {/* Price */}
      <span
        className="text-2xl font-bold tabular-nums tracking-tight"
        style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono, ui-monospace, monospace)' }}
      >
        {data.price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
      </span>

      {/* Change */}
      <div className="flex flex-col items-end">
        <span
          className="text-sm font-semibold tabular-nums"
          style={{ color: changeColor, fontFamily: 'var(--font-mono, ui-monospace, monospace)' }}
        >
          {arrow} {Math.abs(data.change).toFixed(2)}
        </span>
        <span
          className="text-xs font-medium tabular-nums"
          style={{ color: changeColor, fontFamily: 'var(--font-mono, ui-monospace, monospace)' }}
        >
          {isUp ? '+' : ''}{data.change_pct.toFixed(2)}%
        </span>
      </div>

      {/* OHLV mini stats */}
      <div
        className="hidden sm:flex gap-4 ml-2 pl-4 border-l text-xs tabular-nums"
        style={{
          borderColor: 'var(--border)',
          color: 'var(--text-secondary)',
          fontFamily: 'var(--font-mono, ui-monospace, monospace)',
        }}
      >
        <div className="flex flex-col">
          <span style={{ opacity: 0.6 }}>O</span>
          <span>{data.open?.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
        </div>
        <div className="flex flex-col">
          <span style={{ opacity: 0.6 }}>H</span>
          <span>{data.high?.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
        </div>
        <div className="flex flex-col">
          <span style={{ opacity: 0.6 }}>L</span>
          <span>{data.low?.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
        </div>
        <div className="flex flex-col">
          <span style={{ opacity: 0.6 }}>Vol</span>
          <span>{data.volume?.toLocaleString()}</span>
        </div>
      </div>
    </div>
  );
}
