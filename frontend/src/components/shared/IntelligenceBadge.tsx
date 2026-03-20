interface IntelligenceBadgeProps {
  scrappy?: boolean | { present?: boolean; stale?: boolean; conflict?: boolean } | null;
  aiReferee?: boolean | { ran?: boolean } | null;
  compact?: boolean;
}

export function IntelligenceBadge({ scrappy, aiReferee, compact }: IntelligenceBadgeProps) {
  const scrappyPresent = scrappy === true || (typeof scrappy === 'object' && scrappy?.present);
  const scrappyStale = typeof scrappy === 'object' && scrappy?.stale;
  const scrappyConflict = typeof scrappy === 'object' && scrappy?.conflict;
  const aiRefereeRan = aiReferee === true || (typeof aiReferee === 'object' && aiReferee?.ran);

  if (compact) {
    return (
      <span style={{ display: 'flex', gap: '0.25rem', alignItems: 'center' }}>
        {scrappyPresent && (
          <span title={scrappyStale || scrappyConflict ? 'Scrappy (stale/conflict)' : 'Scrappy'}>
            🧠{scrappyStale || scrappyConflict ? '⚠' : ''}
          </span>
        )}
        {aiRefereeRan && <span title="AI Referee">🤖</span>}
        {!scrappyPresent && !aiRefereeRan && <span className="muted-text">—</span>}
      </span>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', fontSize: '0.85rem' }}>
      {scrappyPresent && (
        <div>
          <span>🧠 Scrappy</span>
          {scrappyStale && <span className="flag-badge flag-badge--warn" style={{ marginLeft: '0.25rem' }}>stale</span>}
          {scrappyConflict && <span className="flag-badge flag-badge--warn" style={{ marginLeft: '0.25rem' }}>conflict</span>}
        </div>
      )}
      {aiRefereeRan && <div>🤖 AI Referee</div>}
      {!scrappyPresent && !aiRefereeRan && <span className="muted-text">No intelligence</span>}
    </div>
  );
}
