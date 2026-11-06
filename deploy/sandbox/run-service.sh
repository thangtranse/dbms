#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
set -a
source "$PROJECT_ROOT/.env"
set +a
export TERADATA_HOST=127.0.0.1 QDRANT_URL=http://127.0.0.1:6333
export TERADATA_DATABASE=officelunch QDRANT_PREFIX=officelunch
export ARTIFACT_DIR="${OFFICE_LUNCH_ARTIFACT_DIR:-/Users/gper/Workplace/dubbing/office-lunch-lab/backend/artifacts}"
export FOOD_PATH="$PROJECT_ROOT/office-lunch/pipeline/data/food.txt"
export PYTHONPATH="$PROJECT_ROOT/backend"
export PYTHONHASHSEED=0 PYTHONUNBUFFERED=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export XDG_CACHE_HOME="$PROJECT_ROOT/.runtime/cache"
export MPLCONFIGDIR="$XDG_CACHE_HOME/matplotlib"
mkdir -p "$MPLCONFIGDIR"

case "${1:?api, frontend, worker or python required}" in
  api)
    cd "$PROJECT_ROOT/backend"
    exec .venv/bin/uvicorn ol.api:app --host 127.0.0.1 --port 8002 --workers 1
    ;;
  frontend)
    cd "$PROJECT_ROOT/office-lunch"
    export NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=18300
    exec /Users/gper/.nvm/versions/node/v22.23.3/bin/node .next/standalone/server.js
    ;;
  worker)
    cd "$PROJECT_ROOT/backend"
    exec .venv/bin/python -m ol.cli sync --loop
    ;;
  python)
    shift
    cd "$PROJECT_ROOT/backend"
    exec .venv/bin/python "$@"
    ;;
  *) exit 64 ;;
esac
