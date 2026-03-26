import { useState, useEffect } from 'react';
import { api } from '../hooks/useApi';

const PROVIDERS = ['openai', 'anthropic', 'google', 'deepseek', 'xai', 'ollama', 'openrouter'];

const ANALYSTS = [
  { key: 'market', label: 'Market Analyst' },
  { key: 'social', label: 'Social Analyst' },
  { key: 'news', label: 'News Analyst' },
  { key: 'fundamentals', label: 'Fundamentals Analyst' },
];

const SHOW_BACKEND_URL = new Set(['ollama', 'openrouter', 'xai']);

function todayStr() {
  return new Date().toISOString().split('T')[0];
}

export default function RunForm({ onSubmit, defaults: defaultsProp, disabled }) {
  const [configData, setConfigData] = useState({ deep_models: {}, quick_models: {} });

  // Fetch available models from backend
  useEffect(() => {
    api('/api/config')
      .then((data) => setConfigData(data))
      .catch(() => {});
  }, []);

  const [form, setForm] = useState({
    ticker: '',
    trade_date: todayStr(),
    provider: 'openai',
    quick_model: '',
    deep_model: '',
    effort: '',
    backend_url: '',
    max_debate_rounds: 1,
    max_risk_rounds: 1,
    analysts: ['market', 'social', 'news', 'fundamentals'],
  });

  // Fetch defaults from settings on mount
  useEffect(() => {
    api('/api/settings')
      .then((data) => {
        setForm((prev) => ({
          ...prev,
          provider: data.provider || prev.provider,
          quick_model: data.quick_model || '',
          deep_model: data.deep_model || '',
          effort: data.effort || '',
          backend_url: data.backend_url || '',
          max_debate_rounds: data.max_debate_rounds ?? prev.max_debate_rounds,
          max_risk_rounds: data.max_risk_rounds ?? prev.max_risk_rounds,
          analysts: data.analysts?.length ? data.analysts : prev.analysts,
        }));
      })
      .catch(() => {
        // Silently ignore -- use local defaults
      });
  }, []);

  // Merge passed defaults prop
  useEffect(() => {
    if (defaultsProp) {
      setForm((prev) => ({ ...prev, ...defaultsProp }));
    }
  }, [defaultsProp]);

  const update = (field, value) => setForm((prev) => ({ ...prev, [field]: value }));

  const toggleAnalyst = (key) => {
    setForm((prev) => {
      const next = prev.analysts.includes(key)
        ? prev.analysts.filter((a) => a !== key)
        : [...prev.analysts, key];
      return { ...next.length ? { ...prev, analysts: next } : prev };
    });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!form.ticker.trim()) return;
    if (form.analysts.length === 0) return;
    onSubmit(form);
  };

  const quickModels = configData.quick_models?.[form.provider] || [];
  const deepModels = configData.deep_models?.[form.provider] || [];

  // Auto-select first model when provider changes and current selection isn't in the list
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

  return (
    <form onSubmit={handleSubmit}>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Ticker */}
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
            Ticker <span style={{ color: 'var(--danger)' }}>*</span>
          </label>
          <input
            type="text"
            required
            placeholder="AAPL"
            value={form.ticker}
            onChange={(e) => update('ticker', e.target.value.toUpperCase())}
            className="px-3 py-2 rounded-lg text-sm border outline-none transition-colors focus:ring-2"
            style={{
              backgroundColor: 'var(--bg-secondary)',
              borderColor: 'var(--border)',
              color: 'var(--text-primary)',
              '--tw-ring-color': 'var(--accent)',
            }}
          />
        </div>

        {/* Trade Date */}
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
            Trade Date
          </label>
          <input
            type="date"
            value={form.trade_date}
            onChange={(e) => update('trade_date', e.target.value)}
            className="px-3 py-2 rounded-lg text-sm border outline-none transition-colors focus:ring-2"
            style={{
              backgroundColor: 'var(--bg-secondary)',
              borderColor: 'var(--border)',
              color: 'var(--text-primary)',
              '--tw-ring-color': 'var(--accent)',
            }}
          />
        </div>

        {/* Provider */}
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
            Provider
          </label>
          <select
            value={form.provider}
            onChange={(e) => update('provider', e.target.value)}
            className="px-3 py-2 rounded-lg text-sm border outline-none transition-colors focus:ring-2"
            style={{
              backgroundColor: 'var(--bg-secondary)',
              borderColor: 'var(--border)',
              color: 'var(--text-primary)',
              '--tw-ring-color': 'var(--accent)',
            }}
          >
            {PROVIDERS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>

        {/* Quick Model */}
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
            Quick Model
          </label>
          <select
            value={form.quick_model}
            onChange={(e) => update('quick_model', e.target.value)}
            className="px-3 py-2 rounded-lg text-sm border outline-none transition-colors focus:ring-2"
            style={{
              backgroundColor: 'var(--bg-secondary)',
              borderColor: 'var(--border)',
              color: 'var(--text-primary)',
              '--tw-ring-color': 'var(--accent)',
            }}
          >
            {quickModels.length === 0 && <option value="">Loading models...</option>}
            {quickModels.map((m) => (
              <option key={m.value} value={m.value}>{m.label}</option>
            ))}
          </select>
        </div>

        {/* Deep Model */}
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
            Deep Model
          </label>
          <select
            value={form.deep_model}
            onChange={(e) => update('deep_model', e.target.value)}
            className="px-3 py-2 rounded-lg text-sm border outline-none transition-colors focus:ring-2"
            style={{
              backgroundColor: 'var(--bg-secondary)',
              borderColor: 'var(--border)',
              color: 'var(--text-primary)',
              '--tw-ring-color': 'var(--accent)',
            }}
          >
            {deepModels.length === 0 && <option value="">Loading models...</option>}
            {deepModels.map((m) => (
              <option key={m.value} value={m.value}>{m.label}</option>
            ))}
          </select>
        </div>

        {/* Effort */}
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
            Effort
          </label>
          <select
            value={form.effort}
            onChange={(e) => update('effort', e.target.value)}
            className="px-3 py-2 rounded-lg text-sm border outline-none transition-colors focus:ring-2"
            style={{
              backgroundColor: 'var(--bg-secondary)',
              borderColor: 'var(--border)',
              color: 'var(--text-primary)',
              '--tw-ring-color': 'var(--accent)',
            }}
          >
            <option value="">None</option>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
          </select>
        </div>

        {/* Backend URL -- only for ollama / openrouter / xai */}
        {SHOW_BACKEND_URL.has(form.provider) && (
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
              Backend URL
            </label>
            <input
              type="text"
              placeholder="http://localhost:11434"
              value={form.backend_url}
              onChange={(e) => update('backend_url', e.target.value)}
              className="px-3 py-2 rounded-lg text-sm border outline-none transition-colors focus:ring-2"
              style={{
                backgroundColor: 'var(--bg-secondary)',
                borderColor: 'var(--border)',
                color: 'var(--text-primary)',
                '--tw-ring-color': 'var(--accent)',
              }}
            />
          </div>
        )}

        {/* Research Depth */}
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
            Research Depth
          </label>
          <select
            value={form.max_debate_rounds}
            onChange={(e) => {
              const v = Number(e.target.value);
              setForm((prev) => ({ ...prev, max_debate_rounds: v, max_risk_rounds: v }));
            }}
            className="px-3 py-2 rounded-lg text-sm border outline-none transition-colors focus:ring-2"
            style={{
              backgroundColor: 'var(--bg-secondary)',
              borderColor: 'var(--border)',
              color: 'var(--text-primary)',
              '--tw-ring-color': 'var(--accent)',
            }}
          >
            <option value={1}>Shallow - Quick research, few debate rounds</option>
            <option value={3}>Medium - Moderate debate and strategy discussion</option>
            <option value={5}>Deep - Comprehensive, in-depth debate</option>
          </select>
        </div>
      </div>

      {/* Analysts checkboxes */}
      <div className="mt-4">
        <label className="text-sm font-medium block mb-2" style={{ color: 'var(--text-secondary)' }}>
          Selected Analysts <span style={{ color: 'var(--danger)' }}>*</span>
        </label>
        <div className="flex flex-wrap gap-4">
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
        {form.analysts.length === 0 && (
          <p className="text-xs mt-1" style={{ color: 'var(--danger)' }}>
            At least one analyst is required.
          </p>
        )}
      </div>

      {/* Submit */}
      <div className="mt-5">
        <button
          type="submit"
          disabled={disabled || !form.ticker.trim() || form.analysts.length === 0}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          style={{
            backgroundColor: disabled ? 'var(--text-secondary)' : 'var(--accent)',
          }}
          onMouseEnter={(e) => {
            if (!disabled) e.currentTarget.style.backgroundColor = 'var(--accent-hover)';
          }}
          onMouseLeave={(e) => {
            if (!disabled) e.currentTarget.style.backgroundColor = 'var(--accent)';
          }}
        >
          <span>&#9654;</span>
          Run Analysis
        </button>
      </div>
    </form>
  );
}
