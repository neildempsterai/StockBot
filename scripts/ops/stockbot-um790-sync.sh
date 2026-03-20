#!/usr/bin/env bash
# Sync UM790 → GitHub (UM790 is source of truth for StockBot)
# Run this on the UM790 from the StockBot repo root: ./scripts/ops/stockbot-um790-sync.sh
# Repo: https://github.com/neildempsterai/StockBot.git

set -e
cd "$(git rev-parse --show-toplevel)"

echo "StockBot UM790 → GitHub sync (source of truth: UM790)"
git status -sb

if [ -n "$(git status --porcelain)" ]; then
  git add -A
  git commit -m "Sync from UM790 (source of truth)"
else
  echo "No local changes."
fi

git push origin main
echo "GitHub is in sync with UM790."
