"""Build the Python API as the target-named Tauri sidecar binary."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[2]
TAURI_DIR = PROJECT_DIR / "desktop" / "src-tauri"


def target_triple() -> str:
    result = subprocess.run(
        ["rustc", "-vV"], check=True, capture_output=True, text=True
    )
    for line in result.stdout.splitlines():
        if line.startswith("host: "):
            return line.removeprefix("host: ").strip()
    raise RuntimeError("rustc 未返回 host target")


def pyinstaller_command(platform: str) -> list[str]:
    build_dir = PROJECT_DIR / "build" / "pyinstaller"
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
    ]
    if platform == "win32":
        command.extend(["--hide-console", "hide-early"])
    command.extend(
        [
            "--name",
            "zhiming-api",
            "--specpath",
            str(build_dir),
            "--workpath",
            str(build_dir / "work"),
            "--distpath",
            str(build_dir / "dist"),
            "--collect-all",
            "fastembed",
            "--collect-all",
            "onnxruntime",
            "--collect-all",
            "sqlite_vec",
            "--collect-all",
            "keyring",
            "--exclude-module",
            "keyring.testing",
            "--exclude-module",
            "pytest",
            "--exclude-module",
            "py",
            str(PROJECT_DIR / "desktop" / "scripts" / "sidecar_entry.py"),
        ]
    )
    return command


def main() -> None:
    name = "zhiming-api"
    build_dir = PROJECT_DIR / "build" / "pyinstaller"
    cache_dir = build_dir / "cache"
    dist_dir = build_dir / "dist"
    build_env = {**os.environ, "PYINSTALLER_CONFIG_DIR": str(cache_dir)}
    subprocess.run(
        pyinstaller_command(sys.platform),
        cwd=PROJECT_DIR,
        env=build_env,
        check=True,
    )
    suffix = ".exe" if sys.platform == "win32" else ""
    source = dist_dir / f"{name}{suffix}"
    destination = TAURI_DIR / "binaries" / f"{name}-{target_triple()}{suffix}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    print(destination)


if __name__ == "__main__":
    main()
