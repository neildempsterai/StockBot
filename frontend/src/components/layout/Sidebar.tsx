import { NavLink } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../../api/client';
import { ENDPOINTS } from '../../api/endpoints';
import type { RuntimeStatusResponse } from '../../types/api';

interface NavItem {
  to: string;
  label: string;
  icon: string;
  section?: string;
}

const NAV_ITEMS: NavItem[] = [
  { to: '/command', label: 'Command Center', icon: '⌘', section: 'Trading' },
  { to: '/signals', label: 'Live Signals', icon: '⚡' },
  { to: '/shadow-trades', label: 'Shadow Trades', icon: '👻' },
  { to: '/portfolio', label: 'Portfolio', icon: '💼' },
  { to: '/orders', label: 'Orders', icon: '📝', section: 'Paper Account' },
  { to: '/activities', label: 'Activities', icon: '🧾' },
  { to: '/calendar', label: 'Calendar', icon: '📅' },
  { to: '/assets', label: 'Assets', icon: '🏦' },
  { to: '/intelligence', label: 'Premarket Prep', icon: '🧠', section: 'Analysis' },
  { to: '/ai-referee', label: 'AI Assessments', icon: '🤖' },
  { to: '/performance', label: 'Outcomes', icon: '📈' },
  { to: '/experiments', label: 'Mode Analysis', icon: '🔬' },
  { to: '/system-health', label: 'System Health', icon: '❤️', section: 'System' },
  { to: '/strategy-lab', label: 'Strategy Lab', icon: '🧪' },
  { to: '/settings', label: 'Settings', icon: '⚙️', section: 'Config' },
];

export function Sidebar() {
  const { data: runtimeStatus } = useQuery({
    queryKey: ['runtimeStatus'],
    queryFn: () => apiGet<RuntimeStatusResponse>(ENDPOINTS.runtimeStatus),
    refetchInterval: 30_000,
  });

  const executionMode = runtimeStatus?.strategy?.execution_mode ?? 'shadow';
  const paperArmed = runtimeStatus?.paper_trading_armed ?? false;

  let lastSection = '';
  return (
    <aside className="sidebar">
      <NavLink to="/" className="sidebar__logo">
        <span className="sidebar__logo-icon">📊</span>
        <span>StockBot</span>
      </NavLink>
      <nav className="sidebar__nav">
        {NAV_ITEMS.map((item) => {
          const showSection = item.section && item.section !== lastSection;
          if (item.section) lastSection = item.section;
          return (
            <div key={item.to}>
              {showSection && (
                <div className="sidebar__section-label">{item.section}</div>
              )}
              <NavLink
                to={item.to}
                className={({ isActive }) => (isActive ? 'active' : '')}
              >
                <span className="sidebar__nav-icon">{item.icon}</span>
                <span>{item.label}</span>
              </NavLink>
            </div>
          );
        })}
      </nav>
      <div className="sidebar__footer">
        <div>StockBot v0.1</div>
        <div style={{
          marginTop: '0.25rem',
          color: paperArmed ? 'var(--success)' : 'var(--error)',
          fontWeight: 600,
        }}>
          {executionMode} · {paperArmed ? 'armed' : 'disarmed'}
        </div>
      </div>
    </aside>
  );
}
