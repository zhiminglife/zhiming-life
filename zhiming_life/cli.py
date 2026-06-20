"""命令行对话 —— 开源版的「简单对话功能」入口。

跑法：
    python -m zhiming_life

这里给一个朴素的终端 REPL，让你不碰前端也能把整条「问诊 → 排盘 → 解读」链路
跑起来，看清后端在干什么。
"""

from __future__ import annotations

import sys

from dotenv import load_dotenv

from zhiming_life import conductor
from zhiming_life.llm import LLMConfigError

BANNER = """\
　知命·开源版（zhiming-life）
　────────────────────────────
　这是 https://zhiming.life 的开源教学版，演示多智能体命理系统的搭建思路。
　报上你的生辰（如「我 1990 年农历六月十五 午时，公历的也行」），或直接问问题。
　输入 q 退出。
"""


def main() -> int:
    load_dotenv()  # 自动读 .env（python-dotenv），不劳用户手动 export
    print(BANNER)
    history: list[dict] = []
    while True:
        try:
            user = input("你 › ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n　后会有期。")
            return 0
        if not user:
            continue
        if user.lower() in {"q", "quit", "exit"}:
            print("　后会有期。")
            return 0

        try:
            reply, history = conductor.run_turn(history, user)
        except LLMConfigError as e:
            print(f"\n　[配置] {e}\n")
            return 1
        except Exception as e:  # noqa: BLE001 — 终端 demo，任何意外都给人话别炸栈
            print(f"\n　[出错] {e}\n")
            continue

        print(f"\n师傅 › {reply}\n")


if __name__ == "__main__":
    sys.exit(main())
