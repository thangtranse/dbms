#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export PATH="/Users/gper/.nvm/versions/node/v22.23.3/bin:$PATH"
export npm_config_cache="$PROJECT_ROOT/.runtime/npm-cache"
export NEXT_TELEMETRY_DISABLED=1
cd "$PROJECT_ROOT/office-lunch"
npm ci
BACKEND_URL=http://127.0.0.1:8002 npm run build
mkdir -p .next/standalone/.next
cp -R .next/static .next/standalone/.next/
cp -R public .next/standalone/
# API and frontend expose the same immutable build metadata on this native deployment.
cp build-info.json "$PROJECT_ROOT/backend/build-info.json"
