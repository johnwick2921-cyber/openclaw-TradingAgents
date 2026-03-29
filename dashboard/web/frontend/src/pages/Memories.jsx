import { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '../hooks/useApi';
import MemoryExplorer from '../components/MemoryExplorer';
import ErrorBanner from '../components/ErrorBanner';

const AGENTS = [
  { value: 'bull', label: 'Bull Researcher' },
  { value: 'bear', label: 'Bear Researcher' },
  { value: 'trader', label: 'Trader' },
  { value: 'invest_judge', label: 'Investment Judge' },
  { value: 'portfolio_manager', label: 'Portfolio Manager' },
];

export default function Memories() {
  const [agent, setAgent] = useState('bull');
  const [memories, setMemories] = useState([]);
  const [counts, setCounts] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');
  const [confirmClear, setConfirmClear] = useState(false);
  const [successMsg, setSuccessMsg] = useState(null);
  const importRef = useRef(null);
  const searchTimer = useRef(null);

  // Fetch memory counts for all agents
  const fetchCounts = useCallback(async () => {
    const newCounts = {};
    await Promise.all(
      AGENTS.map(async ({ value }) => {
        try {
          const data = await api(`/api/memories/${value}`);
          const list = data?.memories || data;
          newCounts[value] = Array.isArray(list) ? list.length : (data?.count || 0);
        } catch {
          newCounts[value] = 0;
        }
      })
    );
    setCounts(newCounts);
  }, []);

  // Fetch memories for the selected agent
  const fetchMemories = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api(`/api/memories/${agent}`);
      const mlist = data?.memories || data;
      setMemories(Array.isArray(mlist) ? mlist : []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [agent]);

  // Search memories
  const searchMemories = useCallback(
    async (query) => {
      if (!query.trim()) {
        fetchMemories();
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const data = await api(`/api/memories/${agent}/search?q=${encodeURIComponent(query)}`);
        const mlist = data?.memories || data;
      setMemories(Array.isArray(mlist) ? mlist : []);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    },
    [agent, fetchMemories]
  );

  useEffect(() => {
    fetchMemories();
    fetchCounts();
  }, [fetchMemories, fetchCounts]);

  // Debounced search
  const handleSearchChange = (value) => {
    setSearch(value);
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => {
      searchMemories(value);
    }, 400);
  };

  // Delete a single memory
  const handleDelete = async (id) => {
    try {
      await api(`/api/memories/${agent}/${id}`, { method: 'DELETE' });
      setMemories((prev) => prev.filter((m) => m.id !== id));
      setCounts((prev) => ({ ...prev, [agent]: Math.max(0, (prev[agent] || 1) - 1) }));
    } catch (err) {
      setError(err.message);
    }
  };

  // Clear all memories for the selected agent
  const handleClearAll = async () => {
    if (!confirmClear) {
      setConfirmClear(true);
      return;
    }
    try {
      await api(`/api/memories/${agent}`, { method: 'DELETE' });
      setMemories([]);
      setCounts((prev) => ({ ...prev, [agent]: 0 }));
      setConfirmClear(false);
      showSuccess('All memories cleared.');
    } catch (err) {
      setError(err.message);
      setConfirmClear(false);
    }
  };

  // Export memories
  const handleExport = async () => {
    try {
      const data = await api('/api/memories/export');
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `memories-export-${new Date().toISOString().split('T')[0]}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      showSuccess('Memories exported successfully.');
    } catch (err) {
      setError(err.message);
    }
  };

  // Import memories
  const handleImport = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      const data = JSON.parse(text);
      let importData = data;
      if (!data.memories && typeof data === 'object') {
        // Convert {bull: [...], bear: [...]} to {memories: [...flat]}
        const flat = [];
        for (const [agent, mems] of Object.entries(data)) {
          if (Array.isArray(mems)) {
            mems.forEach(m => flat.push({ ...m, agent_name: m.agent_name || agent }));
          }
        }
        importData = { memories: flat };
      }
      await api('/api/memories/import', { method: 'POST', body: importData });
      await fetchMemories();
      await fetchCounts();
      showSuccess('Memories imported successfully.');
    } catch (err) {
      setError(err.message || 'Failed to import memories.');
    }
    // Reset file input
    if (importRef.current) importRef.current.value = '';
  };

  const showSuccess = (msg) => {
    setSuccessMsg(msg);
    setTimeout(() => setSuccessMsg(null), 3000);
  };

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h2 className="text-2xl font-semibold" style={{ color: 'var(--text-primary)' }}>
          Memories
        </h2>
        <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
          Browse and manage agent memories from past analyses.
        </p>
      </div>

      {/* Banners */}
      {error && (
        <ErrorBanner message={error} type="error" onDismiss={() => setError(null)} />
      )}
      {successMsg && (
        <ErrorBanner message={successMsg} type="info" onDismiss={() => setSuccessMsg(null)} />
      )}

      {/* Controls bar */}
      <div
        className="rounded-xl border p-4"
        style={{ backgroundColor: 'var(--bg-primary)', borderColor: 'var(--border)' }}
      >
        <div className="flex flex-col sm:flex-row gap-3">
          {/* Agent selector */}
          <div className="flex flex-col gap-1.5 sm:w-56">
            <label className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
              Agent
            </label>
            <select
              value={agent}
              onChange={(e) => {
                setAgent(e.target.value);
                setSearch('');
                setConfirmClear(false);
              }}
              className="px-3 py-2 rounded-lg text-sm border outline-none transition-colors focus:ring-2"
              style={{
                backgroundColor: 'var(--bg-secondary)',
                borderColor: 'var(--border)',
                color: 'var(--text-primary)',
                '--tw-ring-color': 'var(--accent)',
              }}
            >
              {AGENTS.map(({ value, label }) => (
                <option key={value} value={value}>
                  {label} {counts[value] != null ? `(${counts[value]})` : ''}
                </option>
              ))}
            </select>
          </div>

          {/* Search bar */}
          <div className="flex flex-col gap-1.5 flex-1">
            <label className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
              Search
            </label>
            <div className="relative">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2"
                style={{ color: 'var(--text-secondary)' }}
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fillRule="evenodd"
                  d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z"
                  clipRule="evenodd"
                />
              </svg>
              <input
                type="text"
                placeholder="Filter memories by keyword..."
                value={search}
                onChange={(e) => handleSearchChange(e.target.value)}
                className="w-full pl-9 pr-3 py-2 rounded-lg text-sm border outline-none transition-colors focus:ring-2"
                style={{
                  backgroundColor: 'var(--bg-secondary)',
                  borderColor: 'var(--border)',
                  color: 'var(--text-primary)',
                  '--tw-ring-color': 'var(--accent)',
                }}
              />
            </div>
          </div>
        </div>

        {/* Action bar */}
        <div className="flex flex-wrap gap-2 mt-4 pt-4 border-t" style={{ borderColor: 'var(--border)' }}>
          {/* Clear All */}
          <button
            onClick={handleClearAll}
            disabled={memories.length === 0 && !confirmClear}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            style={{
              color: confirmClear ? '#fff' : 'var(--danger)',
              backgroundColor: confirmClear
                ? 'var(--danger)'
                : 'color-mix(in srgb, var(--danger) 10%, transparent)',
            }}
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
            {confirmClear ? 'Are you sure? This cannot be undone.' : 'Clear All'}
          </button>

          {/* Export */}
          <button
            onClick={handleExport}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
            style={{
              color: 'var(--accent)',
              backgroundColor: 'color-mix(in srgb, var(--accent) 10%, transparent)',
            }}
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clipRule="evenodd" />
            </svg>
            Export
          </button>

          {/* Import */}
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
            Import
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

      {/* Memory Explorer */}
      <MemoryExplorer
        memories={memories}
        onDelete={handleDelete}
        onClearAll={handleClearAll}
        loading={loading}
      />
    </div>
  );
}
