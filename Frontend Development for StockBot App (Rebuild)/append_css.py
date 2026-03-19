css = """
/* ── Sidebar layout ───────────────────────────────────────────── */
.layout--with-sidebar {
  display: flex;
  flex-direction: row;
  min-height: 100%;
  height: 100%;
}
.sidebar {
  width: 200px;
  min-width: 200px;
  background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  overflow-y: auto;
}
.sidebar__logo {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 1rem;
  font-weight: 700;
  font-size: 0.875rem;
  color: var(--text);
  text-decoration: none;
  border-bottom: 1px solid var(--border);
}
.sidebar__logo-icon { font-size: 1.1rem; }
.sidebar__section-label {
  font-size: 10px;
  text-transform: uppercase;
  color: var(--text-muted);
  padding: 0.75rem 1rem 0.25rem;
  letter-spacing: 0.08em;
}
.sidebar__nav {
  display: flex;
  flex-direction: column;
  padding: 0.25rem 0;
}
.sidebar__nav a {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.45rem 1rem;
  color: var(--text-muted);
  text-decoration: none;
  font-size: 12px;
  border-left: 2px solid transparent;
  transition: color 0.15s, background 0.15s;
}
.sidebar__nav a:hover {
  color: var(--text);
  background: rgba(88, 166, 255, 0.06);
}
.sidebar__nav a.active {
  color: var(--accent);
  border-left-color: var(--accent);
  background: rgba(88, 166, 255, 0.08);
}
.sidebar__nav-icon { font-size: 13px; width: 16px; text-align: center; }
.sidebar__footer {
  margin-top: auto;
  padding: 0.75rem 1rem;
  font-size: 10px;
  color: var(--text-muted);
  border-top: 1px solid var(--border);
}
.layout__body {
  flex: 1 1 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.topbar--slim {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.4rem 1rem;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  gap: 0.75rem;
}
.topbar__right {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

/* ── Page layout helpers ──────────────────────────────────────── */
.page-stack {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  width: 100%;
}
.page-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}
.page-title { font-size: 1.25rem; margin: 0; }

/* ── Section header ───────────────────────────────────────────── */
.section-header {
  display: flex;
  align-items: baseline;
  gap: 0.75rem;
  border-bottom: 1px solid var(--border);
  padding-bottom: 0.4rem;
}
.section-header__title {
  font-size: 0.8rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text);
}
.section-header__subtitle {
  font-size: 11px;
  color: var(--text-muted);
}

/* ── Refresh badge ────────────────────────────────────────────── */
.refresh-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 11px;
  color: var(--text-muted);
  padding: 0.2rem 0.5rem;
  border: 1px solid var(--border);
  border-radius: 4px;
}
.refresh-badge__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-muted);
}
.refresh-badge__dot--live {
  background: var(--success);
  animation: pulse 2s infinite;
}
.refresh-badge__dot--fetching {
  background: var(--accent);
  animation: pulse 0.8s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}

/* ── Empty state ──────────────────────────────────────────────── */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 2.5rem;
  border: 1px dashed var(--border);
  border-radius: 8px;
  color: var(--text-muted);
  text-align: center;
}
.empty-state__icon { font-size: 1.75rem; }
.empty-state__message { font-size: 13px; }

/* ── Chart container ──────────────────────────────────────────── */
.chart-container {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 1rem;
}

/* ── P&L coloring ─────────────────────────────────────────────── */
.pnl--positive { color: var(--success); }
.pnl--negative { color: var(--error); }
.pnl--neutral  { color: var(--text-muted); }

/* ── Table cell helpers ───────────────────────────────────────── */
.cell--symbol  { font-weight: 600; color: var(--accent); }
.cell--mono    { font-family: inherit; font-size: 11px; }
.cell--muted   { color: var(--text-muted); }
.cell--small   { font-size: 11px; }
.cell--ts      { color: var(--text-muted); font-size: 11px; white-space: nowrap; }
.cell--pnl     { font-weight: 600; }
.cell--rationale { max-width: 280px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
tr:hover { background: rgba(255,255,255,0.02); }

/* ── Badges ───────────────────────────────────────────────────── */
.scrappy-badge {
  display: inline-block;
  padding: 0.15rem 0.4rem;
  border-radius: 3px;
  font-size: 10px;
  background: rgba(163, 113, 247, 0.2);
  color: var(--shadow);
  border: 1px solid rgba(163, 113, 247, 0.4);
}
.flag-badge {
  display: inline-block;
  padding: 0.15rem 0.4rem;
  border-radius: 3px;
  font-size: 10px;
}
.flag-badge--ok   { background: rgba(63, 185, 80, 0.15); color: var(--success); }
.flag-badge--warn { background: rgba(210, 153, 34, 0.15); color: var(--warning); }
.catalyst-badge {
  display: inline-block;
  padding: 0.15rem 0.4rem;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 600;
}
.catalyst-badge--high   { background: rgba(248, 81, 73, 0.15); color: var(--error); }
.catalyst-badge--medium { background: rgba(210, 153, 34, 0.15); color: var(--warning); }
.catalyst-badge--low    { background: rgba(139, 148, 158, 0.15); color: var(--text-muted); }
.score-badge {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 700;
}
.score-badge--high { background: rgba(63, 185, 80, 0.2); color: var(--success); }
.score-badge--mid  { background: rgba(210, 153, 34, 0.2); color: var(--warning); }
.score-badge--low  { background: rgba(248, 81, 73, 0.2); color: var(--error); }
.signal-side--buy  { color: var(--success); font-weight: 700; }
.signal-side--sell { color: var(--error);   font-weight: 700; }

/* ── KPI card variants ────────────────────────────────────────── */
.kpi-card--ok  { border-left: 3px solid var(--success); }
.kpi-card--err { border-left: 3px solid var(--error); }
.kpi-card--status .kpi-card__value { font-size: 1rem; }

/* ── Info note ────────────────────────────────────────────────── */
.info-note {
  padding: 0.6rem 0.9rem;
  border: 1px dashed var(--border);
  border-radius: 6px;
  color: var(--text-muted);
  font-size: 11px;
}

/* ── Settings table ───────────────────────────────────────────── */
.settings-table {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  overflow: hidden;
}
.settings-row {
  display: flex;
  align-items: baseline;
  gap: 1rem;
  padding: 0.5rem 1rem;
  border-bottom: 1px solid var(--border);
}
.settings-row:last-child { border-bottom: none; }
.settings-row__key {
  min-width: 200px;
  font-size: 11px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.settings-row__value {
  font-size: 13px;
  color: var(--text);
}
"""

with open('/home/ubuntu/StockBot/frontend/src/index.css', 'a') as f:
    f.write(css)
print('CSS appended successfully')
