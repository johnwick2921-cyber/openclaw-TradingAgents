export default function RiskPanel({ risk, jadecap }) {
  const params = [
    { label: 'Max Loss / Trade', value: `$${risk?.max_loss_per_trade || 500}` },
    { label: 'Daily Loss Limit', value: `$${risk?.daily_loss_limit || 1000}` },
    { label: 'Max Drawdown', value: `${risk?.max_drawdown_pct || 5}%` },
    { label: 'Max Consecutive Losses', value: risk?.max_consecutive_losses || 3 },
    { label: 'Min Risk/Reward', value: `${risk?.min_risk_reward || 3}:1` },
  ];
  if (jadecap) {
    params.push(
      { label: 'ATR Stop Multiplier', value: `${jadecap.atr_stop_multiplier || 1.5}x` },
      { label: 'T1 Close', value: `${(jadecap.t1_close_pct || 0.5) * 100}%` },
      { label: 'Hard Close', value: `${jadecap.hard_close_time || '15:45'} ET` },
      { label: 'Instrument', value: `${jadecap.active_instrument || 'NQ'} ($${jadecap.instruments?.[jadecap.active_instrument]?.point_value || 20}/pt)` },
    );
  }
  return (
    <div className="grid grid-cols-2 gap-2">
      {params.map(({ label, value }) => (
        <div key={label} className="px-3 py-2 rounded-lg" style={{ backgroundColor: 'var(--bg-secondary)' }}>
          <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>{label}</div>
          <div className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{value}</div>
        </div>
      ))}
    </div>
  );
}
