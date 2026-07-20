#!/usr/bin/env bash
set -euo pipefail

ENV_DIR="${HOME}/.venvs/freshsense-training"

echo "[1/4] Verifying the NVIDIA GPU exposed by WSL2"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader

echo "[2/4] Installing the Python virtual-environment prerequisites"
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip

echo "[3/4] Creating the isolated FreshSense GPU environment"
python3 -m venv "${ENV_DIR}"
"${ENV_DIR}/bin/python" -m pip install --upgrade pip setuptools wheel
"${ENV_DIR}/bin/python" -m pip install 'tensorflow[and-cuda]==2.21.*' pillow numpy h5py pytest

echo "[4/4] Linking the virtual-environment CUDA libraries"
TF_PACKAGE_DIR="$(dirname "$("${ENV_DIR}/bin/python" -c 'print(__import__("tensorflow").__file__)')")"
ln -svf "${ENV_DIR}"/lib/python*/site-packages/nvidia/*/lib/*.so* "${TF_PACKAGE_DIR}/"
PTXAS_PATH="$(find "${ENV_DIR}"/lib/python*/site-packages/nvidia/cuda_nvcc/bin -name ptxas -print -quit)"
if [[ -n "${PTXAS_PATH}" ]]; then
  ln -sf "${PTXAS_PATH}" "${ENV_DIR}/bin/ptxas"
fi
NVIDIA_LIB_PATH="$(find "${ENV_DIR}"/lib/python*/site-packages/nvidia -type d -name lib -print | paste -sd: -)"
export LD_LIBRARY_PATH="${NVIDIA_LIB_PATH}:${LD_LIBRARY_PATH:-}"

echo "Verifying TensorFlow CUDA access"
"${ENV_DIR}/bin/python" - <<'PY'
import tensorflow as tf

gpus = tf.config.list_physical_devices("GPU")
print("TensorFlow:", tf.__version__)
print("GPUs:", gpus)
if not gpus:
    raise SystemExit("TensorFlow did not detect the RTX GPU.")
PY

echo "FreshSense WSL2 GPU environment is ready: ${ENV_DIR}"
