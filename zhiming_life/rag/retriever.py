"""原终端 demo 的 RAG 兼容接口。

桌面端使用 desktop_api.library 中的双库检索，并由 API 在调用 conductor 时注入
实际命中内容。这里保持空实现，避免改变原有 CLI 的轻量运行方式。

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
