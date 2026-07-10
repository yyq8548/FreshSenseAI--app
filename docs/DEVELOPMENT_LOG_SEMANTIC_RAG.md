# Development Log — Embedding-based Semantic RAG

## Milestone

Replaced keyword-only ranking with a fully local semantic retrieval path while
keeping a visible, deterministic fallback for reliability.

## What was implemented

- Added a FastEmbed/ONNX embedding adapter in `tools/embeddings.py`.
- Pinned `fastembed==0.8.0` in both application requirement files.
- Selected `BAAI/bge-small-en-v1.5`, which produces 384-dimensional text
  embeddings and is small enough to bundle with the Windows app.
- Embedded the curated knowledge passages at agent startup and normalized them
  for in-memory cosine-similarity ranking.
- Embedded each retrieval query with the model's query-specific method.
- Added retrieval method, model name, result count, and per-document score to
  agent metadata and displayed the active mode in both user interfaces.
- Added a model-preparation script and integrated it into the Windows build.
- Bundled the prepared embedding cache in the PyInstaller distribution while
  excluding it from Git source control.

## Retrieval and safety behavior

The retriever builds a query from the accepted fruit class and freshness state.
It limits eligible passages before ranking:

- accepted predictions: the predicted fruit plus general safety passages;
- unsupported or uncertain photos: general passages only; and
- direct developer retrieval calls without an agent state: all passages.

The highest cosine-similarity scores are returned up to the configured `top_k`.
If FastEmbed, ONNX Runtime, the model cache, or an embedding operation is
unavailable, the agent uses its existing local keyword ranking and adds a
warning. It does not silently claim semantic retrieval succeeded.

## Privacy and deployment

Embeddings are generated on-device. No image, query, scan history, or knowledge
passage is sent to an external embedding API. `scripts/prepare_embedding_model.py`
downloads and validates the pinned embedding model during development or build
time. Production builds use local-files-only mode and include the prepared
cache, so end users do not need a network connection on first run.

## Validation

The automated tests cover:

- conceptual ranking when the query and relevant passage do not share terms;
- fruit/general passage scoping;
- semantic method, model, and score metadata;
- transparent keyword fallback; and
- embedding vector shape and normalization behavior.

A real-model integration check verifies a 384-dimensional embedding and ranks
banana storage guidance for a fresh-banana query. The desktop smoke test and
PyInstaller build validate the complete application path and bundled assets.

## Architectural boundary

This milestone does not add a vector database. The knowledge base is small, so
precomputing its vectors in memory is simpler, private, and fast. A vector
database becomes useful later if the corpus grows large, is updated frequently,
or needs persistence across multiple services.
