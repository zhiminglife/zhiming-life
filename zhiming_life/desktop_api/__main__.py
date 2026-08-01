"""Run the local desktop API from source."""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path


def _parent_is_alive(pid: int) -> bool:
    if os.name == "nt":
        import ctypes

        handle = ctypes.windll.kernel32.OpenProcess(0x00100000, False, pid)
        if not handle:
            return False
        try:
            return ctypes.windll.kernel32.WaitForSingleObject(handle, 0) == 0x00000102
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _exit_when_parent_stops(pid: int) -> None:
    while _parent_is_alive(pid):
        time.sleep(1)
    os._exit(0)


def main() -> None:
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - desktop dependency
        raise SystemExit("请先安装桌面端依赖：pip install -e '.[desktop]'") from exc

    from .app import create_app

    data_dir = Path(os.getenv("ZHIMING_LIFE_DATA_DIR", ".zhiming-life-data"))
    resource_dir = os.getenv("ZHIMING_LIFE_RESOURCE_DIR")
    token = os.getenv("ZHIMING_LIFE_API_TOKEN")
    port = int(os.getenv("ZHIMING_LIFE_API_PORT", "8765"))
    parent_pid = os.getenv("ZHIMING_LIFE_PARENT_PID")
    if parent_pid:
        threading.Thread(
            target=_exit_when_parent_stops,
            args=(int(parent_pid),),
            daemon=True,
        ).start()
    uvicorn.run(
        create_app(
            data_dir=data_dir,
            api_token=token,
            resource_dir=resource_dir,
        ),
        host="127.0.0.1",
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
