import sys
import types

import numpy as np
import pytest

from tools.embeddings import EmbeddingUnavailableError, FastEmbedTextEmbedder


class _FakeTextEmbedding:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def passage_embed(self, texts):
        for index, _text in enumerate(texts):
            yield np.asarray([3.0, 4.0 + index], dtype=np.float32)

    def query_embed(self, query):
        yield np.asarray([0.0, 5.0], dtype=np.float32)


def test_fastembed_adapter_normalizes_passages_and_query(monkeypatch, tmp_path):
    monkeypatch.setitem(
        sys.modules,
        "fastembed",
        types.SimpleNamespace(TextEmbedding=_FakeTextEmbedding),
    )
    embedder = FastEmbedTextEmbedder(
        model_name="test/model",
        cache_dir=str(tmp_path),
        local_files_only=True,
        threads=1,
    )

    passages = embedder.embed_passages(["first", "second"])
    query = embedder.embed_query("storage guidance")

    assert passages.shape == (2, 2)
    assert np.allclose(np.linalg.norm(passages, axis=1), [1.0, 1.0])
    assert np.allclose(query, [0.0, 1.0])


def test_fastembed_adapter_rejects_zero_query_vector(monkeypatch, tmp_path):
    class ZeroQueryEmbedding(_FakeTextEmbedding):
        def query_embed(self, query):
            yield np.asarray([0.0, 0.0], dtype=np.float32)

    monkeypatch.setitem(
        sys.modules,
        "fastembed",
        types.SimpleNamespace(TextEmbedding=ZeroQueryEmbedding),
    )
    embedder = FastEmbedTextEmbedder(
        model_name="test/model",
        cache_dir=str(tmp_path),
    )

    with pytest.raises(EmbeddingUnavailableError, match="zero-length query"):
        embedder.embed_query("storage guidance")
