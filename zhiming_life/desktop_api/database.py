"""SQLite persistence for the local desktop product records."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


class NotFoundError(LookupError):
    """A requested local record does not exist."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    """Small explicit data store for persons, sessions, messages, and settings."""

    def __init__(self, data_dir: Path | str):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.data_dir / "app.sqlite"
        self._init_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS persons (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    relationship TEXT NOT NULL DEFAULT 'other',
                    birth_json TEXT,
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    primary_person_id TEXT NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
                    secondary_person_id TEXT REFERENCES persons(id) ON DELETE SET NULL,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_sessions_primary
                    ON sessions(primary_person_id, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_sessions_secondary
                    ON sessions(secondary_person_id, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_messages_session
                    ON messages(session_id, id);
                """
            )

    @staticmethod
    def _person(row: sqlite3.Row) -> dict:
        item = dict(row)
        item["birth"] = json.loads(item.pop("birth_json")) if item["birth_json"] else None
        return item

    def create_person(
        self,
        *,
        name: str,
        relationship: str = "other",
        birth: dict | None = None,
        notes: str = "",
        person_id: str | None = None,
    ) -> dict:
        if not name.strip():
            raise ValueError("name 不能为空")
        pid = person_id or str(uuid.uuid4())
        now = _now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO persons(id,name,relationship,birth_json,notes,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (
                    pid,
                    name.strip(),
                    relationship.strip() or "other",
                    json.dumps(birth, ensure_ascii=False) if birth else None,
                    notes.strip(),
                    now,
                    now,
                ),
            )
        return self.get_person(pid)

    def get_person(self, person_id: str) -> dict:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM persons WHERE id=?", (person_id,)).fetchone()
        if row is None:
            raise NotFoundError("命主不存在")
        return self._person(row)

    def list_persons(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM persons ORDER BY updated_at DESC, created_at DESC"
            ).fetchall()
        return [self._person(row) for row in rows]

    def update_person(self, person_id: str, **changes) -> dict:
        allowed = {"name", "relationship", "birth", "notes"}
        values = {key: value for key, value in changes.items() if key in allowed and value is not None}
        if not values:
            return self.get_person(person_id)
        if "name" in values and not str(values["name"]).strip():
            raise ValueError("name 不能为空")

        columns: list[str] = []
        params: list[object] = []
        for key, value in values.items():
            column = "birth_json" if key == "birth" else key
            columns.append(f"{column}=?")
            params.append(
                json.dumps(value, ensure_ascii=False) if key == "birth" and value else value
            )
        columns.append("updated_at=?")
        params.append(_now())
        params.append(person_id)
        with self._connect() as conn:
            cursor = conn.execute(
                f"UPDATE persons SET {', '.join(columns)} WHERE id=?",  # noqa: S608
                params,
            )
            if cursor.rowcount == 0:
                raise NotFoundError("命主不存在")
        return self.get_person(person_id)

    def delete_person(self, person_id: str) -> None:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM persons WHERE id=?", (person_id,))
            if cursor.rowcount == 0:
                raise NotFoundError("命主不存在")

    @staticmethod
    def _session(row: sqlite3.Row) -> dict:
        return dict(row)

    def create_session(
        self,
        *,
        primary_person_id: str,
        title: str,
        secondary_person_id: str | None = None,
        session_id: str | None = None,
    ) -> dict:
        self.get_person(primary_person_id)
        if secondary_person_id:
            self.get_person(secondary_person_id)
        sid = session_id or str(uuid.uuid4())
        now = _now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO sessions(id,primary_person_id,secondary_person_id,title,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?)",
                (sid, primary_person_id, secondary_person_id, title.strip() or "新开一问", now, now),
            )
        return self.get_session(sid)

    def get_session(self, session_id: str) -> dict:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        if row is None:
            raise NotFoundError("咨询不存在")
        return self._session(row)

    def list_sessions(self, person_id: str | None = None) -> list[dict]:
        with self._connect() as conn:
            if person_id:
                rows = conn.execute(
                    "SELECT * FROM sessions "
                    "WHERE primary_person_id=? OR secondary_person_id=? "
                    "ORDER BY updated_at DESC, created_at DESC",
                    (person_id, person_id),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM sessions ORDER BY updated_at DESC, created_at DESC"
                ).fetchall()
        return [self._session(row) for row in rows]

    def add_message(self, session_id: str, role: str, content: str) -> dict:
        if role not in {"user", "assistant", "system"}:
            raise ValueError("role 必须是 user、assistant 或 system")
        self.get_session(session_id)
        now = _now()
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO messages(session_id,role,content,created_at) VALUES(?,?,?,?)",
                (session_id, role, content, now),
            )
            conn.execute("UPDATE sessions SET updated_at=? WHERE id=?", (now, session_id))
            message_id = cursor.lastrowid
        return self.get_message(int(message_id))

    def get_message(self, message_id: int) -> dict:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM messages WHERE id=?", (message_id,)).fetchone()
        if row is None:
            raise NotFoundError("消息不存在")
        return dict(row)

    def list_messages(self, session_id: str) -> list[dict]:
        self.get_session(session_id)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM messages WHERE session_id=? ORDER BY id", (session_id,)
            ).fetchall()
        return [dict(row) for row in rows]

    def get_setting(self, key: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return str(row["value"]) if row else None

    def set_setting(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO settings(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )
