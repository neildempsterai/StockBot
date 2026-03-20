import { StateBadge } from './StateBadge';

interface FallbackWarningBadgeProps {
  gatewayFallback?: string | null;
  workerFallback?: string | null;
  staticFallbackAtEntry?: boolean;
}

export function FallbackWarningBadge({ gatewayFallback, workerFallback, staticFallbackAtEntry }: FallbackWarningBadgeProps) {
  if (staticFallbackAtEntry) {
    return <StateBadge label="Static Fallback at Entry" variant="error" />;
  }
  if (gatewayFallback || workerFallback) {
    const reasons = [gatewayFallback, workerFallback].filter(Boolean);
    return <StateBadge label={`Fallback: ${reasons.join('; ')}`} variant="warning" />;
  }
  return null;
}
