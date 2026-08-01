"""八字宗师 agent —— 在算好的盘面上做分段解读。"""

from __future__ import annotations

from zhiming_life import llm
from zhiming_life.core import Chart
from zhiming_life.prompts import BAZI_MASTER_SYSTEM, build_context
from zhiming_life.rag import retrieve


def read(
    chart: Chart,
    question: str,
    history: list[dict],
    *,
    references: str = "",
    related_person_context: str = "",
) -> str:
    """生成一段解读。

    流程演示了「确定性预跑 + 知识投喂 + 师傅推理」的接缝：
      1. chart 是 Python 算死的客观盘面（不让 LLM 自己排盘）。
      2. retrieve() 是 RAG 接口——接上语料就能引经典 / 命例；返回空时
         师傅靠自身知识解读（见 rag/README.md）。
      3. 师傅 prompt + 盘面 + 问题 → 一段分段递进的 markdown。
    """
    refs = retrieve(query=question or "命运综述", chart=chart)
    context = build_context(chart.render(), question)
    if refs:
        context += "\n\n【参考资料（仅供联想，不可整体类比到本盘）】\n" + refs
    if references:
        context += "\n\n【本地知识与匿名命例（仅供联想，不作判决）】\n" + references
    if related_person_context:
        context += "\n\n【合看命主（客观排盘）】\n" + related_person_context

    messages = [*history, {"role": "user", "content": context}]
    return llm.chat(BAZI_MASTER_SYSTEM, messages, temperature=0.8)
