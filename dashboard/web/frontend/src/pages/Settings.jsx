import { useState, useEffect, useRef, useCallback } from 'react';
import { api } from '../hooks/useApi';
import { useTheme } from '../hooks/useTheme';
import ErrorBanner from '../components/ErrorBanner';

const PROVIDERS = ['openai', 'anthropic', 'google', 'deepseek', 'xai', 'ollama', 'openrouter'];

const ANALYSTS = [
  { key: 'market', label: 'Market Analyst' },
  { key: 'social', label: 'Social Analyst' },
  { key: 'news', label: 'News Analyst' },
  { key: 'fundamentals', label: 'Fundamentals Analyst' },
];

const API_KEYS = [
  { key: 'OPENAI_API_KEY', label: 'OpenAI' },
  { key: 'ANTHROPIC_API_KEY', label: 'Anthropic' },
  { key: 'GOOGLE_API_KEY', label: 'Google' },
  { key: 'DEEPSEEK_API_KEY', label: 'DeepSeek' },
  { key: 'XAI_API_KEY', label: 'xAI' },
  { key: 'OPENROUTER_API_KEY', label: 'OpenRouter' },
  { key: 'ALPHA_VANTAGE_API_KEY', label: 'Alpha Vantage' },
  { key: 'DATABENTO_API_KEY', label: 'Databento' },
];

/* ---------- reusable styled helpers ---------- */

const inputStyle = {
  backgroundColor: 'var(--bg-secondary)',
  borderColor: 'var(--border)',
  color: 'var(--text-primary)',
  '--tw-ring-color': 'var(--accent)',
};

const inputClass =
  'px-3 py-2 rounded-lg text-sm border outline-none transition-colors focus:ring-2 w-full';

function Card({ title, children }) {
  return (
    <div
      className="rounded-xl border p-6"
      style={{ backgroundColor: 'var(--bg-primary)', borderColor: 'var(--border)' }}
    >
      {title && (
        <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
          {title}
        </h3>
      )}
      {children}
    </div>
  );
}

function Label({ children }) {
  return (
    <label className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
      {children}
    </label>
  );
}

function PrimaryButton({ onClick, disabled, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      style={{ backgroundColor: disabled ? 'var(--text-secondary)' : 'var(--accent)' }}
      onMouseEnter={(e) => {
        if (!disabled) e.currentTarget.style.backgroundColor = 'var(--accent-hover)';
      }}
      onMouseLeave={(e) => {
        if (!disabled) e.currentTarget.style.backgroundColor = 'var(--accent)';
      }}
    >
      {children}
    </button>
  );
}

function DangerButton({ onClick, disabled, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      style={{
        color: 'var(--danger)',
        backgroundColor: 'color-mix(in srgb, var(--danger) 10%, transparent)',
      }}
    >
      {children}
    </button>
  );
}

/* ============ Collapsible Section ============ */

function CollapsibleSection({ title, defaultOpen = true, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div
      className="rounded-xl border overflow-hidden"
      style={{ borderColor: 'var(--border)', backgroundColor: 'var(--bg-primary)' }}
    >
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-5 py-4 text-left transition-colors"
        style={{ backgroundColor: open ? 'var(--bg-secondary)' : 'transparent' }}
      >
        <span className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>
          {title}
        </span>
        <svg
          width="20"
          height="20"
          viewBox="0 0 20 20"
          fill="none"
          className="transition-transform"
          style={{ transform: open ? 'rotate(180deg)' : 'rotate(0deg)', color: 'var(--text-secondary)' }}
        >
          <path d="M5 7.5L10 12.5L15 7.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </button>
      {open && <div className="px-5 py-4">{children}</div>}
    </div>
  );
}

/* ============ Main Component ============ */

export default function Settings() {
  const { theme, setTheme } = useTheme();
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);
  const [stratKey, setStratKey] = useState('default');

  const showSuccess = (msg) => {
    setSuccessMsg(msg);
    setTimeout(() => setSuccessMsg(null), 3000);
  };

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h2 className="text-2xl font-semibold" style={{ color: 'var(--text-primary)' }}>
          Settings
        </h2>
        <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
          Manage your default configuration, API keys, and preferences.
        </p>
      </div>

      {/* Banners */}
      {error && <ErrorBanner message={error} type="error" onDismiss={() => setError(null)} />}
      {successMsg && (
        <ErrorBanner message={successMsg} type="info" onDismiss={() => setSuccessMsg(null)} />
      )}

      <CollapsibleSection title="Strategy Configuration" defaultOpen={true}>
        <StrategyConfigSection onError={setError} onSuccess={showSuccess} onSwitch={setStratKey} />
      </CollapsibleSection>
      <CollapsibleSection title="Default Configuration" defaultOpen={false}>
        <DefaultConfigSection onError={setError} onSuccess={showSuccess} stratKey={stratKey} />
      </CollapsibleSection>
      <CollapsibleSection title="Data Providers" defaultOpen={false}>
        <DataProvidersSection onError={setError} onSuccess={showSuccess} />
      </CollapsibleSection>
      <CollapsibleSection title="API Keys" defaultOpen={false}>
        <ApiKeysSection onError={setError} onSuccess={showSuccess} />
      </CollapsibleSection>
      <ThemeSection theme={theme} setTheme={setTheme} />
      <DataManagementSection onError={setError} onSuccess={showSuccess} />
      <AboutSection />
    </div>
  );
}

/* ---------- 1. Default Configuration ---------- */

function DefaultConfigSection({ onError, onSuccess, stratKey }) {
  const [form, setForm] = useState({
    provider: 'openai',
    quick_model: '',
    deep_model: '',
    effort: '',
    backend_url: '',
    analysts: ['market', 'social', 'news', 'fundamentals'],
    max_debate_rounds: 1,
    max_risk_rounds: 1,
  });
  const [saving, setSaving] = useState(false);
  const [configData, setConfigData] = useState({ deep_models: {}, quick_models: {} });

  // Fetch available models
  useEffect(() => {
    api('/api/config')
      .then((data) => setConfigData(data))
      .catch(() => {});
  }, []);


  // Fetch saved settings
  useEffect(() => {
    api('/api/settings')
      .then((data) => {
        setForm({
          provider: data.provider || 'openai',
          quick_model: data.quick_model || '',
          deep_model: data.deep_model || '',
          effort: data.effort || '',
          backend_url: data.backend_url || '',
          analysts: data.analysts?.length ? data.analysts : ['market', 'social', 'news', 'fundamentals'],
          max_debate_rounds: data.max_debate_rounds ?? 1,
          max_risk_rounds: data.max_risk_rounds ?? 1,
        });
      })
      .catch(() => {});
  }, []);

  // When strategy switches, apply its suggested defaults
  useEffect(() => {
    const strat = STRATEGIES[stratKey];
    if (!strat || !strat.suggested_defaults) return;
    const d = strat.suggested_defaults;
    setForm((prev) => ({
      ...prev,
      analysts: d.analysts || prev.analysts,
    }));
  }, [stratKey]);

  const quickModels = configData.quick_models?.[form.provider] || [];
  const deepModels = configData.deep_models?.[form.provider] || [];

  // Auto-select first model when provider changes
  useEffect(() => {
    const qModels = configData.quick_models?.[form.provider] || [];
    const dModels = configData.deep_models?.[form.provider] || [];
    const qValues = qModels.map((m) => m.value);
    const dValues = dModels.map((m) => m.value);
    setForm((prev) => ({
      ...prev,
      quick_model: qValues.includes(prev.quick_model) ? prev.quick_model : (qValues[0] || ''),
      deep_model: dValues.includes(prev.deep_model) ? prev.deep_model : (dValues[0] || ''),
    }));
  }, [form.provider, configData]);

  const update = (field, value) => setForm((prev) => ({ ...prev, [field]: value }));

  const toggleAnalyst = (key) => {
    setForm((prev) => {
      const has = prev.analysts.includes(key);
      const next = has ? prev.analysts.filter((a) => a !== key) : [...prev.analysts, key];
      return next.length ? { ...prev, analysts: next } : prev;
    });
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await api('/api/settings', { method: 'PUT', body: form });
      onSuccess('Default configuration saved.');
    } catch (err) {
      onError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Provider */}
        <div className="flex flex-col gap-1.5">
          <Label>Provider</Label>
          <select
            value={form.provider}
            onChange={(e) => update('provider', e.target.value)}
            className={inputClass}
            style={inputStyle}
          >
            {PROVIDERS.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </div>

        {/* Quick Model */}
        <div className="flex flex-col gap-1.5">
          <Label>Quick Model</Label>
          <select
            value={form.quick_model}
            onChange={(e) => update('quick_model', e.target.value)}
            className={inputClass}
            style={inputStyle}
          >
            {quickModels.length === 0 && <option value="">Loading models...</option>}
            {quickModels.map((m) => (
              <option key={m.value} value={m.value}>{m.label}</option>
            ))}
          </select>
        </div>

        {/* Deep Model */}
        <div className="flex flex-col gap-1.5">
          <Label>Deep Model</Label>
          <select
            value={form.deep_model}
            onChange={(e) => update('deep_model', e.target.value)}
            className={inputClass}
            style={inputStyle}
          >
            {deepModels.length === 0 && <option value="">Loading models...</option>}
            {deepModels.map((m) => (
              <option key={m.value} value={m.value}>{m.label}</option>
            ))}
          </select>
        </div>

        {/* Effort */}
        <div className="flex flex-col gap-1.5">
          <Label>Effort</Label>
          <select
            value={form.effort}
            onChange={(e) => update('effort', e.target.value)}
            className={inputClass}
            style={inputStyle}
          >
            <option value="">None</option>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
          </select>
        </div>

        {/* Backend URL */}
        <div className="flex flex-col gap-1.5">
          <Label>Backend URL (optional)</Label>
          <input
            type="text"
            placeholder="http://localhost:11434"
            value={form.backend_url}
            onChange={(e) => update('backend_url', e.target.value)}
            className={inputClass}
            style={inputStyle}
          />
        </div>

        {/* Research Depth */}
        <div className="flex flex-col gap-1.5">
          <Label>Research Depth</Label>
          <select
            value={form.max_debate_rounds}
            onChange={(e) => {
              const v = Number(e.target.value);
              setForm((prev) => ({ ...prev, max_debate_rounds: v, max_risk_rounds: v }));
            }}
            className={inputClass}
            style={inputStyle}
          >
            <option value={1}>Shallow - Quick research, few debate rounds</option>
            <option value={3}>Medium - Moderate debate and strategy discussion</option>
            <option value={5}>Deep - Comprehensive, in-depth debate</option>
          </select>
        </div>

      </div>

      {/* Default Analysts */}
      <div className="mt-4">
        <Label>Default Analysts</Label>
        <div className="flex flex-wrap gap-4 mt-2">
          {ANALYSTS.map(({ key, label }) => (
            <label
              key={key}
              className="flex items-center gap-2 text-sm cursor-pointer select-none"
              style={{ color: 'var(--text-primary)' }}
            >
              <input
                type="checkbox"
                checked={form.analysts.includes(key)}
                onChange={() => toggleAnalyst(key)}
                className="rounded"
                style={{ accentColor: 'var(--accent)' }}
              />
              {label}
            </label>
          ))}
        </div>
      </div>

      <div className="mt-5">
        <PrimaryButton onClick={handleSave} disabled={saving}>
          {saving ? 'Saving...' : 'Save Defaults'}
        </PrimaryButton>
      </div>
    </Card>
  );
}

/* ---------- 1b. Strategy Configuration ---------- */

// Strategy registry — add new strategies here
const STRATEGIES = {
  default: {
    name: 'Default (Original TradingAgents)',
    description: 'Standard multi-agent stock analysis — all analysts, yfinance/Alpha Vantage data',
    entry_models: [],
    kill_zones: [],
    checklist: [],
    risk_defaults: { min_rr: 1, max_trades_per_kz: 99, hard_close_time: '16:00' },
    instruments: [],
    suggested_defaults: {
      analysts: ['market', 'social', 'news', 'fundamentals'],
      data_vendors: { core_stock_apis: 'yfinance', technical_indicators: 'yfinance', news_data: 'yfinance', fundamental_data: 'yfinance' },
    },
  },
  jadecap_ict: {
    name: 'JadeCap ICT (Kyle Ng)',
    description: 'ICT Power of Three (AMD) — NQ/MNQ futures, prop firm trading',
    entry_models: [
      { key: 'daily_sweep_sfp', label: 'Entry 0 — SFP / Daily Sweep', desc: '#1 strategy — sweep swing H/L, close back inside = SFP' },
      { key: 'fvg', label: 'Entry 1 — Fair Value Gap (FVG)', desc: '3-candle imbalance gap retrace' },
      { key: 'ob', label: 'Entry 2 — Order Block (OB)', desc: 'Last opposing candle before displacement' },
      { key: 'liq_raid', label: 'Entry 3 — Liquidity Raid (Turtle Soup)', desc: 'Sweep key H/L then reverse' },
      { key: 'breaker', label: 'Entry 4 — Breaker Block', desc: 'Failed OB flips to opposite S/R' },
      { key: 'ote', label: 'Entry 5 — OTE Fibonacci (62-79%)', desc: 'Optimal trade entry at Fib retracement' },
    ],
    kill_zones: [
      { key: 'am', label: 'AM Kill Zone', time: '9:30 – 11:30 AM EST', primary: true },
      { key: 'silver1', label: 'Silver Bullet AM', time: '10:00 – 11:00 AM EST', primary: true },
      { key: 'pm', label: 'PM Kill Zone', time: '1:00 – 4:00 PM EST', primary: true },
      { key: 'silver2', label: 'Silver Bullet PM', time: '2:00 – 3:00 PM EST', primary: false },
    ],
    checklist: [
      { key: 'require_htf_bias', label: 'HTF Bias Confirmed', desc: 'Weekly/Daily structure and FVG same direction' },
      { key: 'require_correct_zone', label: 'Price in Correct Zone', desc: 'Discount for longs, premium for shorts' },
      { key: 'require_liquidity_sweep', label: 'Liquidity Swept', desc: 'Prior H/L or session level raided first' },
      { key: 'require_displacement', label: 'Displacement Candle', desc: 'Strong move from swept level' },
      { key: 'require_pd_array', label: 'LTF PD Array Identified', desc: 'FVG/OB/Breaker on 5m or 15m' },
      { key: 'skip_if_target_hit', label: 'Skip if Daily Target Hit', desc: 'No trade if PDH/PDL already taken' },
    ],
    risk_defaults: { min_rr: 2, max_trades_per_kz: 1, hard_close_time: '16:00', base_risk_pct: 0.25 },
    instruments: ['NQ', 'MNQ', 'ES', 'MES'],
    suggested_defaults: {
      analysts: ['market', 'news'],
      data_vendors: { core_stock_apis: 'databento', technical_indicators: 'databento', news_data: 'yfinance', fundamental_data: 'yfinance' },
    },
  },
};

/* --- Collapsible sub-section inside StrategyConfig --- */

function StrategySubSection({ title, defaultOpen = false, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div
      className="rounded-lg border overflow-hidden mb-4"
      style={{ borderColor: 'var(--border)', backgroundColor: 'var(--bg-secondary)' }}
    >
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 text-left transition-colors"
        style={{ backgroundColor: open ? 'color-mix(in srgb, var(--accent) 5%, var(--bg-secondary))' : 'transparent' }}
      >
        <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
          {title}
        </span>
        <svg
          width="16" height="16" viewBox="0 0 20 20" fill="none"
          className="transition-transform"
          style={{ transform: open ? 'rotate(180deg)' : 'rotate(0deg)', color: 'var(--text-secondary)' }}
        >
          <path d="M5 7.5L10 12.5L15 7.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </button>
      {open && <div className="px-4 py-3 border-t" style={{ borderColor: 'var(--border)' }}>{children}</div>}
    </div>
  );
}

/* --- Info row helper for display-only sections --- */

function InfoRow({ label, value, mono = false }) {
  return (
    <div className="flex items-start gap-2 py-1">
      <span className="text-xs font-medium shrink-0" style={{ color: 'var(--text-secondary)', minWidth: 90 }}>{label}</span>
      <span className={`text-xs ${mono ? 'font-mono' : ''}`} style={{ color: 'var(--text-primary)' }}>{value}</span>
    </div>
  );
}

function StrategyConfigSection({ onError, onSuccess, onSwitch }) {
  const [form, setForm] = useState({
    strategy: 'jadecap_ict',
    min_rr: 2,
    max_trades_per_kz: 1,
    max_loss_per_trade: 500,
    daily_profit_target: 1000,
    base_risk_pct: 0.25,
    hard_close_time: '16:00',
    instrument: 'NQ',
    entry_models: ['daily_sweep_sfp', 'fvg', 'ob', 'liq_raid', 'breaker', 'ote'],
    kill_zones: ['am', 'silver1', 'pm', 'silver2'],
    htf_timeframes: ['1W', '1D', '4H'],
    ltf_timeframes: ['15m', '5m'],
    require_htf_bias: true,
    require_correct_zone: true,
    require_liquidity_sweep: true,
    require_displacement: true,
    require_pd_array: true,
    skip_if_target_hit: true,
    midday_avoidance_enabled: true,
    holiday_rules_enabled: true,
  });

  const activeStrategy = STRATEGIES[form.strategy] || STRATEGIES.default;
  const [saving, setSaving] = useState(false);
  const isJadeCap = form.strategy !== 'default';

  useEffect(() => {
    api('/api/settings')
      .then((data) => {
        if (data.strategy_config) {
          try {
            const parsed = typeof data.strategy_config === 'string'
              ? JSON.parse(data.strategy_config) : data.strategy_config;
            setForm((prev) => ({ ...prev, ...parsed }));
          } catch {}
        }
      })
      .catch(() => {});
  }, []);

  const toggleEntry = (key) => {
    setForm((prev) => ({
      ...prev,
      entry_models: prev.entry_models.includes(key)
        ? prev.entry_models.filter((k) => k !== key)
        : [...prev.entry_models, key],
    }));
  };

  const toggleCheck = (key) => {
    setForm((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      // Build the strategy settings object
      const strategySettings = {
        strategy: form.strategy,
        // Entry models
        entry_models: form.entry_models,
        // Risk
        min_rr: form.min_rr,
        max_trades_per_kz: form.max_trades_per_kz,
        max_loss_per_trade: form.max_loss_per_trade,
        daily_profit_target: form.daily_profit_target,
        base_risk_pct: form.base_risk_pct,
        hard_close_time: form.hard_close_time,
        // Toggles
        midday_avoidance_enabled: form.midday_avoidance_enabled,
        holiday_rules_enabled: form.holiday_rules_enabled,
        // Preserve other form fields
        instrument: form.instrument,
        kill_zones: form.kill_zones,
        htf_timeframes: form.htf_timeframes,
        ltf_timeframes: form.ltf_timeframes,
        require_htf_bias: form.require_htf_bias,
        require_correct_zone: form.require_correct_zone,
        require_liquidity_sweep: form.require_liquidity_sweep,
        require_displacement: form.require_displacement,
        require_pd_array: form.require_pd_array,
        skip_if_target_hit: form.skip_if_target_hit,
      };
      // Map frontend strategy key to backend key
      const strategyBackendKey = form.strategy === 'jadecap_ict' ? 'jadecap' : form.strategy;
      await api('/api/settings', {
        method: 'PUT',
        body: {
          strategy_config: JSON.stringify(strategySettings),
          strategy: strategyBackendKey,
        },
      });
      onSuccess('Strategy configuration saved');
    } catch (err) {
      onError(err.message || 'Failed to save strategy config');
    } finally {
      setSaving(false);
    }
  };

  const checkboxStyle = { accentColor: 'var(--accent)' };

  return (
    <Card>
      {/* Strategy Selector */}
      <div className="mb-6">
        <Label>Active Strategy</Label>
        <select
          value={form.strategy}
          onChange={(e) => {
            const key = e.target.value;
            const strat = STRATEGIES[key] || STRATEGIES.default;
            setForm((prev) => ({
              ...prev,
              strategy: key,
              entry_models: strat.entry_models.map((m) => m.key),
              kill_zones: strat.kill_zones.map((k) => k.key),
              instrument: strat.instruments[0] || '',
              ...strat.risk_defaults,
            }));
            if (onSwitch) onSwitch(key);
            // Auto-save strategy key immediately so the runner picks it up
            const backendKey = key === 'jadecap_ict' ? 'jadecap' : key;
            api('/api/settings', { method: 'PUT', body: { strategy: backendKey } }).catch(() => {});
          }}
          className={inputClass}
          style={inputStyle}
        >
          {Object.entries(STRATEGIES).map(([key, strat]) => (
            <option key={key} value={key}>{strat.name}</option>
          ))}
        </select>
        <p className="text-xs mt-1.5" style={{ color: 'var(--text-secondary)' }}>
          {activeStrategy.description}
        </p>
      </div>

      {/* ====== Section 1: Entry Models ====== */}
      {isJadeCap && activeStrategy.entry_models?.length > 0 && (
        <StrategySubSection title="Entry Models" defaultOpen={true}>
          <p className="text-xs mb-3" style={{ color: 'var(--text-secondary)', opacity: 0.7 }}>
            Select which ICT entry setups the agents should look for.
          </p>
          <div className="space-y-2">
            {activeStrategy.entry_models.map(({ key, label, desc }) => (
              <label
                key={key}
                className="flex items-start gap-3 px-3 py-2.5 rounded-lg border cursor-pointer transition-colors"
                style={{
                  borderColor: form.entry_models.includes(key) ? 'var(--accent)' : 'var(--border)',
                  backgroundColor: form.entry_models.includes(key)
                    ? 'color-mix(in srgb, var(--accent) 8%, var(--bg-secondary))'
                    : 'var(--bg-primary)',
                }}
              >
                <input
                  type="checkbox"
                  checked={form.entry_models.includes(key)}
                  onChange={() => toggleEntry(key)}
                  className="mt-0.5"
                  style={checkboxStyle}
                />
                <div>
                  <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{label}</span>
                  <span className="text-xs ml-2" style={{ color: 'var(--text-secondary)' }}>{desc}</span>
                </div>
              </label>
            ))}
          </div>
        </StrategySubSection>
      )}

      {/* ====== Section 2: Risk Parameters ====== */}
      {isJadeCap && (
        <StrategySubSection title="Risk Parameters" defaultOpen={true}>
          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-1.5">
              <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>Min R:R</span>
              <select
                value={form.min_rr}
                onChange={(e) => setForm((p) => ({ ...p, min_rr: Number(e.target.value) }))}
                className={inputClass} style={inputStyle}
              >
                <option value={1.5}>1.5R</option>
                <option value={2}>2.0R (Recommended)</option>
                <option value={2.5}>2.5R</option>
                <option value={3}>3.0R</option>
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>Max Trades per Kill Zone</span>
              <select
                value={form.max_trades_per_kz}
                onChange={(e) => setForm((p) => ({ ...p, max_trades_per_kz: Number(e.target.value) }))}
                className={inputClass} style={inputStyle}
              >
                <option value={1}>1 trade (JadeCap rule)</option>
                <option value={2}>2 trades</option>
                <option value={3}>3 trades</option>
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>Max Loss per Trade ($)</span>
              <select
                value={form.max_loss_per_trade || 500}
                onChange={(e) => setForm((p) => ({ ...p, max_loss_per_trade: Number(e.target.value) }))}
                className={inputClass} style={inputStyle}
              >
                <option value={200}>$200</option>
                <option value={300}>$300</option>
                <option value={400}>$400</option>
                <option value={500}>$500 (Recommended)</option>
                <option value={750}>$750</option>
                <option value={1000}>$1,000</option>
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>Daily Profit Target ($)</span>
              <select
                value={form.daily_profit_target || 1000}
                onChange={(e) => setForm((p) => ({ ...p, daily_profit_target: Number(e.target.value) }))}
                className={inputClass} style={inputStyle}
              >
                <option value={500}>$500</option>
                <option value={750}>$750</option>
                <option value={1000}>$1,000 (Recommended)</option>
                <option value={1500}>$1,500</option>
                <option value={2000}>$2,000</option>
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>Hard Close Time (EST)</span>
              <select
                value={form.hard_close_time}
                onChange={(e) => setForm((p) => ({ ...p, hard_close_time: e.target.value }))}
                className={inputClass} style={inputStyle}
              >
                <option value="15:30">3:30 PM</option>
                <option value="16:00">4:00 PM (JadeCap rule)</option>
                <option value="16:15">4:15 PM</option>
              </select>
            </div>
          </div>
        </StrategySubSection>
      )}

      {/* ====== Section 3: Midday Avoidance ====== */}
      {isJadeCap && (
        <StrategySubSection title="Midday Avoidance">
          <div className="flex items-center justify-between mb-3">
            <div>
              <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                11:30 AM - 1:00 PM EST
              </span>
              <span className="block text-xs" style={{ color: 'var(--text-secondary)' }}>
                Chop zone -- no new entries during this window
              </span>
            </div>
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <span className="text-xs" style={{ color: form.midday_avoidance_enabled ? 'var(--accent)' : 'var(--text-secondary)' }}>
                {form.midday_avoidance_enabled ? 'ON' : 'OFF'}
              </span>
              <input
                type="checkbox"
                checked={form.midday_avoidance_enabled}
                onChange={() => setForm((p) => ({ ...p, midday_avoidance_enabled: !p.midday_avoidance_enabled }))}
                className="w-4 h-4"
                style={checkboxStyle}
              />
            </label>
          </div>
          <p className="text-xs" style={{ color: 'var(--text-secondary)', opacity: 0.7 }}>
            When OFF, the midday chop zone rule is relaxed and agents may propose entries during 11:30 AM - 1:00 PM.
          </p>
        </StrategySubSection>
      )}

      {/* ====== Section 7: Holiday Rules ====== */}
      {isJadeCap && (
        <StrategySubSection title="Holiday Rules">
          <div className="flex items-center justify-between mb-3">
            <div>
              <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                Low-Volume Day Avoidance
              </span>
              <span className="block text-xs" style={{ color: 'var(--text-secondary)' }}>
                SFPs become unreliable on low-volume days
              </span>
            </div>
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <span className="text-xs" style={{ color: form.holiday_rules_enabled ? 'var(--accent)' : 'var(--text-secondary)' }}>
                {form.holiday_rules_enabled ? 'ON' : 'OFF'}
              </span>
              <input
                type="checkbox"
                checked={form.holiday_rules_enabled}
                onChange={() => setForm((p) => ({ ...p, holiday_rules_enabled: !p.holiday_rules_enabled }))}
                className="w-4 h-4"
                style={checkboxStyle}
              />
            </label>
          </div>
          <div className="flex flex-wrap gap-2 mb-2">
            {[
              'Thanksgiving Day', 'Black Friday', 'Christmas Eve',
              "New Year's Eve", 'July 4th', 'Good Friday',
              'MLK Day', 'Presidents Day',
            ].map((h) => (
              <span
                key={h}
                className="text-xs px-2 py-1 rounded-full border"
                style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)', backgroundColor: 'var(--bg-primary)' }}
              >
                {h}
              </span>
            ))}
          </div>
          <p className="text-xs" style={{ color: 'var(--text-secondary)', opacity: 0.7 }}>
            When OFF, holiday low-volume warnings are disabled.
          </p>
        </StrategySubSection>
      )}

      {/* ====== Section 8: Kill Zones (toggleable) ====== */}
      {isJadeCap && (
        <StrategySubSection title="Kill Zones" defaultOpen={true}>
          <p className="text-xs mb-3" style={{ color: 'var(--text-secondary)', opacity: 0.7 }}>
            Toggle which trading windows are active. Disabled windows = agent outputs NO TRADE for that window.
          </p>
          <div className="grid grid-cols-2 gap-2">
            {[
              { key: 'am', label: 'AM Kill Zone', time: '9:30 – 11:30 AM EST', primary: true,
                onDesc: 'Agent looks for ICT setups during morning session — highest volume window',
                offDesc: 'Morning session blocked — any AM setup outputs NO TRADE' },
              { key: 'silver1', label: 'Silver Bullet AM', time: '10:00 – 11:00 AM EST', primary: true,
                onDesc: 'FVGs forming 10-11 AM flagged as HIGHEST PROBABILITY — JadeCap\'s best window',
                offDesc: '10-11 AM FVGs treated as regular, not flagged as highest probability' },
              { key: 'pm', label: 'PM Kill Zone', time: '1:00 – 4:00 PM EST', primary: false,
                onDesc: 'Agent looks for setups in afternoon session — continuation or reversal plays',
                offDesc: 'Afternoon session blocked — done trading after AM window' },
              { key: 'silver2', label: 'Silver Bullet PM', time: '2:00 – 3:00 PM EST', primary: false,
                onDesc: 'FVGs forming 2-3 PM flagged as high probability — secondary execution window',
                offDesc: '2-3 PM FVGs treated as regular, not flagged as high probability' },
            ].map(({ key, label, time, primary, onDesc, offDesc }) => {
              const active = form.kill_zones.includes(key);
              return (
                <label
                  key={key}
                  className="flex items-start gap-3 px-3 py-2.5 rounded-lg border cursor-pointer transition-colors"
                  style={{
                    borderColor: active ? 'var(--accent)' : 'var(--border)',
                    backgroundColor: active
                      ? 'color-mix(in srgb, var(--accent) 6%, var(--bg-primary))'
                      : 'var(--bg-primary)',
                  }}
                >
                  <input
                    type="checkbox"
                    checked={active}
                    onChange={() =>
                      setForm((prev) => ({
                        ...prev,
                        kill_zones: active
                          ? prev.kill_zones.filter((k) => k !== key)
                          : [...prev.kill_zones, key],
                      }))
                    }
                    className="mt-1 accent-[var(--accent)]"
                  />
                  <div>
                    <span className="text-sm font-medium" style={{ color: active ? 'var(--text-primary)' : 'var(--text-secondary)' }}>
                      {label}
                      {primary && (
                        <span
                          className="text-xs ml-1.5 px-1.5 py-0.5 rounded"
                          style={{ backgroundColor: 'color-mix(in srgb, var(--accent) 15%, transparent)', color: 'var(--accent)' }}
                        >
                          PRIMARY
                        </span>
                      )}
                    </span>
                    <span className="block text-xs" style={{ color: 'var(--text-secondary)', fontFamily: 'monospace' }}>
                      {time}
                    </span>
                    <span className="block text-xs mt-1" style={{ color: active ? 'var(--success, #22c55e)' : 'var(--text-secondary)', opacity: active ? 0.8 : 0.5 }}>
                      {active ? onDesc : offDesc}
                    </span>
                  </div>
                </label>
              );
            })}
          </div>
          <p className="text-xs mt-2" style={{ color: 'var(--text-secondary)', opacity: 0.5 }}>
            Turning off a Kill Zone means the agent cannot trade during that window.
          </p>
        </StrategySubSection>
      )}

      <div className="mt-2">
        <PrimaryButton onClick={handleSave} disabled={saving}>
          {saving ? 'Saving...' : 'Save Strategy Config'}
        </PrimaryButton>
      </div>
    </Card>
  );
}

/* ---------- 1c. Data Providers ---------- */

const DATA_CATEGORIES = [
  { key: 'core_stock_apis', label: 'Stock Price Data (OHLCV)', description: 'Price history, candles, volume' },
  { key: 'technical_indicators', label: 'Technical Indicators', description: 'RSI, MACD, Bollinger Bands, etc.' },
  { key: 'fundamental_data', label: 'Fundamental Data', description: 'Balance sheet, cash flow, financials' },
  { key: 'news_data', label: 'News Data', description: 'Company news, macro news, insider transactions' },
];

const VENDOR_OPTIONS_BY_CATEGORY = {
  core_stock_apis: [
    { value: 'yfinance', label: 'Yahoo Finance', description: 'Free, no API key needed' },
    { value: 'alpha_vantage', label: 'Alpha Vantage', description: 'Higher quality, requires API key' },
    { value: 'databento', label: 'Databento', description: 'Professional futures/equities data (NQ, ES, etc.)' },
  ],
  technical_indicators: [
    { value: 'yfinance', label: 'Yahoo Finance', description: 'Free, no API key needed' },
    { value: 'alpha_vantage', label: 'Alpha Vantage', description: 'Higher quality, requires API key' },
    { value: 'databento', label: 'Databento', description: 'Professional futures/equities data (NQ, ES, etc.)' },
  ],
  fundamental_data: [
    { value: 'yfinance', label: 'Yahoo Finance', description: 'Free, no API key needed' },
    { value: 'alpha_vantage', label: 'Alpha Vantage', description: 'Higher quality, requires API key' },
  ],
  news_data: [
    { value: 'yfinance', label: 'Yahoo Finance', description: 'Free, no API key needed' },
    { value: 'alpha_vantage', label: 'Alpha Vantage', description: 'Higher quality, requires API key' },
  ],
};

function DataProvidersSection({ onError, onSuccess }) {
  const [vendors, setVendors] = useState({
    core_stock_apis: 'yfinance',
    technical_indicators: 'yfinance',
    fundamental_data: 'yfinance',
    news_data: 'yfinance',
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api('/api/settings')
      .then((data) => {
        if (data.data_vendors) {
          try {
            const parsed = typeof data.data_vendors === 'string' ? JSON.parse(data.data_vendors) : data.data_vendors;
            setVendors((prev) => ({ ...prev, ...parsed }));
          } catch {}
        }
      })
      .catch(() => {});
  }, []);

  const updateVendor = (key, value) => {
    setVendors((prev) => ({ ...prev, [key]: value }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await api('/api/settings', {
        method: 'PUT',
        body: { data_vendors: JSON.stringify(vendors) },
      });
      onSuccess('Data providers saved');
    } catch (err) {
      onError(err.message || 'Failed to save data providers');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <p className="text-sm mb-4" style={{ color: 'var(--text-secondary)' }}>
        Choose where each type of market data comes from. You can mix providers per category.
      </p>

      <div className="space-y-4">
        {DATA_CATEGORIES.map(({ key, label, description }) => (
          <div key={key} className="flex flex-col gap-1.5">
            <Label>{label}</Label>
            <p className="text-xs" style={{ color: 'var(--text-secondary)', opacity: 0.7 }}>
              {description}
            </p>
            <select
              value={vendors[key]}
              onChange={(e) => updateVendor(key, e.target.value)}
              className={inputClass}
              style={inputStyle}
            >
              {(VENDOR_OPTIONS_BY_CATEGORY[key] || []).map(({ value, label: vLabel, description: vDesc }) => (
                <option key={value} value={value}>
                  {vLabel} — {vDesc}
                </option>
              ))}
            </select>
          </div>
        ))}

        {/* Databento info banner */}
        <div
          className="rounded-lg border p-4 mt-2"
          style={{
            borderColor: 'var(--accent)',
            backgroundColor: 'color-mix(in srgb, var(--accent) 8%, var(--bg-secondary))',
          }}
        >
          <p className="text-sm font-medium" style={{ color: 'var(--accent)' }}>
            Databento Integration
          </p>
          <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
            Databento provides professional-grade futures and equities data (NQ, ES, CL, etc.) via their{' '}
            <a
              href="https://databento.com/docs/api-reference-live"
              target="_blank"
              rel="noopener noreferrer"
              className="underline"
              style={{ color: 'var(--accent)' }}
            >
              Live API
            </a>
            . Once integrated, select it as the provider for Stock Price Data and Technical Indicators.
            Requires a <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--bg-secondary)' }}>DATABENTO_API_KEY</code>.
          </p>
        </div>

        {/* Fallback chain info */}
        <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
          If a provider fails (e.g., rate limit), the system automatically falls back to other available providers.
        </p>
      </div>

      <div className="mt-6">
        <PrimaryButton onClick={handleSave} disabled={saving}>
          {saving ? 'Saving...' : 'Save Data Providers'}
        </PrimaryButton>
      </div>
    </Card>
  );
}

/* ---------- 2. API Keys ---------- */

function ApiKeysSection({ onError, onSuccess }) {
  const [keys, setKeys] = useState(() =>
    Object.fromEntries(API_KEYS.map(({ key }) => [key, '']))
  );
  const [status, setStatus] = useState({});
  const [visible, setVisible] = useState({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api('/api/keys/status')
      .then((data) => setStatus(data))
      .catch(() => {});
  }, []);

  const updateKey = (name, value) => setKeys((prev) => ({ ...prev, [name]: value }));

  const toggleVisible = (name) =>
    setVisible((prev) => ({ ...prev, [name]: !prev[name] }));

  const handleSave = async () => {
    setSaving(true);
    try {
      // Only send non-empty keys
      const payload = Object.fromEntries(
        Object.entries(keys).filter(([, v]) => v.trim() !== '')
      );
      await api('/api/keys', { method: 'PUT', body: payload });
      // Refresh status
      const newStatus = await api('/api/keys/status');
      setStatus(newStatus);
      // Clear inputs after save
      setKeys(Object.fromEntries(API_KEYS.map(({ key }) => [key, ''])));
      onSuccess('API keys saved.');
    } catch (err) {
      onError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <div className="space-y-3">
        {API_KEYS.map(({ key, label }) => (
          <div key={key} className="flex items-center gap-3">
            {/* Status dot */}
            <span
              className="h-2.5 w-2.5 rounded-full flex-shrink-0"
              style={{
                backgroundColor: status[key] ? 'var(--success)' : 'var(--danger)',
              }}
              title={status[key] ? 'Set' : 'Not set'}
            />

            {/* Label */}
            <span
              className="text-sm font-medium w-36 flex-shrink-0"
              style={{ color: 'var(--text-primary)' }}
            >
              {label}
            </span>

            {/* Input */}
            <div className="relative flex-1">
              <input
                type={visible[key] ? 'text' : 'password'}
                placeholder={status[key] ? '********' : 'Not set'}
                value={keys[key]}
                onChange={(e) => updateKey(key, e.target.value)}
                className={inputClass}
                style={inputStyle}
              />
              <button
                type="button"
                onClick={() => toggleVisible(key)}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded transition-colors hover:opacity-70"
                style={{ color: 'var(--text-secondary)' }}
                title={visible[key] ? 'Hide' : 'Show'}
              >
                {visible[key] ? (
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M3.707 2.293a1 1 0 00-1.414 1.414l14 14a1 1 0 001.414-1.414l-1.473-1.473A10.014 10.014 0 0019.542 10C18.268 5.943 14.478 3 10 3a9.958 9.958 0 00-4.512 1.074l-1.78-1.781zm4.261 4.26l1.514 1.515a2.003 2.003 0 012.45 2.45l1.514 1.514a4 4 0 00-5.478-5.478z" clipRule="evenodd" />
                    <path d="M12.454 16.697L9.75 13.992a4 4 0 01-3.742-3.741L2.335 6.578A9.98 9.98 0 00.458 10c1.274 4.057 5.065 7 9.542 7 .847 0 1.669-.105 2.454-.303z" />
                  </svg>
                ) : (
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                    <path d="M10 12a2 2 0 100-4 2 2 0 000 4z" />
                    <path fillRule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clipRule="evenodd" />
                  </svg>
                )}
              </button>
            </div>
          </div>
        ))}
      </div>

      <p className="text-xs mt-4" style={{ color: 'var(--text-secondary)' }}>
        Keys are stored in your .env file, never in the database.
      </p>

      <div className="mt-4">
        <PrimaryButton onClick={handleSave} disabled={saving}>
          {saving ? 'Saving...' : 'Save Keys'}
        </PrimaryButton>
      </div>
    </Card>
  );
}

/* ---------- 3. Theme ---------- */

function ThemeSection({ theme, setTheme }) {
  const options = [
    { value: 'dark', label: 'Dark' },
    { value: 'light', label: 'Light' },
    { value: 'system', label: 'System' },
  ];

  return (
    <Card title="Theme">
      <div className="flex gap-4">
        {options.map(({ value, label }) => (
          <label
            key={value}
            className="flex items-center gap-2 text-sm cursor-pointer select-none"
            style={{ color: 'var(--text-primary)' }}
          >
            <input
              type="radio"
              name="theme"
              value={value}
              checked={theme === value}
              onChange={() => setTheme(value)}
              style={{ accentColor: 'var(--accent)' }}
            />
            {label}
          </label>
        ))}
      </div>
      <p className="text-xs mt-3" style={{ color: 'var(--text-secondary)' }}>
        Changes apply immediately. &quot;System&quot; follows your OS preference.
      </p>
    </Card>
  );
}

/* ---------- 4. Data Management ---------- */

function DataManagementSection({ onError, onSuccess }) {
  const [cacheSize, setCacheSize] = useState(null);
  const [totalRuns, setTotalRuns] = useState(null);
  const [clearing, setClearing] = useState(false);
  const importRef = useRef(null);

  const fetchCacheSize = useCallback(async () => {
    try {
      const data = await api('/api/cache/size');
      setCacheSize(data.size_mb != null ? `${data.size_mb} MB` : data.size || 'Unknown');
    } catch {
      setCacheSize('Unknown');
    }
  }, []);

  const fetchRunCount = useCallback(async () => {
    try {
      const data = await api('/api/runs?page=1&per_page=1');
      setTotalRuns(data.total ?? null);
    } catch {
      setTotalRuns(null);
    }
  }, []);

  useEffect(() => {
    fetchCacheSize();
    fetchRunCount();
  }, [fetchCacheSize, fetchRunCount]);

  const handleClearCache = async () => {
    setClearing(true);
    try {
      await api('/api/cache', { method: 'DELETE' });
      await fetchCacheSize();
      onSuccess('Cache cleared successfully.');
    } catch (err) {
      onError(err.message);
    } finally {
      setClearing(false);
    }
  };

  const handleExportAll = async () => {
    try {
      const data = await api('/api/runs?page=1&per_page=10000');
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `tradingagents-export-${new Date().toISOString().split('T')[0]}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      onSuccess('Data exported successfully.');
    } catch (err) {
      onError(err.message);
    }
  };

  const handleImport = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      const data = JSON.parse(text);
      await api('/api/runs/import', { method: 'POST', body: data });
      await fetchRunCount();
      onSuccess('Data imported successfully.');
    } catch (err) {
      onError(err.message || 'Failed to import data.');
    }
    if (importRef.current) importRef.current.value = '';
  };

  return (
    <Card title="Data Management">
      <div className="space-y-4">
        {/* Cache */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
              Data cache: {cacheSize ?? '...'}
            </p>
          </div>
          <DangerButton onClick={handleClearCache} disabled={clearing}>
            {clearing ? 'Clearing...' : 'Clear Cache'}
          </DangerButton>
        </div>

        {/* Runs stats */}
        {totalRuns != null && (
          <div>
            <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
              Total runs: <span style={{ color: 'var(--text-primary)' }}>{totalRuns}</span>
            </p>
          </div>
        )}

        {/* Export / Import */}
        <div
          className="flex flex-wrap gap-3 pt-4 border-t"
          style={{ borderColor: 'var(--border)' }}
        >
          <button
            type="button"
            onClick={handleExportAll}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
            style={{
              color: 'var(--accent)',
              backgroundColor: 'color-mix(in srgb, var(--accent) 10%, transparent)',
            }}
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clipRule="evenodd" />
            </svg>
            Export All Data
          </button>

          <label
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer"
            style={{
              color: 'var(--accent)',
              backgroundColor: 'color-mix(in srgb, var(--accent) 10%, transparent)',
            }}
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zM6.293 6.707a1 1 0 010-1.414l3-3a1 1 0 011.414 0l3 3a1 1 0 01-1.414 1.414L11 5.414V13a1 1 0 11-2 0V5.414L7.707 6.707a1 1 0 01-1.414 0z" clipRule="evenodd" />
            </svg>
            Import Data
            <input
              ref={importRef}
              type="file"
              accept=".json"
              onChange={handleImport}
              className="hidden"
            />
          </label>
        </div>
      </div>
    </Card>
  );
}

/* ---------- 5. About ---------- */

function AboutSection() {
  return (
    <Card title="About">
      <p className="text-sm" style={{ color: 'var(--text-primary)' }}>
        <span className="font-semibold">TradingAgents</span> v0.2.2
      </p>
      <a
        href="https://github.com/TauricResearch/TradingAgents"
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1.5 text-sm mt-2 transition-colors hover:underline"
        style={{ color: 'var(--accent)' }}
      >
        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
          <path fillRule="evenodd" d="M12.316 3.051a1 1 0 01.633 1.265l-4 12a1 1 0 11-1.898-.632l4-12a1 1 0 011.265-.633zM5.707 6.293a1 1 0 010 1.414L3.414 10l2.293 2.293a1 1 0 11-1.414 1.414l-3-3a1 1 0 010-1.414l3-3a1 1 0 011.414 0zm8.586 0a1 1 0 011.414 0l3 3a1 1 0 010 1.414l-3 3a1 1 0 11-1.414-1.414L16.586 10l-2.293-2.293a1 1 0 010-1.414z" clipRule="evenodd" />
        </svg>
        View on GitHub
      </a>
    </Card>
  );
}
