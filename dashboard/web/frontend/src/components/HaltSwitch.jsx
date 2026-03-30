import { api } from '../hooks/useApi';

export default function HaltSwitch({ halted, onToggle }) {
  const handleToggle = async () => {
    try {
      await api('/api/trading/halt', { method: 'PUT', body: { halt: !halted } });
      onToggle(!halted);
    } catch (err) {
      console.error('Halt toggle failed:', err);
    }
  };

  return (
    <button
      onClick={handleToggle}
      className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all"
      style={{
        backgroundColor: halted
          ? 'color-mix(in srgb, var(--danger) 15%, transparent)'
          : 'color-mix(in srgb, var(--success) 15%, transparent)',
        color: halted ? 'var(--danger)' : 'var(--success)',
        border: `1px solid ${halted ? 'var(--danger)' : 'var(--success)'}`,
      }}
    >
      <span className="w-2 h-2 rounded-full" style={{ backgroundColor: halted ? 'var(--danger)' : 'var(--success)' }} />
      {halted ? 'HALTED — Click to Resume' : 'ACTIVE — Click to Halt'}
    </button>
  );
}
