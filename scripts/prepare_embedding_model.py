"""Download and verify the embedding model used by offline desktop builds."""

from __future__ import annotations

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from tools.embeddings import FastEmbedTextEmbedder
from utils.config import EMBEDDING_MODEL_NAME


def main() -> int:
    cache_dir = PROJECT_ROOT / "models" / "embedding_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    embedder = FastEmbedTextEmbedder(
        model_name=EMBEDDING_MODEL_NAME,
        cache_dir=str(cache_dir),
        local_files_only=False,
    )
    vector = embedder.embed_query("How should ripe fruit be stored safely?")
    if vector.shape != (384,):
        raise RuntimeError(
            f"Unexpected embedding dimension {vector.shape}; expected 384 values."
        )
    print(f"Embedding model ready: {EMBEDDING_MODEL_NAME}")
    print(f"Cache directory: {cache_dir}")
    print(f"Embedding dimension: {vector.shape[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
