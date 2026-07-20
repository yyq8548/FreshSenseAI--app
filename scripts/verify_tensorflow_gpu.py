"""Verify that TensorFlow can execute an operation on the configured GPU."""

from __future__ import annotations

import time

import tensorflow as tf


gpus = tf.config.list_physical_devices("GPU")
print("TensorFlow:", tf.__version__)
print("GPUs:", gpus)
if not gpus:
    raise SystemExit("TensorFlow did not detect a GPU.")

with tf.device("/GPU:0"):
    left = tf.random.normal((4096, 4096))
    right = tf.random.normal((4096, 4096))
    started = time.perf_counter()
    result = tf.linalg.matmul(left, right)
    checksum = float(tf.reduce_sum(result).numpy())
elapsed = time.perf_counter() - started
print(f"GPU matrix multiply completed in {elapsed:.3f}s; checksum={checksum:.4f}")
