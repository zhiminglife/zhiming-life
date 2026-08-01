from __future__ import annotations

from zhiming_life.desktop_api.resources import BundledResources


def test_seed_libraries_are_copied_only_when_user_database_is_missing(tmp_path) -> None:
    resource_dir = tmp_path / "resources"
    seed_dir = resource_dir / "seeds"
    seed_dir.mkdir(parents=True)
    (seed_dir / "knowledge.sqlite").write_bytes(b"bundled knowledge")
    (seed_dir / "cases.sqlite").write_bytes(b"bundled cases")
    data_dir = tmp_path / "user-data"

    resources = BundledResources(resource_dir)
    resources.install_seed_libraries(data_dir)

    assert (data_dir / "knowledge.sqlite").read_bytes() == b"bundled knowledge"
    assert (data_dir / "cases.sqlite").read_bytes() == b"bundled cases"

    (data_dir / "knowledge.sqlite").write_bytes(b"user knowledge")
    resources.install_seed_libraries(data_dir)

    assert (data_dir / "knowledge.sqlite").read_bytes() == b"user knowledge"


def test_bundled_model_directories_are_exposed_when_present(tmp_path) -> None:
    resource_dir = tmp_path / "resources"
    embedding_dir = resource_dir / "models" / "embedding"
    reranker_dir = resource_dir / "models" / "reranker"
    embedding_dir.mkdir(parents=True)
    reranker_dir.mkdir(parents=True)
    (embedding_dir / "model_optimized.onnx").touch()
    (embedding_dir / "tokenizer.json").touch()
    (reranker_dir / "onnx").mkdir()
    (reranker_dir / "onnx" / "model_int8.onnx").touch()
    (reranker_dir / "tokenizer.json").touch()

    resources = BundledResources(resource_dir)

    assert resources.embedding_model_dir == embedding_dir
    assert resources.reranker_model_dir == reranker_dir


def test_missing_bundled_model_directories_do_not_claim_offline_readiness(
    tmp_path,
) -> None:
    resources = BundledResources(tmp_path / "missing")

    assert resources.embedding_model_dir is None
    assert resources.reranker_model_dir is None


def test_incomplete_model_directories_do_not_claim_offline_readiness(tmp_path) -> None:
    resource_dir = tmp_path / "resources"
    (resource_dir / "models" / "embedding").mkdir(parents=True)
    (resource_dir / "models" / "reranker").mkdir(parents=True)

    resources = BundledResources(resource_dir)

    assert resources.embedding_model_dir is None
    assert resources.reranker_model_dir is None
