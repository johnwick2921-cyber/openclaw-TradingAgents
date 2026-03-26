import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useWebSocket } from '../hooks/useWebSocket';
import { api } from '../hooks/useApi';
import AgentProgress from '../components/AgentProgress';
import LiveMessages from '../components/LiveMessages';
import ReportViewer from '../components/ReportViewer';
import ErrorBanner from '../components/ErrorBanner';

export default function LiveRun() {
  const { id: runId } = useParams();
  const navigate = useNavigate();

  // Check run status before connecting WebSocket
  const [runAlive, setRunAlive] = useState(true);

  // Derived state built from events
  const [agents, setAgents] = useState([]);
  const [messages, setMessages] = useState([]);
  const [reports, setReports] = useState([]); // accumulate all reports
  const [latestReport, setLatestReport] = useState(null);
  const [tokenStats, setTokenStats] = useState({ tokens_in: 0, tokens_out: 0 });
  const [runMeta, setRunMeta] = useState({ ticker: '', date: '' });
  const [status, setStatus] = useState('running'); // running | complete | failed
  const [errorMsg, setErrorMsg] = useState(null);
  const [warningMsg, setWarningMsg] = useState(null);
  const [cancelling, setCancelling] = useState(false);

  // On mount: check if run is actually still running
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await api(`/api/runs/${runId}`);
        if (cancelled) return;
        const run = data.run || data;
        if (run.status === 'completed') {
          navigate(`/runs/${runId}`, { replace: true });
          return;
        }
        if (run.status === 'failed' || run.status === 'cancelled') {
          setStatus('failed');
          setErrorMsg(run.error_message || `Run ${run.status}.`);
          setRunAlive(false);
          return;
        }
        // Still running — populate meta
        setRunMeta({ ticker: run.ticker || '', date: run.trade_date || '' });
      } catch {
        // Run not found — go to dashboard
        navigate('/', { replace: true });
      }
    })();
    return () => { cancelled = true; };
  }, [runId, navigate]);

  // Only connect WebSocket if run is alive
  const { events, connected } = useWebSocket(
    runAlive ? `/ws/runs/${runId}` : null
  );

  // Timer
  const [elapsed, setElapsed] = useState(0);
  const startTimeRef = useRef(Date.now());
  const timerRef = useRef(null);

  useEffect(() => {
    if (!runAlive) return;
    timerRef.current = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTimeRef.current) / 1000));
    }, 1000);
    return () => clearInterval(timerRef.current);
  }, [runAlive]);

  // Process incoming events
  const processedCountRef = useRef(0);

  useEffect(() => {
    if (events.length <= processedCountRef.current) return;

    const newEvents = events.slice(processedCountRef.current);
    processedCountRef.current = events.length;

    for (const rawEvt of newEvents) {
      // Backend wraps payload in "data" field — flatten for easier access
      const d = rawEvt.data || {};
      const evt = { ...rawEvt, ...d };

      switch (evt.type) {
        case 'agent_status':
          setAgents((prev) => {
            const existing = prev.findIndex((a) => a.name === evt.agent);
            const entry = { name: evt.agent, status: evt.status, duration: evt.duration };
            if (existing >= 0) {
              const updated = [...prev];
              updated[existing] = entry;
              return updated;
            }
            return [...prev, entry];
          });
          break;

        case 'message':
        case 'tool_call':
        case 'tool_call_detail':
        case 'warning':
        case 'error':
          setMessages((prev) => [
            ...prev,
            {
              _id: evt._id,
              timestamp: evt.timestamp || new Date().toISOString(),
              agent: evt.agent,
              content: evt.content || evt.message || evt.tool || '',
              type: evt.type,
            },
          ]);
          if (evt.type === 'warning') {
            setWarningMsg(evt.content || evt.message);
          }
          break;

        case 'report':
        case 'report_section': {
          const REPORT_NAMES = {
            market_report: 'Market Analysis',
            sentiment_report: 'Sentiment Analysis',
            news_report: 'News & Macro Analysis',
            fundamentals_report: 'Fundamentals Analysis',
            bull_analysis: 'Bull Researcher',
            bear_analysis: 'Bear Researcher',
            investment_plan: 'Research Manager Decision',
            trader_investment_plan: 'Trader Proposal',
            final_trade_decision: 'Portfolio Manager — Final Decision',
          };
          const rawTitle = evt.section || evt.title || 'Report';
          const title = REPORT_NAMES[rawTitle] || rawTitle;
          const content = evt.content;
          const report = { title, content };
          setLatestReport(report);
          // Only add if this title hasn't been added yet (prevents duplicates from repeated chunks)
          setReports((prev) => {
            if (prev.some((r) => r.title === title)) {
              // Update existing report with latest content
              return prev.map((r) => r.title === title ? report : r);
            }
            return [...prev, report];
          });
          break;
        }

        case 'token_stats':
          setTokenStats({
            tokens_in: evt.tokens_in ?? evt.total_input_tokens ?? 0,
            tokens_out: evt.tokens_out ?? evt.total_output_tokens ?? 0,
          });
          break;

        case 'run_started':
          setRunMeta({ ticker: evt.ticker || '', date: evt.trade_date || '' });
          break;

        case 'complete':
          setStatus('complete');
          setRunAlive(false); // stop WebSocket reconnecting
          clearInterval(timerRef.current);
          setTimeout(() => {
            navigate(`/runs/${runId}`);
          }, 3000);
          break;

        case 'failed':
        case 'cancelled':
          setStatus('failed');
          setRunAlive(false); // stop WebSocket reconnecting
          setErrorMsg(evt.message || evt.content || evt.error || 'Run failed.');
          clearInterval(timerRef.current);
          break;

        default:
          break;
      }
    }
  }, [events, runId, navigate]);

  const handleCancel = useCallback(async () => {
    setCancelling(true);
    try {
      await api(`/api/runs/${runId}/cancel`, { method: 'POST' });
    } catch (err) {
      setErrorMsg(`Cancel failed: ${err.message}`);
    } finally {
      setCancelling(false);
    }
  }, [runId]);

  const formatElapsed = (s) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
  };

  return (
    <div className="space-y-4">
      {/* Connection indicator */}
      {!connected && (
        <div
          className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm"
          style={{
            backgroundColor: 'color-mix(in srgb, var(--warning) 12%, transparent)',
            color: 'var(--warning)',
            border: '1px solid color-mix(in srgb, var(--warning) 30%, transparent)',
          }}
        >
          <span className="inline-block h-2 w-2 rounded-full animate-pulse" style={{ backgroundColor: 'var(--warning)' }} />
          Reconnecting to server...
        </div>
      )}

      {/* Success banner */}
      {status === 'complete' && (
        <ErrorBanner
          type="info"
          message="Run completed successfully. Redirecting to results..."
        />
      )}

      {/* Error banner */}
      {status === 'failed' && errorMsg && (
        <ErrorBanner type="error" message={errorMsg} />
      )}

      {/* Warning banner */}
      {warningMsg && status === 'running' && (
        <ErrorBanner
          type="warning"
          message={warningMsg}
          onDismiss={() => setWarningMsg(null)}
        />
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {runMeta.ticker && (
            <h2
              className="text-xl font-bold"
              style={{ color: 'var(--text-primary)' }}
            >
              {runMeta.ticker}
            </h2>
          )}
          {runMeta.date && (
            <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>
              {runMeta.date}
            </span>
          )}
          {!runMeta.ticker && (
            <h2
              className="text-xl font-bold"
              style={{ color: 'var(--text-primary)' }}
            >
              Live Run: {runId}
            </h2>
          )}
          <span
            className="inline-block h-2 w-2 rounded-full"
            style={{
              backgroundColor: connected ? 'var(--success)' : 'var(--danger)',
            }}
          />
        </div>

        <button
          onClick={handleCancel}
          disabled={cancelling || status !== 'running'}
          className="px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
          style={{
            backgroundColor: 'color-mix(in srgb, var(--danger) 12%, transparent)',
            color: 'var(--danger)',
            border: '1px solid color-mix(in srgb, var(--danger) 30%, transparent)',
          }}
        >
          {cancelling ? 'Cancelling...' : 'Cancel Run'}
        </button>
      </div>

      {/* Main columns */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        {/* Left: Agent Progress (40% = 2/5) */}
        <div className="lg:col-span-2">
          <AgentProgress agents={agents} />
        </div>

        {/* Right: Live Messages (60% = 3/5) */}
        <div className="lg:col-span-3">
          <LiveMessages messages={messages} />
        </div>
      </div>

      {/* Bottom: All completed reports */}
      {reports.map((r) => (
        <ReportViewer key={r.title} title={r.title} content={r.content} defaultExpanded={false} />
      ))}

      {/* Status bar */}
      <div
        className="flex items-center justify-between px-4 py-2 rounded-lg text-xs"
        style={{
          backgroundColor: 'var(--bg-tertiary)',
          color: 'var(--text-secondary)',
        }}
      >
        <div className="flex items-center gap-4">
          <span>Tokens In: <strong className="tabular-nums">{tokenStats.tokens_in.toLocaleString()}</strong></span>
          <span>Tokens Out: <strong className="tabular-nums">{tokenStats.tokens_out.toLocaleString()}</strong></span>
        </div>
        <div className="flex items-center gap-4">
          <span>Elapsed: <strong className="tabular-nums">{formatElapsed(elapsed)}</strong></span>
          <span>Events: <strong className="tabular-nums">{events.length}</strong></span>
        </div>
      </div>
    </div>
  );
}
