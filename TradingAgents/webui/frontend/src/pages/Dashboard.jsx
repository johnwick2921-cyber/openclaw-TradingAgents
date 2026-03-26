import { useState, useEffect, useCallback } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { api } from '../hooks/useApi';
import RunForm from '../components/RunForm';
import RunTable from '../components/RunTable';
import ErrorBanner from '../components/ErrorBanner';
import PriceTicker from '../components/PriceTicker';

export default function Dashboard() {
  const navigate = useNavigate();

  const [runs, setRuns] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [perPage] = useState(20);
  const [sortBy, setSortBy] = useState('created_at');
  const [order, setOrder] = useState('desc');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const fetchRuns = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api(
        `/api/runs?page=${page}&per_page=${perPage}&sort_by=${sortBy}&order=${order}`
      );
      setRuns(data.runs || []);
      setTotal(data.total ?? (data.runs?.length || 0));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [page, perPage, sortBy, order]);

  useEffect(() => {
    fetchRuns();
  }, [fetchRuns]);

  // Find any running run
  const runningRun = runs.find((r) => r.status === 'running');

  const handleSort = (col, dir) => {
    setSortBy(col);
    setOrder(dir);
    setPage(1);
  };

  const handlePageChange = (newPage) => {
    setPage(newPage);
  };

  const handleDelete = async (id) => {
    try {
      await api(`/api/runs/${id}`, { method: 'DELETE' });
      setRuns((prev) => prev.filter((r) => r.id !== id));
      setTotal((prev) => Math.max(0, prev - 1));
    } catch (err) {
      setError(err.message);
    }
  };

  const handleSubmit = async (formData) => {
    setSubmitting(true);
    setError(null);
    try {
      // Map form field names to API field names
      const payload = {
        ...formData,
        max_risk_discuss_rounds: formData.max_risk_rounds ?? 1,
      };
      delete payload.max_risk_rounds;
      delete payload.analysts;
      payload.selected_analysts = formData.analysts || [];
      const result = await api('/api/runs', { method: 'POST', body: payload });
      navigate(`/runs/${result.run_id}/live`);
    } catch (err) {
      setError(err.message);
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Live NQ price */}
      <PriceTicker symbol="NQ" />

      {/* Error banner */}
      {error && (
        <ErrorBanner
          message={error}
          type="error"
          onDismiss={() => setError(null)}
        />
      )}

      {/* Running banner */}
      {runningRun && (
        <ErrorBanner
          message={
            <span>
              Analysis for <strong>{runningRun.ticker}</strong> is currently running.{' '}
              <Link
                to={`/runs/${runningRun.id}/live`}
                className="underline font-semibold"
                style={{ color: 'inherit' }}
              >
                View live progress
              </Link>
            </span>
          }
          type="info"
        />
      )}

      {/* Run Form Card */}
      <div
        className="rounded-xl border p-6"
        style={{
          backgroundColor: 'var(--bg-primary)',
          borderColor: 'var(--border)',
        }}
      >
        <h2
          className="text-lg font-semibold mb-4"
          style={{ color: 'var(--text-primary)' }}
        >
          New Analysis
        </h2>
        <RunForm onSubmit={handleSubmit} disabled={submitting} />
      </div>

      {/* Run Table Card */}
      <div
        className="rounded-xl border p-6"
        style={{
          backgroundColor: 'var(--bg-primary)',
          borderColor: 'var(--border)',
        }}
      >
        <h2
          className="text-lg font-semibold mb-4"
          style={{ color: 'var(--text-primary)' }}
        >
          Past Runs
        </h2>
        <RunTable
          runs={runs}
          total={total}
          page={page}
          perPage={perPage}
          onPageChange={handlePageChange}
          onSort={handleSort}
          onDelete={handleDelete}
          loading={loading}
        />
      </div>
    </div>
  );
}
