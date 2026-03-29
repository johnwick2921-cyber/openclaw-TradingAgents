import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../hooks/useApi';
import SignalBadge from '../components/SignalBadge';
import ReportViewer from '../components/ReportViewer';
import DebateViewer from '../components/DebateViewer';
import ErrorBanner from '../components/ErrorBanner';

const TABS = [
  { key: 'analysts', label: 'Analysts' },
  { key: 'research_debate', label: 'Research Debate' },
  { key: 'trader', label: 'Trader' },
  { key: 'risk_debate', label: 'Risk Debate' },
  { key: 'final', label: 'Final Decision' },
];

const ANALYST_SECTIONS = [
  { key: 'market', label: 'Market Analysis' },
  { key: 'sentiment', label: 'Sentiment Analysis' },
  { key: 'news', label: 'News Analysis' },
  { key: 'fundamentals', label: 'Fundamentals Analysis' },
];

export default function RunDetails() {
  const { id: runId } = useParams();
  const navigate = useNavigate();

  const [run, setRun] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('analysts');

  // Action states
  const [rerunning, setRerunning] = useState(false);
  const [copied, setCopied] = useState(false);
  const [reflectPnl, setReflectPnl] = useState('');
  const [reflectResult, setReflectResult] = useState(null);
  const [reflecting, setReflecting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api(`/api/runs/${runId}`)
      .then((data) => {
        if (cancelled) return;

        // Transform API response into a flat structure for the page
        const r = data.run || data;
        const reports = data.reports || [];
        const debates = data.debates || [];

        // Build reports lookup by section name
        const reportMap = {};
        for (const rp of reports) {
          reportMap[rp.section_name] = rp.content;
        }

        // Build debate objects
        const investDebate = debates.find((d) => d.debate_type === 'investment');
        const riskDebate = debates.find((d) => d.debate_type === 'risk');

        // Parse debate history into exchanges array
        const parseExchanges = (history) => {
          if (!history) return [];
          // Split on speaker prefixes like "Bull Analyst:", "Bear Analyst:", etc.
          const parts = history.split(/(?=(?:Bull|Bear|Aggressive|Conservative|Neutral)\s+Analyst:)/);
          return parts
            .filter((p) => p.trim())
            .map((p) => {
              const colonIdx = p.indexOf(':');
              if (colonIdx > 0) {
                return { speaker: p.slice(0, colonIdx).trim(), content: p.slice(colonIdx + 1).trim() };
              }
              return { speaker: 'Unknown', content: p.trim() };
            });
        };

        const transformed = {
          ...r,
          ticker: r.ticker,
          date: r.trade_date,
          signal: r.signal,
          duration: r.duration_seconds,
          token_stats: { tokens_in: r.tokens_in || 0, tokens_out: r.tokens_out || 0 },
          // Analyst reports
          market_report: reportMap.market_report,
          sentiment_report: reportMap.sentiment_report,
          news_report: reportMap.news_report,
          fundamentals_report: reportMap.fundamentals_report,
          // Trader
          trader_plan: reportMap.trader_investment_plan,
          // Final decision
          final_trade_decision: reportMap.final_trade_decision,
          investment_plan: reportMap.investment_plan,
          // Debates
          research_debate: {
            exchanges: parseExchanges(investDebate?.full_history),
            judge_decision: investDebate?.judge_decision,
          },
          risk_debate: {
            exchanges: parseExchanges(riskDebate?.full_history),
            judge_decision: riskDebate?.judge_decision,
          },
        };

        setRun(transformed);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [runId]);

  const handleRerun = useCallback(async () => {
    setRerunning(true);
    try {
      const result = await api(`/api/runs/${runId}/rerun`, { method: 'POST' });
      navigate(`/runs/${result.id || result.run_id}/live`);
    } catch (err) {
      setError(`Re-run failed: ${err.message}`);
    } finally {
      setRerunning(false);
    }
  }, [runId, navigate]);

  const handleExport = useCallback(async () => {
    try {
      const data = await api(`/api/runs/${runId}/export`);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `run-${runId}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(`Export failed: ${err.message}`);
    }
  }, [runId]);

  const handleCopyReport = useCallback(async () => {
    if (!run?.final_trade_decision) return;
    try {
      await navigator.clipboard.writeText(run.final_trade_decision);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      const ta = document.createElement('textarea');
      ta.value = run.final_trade_decision;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [run]);

  const handleReflect = useCallback(async () => {
    if (!reflectPnl) return;
    setReflecting(true);
    setReflectResult(null);
    try {
      const result = await api(`/api/runs/${runId}/reflect`, {
        method: 'POST',
        body: { returns_losses: parseFloat(reflectPnl) },
      });
      setReflectResult(result.message || result.lesson || 'Reflection saved.');
    } catch (err) {
      setReflectResult(err.message || 'Not implemented yet.');
    } finally {
      setReflecting(false);
    }
  }, [runId, reflectPnl]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div
          className="h-8 w-8 rounded-full border-2 border-t-transparent animate-spin"
          style={{ borderColor: 'var(--accent)', borderTopColor: 'transparent' }}
        />
      </div>
    );
  }

  if (error && !run) {
    return <ErrorBanner type="error" message={error} />;
  }

  if (!run) {
    return <ErrorBanner type="error" message="Run not found." />;
  }

  const formatDuration = (d) => {
    if (d == null) return '--';
    if (typeof d === 'number') {
      const m = Math.floor(d / 60);
      const s = (d % 60).toFixed(1);
      return m > 0 ? `${m}m ${s}s` : `${s}s`;
    }
    return String(d);
  };

  return (
    <div className="space-y-6">
      {/* Error banner */}
      {error && <ErrorBanner type="error" message={error} onDismiss={() => setError(null)} />}

      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <h2
            className="text-2xl font-bold"
            style={{ color: 'var(--text-primary)' }}
          >
            {run.ticker || `Run ${runId}`}
          </h2>
          {run.date && (
            <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>
              {run.date}
            </span>
          )}
          <SignalBadge signal={run.signal} />
        </div>

        <div className="flex items-center gap-3 text-sm" style={{ color: 'var(--text-secondary)' }}>
          <span>Duration: <strong>{formatDuration(run.duration)}</strong></span>
          {run.token_stats && (
            <>
              <span className="opacity-40">|</span>
              <span>
                Tokens: <strong>{(run.token_stats.tokens_in ?? 0).toLocaleString()}</strong> in / <strong>{(run.token_stats.tokens_out ?? 0).toLocaleString()}</strong> out
              </span>
            </>
          )}
        </div>
      </div>

      {/* Tab navigation */}
      <div
        className="flex gap-1 border-b"
        style={{ borderColor: 'var(--border)' }}
      >
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className="px-4 py-2 text-sm font-medium transition-colors relative"
            style={{
              color: activeTab === tab.key ? 'var(--accent)' : 'var(--text-secondary)',
            }}
          >
            {tab.label}
            {activeTab === tab.key && (
              <span
                className="absolute bottom-0 left-0 right-0 h-0.5 rounded-full"
                style={{ backgroundColor: 'var(--accent)' }}
              />
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="space-y-4">
        {activeTab === 'analysts' && (
          <>
            {ANALYST_SECTIONS.map(({ key, label }) => {
              const content = run.analysts?.[key] || run[`${key}_report`] || run[key];
              if (!content) return null;
              return <ReportViewer key={key} title={label} content={content} />;
            })}
            {ANALYST_SECTIONS.every(
              ({ key }) => !(run.analysts?.[key] || run[`${key}_report`] || run[key])
            ) && (
              <p className="text-sm py-8 text-center" style={{ color: 'var(--text-secondary)' }}>
                No analyst reports available.
              </p>
            )}
          </>
        )}

        {activeTab === 'research_debate' && (
          <DebateViewer
            exchanges={run.research_debate?.exchanges || run.investment_debate?.exchanges || []}
            judgeDecision={run.research_debate?.judge_decision || run.investment_debate?.judge_decision}
          />
        )}

        {activeTab === 'trader' && (
          <ReportViewer
            title="Trader Plan"
            content={run.trader_plan || run.trader?.plan || run.trader}
          />
        )}

        {activeTab === 'risk_debate' && (
          <DebateViewer
            exchanges={run.risk_debate?.exchanges || []}
            judgeDecision={run.risk_debate?.judge_decision}
          />
        )}

        {activeTab === 'final' && (
          <>
            <ReportViewer
              title="Final Trade Decision"
              content={run.final_trade_decision}
            />
            {run.signal && (
              <div
                className="flex items-center gap-3 px-4 py-3 rounded-lg border"
                style={{
                  backgroundColor: 'var(--bg-secondary)',
                  borderColor: 'var(--border)',
                }}
              >
                <span className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
                  Signal:
                </span>
                <SignalBadge signal={run.signal} />
              </div>
            )}
          </>
        )}
      </div>

      {/* Action buttons */}
      <div
        className="flex flex-wrap items-center gap-3 pt-2 border-t"
        style={{ borderColor: 'var(--border)' }}
      >
        <button
          onClick={handleRerun}
          disabled={rerunning}
          className="px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
          style={{
            backgroundColor: 'var(--accent)',
            color: '#ffffff',
          }}
        >
          {rerunning ? 'Starting...' : 'Re-run'}
        </button>

        <button
          onClick={handleExport}
          className="px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          style={{
            backgroundColor: 'var(--bg-tertiary)',
            color: 'var(--text-primary)',
            border: '1px solid var(--border)',
          }}
        >
          Export JSON
        </button>

        <button
          onClick={handleCopyReport}
          disabled={!run.final_trade_decision}
          className="px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
          style={{
            backgroundColor: 'var(--bg-tertiary)',
            color: copied ? 'var(--success)' : 'var(--text-primary)',
            border: '1px solid var(--border)',
          }}
        >
          {copied ? 'Copied!' : 'Copy Report'}
        </button>
      </div>

      {/* Reflect section */}
      <div
        className="rounded-xl border p-4 space-y-3"
        style={{
          backgroundColor: 'var(--bg-secondary)',
          borderColor: 'var(--border)',
        }}
      >
        <h3
          className="text-sm font-semibold"
          style={{ color: 'var(--text-primary)' }}
        >
          Reflect
        </h3>
        <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
          Enter actual P&L to generate lessons
        </p>

        <div className="flex items-center gap-3">
          <input
            type="number"
            value={reflectPnl}
            onChange={(e) => setReflectPnl(e.target.value)}
            placeholder="e.g. 2.5 or -1.3"
            className="flex-1 max-w-xs px-3 py-2 rounded-lg text-sm outline-none transition-colors"
            style={{
              backgroundColor: 'var(--bg-tertiary)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border)',
            }}
          />
          <button
            onClick={handleReflect}
            disabled={reflecting || !reflectPnl}
            className="px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
            style={{
              backgroundColor: 'var(--accent)',
              color: '#ffffff',
            }}
          >
            {reflecting ? 'Submitting...' : 'Submit'}
          </button>
        </div>

        {reflectResult && (
          <div
            className="text-sm px-3 py-2 rounded-lg"
            style={{
              backgroundColor: 'var(--bg-tertiary)',
              color: 'var(--text-primary)',
            }}
          >
            {reflectResult}
          </div>
        )}
      </div>
    </div>
  );
}
