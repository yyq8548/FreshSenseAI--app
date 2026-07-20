#!/usr/bin/env bash
set -euo pipefail

ENV_DIR="${FRESHSENSE_TRAINING_ENV:-${HOME}/.venvs/freshsense-training}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATASET_ROOT="${1:-${FRESHSENSE_EXPANDED_DATASET_ROOT:-}}"

if [[ -z "${DATASET_ROOT}" ]]; then
  echo "Usage: $0 /path/to/prepared_expanded_dataset" >&2
  exit 2
fi
NVIDIA_LIB_PATH="$(find "${ENV_DIR}"/lib/python*/site-packages/nvidia -type d -name lib -print | paste -sd: -)"
export LD_LIBRARY_PATH="${NVIDIA_LIB_PATH}:${LD_LIBRARY_PATH:-}"
export TF_CPP_MIN_LOG_LEVEL=1

cd "${PROJECT_ROOT}"
"${ENV_DIR}/bin/python" scripts/train_imagenet_densenet.py \
  --manifest "${DATASET_ROOT}/manifest.json" \
  --dataset "${DATASET_ROOT}" \
  --batch-size 64
