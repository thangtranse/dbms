#!/bin/sh
# Run from the lab root: backend/run-sandbox.sh <CLI command and arguments>
set -eu
LAB_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
set -a
. "${SANDBOX_ENV_FILE:-/Users/gper/Workplace/dubbing/dbms/.env}"
set +a
export TERADATA_HOST=127.0.0.1 QDRANT_URL=http://127.0.0.1:6333
export TERADATA_DATABASE=officelunch QDRANT_PREFIX=officelunch
export PYTHONPATH="$LAB_ROOT/backend" ARTIFACT_DIR="$LAB_ROOT/backend/artifacts" FOOD_PATH="$LAB_ROOT/data/food.txt"
export PYTHONHASHSEED=0 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
exec "$LAB_ROOT/backend/.venv/bin/python" -m ol.cli "$@"
