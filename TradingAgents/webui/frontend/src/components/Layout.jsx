import { NavLink, Outlet } from 'react-router-dom';
import { useTheme } from '../hooks/useTheme';
import StatusDot from './StatusDot';

const navLinks = [
  { to: '/', label: 'Dashboard' },
  { to: '/memories', label: 'Memories' },
  { to: '/settings', label: 'Settings' },
];

function ThemeToggle({ theme, setTheme }) {
  const cycle = () => {
    const next = theme === 'light' ? 'dark' : theme === 'dark' ? 'system' : 'light';
    setTheme(next);
  };

  const icon = theme === 'dark' ? (
    // Moon icon
    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
      <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" />
    </svg>
  ) : theme === 'light' ? (
    // Sun icon
    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
      <path fillRule="evenodd" d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z" clipRule="evenodd" />
    </svg>
  ) : (
    // System icon (monitor)
    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
      <path fillRule="evenodd" d="M3 5a2 2 0 012-2h10a2 2 0 012 2v8a2 2 0 01-2 2h-2.22l.123.489.27.108.044.018a1 1 0 01-.39 1.922H7.178a1 1 0 01-.391-1.922l.044-.018.27-.108.122-.49H5a2 2 0 01-2-2V5zm2 0h10v8H5V5z" clipRule="evenodd" />
    </svg>
  );

  return (
    <button
      onClick={cycle}
      className="p-2 rounded-lg transition-colors hover:opacity-80"
      style={{ color: 'var(--text-secondary)' }}
      title={`Theme: ${theme}`}
    >
      {icon}
    </button>
  );
}

export default function Layout() {
  const { theme, setTheme } = useTheme();

  return (
    <div className="min-h-screen" style={{ backgroundColor: 'var(--bg-primary)' }}>
      {/* Header */}
      <header
        className="sticky top-0 z-50 border-b backdrop-blur-sm"
        style={{
          backgroundColor: 'color-mix(in srgb, var(--bg-primary) 80%, transparent)',
          borderColor: 'var(--border)',
        }}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-14">
            {/* Left: Title + StatusDot */}
            <div className="flex items-center gap-3">
              <h1
                className="text-lg font-semibold tracking-tight"
                style={{ color: 'var(--text-primary)' }}
              >
                TradingAgents
              </h1>
              <StatusDot />
            </div>

            {/* Center: Nav links */}
            <nav className="flex items-center gap-1">
              {navLinks.map(({ to, label }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={to === '/'}
                  className={({ isActive }) =>
                    `px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                      isActive ? 'font-semibold' : ''
                    }`
                  }
                  style={({ isActive }) => ({
                    color: isActive ? 'var(--accent)' : 'var(--text-secondary)',
                    backgroundColor: isActive ? 'color-mix(in srgb, var(--accent) 10%, transparent)' : 'transparent',
                  })}
                >
                  {label}
                </NavLink>
              ))}
            </nav>

            {/* Right: Theme toggle */}
            <ThemeToggle theme={theme} setTheme={setTheme} />
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <Outlet />
      </main>
    </div>
  );
}
