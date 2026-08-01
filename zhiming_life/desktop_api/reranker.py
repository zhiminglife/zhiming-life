"""Reranker abstraction for the local RAG pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

_INT8_MODEL_NAME = "onnx-community/bge-reranker-base-ONNX-int8"
_INT8_MODEL_SOURCE = "onnx-community/bge-reranker-base-ONNX"
_INT8_MODEL_FILE = "onnx/model_int8.onnx"


class RerankerProvider(Protocol):
    def rerank(self, query: str, documents: list[str]) -> list[float]:
        ...


class FastEmbedReranker:
    """Lazy ONNX cross-encoder suitable for Chinese desktop RAG."""

    def __init__(
        self,
        *,
        model_name: str = _INT8_MODEL_NAME,
        cache_dir: Path | str | None = None,
        model_dir: Path | str | None = None,
    ) -> None:
        self.model_name = model_name
        self.cache_dir = str(cache_dir) if cache_dir else None
        self.model_dir = str(model_dir) if model_dir else None
        self._model = None

    def _get_model(self):
        if self._model is None:
            from fastembed.common.model_description import ModelSource
            from fastembed.rerank.cross_encoder import TextCrossEncoder

            supported = {
                item["model"].lower()
                for item in TextCrossEncoder.list_supported_models()
            }
            if (
                self.model_name == _INT8_MODEL_NAME
                and self.model_name.lower() not in supported
            ):
                TextCrossEncoder.add_custom_model(
                    model=_INT8_MODEL_NAME,
                    sources=ModelSource(hf=_INT8_MODEL_SOURCE),
                    model_file=_INT8_MODEL_FILE,
                    description="INT8 BGE reranker for Chinese desktop RAG.",
                    license="mit",
                    size_in_gb=0.26,
                )
            kwargs = {"cache_dir": self.cache_dir}
            if self.model_dir:
                kwargs["specific_model_path"] = self.model_dir
            self._model = TextCrossEncoder(self.model_name, **kwargs)
        return self._model

    def rerank(self, query: str, documents: list[str]) -> list[float]:
        try:
            return [
                float(score) for score in self._get_model().rerank(query, documents)
            ]
        except Exception as exc:
            raise RuntimeError("本地重排模型不可用") from exc
