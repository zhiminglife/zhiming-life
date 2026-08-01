"""Conductor —— 单轮编排（整个「多智能体怎么协作」的可运行缩影）。

这是开源版最值得看的一个文件：它用最少的代码讲清了 zhiming.life 的骨架思路——
**前台分诊 → 确定性预跑盘面 → 专家在事实上推理**。

一轮对话的流程：
  1. supervisor 看完整对话，判断意图、收集生辰、决定路由。
  2. 还缺信息 / 非命理 → 直接把 supervisor 的话回给用户（问诊或回绝）。
  3. 信息齐、走八字 → 先用纯 Python 把盘排死（core.paipan），
     再把客观盘面交给宗师做分段解读。

这条主干上可以挂更多术数专家、更深的能力和各种工程设施，但骨架就是这一条。
这里只保留主干，让你一眼看懂「supervisor + specialist + 确定性工具」是怎么咬合的。
"""

from __future__ import annotations

from zhiming_life.agents import bazi_master, supervisor
from zhiming_life.core import paipan


def run_turn(
    history: list[dict],
    user_message: str,
    *,
    known_birth: dict | None = None,
    references: str = "",
    related_person_context: str = "",
) -> tuple[str, list[dict]]:
    """处理一轮用户输入，返回（给用户的回复，更新后的对话历史）。

    history 是 [{"role": "user"|"assistant", "content": str}, ...]。
    保持 agent 无状态：每轮把完整历史喂进去，不在 agent 内部存会话——
    这让重试 / 流式 / 多实例都简单——agent 不存会话，每轮把上下文装配好喂进去。
    """
    history = [*history, {"role": "user", "content": user_message}]

    birth_is_complete = (
        bool(known_birth)
        and all(
            known_birth.get(key) is not None
            for key in ("year", "month", "day", "hour", "calendar")
        )
        and int(known_birth["hour"]) >= 0
    )
    decision = None if birth_is_complete else supervisor.decide(history)

    # 生辰没齐 / 非命理：supervisor 自己接住，不惊动宗师。
    if decision is not None and not (
        decision.ready and decision.route == "bazi" and decision.birth
    ):
        reply = decision.reply or "再说说看？"
        return reply, [*history, {"role": "assistant", "content": reply}]

    # 信息齐：确定性排盘 → 宗师解读
    b = known_birth if birth_is_complete else decision.birth
    chart = paipan(
        year=int(b["year"]),
        month=int(b["month"]),
        day=int(b["day"]),
        hour=int(b["hour"]),
        calendar=b.get("calendar", "solar"),
        is_leap_month=bool(b.get("is_leap_month", False)),
    )
    # 用户这一轮的原话作为「想了解什么」——supervisor 已确认是综述类需求
    reading = bazi_master.read(
        chart,
        question=user_message,
        history=history[:-1],
        references=references,
        related_person_context=related_person_context,
    )
    return reading, [*history, {"role": "assistant", "content": reading}]
