"""Prompt 骨架层。

这里的 prompt 都是**示例骨架**：展示一份命理 prompt 的结构，填入你自己的
内容即可。设计思路见 prompts/README.md。
"""

from zhiming_life.prompts.bazi_master import BAZI_MASTER_SYSTEM, build_context
from zhiming_life.prompts.supervisor import SUPERVISOR_SYSTEM

__all__ = ["SUPERVISOR_SYSTEM", "BAZI_MASTER_SYSTEM", "build_context"]
