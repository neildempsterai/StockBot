export function LoadingSkeleton({ lines = 4, rows }: { lines?: number; rows?: number }) {
  const n = rows ?? lines;
  return (
    <div className="loading-skeleton">
      {Array.from({ length: n }).map((_, i) => (
        <div key={i} className="loading-skeleton__line" />
      ))}
    </div>
  );
}
