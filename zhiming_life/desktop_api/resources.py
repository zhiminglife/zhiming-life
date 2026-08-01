"""Resolve offline models and first-run library templates bundled by Tauri."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BundledResources:
    root: Path

    def __init__(self, root: Path | str) -> None:
        object.__setattr__(self, "root", Path(root))

    @property
    def embedding_model_dir(self) -> Path | None:
        path = self.root / "models" / "embedding"
        required = (path / "model_optimized.onnx", path / "tokenizer.json")
        return path if all(item.is_file() for item in required) else None

    @property
    def reranker_model_dir(self) -> Path | None:
        path = self.root / "models" / "reranker"
        required = (path / "onnx" / "model_int8.onnx", path / "tokenizer.json")
        return path if all(item.is_file() for item in required) else None

    def install_seed_libraries(self, data_dir: Path | str) -> None:
        target_dir = Path(data_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        for filename in ("knowledge.sqlite", "cases.sqlite"):
            source = self.root / "seeds" / filename
            target = target_dir / filename
            if source.is_file() and not target.exists():
                shutil.copy2(source, target)
