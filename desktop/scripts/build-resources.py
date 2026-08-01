"""Build the two first-run SQLite libraries from bundled, attributed sources."""

from __future__ import annotations

import json
from pathlib import Path

from zhiming_life.desktop_api.embedding import FastEmbedProvider
from zhiming_life.desktop_api.library import LibraryStore


PROJECT_DIR = Path(__file__).resolve().parents[2]
RESOURCE_DIR = PROJECT_DIR / "desktop" / "src-tauri" / "resources"


def main() -> None:
    embedding_dir = RESOURCE_DIR / "models" / "embedding"
    if not embedding_dir.is_dir():
        raise SystemExit("缺少内置 embedding 模型目录")

    seed_dir = RESOURCE_DIR / "seeds"
    seed_dir.mkdir(parents=True, exist_ok=True)
    seed_paths = {
        "knowledge": seed_dir / "knowledge.sqlite",
        "cases": seed_dir / "cases.sqlite",
    }
    for path in seed_paths.values():
        path.unlink(missing_ok=True)

    embedder = FastEmbedProvider(model_dir=embedding_dir)
    libraries = {
        kind: LibraryStore(
            kind=kind,
            db_path=path,
            embedder=embedder,
            use_sqlite_vec=True,
        )
        for kind, path in seed_paths.items()
    }
    manifest_path = RESOURCE_DIR / "sources" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in manifest["sources"]:
        content_path = manifest_path.parent / item["file"]
        libraries[item["kind"]].import_text(
            item["title"],
            content_path.read_text(encoding="utf-8"),
            item["source_name"],
        )

    for kind, library in libraries.items():
        status = library.status()
        print(f"{kind}: {status['source_count']} sources, {status['chunk_count']} chunks")


if __name__ == "__main__":
    main()
