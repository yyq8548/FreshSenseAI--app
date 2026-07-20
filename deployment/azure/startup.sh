#!/usr/bin/env bash
set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$APP_ROOT"

RUNTIME_ROOT="${FRESHSENSE_RUNTIME_ROOT:-/home/site/freshsense-runtime}"
python scripts/prepare_cloud_runtime.py --target "$RUNTIME_ROOT"

export FRESHSENSE_MODEL_PATH="$RUNTIME_ROOT/models/densenet201.h5"
export FRESHSENSE_OPEN_SET_GATE_PATH="$RUNTIME_ROOT/models/open_set_gate.npz"
export FRESHSENSE_EMBEDDING_CACHE_DIR="$RUNTIME_ROOT/models/embedding_cache"
export FRESHSENSE_FRUIT_CATALOG_PATH="$RUNTIME_ROOT/data/fruit_catalog.json"
export FRESHSENSE_KNOWLEDGE_BASE_PATH="$RUNTIME_ROOT/data/food_knowledge_base.json"
export FRESHSENSE_REQUIRE_OPEN_SET_GATE="true"
export FRESHSENSE_EMBEDDING_LOCAL_ONLY="true"

exec python -m uvicorn api.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers 1 \
  --proxy-headers \
  --forwarded-allow-ips "*"
