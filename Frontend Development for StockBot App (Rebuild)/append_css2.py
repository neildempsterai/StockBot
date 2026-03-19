css = """
/* ── Filter / Toolbar */
.filter-row { display: flex; align-items: center; flex-wrap: wrap; gap: 0.4rem; margin-bottom: 0.75rem; }
.filter-label { font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; }
.filter-btn { padding: 0.25rem 0.65rem; font-size: 0.75rem; font-family: inherit; background: transparent; border: 1px solid var(--border); color: var(--text-muted); border-radius: 4px; cursor: pointer; transition: background 0.15s, color 0.15s, border-color 0.15s; }
.filter-btn:hover:not(:disabled) { background: var(--surface); color: var(--text); }
.filter-btn--active { background: var(--surface); border-color: var(--accent); color: var(--accent); }
.filter-btn:disabled { opacity: 0.35; cursor: not-allowed; }
.filter-count { font-size: 0.75rem; color: var(--text-muted); margin-left: 0.5rem; }

/* ── Search & Date inputs */
.search-input, .date-input { padding: 0.3rem 0.6rem; font-size: 0.8rem; font-family: inherit; background: var(--bg); border: 1px solid var(--border); color: var(--text); border-radius: 4px; outline: none; transition: border-color 0.15s; }
.search-input { min-width: 220px; }
.search-input:focus, .date-input:focus { border-color: var(--accent); }
.search-input::placeholder { color: var(--text-muted); }

/* ── Pagination */
.pagination-row { display: flex; align-items: center; gap: 0.75rem; margin-top: 0.75rem; }

/* ── Generic badge */
.badge { display: inline-block; padding: 0.1rem 0.45rem; font-size: 0.7rem; font-weight: 600; border-radius: 3px; letter-spacing: 0.03em; text-transform: uppercase; }
.badge--green  { background: rgba(63,185,80,0.15);   color: var(--success); border: 1px solid rgba(63,185,80,0.3); }
.badge--red    { background: rgba(248,81,73,0.15);   color: var(--error);   border: 1px solid rgba(248,81,73,0.3); }
.badge--yellow { background: rgba(210,153,34,0.15);  color: var(--warning); border: 1px solid rgba(210,153,34,0.3); }
.badge--blue   { background: rgba(88,166,255,0.15);  color: var(--accent);  border: 1px solid rgba(88,166,255,0.3); }
.badge--dim    { background: rgba(139,148,158,0.1);  color: var(--text-muted); border: 1px solid rgba(139,148,158,0.2); }

/* ── Table row highlight */
.data-table tbody tr.row--highlight td { background: rgba(88,166,255,0.06); }

/* ── signal-side inline badges */
.signal-side { display: inline-block; padding: 0.1rem 0.4rem; border-radius: 3px; font-size: 0.7rem; font-weight: 700; letter-spacing: 0.04em; }
.signal-side--buy  { background: rgba(63,185,80,0.15);  color: var(--success); }
.signal-side--sell { background: rgba(248,81,73,0.15);  color: var(--error); }

/* ── empty-state msg alias */
.empty-state__msg { font-size: 13px; color: var(--text-muted); }
"""
with open('/home/ubuntu/StockBot/frontend/src/index.css', 'a') as f:
    f.write(css)
print("done")
