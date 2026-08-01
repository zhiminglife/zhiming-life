import os

from zhiming_life.desktop_api.__main__ import _parent_is_alive


def test_parent_liveness_check_distinguishes_current_and_missing_process() -> None:
    assert _parent_is_alive(os.getpid()) is True
    assert _parent_is_alive(2_147_483_647) is False
