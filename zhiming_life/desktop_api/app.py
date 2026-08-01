"""Loopback FastAPI application used by the Tauri desktop shell."""

from __future__ import annotations

import os
import secrets
from dataclasses import asdict
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from zhiming_life import conductor, llm
from zhiming_life.core import paipan

from .database import Database, NotFoundError
from .embedding import EmbeddingProvider, FastEmbedProvider
from .library import LibraryStore
from .models import MessageCreate, PersonCreate, PersonUpdate, SessionCreate
from .reranker import FastEmbedReranker, RerankerProvider
from .resources import BundledResources
from .secrets import KeyringSecretStore, SecretStore
from .settings import SettingsError, SettingsService


class ModelSettingsWrite(BaseModel):
    base_url: str
    model: str
    api_key: str | None = None


class LibraryImport(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    source_name: str = Field(min_length=1, max_length=260)
    content: str = Field(min_length=1, max_length=5_000_000)
    confirmed_anonymized: bool = False


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"code": code, "message": message})


def _chart_payload(birth: dict) -> dict:
    if int(birth.get("hour", -1)) < 0:
        raise ValueError("出生时辰不完整，暂时无法排盘")
    chart = paipan(
        year=int(birth["year"]),
        month=int(birth["month"]),
        day=int(birth["day"]),
        hour=int(birth["hour"]),
        calendar=birth.get("calendar", "solar"),
        is_leap_month=bool(birth.get("is_leap_month", False)),
    )
    return {
        **asdict(chart),
        "day_master": chart.day_master,
        "day_master_wuxing": chart.day_master_wuxing,
        "wuxing_counts": chart.wuxing_counts,
        "rendered": chart.render(),
    }


def _format_references(items: list[dict]) -> str:
    lines = []
    for index, item in enumerate(items, start=1):
        label = "知识" if item["library_kind"] == "knowledge" else "匿名命例"
        lines.append(f"[{index}] {label}《{item['title']}》：{item['content']}")
    return "\n".join(lines)


def _format_related_person(person: dict) -> str:
    birth = person.get("birth")
    if not birth:
        return f"{person['name']}：生辰信息不完整，无法排盘"
    return f"{person['name']}\n{_chart_payload(birth)['rendered']}"


def create_app(
    data_dir: Path | str,
    secret_store: SecretStore | None = None,
    embedder: EmbeddingProvider | None = None,
    reranker: RerankerProvider | None = None,
    resource_dir: Path | str | None = None,
    *,
    use_sqlite_vec: bool = True,
    api_token: str | None = None,
) -> FastAPI:
    root = Path(data_dir)
    root.mkdir(parents=True, exist_ok=True)
    resources = BundledResources(resource_dir) if resource_dir else None
    if resources:
        resources.install_seed_libraries(root)
    database = Database(root)
    settings = SettingsService(database, secret_store or KeyringSecretStore())
    embeddings = embedder or FastEmbedProvider(
        cache_dir=root / "models",
        model_dir=resources.embedding_model_dir if resources else None,
    )
    ranking = reranker or FastEmbedReranker(
        cache_dir=root / "models",
        model_dir=resources.reranker_model_dir if resources else None,
    )
    libraries = {
        "knowledge": LibraryStore(
            kind="knowledge",
            db_path=root / "knowledge.sqlite",
            embedder=embeddings,
            reranker=ranking,
            use_sqlite_vec=use_sqlite_vec,
        ),
        "cases": LibraryStore(
            kind="cases",
            db_path=root / "cases.sqlite",
            embedder=embeddings,
            reranker=ranking,
            use_sqlite_vec=use_sqlite_vec,
        ),
    }

    app = FastAPI(title="知命桌面端 API", version="0.1.0")
    app.state.database = database
    app.state.settings = settings
    app.state.libraries = libraries
    app.state.api_token = api_token
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:1420",
            "tauri://localhost",
            "http://tauri.localhost",
            "https://tauri.localhost",
        ],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def require_token(request: Request, call_next):
        if (
            app.state.api_token
            and request.method != "OPTIONS"
            and request.url.path.startswith("/api/")
            and request.url.path != "/api/health"
            and request.headers.get("X-Zhiming-Token") != app.state.api_token
        ):
            return _error(401, "unauthorized", "本地 API 令牌无效")
        return await call_next(request)

    @app.exception_handler(NotFoundError)
    async def not_found_handler(_request: Request, exc: NotFoundError):
        return _error(404, "not_found", str(exc))

    @app.exception_handler(SettingsError)
    async def settings_handler(_request: Request, exc: SettingsError):
        return _error(400, "invalid_settings", str(exc))

    @app.exception_handler(ValueError)
    async def value_handler(_request: Request, exc: ValueError):
        return _error(400, "invalid_request", str(exc))

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_request: Request, exc: RequestValidationError):
        message = (
            exc.errors()[0].get("msg", "请求参数无效")
            if exc.errors()
            else "请求参数无效"
        )
        return _error(422, "validation_error", str(message))

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/api/settings/model")
    def get_model_settings() -> dict:
        return asdict(settings.get_model_settings())

    @app.put("/api/settings/model")
    def save_model_settings(payload: ModelSettingsWrite) -> dict:
        return asdict(
            settings.save_model_settings(
                base_url=payload.base_url,
                model=payload.model,
                api_key=payload.api_key,
            )
        )

    @app.post("/api/settings/model/test")
    def test_model_settings() -> dict:
        with llm.use_config(settings.require_llm_config()):
            llm.chat("只回复 OK", [{"role": "user", "content": "ping"}], temperature=0)
        return {"status": "ok"}

    @app.get("/api/persons")
    def list_persons() -> list[dict]:
        return database.list_persons()

    @app.post("/api/persons", status_code=201)
    def create_person(payload: PersonCreate) -> dict:
        return database.create_person(**payload.model_dump(mode="json"))

    @app.get("/api/persons/{person_id}")
    def get_person(person_id: str) -> dict:
        return database.get_person(person_id)

    @app.patch("/api/persons/{person_id}")
    def update_person(person_id: str, payload: PersonUpdate) -> dict:
        return database.update_person(
            person_id, **payload.model_dump(mode="json", exclude_unset=True)
        )

    @app.delete("/api/persons/{person_id}", status_code=204)
    def delete_person(person_id: str) -> None:
        database.delete_person(person_id)

    @app.get("/api/persons/{person_id}/chart")
    def get_chart(person_id: str) -> dict:
        person = database.get_person(person_id)
        if not person["birth"]:
            raise ValueError("请先补全出生信息")
        return _chart_payload(person["birth"])

    @app.get("/api/sessions")
    def list_sessions(person_id: str | None = None) -> list[dict]:
        return database.list_sessions(person_id)

    @app.post("/api/sessions", status_code=201)
    def create_session(payload: SessionCreate) -> dict:
        return database.create_session(**payload.model_dump())

    @app.get("/api/sessions/{session_id}")
    def get_session(session_id: str) -> dict:
        return database.get_session(session_id)

    @app.get("/api/sessions/{session_id}/messages")
    def list_messages(session_id: str) -> list[dict]:
        return database.list_messages(session_id)

    @app.post("/api/sessions/{session_id}/messages")
    def send_message(session_id: str, payload: MessageCreate) -> dict:
        session = database.get_session(session_id)
        config = settings.require_llm_config()
        history = [
            {"role": message["role"], "content": message["content"]}
            for message in database.list_messages(session_id)
            if message["role"] in {"user", "assistant"}
        ]
        person = database.get_person(session["primary_person_id"])
        related_person_context = ""
        if session["secondary_person_id"]:
            related_person = database.get_person(session["secondary_person_id"])
            related_person_context = _format_related_person(related_person)
        evidence = [
            *libraries["knowledge"].search(payload.content, limit=4),
            *libraries["cases"].search(payload.content, limit=3),
        ]
        user_message = database.add_message(session_id, "user", payload.content)
        with llm.use_config(config):
            reply, _updated_history = conductor.run_turn(
                history,
                payload.content,
                known_birth=person["birth"],
                references=_format_references(evidence),
                related_person_context=related_person_context,
            )
        assistant_message = database.add_message(session_id, "assistant", reply)
        return {
            "user_message": user_message,
            "assistant_message": assistant_message,
            "evidence": evidence,
        }

    def library(kind: Literal["knowledge", "cases"]) -> LibraryStore:
        return libraries[kind]

    @app.get("/api/libraries")
    def library_statuses() -> list[dict]:
        return [libraries["knowledge"].status(), libraries["cases"].status()]

    @app.post("/api/libraries/{kind}/import")
    def import_library(
        kind: Literal["knowledge", "cases"], payload: LibraryImport
    ) -> dict:
        if kind == "cases" and not payload.confirmed_anonymized:
            raise ValueError("命例入库前必须确认已匿名化并完成复核")
        result = library(kind).import_text(
            payload.title, payload.content, payload.source_name
        )
        return asdict(result)

    @app.get("/api/libraries/{kind}/sources")
    def list_library_sources(kind: Literal["knowledge", "cases"]) -> list[dict]:
        return library(kind).list_sources()

    @app.delete("/api/libraries/{kind}/sources/{source_id}", status_code=204)
    def delete_library_source(
        kind: Literal["knowledge", "cases"], source_id: str
    ) -> None:
        if not library(kind).delete_source(source_id):
            raise NotFoundError("资料不存在")

    @app.get("/api/libraries/{kind}/search")
    def search_library(
        kind: Literal["knowledge", "cases"],
        q: str = Query(min_length=1, max_length=1000),
        limit: int = Query(default=5, ge=1, le=20),
    ) -> list[dict]:
        return library(kind).search(q, limit)

    return app


def default_app() -> FastAPI:
    data_dir = Path(
        os.getenv(
            "ZHIMING_LIFE_DATA_DIR", Path.home() / ".local" / "share" / "zhiming-life"
        )
    )
    token = os.getenv("ZHIMING_LIFE_API_TOKEN") or secrets.token_urlsafe(32)
    return create_app(
        data_dir=data_dir,
        api_token=token,
        resource_dir=os.getenv("ZHIMING_LIFE_RESOURCE_DIR"),
    )
