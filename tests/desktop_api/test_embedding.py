from __future__ import annotations

from zhiming_life.desktop_api.embedding import FastEmbedProvider


def test_fastembed_uses_bundled_model_directory_without_downloading(
    tmp_path, monkeypatch
) -> None:
    import fastembed

    created = []

    class Vector:
        def tolist(self) -> list[float]:
            return [1.0, 2.0]

    class FakeTextEmbedding:
        registered = []

        @classmethod
        def list_supported_models(cls):
            return list(cls.registered)

        @classmethod
        def add_custom_model(cls, **kwargs) -> None:
            cls.registered.append({"model": kwargs["model"]})

        def __init__(self, **kwargs) -> None:
            created.append(kwargs)

        def embed(self, texts):
            return [Vector() for _ in texts]

    monkeypatch.setattr(fastembed, "TextEmbedding", FakeTextEmbedding)
    model_dir = tmp_path / "embedding"
    model_dir.mkdir()
    provider = FastEmbedProvider(model_dir=model_dir, cache_dir=tmp_path / "cache")

    assert provider.embed_query("事业") == [1.0, 2.0]
    assert created == [
        {
            "model_name": "zhiming/bge-base-zh-v1.5-int8",
            "cache_dir": str(tmp_path / "cache"),
            "specific_model_path": str(model_dir),
        }
    ]
    assert FakeTextEmbedding.registered == [
        {"model": "zhiming/bge-base-zh-v1.5-int8"}
    ]
