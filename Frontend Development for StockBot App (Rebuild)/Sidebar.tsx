import { NavLink } from 'react-router-dom';

interface NavItem {
  to: string;
  label: string;
  icon: string;
  section?: string;
}

const NAV_ITEMS: NavItem[] = [
  { to: '/command',       label: 'Command Center',   icon: '⌘',  section: 'Trading' },
  { to: '/signals',       label: 'Live Signals',     icon: '⚡' },
  { to: '/shadow-trades', label: 'Shadow Trades',    icon: '👻' },
  { to: '/portfolio',     label: 'Portfolio',        icon: '💼' },
  { to: '/orders',        label: 'Orders',           icon: '📝',  section: 'Paper Account' },
  { to: '/activities',    label: 'Activities',       icon: '🧾' },
  { to: '/calendar',      label: 'Calendar',         icon: '📅' },
  { to: '/assets',        label: 'Assets',           icon: '🏦' },
  { to: '/intelligence',  label: 'Intelligence',     icon: '🧠',  section: 'Analysis' },
  { to: '/ai-referee',    label: 'AI Referee',       icon: '🤖' },
  { to: '/performance',   label: 'Performance',      icon: '📈' },
  { to: '/experiments',   label: 'Experiments',      icon: '🔬' },
  { to: '/system-health', label: 'System Health',    icon: '❤️',  section: 'System' },
  { to: '/strategy-lab',  label: 'Strategy Lab',     icon: '🧪' },
  { to: '/history',       label: 'History',          icon: '📋' },
  { to: '/settings',      label: 'Settings',         icon: '⚙️' },
];

export function Sidebar() {
  let lastSection = '';
  return (
    <aside className="sidebar">
      <a href="/" className="sidebar__logo">
        <span className="sidebar__logo-icon">📊</span>
        <span>StockBot</span>
      </a>
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
      <div className="sidebar__footer">StockBot v0.1 · shadow mode</div>
    </aside>
  );
}
