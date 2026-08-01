"""Two-database local RAG storage for knowledge and anonymized cases."""

from __future__ import annotations

import hashlib
import math
import sqlite3
import struct
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Literal

from .embedding import EmbeddingProvider
from .reranker import RerankerProvider

LibraryKind = Literal["knowledge", "cases"]
_RRF_K = 60


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _pack(vector: list[float]) -> bytes:
    return struct.pack(f"<{len(vector)}f", *vector)


def _unpack(blob: bytes) -> list[float]:
    return list(struct.unpack(f"<{len(blob) // 4}f", blob))


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def _vec_table_exists(conn: sqlite3.Connection) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='vec_chunks'"
        ).fetchone()
        is not None
    )


def _cjk_separate(text: str) -> str:
    """Make unicode61 index each CJK character as an independent token."""
    separated: list[str] = []
    for character in text:
        codepoint = ord(character)
        if 0x3400 <= codepoint <= 0x9FFF:
            separated.extend((" ", character, " "))
        else:
            separated.append(character)
    return " ".join("".join(separated).split())


@dataclass(frozen=True)
class ImportResult:
    source_id: str
    status: Literal["inserted", "replaced", "duplicate"]
    chunk_count: int


class LibraryStore:
    """A single knowledge or case library backed by its own SQLite file."""

    def __init__(
        self,
        *,
        kind: LibraryKind,
        db_path: Path | str,
        embedder: EmbeddingProvider,
        reranker: RerankerProvider | None = None,
        use_sqlite_vec: bool = True,
        chunk_size: int = 700,
        chunk_overlap: int = 100,
    ) -> None:
        if kind not in {"knowledge", "cases"}:
            raise ValueError("kind 必须是 knowledge 或 cases")
        if chunk_size < 1 or not 0 <= chunk_overlap < chunk_size:
            raise ValueError("分块大小配置无效")
        self.kind = kind
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.embedder = embedder
        self.reranker = reranker
        self.use_sqlite_vec = use_sqlite_vec
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._sqlite_vec_available: bool | None = None
        self._init_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        if self.use_sqlite_vec and self._sqlite_vec_available is not False:
            try:
                import sqlite_vec

                conn.enable_load_extension(True)
                sqlite_vec.load(conn)
                conn.enable_load_extension(False)
                self._sqlite_vec_available = True
            except (ImportError, sqlite3.Error, AttributeError):
                self._sqlite_vec_available = False
                raise RuntimeError("sqlite-vec 扩展不可用")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sources (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    source_name TEXT NOT NULL UNIQUE,
                    content_hash TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
                    position INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    embedding BLOB NOT NULL,
                    UNIQUE(source_id, position)
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5(
                    title, content, tokenize='unicode61'
                );
                CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source_id, position);
                """
            )
            stored_kind = conn.execute(
                "SELECT value FROM metadata WHERE key='kind'"
            ).fetchone()
            if stored_kind and stored_kind["value"] != self.kind:
                raise ValueError("数据库类型与目标库不一致")
            conn.execute(
                "INSERT OR IGNORE INTO metadata(key,value) VALUES('kind',?)",
                (self.kind,),
            )
            if (
                self.use_sqlite_vec
                and conn.execute("SELECT 1 FROM chunks LIMIT 1").fetchone()
                and not _vec_table_exists(conn)
            ):
                raise RuntimeError("资料库缺少 sqlite-vec 向量索引")

    def _ensure_vec_table(self, conn: sqlite3.Connection, dimensions: int) -> None:
        if not self._sqlite_vec_available:
            return
        existed = _vec_table_exists(conn)
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0("
            f"embedding float[{dimensions}] distance_metric=cosine)"
        )
        if not existed:
            conn.executemany(
                "INSERT INTO vec_chunks(rowid,embedding) VALUES(?,?)",
                conn.execute("SELECT id,embedding FROM chunks").fetchall(),
            )

    def _chunks(self, content: str) -> list[str]:
        normalized = "\n".join(
            line.strip() for line in content.splitlines() if line.strip()
        )
        if not normalized:
            return []
        chunks: list[str] = []
        start = 0
        while start < len(normalized):
            end = min(start + self.chunk_size, len(normalized))
            if end < len(normalized):
                paragraph_end = normalized.rfind("\n", start, end)
                sentence_end = max(
                    normalized.rfind("。", start, end),
                    normalized.rfind("！", start, end),
                    normalized.rfind("？", start, end),
                )
                boundary = max(paragraph_end, sentence_end)
                if boundary > start + self.chunk_size // 2:
                    end = boundary + 1
            chunks.append(normalized[start:end])
            if end == len(normalized):
                break
            start = max(end - self.chunk_overlap, start + 1)
        return chunks

    def _delete_source(self, conn: sqlite3.Connection, source_id: str) -> None:
        has_vec_table = bool(
            self._sqlite_vec_available and _vec_table_exists(conn)
        )
        chunk_ids = [
            int(row["id"])
            for row in conn.execute(
                "SELECT id FROM chunks WHERE source_id=?", (source_id,)
            )
        ]
        for chunk_id in chunk_ids:
            conn.execute("DELETE FROM chunk_fts WHERE rowid=?", (chunk_id,))
            if has_vec_table:
                conn.execute("DELETE FROM vec_chunks WHERE rowid=?", (chunk_id,))
        conn.execute("DELETE FROM sources WHERE id=?", (source_id,))

    def import_text(self, title: str, content: str, source_name: str) -> ImportResult:
        title = title.strip()
        source_name = source_name.strip()
        content = content.strip()
        if not title or not source_name or not content:
            raise ValueError("标题、来源和正文不能为空")
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        pieces = self._chunks(content)
        vectors = self.embedder.embed_documents(pieces)
        if len(vectors) != len(pieces) or any(not vector for vector in vectors):
            raise ValueError("向量模型返回结果无效")

        with self._connect() as conn:
            duplicate = conn.execute(
                "SELECT id FROM sources WHERE content_hash=?", (content_hash,)
            ).fetchone()
            if duplicate:
                chunk_count = conn.execute(
                    "SELECT COUNT(*) AS count FROM chunks WHERE source_id=?",
                    (duplicate["id"],),
                ).fetchone()["count"]
                return ImportResult(str(duplicate["id"]), "duplicate", int(chunk_count))

            previous = conn.execute(
                "SELECT id FROM sources WHERE source_name=?", (source_name,)
            ).fetchone()
            status: Literal["inserted", "replaced"] = "inserted"
            if previous:
                self._delete_source(conn, str(previous["id"]))
                status = "replaced"

            source_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO sources(id,title,source_name,content_hash,created_at) "
                "VALUES(?,?,?,?,?)",
                (source_id, title, source_name, content_hash, _now()),
            )
            self._ensure_vec_table(conn, len(vectors[0]))
            for position, (piece, vector) in enumerate(zip(pieces, vectors)):
                cursor = conn.execute(
                    "INSERT INTO chunks(source_id,position,content,embedding) VALUES(?,?,?,?)",
                    (source_id, position, piece, _pack(vector)),
                )
                chunk_id = int(cursor.lastrowid)
                conn.execute(
                    "INSERT INTO chunk_fts(rowid,title,content) VALUES(?,?,?)",
                    (chunk_id, _cjk_separate(title), _cjk_separate(piece)),
                )
                if self._sqlite_vec_available:
                    conn.execute(
                        "INSERT INTO vec_chunks(rowid,embedding) VALUES(?,?)",
                        (chunk_id, _pack(vector)),
                    )
        return ImportResult(source_id, status, len(pieces))

    def list_sources(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT s.id,s.title,s.source_name,s.created_at,COUNT(c.id) AS chunk_count "
                "FROM sources s LEFT JOIN chunks c ON c.source_id=s.id "
                "GROUP BY s.id,s.title,s.source_name,s.created_at "
                "ORDER BY s.created_at DESC,s.title"
            ).fetchall()
        return [
            {
                "id": str(row["id"]),
                "title": str(row["title"]),
                "source_name": str(row["source_name"]),
                "chunk_count": int(row["chunk_count"]),
                "created_at": str(row["created_at"]),
            }
            for row in rows
        ]

    def delete_source(self, source_id: str) -> bool:
        with self._connect() as conn:
            exists = conn.execute(
                "SELECT 1 FROM sources WHERE id=?", (source_id,)
            ).fetchone()
            if not exists:
                return False
            self._delete_source(conn, source_id)
        return True

    def search(self, query: str, limit: int = 5) -> list[dict]:
        query = query.strip()
        if not query or limit < 1:
            return []
        query_vector = self.embedder.embed_query(query)
        with self._connect() as conn:
            has_vec_table = bool(
                self._sqlite_vec_available and _vec_table_exists(conn)
            )
            count = int(
                conn.execute("SELECT COUNT(*) AS count FROM chunks").fetchone()["count"]
            )
            candidate_limit = min(count, max(limit * 4, 20))

            try:
                fts_matches = conn.execute(
                    "SELECT rowid FROM chunk_fts WHERE chunk_fts MATCH ? "
                    "ORDER BY rank LIMIT ?",
                    (_cjk_separate(query), candidate_limit),
                ).fetchall()
            except sqlite3.OperationalError:
                fts_matches = []
            fts_ranks = {
                int(match["rowid"]): rank for rank, match in enumerate(fts_matches)
            }

            if self.use_sqlite_vec:
                if not has_vec_table:
                    raise RuntimeError("资料库缺少 sqlite-vec 向量索引")
                matches = (
                    conn.execute(
                        "SELECT rowid,distance FROM vec_chunks "
                        "WHERE embedding MATCH ? AND k=? ORDER BY distance",
                        (_pack(query_vector), candidate_limit),
                    ).fetchall()
                    if candidate_limit
                    else []
                )
                vector_ids = [int(match["rowid"]) for match in matches]
            else:
                vector_rows = conn.execute("SELECT id,embedding FROM chunks").fetchall()
                ranked_vectors = sorted(
                    (
                        (
                            _cosine(query_vector, _unpack(row["embedding"])),
                            int(row["id"]),
                        )
                        for row in vector_rows
                    ),
                    reverse=True,
                )
                vector_ids = [
                    chunk_id
                    for score, chunk_id in ranked_vectors[:candidate_limit]
                    if score > 0
                ]
            vector_ranks = {chunk_id: rank for rank, chunk_id in enumerate(vector_ids)}

            candidate_ids = set(fts_ranks) | set(vector_ranks)
            if not candidate_ids:
                return []
            scores = {
                chunk_id: (
                    (
                        1.0 / (_RRF_K + fts_ranks[chunk_id] + 1)
                        if chunk_id in fts_ranks
                        else 0.0
                    )
                    + (
                        1.0 / (_RRF_K + vector_ranks[chunk_id] + 1)
                        if chunk_id in vector_ranks
                        else 0.0
                    )
                )
                for chunk_id in candidate_ids
            }
            placeholders = ",".join("?" for _ in candidate_ids)
            rows = conn.execute(
                "SELECT c.id,c.content,c.position,s.id AS source_id,s.title,s.source_name "
                "FROM chunks c JOIN sources s ON s.id=c.source_id "
                f"WHERE c.id IN ({placeholders})",  # noqa: S608
                list(candidate_ids),
            ).fetchall()

        results = [
            {
                "library_kind": self.kind,
                "source_id": row["source_id"],
                "source_name": row["source_name"],
                "title": row["title"],
                "position": row["position"],
                "content": row["content"],
                "score": round(scores[int(row["id"])], 6),
            }
            for row in rows
        ]
        results.sort(
            key=lambda item: (-item["score"], item["source_name"], item["position"])
        )
        if self.reranker:
            try:
                reranker_scores = self.reranker.rerank(
                    query,
                    [f"{item['title']}\n{item['content']}" for item in results],
                )
            except RuntimeError:
                return results[:limit]
            if len(reranker_scores) != len(results):
                raise ValueError("重排模型返回结果无效")
            for item, score in zip(results, reranker_scores):
                item["score"] = round(float(score), 6)
            results.sort(
                key=lambda item: (-item["score"], item["source_name"], item["position"])
            )
        return results[:limit]

    def status(self) -> dict:
        with self._connect() as conn:
            source_count = conn.execute(
                "SELECT COUNT(*) AS count FROM sources"
            ).fetchone()["count"]
            chunk_count = conn.execute(
                "SELECT COUNT(*) AS count FROM chunks"
            ).fetchone()["count"]
        return {
            "kind": self.kind,
            "path": str(self.db_path),
            "source_count": int(source_count),
            "chunk_count": int(chunk_count),
            "vector_backend": "sqlite-vec" if self.use_sqlite_vec else "python",
        }
