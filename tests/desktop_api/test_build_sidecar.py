from __future__ import annotations

import runpy
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "desktop" / "scripts" / "build-sidecar.py"


def load_build_script() -> dict[str, object]:
    return runpy.run_path(str(SCRIPT))


def test_windows_sidecar_hides_its_console_before_python_starts() -> None:
    command_builder = load_build_script()["pyinstaller_command"]

    command = command_builder("win32")

    option_index = command.index("--hide-console")
    assert command[option_index + 1] == "hide-early"


def test_non_windows_sidecar_does_not_receive_windows_only_console_option() -> None:
    command_builder = load_build_script()["pyinstaller_command"]

    command = command_builder("darwin")

    assert "--hide-console" not in command
