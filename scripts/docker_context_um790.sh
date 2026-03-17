#!/usr/bin/env bash
# Create Docker context for UM790 over Tailscale SSH. No public Docker port.
# Usage: ./scripts/docker_context_um790.sh [linux-user] [tailscale-hostname]
# Example: ./scripts/docker_context_um790.sh neil um790

set -euo pipefail
USER="${1:-${DOCKER_UM790_USER:-}}"
HOST="${2:-${DOCKER_UM790_HOST:-}}"
if [[ -z "$USER" || -z "$HOST" ]]; then
  echo "Usage: $0 <linux-user> <tailscale-hostname>" >&2
  echo "  e.g. $0 neil um790" >&2
  echo "  or set DOCKER_UM790_USER and DOCKER_UM790_HOST" >&2
  exit 1
fi
docker context create um790 --docker "host=ssh://${USER}@${HOST}" 2>/dev/null || docker context use um790
docker context use um790
echo "Context um790 set. Deploy with:"
echo "  docker --context um790 compose -f infra/compose.yaml up -d --build"
