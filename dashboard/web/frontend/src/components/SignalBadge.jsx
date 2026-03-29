const SIGNAL_CONFIG = {
  BUY: { color: 'var(--signal-buy)', label: 'BUY' },
  OVERWEIGHT: { color: 'var(--signal-overweight)', label: 'OVERWEIGHT' },
  HOLD: { color: 'var(--signal-hold)', label: 'HOLD' },
  UNDERWEIGHT: { color: 'var(--signal-underweight)', label: 'UNDERWEIGHT' },
  SELL: { color: 'var(--signal-sell)', label: 'SELL' },
};

export default function SignalBadge({ signal }) {
  const config = SIGNAL_CONFIG[signal?.toUpperCase()] || SIGNAL_CONFIG.HOLD;

  return (
    <span
      className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold"
      style={{
        backgroundColor: `color-mix(in srgb, ${config.color} 15%, transparent)`,
        color: config.color,
        border: `1px solid color-mix(in srgb, ${config.color} 30%, transparent)`,
      }}
    >
      {config.label}
    </span>
  );
}
