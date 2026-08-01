"""Embedding abstraction and lazy FastEmbed implementation."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


BUNDLED_EMBEDDING_MODEL = "zhiming/bge-base-zh-v1.5-int8"


class EmbeddingProvider(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class FastEmbedProvider:
    """Load the ONNX embedding model only when the first document is used."""

    def __init__(
        self,
        *,
        model_name: str = BUNDLED_EMBEDDING_MODEL,
        cache_dir: Path | str | None = None,
        model_dir: Path | str | None = None,
    ) -> None:
        self.model_name = model_name
        self.cache_dir = str(cache_dir) if cache_dir else None
        self.model_dir = str(model_dir) if model_dir else None
        self._model = None

    def _get_model(self):
        if self._model is None:
            try:
                from fastembed import TextEmbedding
                from fastembed.common.model_description import ModelSource, PoolingType
            except ImportError as exc:  # pragma: no cover - desktop dependency
                raise RuntimeError("未安装 FastEmbed，无法使用本地知识库") from exc
            if self.model_name == BUNDLED_EMBEDDING_MODEL:
                supported = {
                    item["model"].lower()
                    for item in TextEmbedding.list_supported_models()
                }
                if self.model_name.lower() not in supported:
                    TextEmbedding.add_custom_model(
                        model=self.model_name,
                        pooling=PoolingType.CLS,
                        normalization=True,
                        sources=ModelSource(hf="Xenova/bge-base-zh-v1.5"),
                        dim=768,
                        model_file="model_optimized.onnx",
                        description="Quantized Chinese BGE base embedding model",
                        license="mit",
                        size_in_gb=0.11,
                    )
            kwargs = {"model_name": self.model_name}
            if self.cache_dir:
                kwargs["cache_dir"] = self.cache_dir
            if self.model_dir:
                kwargs["specific_model_path"] = self.model_dir
            self._model = TextEmbedding(**kwargs)
        return self._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._get_model().embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        vectors = self.embed_documents([text])
        return vectors[0]
