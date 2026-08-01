from pathlib import Path

from fastapi.testclient import TestClient

from zhiming_life.desktop_api.app import create_app
from zhiming_life.desktop_api.secrets import MemorySecretStore


def test_bundled_models_seed_libraries_and_sqlite_vec_work_offline(
    tmp_path: Path, monkeypatch
) -> None:
    resource_dir = (
        Path(__file__).parents[2] / "desktop" / "src-tauri" / "resources"
    )
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    application = create_app(
        data_dir=tmp_path,
        resource_dir=resource_dir,
        secret_store=MemorySecretStore(),
        use_sqlite_vec=True,
    )

    with TestClient(application) as client:
        statuses = {item["kind"]: item for item in client.get("/api/libraries").json()}
        knowledge = client.get(
            "/api/libraries/knowledge/search",
            params={"q": "事业调整与伴侣沟通", "limit": 1},
        )
        cases = client.get(
            "/api/libraries/cases/search",
            params={"q": "事业变化与关系压力", "limit": 1},
        )

    assert statuses["knowledge"]["source_count"] == 2
    assert statuses["cases"]["source_count"] == 2
    assert statuses["knowledge"]["vector_backend"] == "sqlite-vec"
    assert statuses["cases"]["vector_backend"] == "sqlite-vec"
    assert knowledge.status_code == 200
    assert cases.status_code == 200
    assert knowledge.json()[0]["library_kind"] == "knowledge"
    assert cases.json()[0]["library_kind"] == "cases"
