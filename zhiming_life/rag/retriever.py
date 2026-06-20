"""RAG 检索接口 —— 接缝在，自己接语料（stub）。

这里只给 RAG 的**接口形状**：师傅解读前调 `retrieve()` 拿参考资料。默认返回
空字符串——师傅靠模型自身的命理知识解读，依然能跑，只是少了「结论可追溯到古籍」
那一层。想要这一层，自己准备语料、在下面的 TODO 里接上你的检索实现即可。

RAG 的设计思路见 rag/README.md：命例只触发联想、不作判决——「同盘不同命」
是这一层的底线。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zhiming_life.core import Chart


def retrieve(query: str, chart: "Chart | None" = None) -> str:
    """按 query（+ 本盘特征）检索参考资料，返回拼好的文本（默认为空）。

    要接自己的语料，在这里实现，例如：
        hits = your_store.search(query, top_k=3)
        return "\\n\\n".join(format_with_disclaimer(h) for h in hits)

    记得给命例类结果包上「仅供参考 · 同盘不同命」的 wrapper——那不是客套，
    是防止 LLM 拿别人的命例结论硬套到本盘的硬约束。
    """
    return ""
