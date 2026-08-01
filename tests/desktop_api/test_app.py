from __future__ import annotations

from fastapi.testclient import TestClient

from zhiming_life.agents import bazi_master
from zhiming_life.desktop_api import app as app_module
from zhiming_life.desktop_api.secrets import MemorySecretStore


class KeywordEmbedder:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return [float(text.count("财")), float(text.count("事业"))]


class PreserveOrderReranker:
    def rerank(self, query: str, documents: list[str]) -> list[float]:
        return [float(len(documents) - index) for index in range(len(documents))]


def birth() -> dict:
    return {
        "calendar": "solar",
        "year": 1990,
        "month": 6,
        "day": 15,
        "hour": 14,
        "gender": "male",
        "is_leap_month": False,
        "birth_place": "",
    }


def make_client(tmp_path):
    application = app_module.create_app(
        data_dir=tmp_path,
        secret_store=MemorySecretStore(),
        embedder=KeywordEmbedder(),
        reranker=PreserveOrderReranker(),
        use_sqlite_vec=False,
    )
    return TestClient(application)


def test_health_and_write_only_model_settings(tmp_path) -> None:
    with make_client(tmp_path) as client:
        assert client.get("/api/health").json() == {"status": "ok"}

        response = client.put(
            "/api/settings/model",
            json={
                "base_url": "https://gateway.example/v1/",
                "model": "example-model",
                "api_key": "secret-key",
            },
        )
        assert response.status_code == 200
        assert response.json() == {
            "base_url": "https://gateway.example/v1",
            "model": "example-model",
            "has_api_key": True,
        }
        assert "secret-key" not in client.get("/api/settings/model").text


def test_api_token_protects_all_private_endpoints(tmp_path) -> None:
    application = app_module.create_app(
        data_dir=tmp_path,
        secret_store=MemorySecretStore(),
        embedder=KeywordEmbedder(),
        reranker=PreserveOrderReranker(),
        use_sqlite_vec=False,
        api_token="desktop-token",
    )
    with TestClient(application) as client:
        assert client.get("/api/health").status_code == 200
        denied = client.get("/api/persons")
        allowed = client.get(
            "/api/persons", headers={"X-Zhiming-Token": "desktop-token"}
        )

    assert denied.status_code == 401
    assert denied.json()["message"] == "本地 API 令牌无效"
    assert allowed.status_code == 200


def test_tauri_origin_cors_preflight_is_not_blocked_by_api_token(tmp_path) -> None:
    application = app_module.create_app(
        data_dir=tmp_path,
        secret_store=MemorySecretStore(),
        embedder=KeywordEmbedder(),
        reranker=PreserveOrderReranker(),
        use_sqlite_vec=False,
        api_token="desktop-token",
    )
    with TestClient(application) as client:
        response = client.options(
            "/api/persons",
            headers={
                "Origin": "tauri://localhost",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "x-zhiming-token",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "tauri://localhost"


def test_model_connection_endpoint_uses_saved_configuration(
    tmp_path, monkeypatch
) -> None:
    captured = {}

    def fake_chat(system, messages, *, temperature=0.7):
        captured["system"] = system
        captured["messages"] = messages
        captured["temperature"] = temperature
        return "OK"

    monkeypatch.setattr(app_module.llm, "chat", fake_chat)
    with make_client(tmp_path) as client:
        client.put(
            "/api/settings/model",
            json={
                "base_url": "https://gateway.example/v1",
                "model": "example-model",
                "api_key": "secret-key",
            },
        )
        response = client.post("/api/settings/model/test")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert captured == {
        "system": "只回复 OK",
        "messages": [{"role": "user", "content": "ping"}],
        "temperature": 0,
    }


def test_person_api_lifecycle_and_multi_person_session_listing(tmp_path) -> None:
    with make_client(tmp_path) as client:
        primary = client.post(
            "/api/persons",
            json={"name": "林先生", "relationship": "self", "birth": birth()},
        ).json()
        secondary = client.post(
            "/api/persons",
            json={
                "name": "周女士",
                "relationship": "partner",
                "birth": {**birth(), "year": 1992, "month": 9, "day": 8},
            },
        ).json()
        updated = client.patch(
            f"/api/persons/{primary['id']}", json={"notes": "正在考虑事业调整"}
        )
        session = client.post(
            "/api/sessions",
            json={
                "primary_person_id": primary["id"],
                "secondary_person_id": secondary["id"],
                "title": "事业与关系合看",
            },
        ).json()

        assert updated.status_code == 200
        assert updated.json()["notes"] == "正在考虑事业调整"
        assert client.get(f"/api/sessions/{session['id']}").json()["title"] == "事业与关系合看"
        assert [item["id"] for item in client.get(
            "/api/sessions", params={"person_id": primary["id"]}
        ).json()] == [session["id"]]
        assert [item["id"] for item in client.get(
            "/api/sessions", params={"person_id": secondary["id"]}
        ).json()] == [session["id"]]

        deleted = client.delete(f"/api/persons/{primary['id']}")
        assert deleted.status_code == 204
        assert client.get(f"/api/persons/{primary['id']}").status_code == 404
        assert client.get(f"/api/sessions/{session['id']}").status_code == 404


def test_person_session_and_consultation_flow(tmp_path, monkeypatch) -> None:
    captured = {}

    def fake_run_turn(
        history,
        user_message,
        *,
        known_birth=None,
        references="",
        related_person_context="",
    ):
        captured["birth"] = known_birth
        captured["references"] = references
        reply = "这是本轮八字解读。"
        return reply, [
            *history,
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": reply},
        ]

    monkeypatch.setattr(app_module.conductor, "run_turn", fake_run_turn)
    with make_client(tmp_path) as client:
        client.put(
            "/api/settings/model",
            json={
                "base_url": "https://gateway.example/v1",
                "model": "example-model",
                "api_key": "secret-key",
            },
        )
        person = client.post(
            "/api/persons",
            json={"name": "我自己", "relationship": "self", "birth": birth()},
        ).json()
        assert client.get(f"/api/persons/{person['id']}").json()["name"] == "我自己"
        assert client.get(f"/api/persons/{person['id']}/chart").status_code == 200

        session = client.post(
            "/api/sessions",
            json={"primary_person_id": person["id"], "title": "看看事业"},
        ).json()
        response = client.post(
            f"/api/sessions/{session['id']}/messages",
            json={"content": "今年事业如何？"},
        )

        assert response.status_code == 200
        assert response.json()["assistant_message"]["content"] == "这是本轮八字解读。"
        assert captured["birth"]["year"] == 1990
        messages = client.get(f"/api/sessions/{session['id']}/messages").json()
        assert [message["role"] for message in messages] == ["user", "assistant"]


def test_secondary_person_chart_reaches_the_expert_context(
    tmp_path, monkeypatch
) -> None:
    captured = {}

    def fake_chat(system, messages, *, temperature=0.7):
        captured["context"] = messages[-1]["content"]
        return "这是合看解读。"

    monkeypatch.setattr(bazi_master.llm, "chat", fake_chat)
    monkeypatch.setattr(bazi_master, "retrieve", lambda **_kwargs: "")
    second_birth = {**birth(), "year": 1992, "month": 8, "day": 20}

    with make_client(tmp_path) as client:
        client.put(
            "/api/settings/model",
            json={
                "base_url": "https://gateway.example/v1",
                "model": "example-model",
                "api_key": "secret-key",
            },
        )
        primary = client.post(
            "/api/persons",
            json={"name": "甲方", "relationship": "self", "birth": birth()},
        ).json()
        secondary = client.post(
            "/api/persons",
            json={
                "name": "乙方",
                "relationship": "partner",
                "birth": second_birth,
            },
        ).json()
        session = client.post(
            "/api/sessions",
            json={
                "primary_person_id": primary["id"],
                "secondary_person_id": secondary["id"],
                "title": "两人关系合看",
            },
        ).json()

        response = client.post(
            f"/api/sessions/{session['id']}/messages",
            json={"content": "我们如何更好地相处？"},
        )

    assert response.status_code == 200
    assert response.json()["assistant_message"]["content"] == "这是合看解读。"
    assert "【合看命主（客观排盘）】" in captured["context"]
    assert "乙方" in captured["context"]


def test_import_and_search_keep_libraries_separate(tmp_path) -> None:
    with make_client(tmp_path) as client:
        knowledge_import = client.post(
            "/api/libraries/knowledge/import",
            json={
                "title": "财星基础",
                "source_name": "wealth.md",
                "content": "财财，讲现实资源。",
                "confirmed_anonymized": False,
            },
        )
        assert knowledge_import.status_code == 200

        rejected_case = client.post(
            "/api/libraries/cases/import",
            json={
                "title": "命例",
                "source_name": "case.md",
                "content": "事业事业，匿名复盘。",
                "confirmed_anonymized": False,
            },
        )
        assert rejected_case.status_code == 400

        case_import = client.post(
            "/api/libraries/cases/import",
            json={
                "title": "匿名命例",
                "source_name": "case.md",
                "content": "事业事业，匿名复盘。",
                "confirmed_anonymized": True,
            },
        )
        assert case_import.status_code == 200

        knowledge = client.get(
            "/api/libraries/knowledge/search", params={"q": "财"}
        ).json()
        cases = client.get("/api/libraries/cases/search", params={"q": "事业"}).json()
        assert knowledge[0]["library_kind"] == "knowledge"
        assert cases[0]["library_kind"] == "cases"
        assert (
            client.get("/api/libraries/cases/search", params={"q": "财"}).json() == []
        )


def test_library_sources_can_be_listed_and_deleted(tmp_path) -> None:
    with make_client(tmp_path) as client:
        imported = client.post(
            "/api/libraries/knowledge/import",
            json={
                "title": "事业基础",
                "source_name": "知命内置知识 · 原创整理 · v1",
                "content": "事业事业，先验证现实条件。",
                "confirmed_anonymized": False,
            },
        ).json()

        sources = client.get("/api/libraries/knowledge/sources")
        assert sources.status_code == 200
        assert sources.json() == [
            {
                "id": imported["source_id"],
                "title": "事业基础",
                "source_name": "知命内置知识 · 原创整理 · v1",
                "chunk_count": 1,
                "created_at": sources.json()[0]["created_at"],
            }
        ]

        deleted = client.delete(
            f"/api/libraries/knowledge/sources/{imported['source_id']}"
        )
        assert deleted.status_code == 204
        assert client.get("/api/libraries/knowledge/sources").json() == []
        missing = client.delete(
            f"/api/libraries/knowledge/sources/{imported['source_id']}"
        )
        assert missing.status_code == 404
        assert missing.json()["message"] == "资料不存在"


def test_uniform_not_found_error(tmp_path) -> None:
    with make_client(tmp_path) as client:
        response = client.get("/api/persons/missing")

    assert response.status_code == 404
    assert response.json() == {"code": "not_found", "message": "命主不存在"}


def test_create_app_shares_reranker_between_both_libraries(tmp_path) -> None:
    reranker = PreserveOrderReranker()

    application = app_module.create_app(
        data_dir=tmp_path,
        secret_store=MemorySecretStore(),
        embedder=KeywordEmbedder(),
        reranker=reranker,
        use_sqlite_vec=False,
    )

    assert application.state.libraries["knowledge"].reranker is reranker
    assert application.state.libraries["cases"].reranker is reranker
