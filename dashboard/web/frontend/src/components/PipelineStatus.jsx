export default function PipelineStatus({ analysis, strategy }) {
  const analysts = analysis?.analysts || ['market', 'social', 'news', 'fundamentals'];
  const debateRounds = analysis?.max_debate_rounds || 1;
  const riskRounds = analysis?.max_risk_discuss_rounds || 1;
  const tiers = [
    { label: 'Tier 1: Analysts', detail: analysts.join(', '), color: 'var(--accent)' },
    { label: 'Tier 2: Bull/Bear Debate', detail: `${debateRounds} round${debateRounds > 1 ? 's' : ''}`, color: 'var(--success)' },
    { label: 'Tier 3: Judge + Trader + Risk', detail: `${riskRounds} round${riskRounds > 1 ? 's' : ''} (aggressive → conservative → neutral)`, color: 'var(--warning)' },
    { label: 'Tier 4: Portfolio Manager', detail: 'Final BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL', color: 'var(--danger)' },
  ];
  return (
    <div className="space-y-2">
      {tiers.map((tier, i) => (
        <div key={i} className="flex items-center gap-3 px-3 py-2 rounded-lg" style={{ backgroundColor: 'var(--bg-secondary)' }}>
          <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: tier.color }} />
          <div>
            <div className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{tier.label}</div>
            <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>{tier.detail}</div>
          </div>
        </div>
      ))}
      <div className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
        Strategy: <strong>{strategy || 'default'}</strong> | Timeout: {analysis?.agent_timeout_seconds || 300}s/agent
      </div>
    </div>
  );
}
