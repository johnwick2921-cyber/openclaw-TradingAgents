import { useState, useEffect } from 'react';

export default function StatusDot() {
  const [healthy, setHealthy] = useState(false);

  useEffect(() => {
    const check = () => {
      fetch('/api/health')
        .then((res) => setHealthy(res.ok))
        .catch(() => setHealthy(false));
    };

    check();
    const interval = setInterval(check, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <span
      className="inline-block h-2.5 w-2.5 rounded-full flex-shrink-0"
      style={{ backgroundColor: healthy ? 'var(--success)' : 'var(--danger)' }}
      title={healthy ? 'API connected' : 'API disconnected'}
    />
  );
}
