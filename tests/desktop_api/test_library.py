from __future__ import annotations

import sqlite3
import sys

import pytest
from zhiming_life.desktop_api import library as library_module
from zhiming_life.desktop_api.library import LibraryStore


class KeywordEmbedder:
    dimensions = 4

    @staticmethod
    def _vector(text: str) -> list[float]:
        return [
            float(text.count("财")),
            float(text.count("事业")),
            float(text.count("婚姻")),
            float(text.count("健康")),
        ]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


class ZeroEmbedder:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.0, 0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [0.0, 0.0]


class FusionEmbedder:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] if "纯向量候选" in text else [0.8, 0.6] for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0]


class VectorPreferenceReranker:
    def rerank(self, query: str, documents: list[str]) -> list[float]:
        return [10.0 if "纯向量候选" in document else 1.0 for document in documents]


class UnavailableReranker:
    def rerank(self, query: str, documents: list[str]) -> list[float]:
        raise RuntimeError("reranker model unavailable")


def make_store(tmp_path, kind: str) -> LibraryStore:
    return LibraryStore(
        kind=kind,
        db_path=tmp_path / f"{kind}.sqlite",
        embedder=KeywordEmbedder(),
        use_sqlite_vec=False,
        chunk_size=40,
        chunk_overlap=5,
    )


def test_knowledge_and_case_libraries_are_physically_isolated(tmp_path) -> None:
    knowledge = make_store(tmp_path, "knowledge")
    cases = make_store(tmp_path, "cases")

    knowledge.import_text("财星基础", "财星体现资源与现实能力。", "knowledge.txt")
    cases.import_text("匿名命例", "来访者在事业转换期重新规划工作。", "case.txt")

    assert knowledge.db_path != cases.db_path
    assert knowledge.db_path.exists()
    assert cases.db_path.exists()
    assert knowledge.status()["source_count"] == 1
    assert cases.status()["source_count"] == 1
    assert knowledge.search("财")[0]["library_kind"] == "knowledge"
    assert cases.search("事业")[0]["library_kind"] == "cases"
    assert cases.search("财") == []


def test_identical_content_is_deduplicated(tmp_path) -> None:
    library = make_store(tmp_path, "knowledge")

    first = library.import_text("第一版", "婚姻关系重在沟通。", "book.txt")
    duplicate = library.import_text("换个标题", "婚姻关系重在沟通。", "copy.txt")

    assert first.status == "inserted"
    assert duplicate.status == "duplicate"
    assert duplicate.source_id == first.source_id
    assert library.status()["source_count"] == 1


def test_same_source_name_replaces_previous_content(tmp_path) -> None:
    library = make_store(tmp_path, "cases")
    first = library.import_text("旧命例", "事业事业，旧的工作判断。", "case-001.md")

    replacement = library.import_text(
        "新命例", "婚姻婚姻，新的关系复盘。", "case-001.md"
    )

    assert replacement.status == "replaced"
    assert replacement.source_id != first.source_id
    assert library.status()["source_count"] == 1
    assert library.search("事业") == []
    assert library.search("婚姻")[0]["title"] == "新命例"


def test_sources_can_be_listed_and_deleted_without_exposing_chunks(tmp_path) -> None:
    library = make_store(tmp_path, "knowledge")
    imported = library.import_text("事业基础", "事业事业，先验证现实条件。", "career.md")

    assert library.list_sources() == [
        {
            "id": imported.source_id,
            "title": "事业基础",
            "source_name": "career.md",
            "chunk_count": 1,
            "created_at": library.list_sources()[0]["created_at"],
        }
    ]
    assert library.delete_source(imported.source_id) is True
    assert library.delete_source(imported.source_id) is False
    assert library.list_sources() == []
    assert library.search("事业") == []


def test_search_returns_top_k_in_similarity_order(tmp_path) -> None:
    library = make_store(tmp_path, "knowledge")
    library.import_text("财务", "财财财，偏重现实资源。", "wealth.md")
    library.import_text("事业", "事业事业事业，偏重职业发展。", "career.md")
    library.import_text("综合", "财与事业都需要平衡。", "mixed.md")

    results = library.search("事业事业", limit=2)

    assert [item["title"] for item in results] == ["事业", "综合"]
    assert results[0]["score"] >= results[1]["score"]


def test_search_uses_cjk_fts_when_vectors_have_no_signal(tmp_path) -> None:
    library = LibraryStore(
        kind="knowledge",
        db_path=tmp_path / "knowledge.sqlite",
        embedder=ZeroEmbedder(),
        use_sqlite_vec=False,
    )
    library.import_text("庚金基础", "喜火炼，亦需土生。", "geng.md")
    library.import_text("甲木基础", "向阳生发，喜水滋养。", "jia.md")

    results = library.search("庚")

    assert [item["title"] for item in results] == ["庚金基础"]


def test_vec_backend_requires_the_vec_table_not_only_the_extension() -> None:
    conn = sqlite3.connect(":memory:")

    assert library_module._vec_table_exists(conn) is False
    conn.execute("CREATE TABLE vec_chunks(id INTEGER PRIMARY KEY)")
    assert library_module._vec_table_exists(conn) is True


def test_sqlite_vec_is_required_when_enabled(tmp_path, monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "sqlite_vec", None)

    with pytest.raises(RuntimeError, match="sqlite-vec 扩展不可用"):
        LibraryStore(
            kind="knowledge",
            db_path=tmp_path / "knowledge.sqlite",
            embedder=KeywordEmbedder(),
            use_sqlite_vec=True,
        )


def test_rrf_promotes_result_recalled_by_both_search_channels(tmp_path) -> None:
    library = LibraryStore(
        kind="knowledge",
        db_path=tmp_path / "knowledge.sqlite",
        embedder=FusionEmbedder(),
        use_sqlite_vec=False,
    )
    library.import_text("向量结果", "纯向量候选，不包含目标词。", "vector.md")
    library.import_text("融合结果", "事业判断需要结合长期节奏。", "hybrid.md")

    results = library.search("事业", limit=2)

    assert [item["title"] for item in results] == ["融合结果", "向量结果"]


def test_reranker_controls_final_order_after_rrf_recall(tmp_path) -> None:
    library = LibraryStore(
        kind="knowledge",
        db_path=tmp_path / "knowledge.sqlite",
        embedder=FusionEmbedder(),
        reranker=VectorPreferenceReranker(),
        use_sqlite_vec=False,
    )
    library.import_text("向量结果", "纯向量候选，不包含目标词。", "vector.md")
    library.import_text("融合结果", "事业判断需要结合长期节奏。", "hybrid.md")

    results = library.search("事业", limit=2)

    assert [item["title"] for item in results] == ["向量结果", "融合结果"]
    assert [item["score"] for item in results] == [10.0, 1.0]


def test_fastembed_reranker_loads_selected_model_lazily(tmp_path, monkeypatch) -> None:
    from fastembed.rerank import cross_encoder

    from zhiming_life.desktop_api import reranker as reranker_module

    created = []
    registered = []

    class FakeCrossEncoder:
        supported_models = []

        @classmethod
        def list_supported_models(cls):
            return [{"model": model} for model in cls.supported_models]

        @classmethod
        def add_custom_model(cls, **kwargs) -> None:
            registered.append(kwargs)
            cls.supported_models.append(kwargs["model"])

        def __init__(self, model_name: str, **kwargs) -> None:
            created.append((model_name, kwargs))

        def rerank(self, query: str, documents: list[str]):
            return iter([0.25, 0.75])

    monkeypatch.setattr(cross_encoder, "TextCrossEncoder", FakeCrossEncoder)
    model_dir = tmp_path / "reranker"
    model_dir.mkdir()
    provider = reranker_module.FastEmbedReranker(
        cache_dir=tmp_path, model_dir=model_dir
    )

    assert created == []
    assert provider.rerank("事业", ["甲", "乙"]) == [0.25, 0.75]
    assert provider.rerank("事业", ["甲", "乙"]) == [0.25, 0.75]
    assert created == [
        (
            "onnx-community/bge-reranker-base-ONNX-int8",
            {
                "cache_dir": str(tmp_path),
                "specific_model_path": str(model_dir),
            },
        )
    ]
    assert len(registered) == 1
    assert registered[0]["model"] == "onnx-community/bge-reranker-base-ONNX-int8"
    assert registered[0]["sources"].hf == "onnx-community/bge-reranker-base-ONNX"
    assert registered[0]["model_file"] == "onnx/model_int8.onnx"
    assert registered[0]["license"] == "mit"


def test_search_falls_back_to_rrf_when_reranker_is_unavailable(tmp_path) -> None:
    library = LibraryStore(
        kind="knowledge",
        db_path=tmp_path / "knowledge.sqlite",
        embedder=FusionEmbedder(),
        reranker=UnavailableReranker(),
        use_sqlite_vec=False,
    )
    library.import_text("向量结果", "纯向量候选，不包含目标词。", "vector.md")
    library.import_text("融合结果", "事业判断需要结合长期节奏。", "hybrid.md")

    try:
        results = library.search("事业", limit=2)
    except RuntimeError:
        results = []

    assert [item["title"] for item in results] == ["融合结果", "向量结果"]
