"""五行 / 干支基础映射 —— 数据表直接取自 lunar-python，不自己维护一份。

这一层是命理算法的「字典」：哪个天干属什么五行、五行之间谁生谁克。

**干 / 支的五行映射表，lunar-python 已经提供了**（`LunarUtil.WU_XING_GAN` /
`WU_XING_ZHI`），所以这里直接引用库的表，不手抄一份——手抄的副本迟早和库脱节，
也违背「能用第三方库就别自己实现」的原则。

**五行相生 / 相克的关系**库没有暴露，是命理领域的两个小常量，这里定义。它演示了
一条关键工程边界——

**只给关系，不给方向。**

「木生火」「金克木」是抽象的五行关系。但落到一张具体的盘上，到底是「金克木 →
木受损」还是「弱金克旺木 → 木坚金缺、反伤金」，取决于旺衰、用神、时位。算法层
**绝不**把「克」翻译成「受损」——那是易经辩证思维（生不必喜、克不必凶、物极必反）
的工程化。要不要喜、要不要凶，留给解读层（师傅）按旺衰 + 用神综合判断。
"""

from __future__ import annotations

from zhiming_life.vendor.lunar_python.util import LunarUtil

# 天干 / 地支五行——直接用 lunar-python 提供的现成映射，不另维护副本
GAN_WUXING: dict[str, str] = LunarUtil.WU_XING_GAN  # {'甲':'木', '乙':'木', ...}
ZHI_WUXING: dict[str, str] = LunarUtil.WU_XING_ZHI  # {'子':'水', '丑':'土', ...}（地支取本气）

# 五行相生：A 生 B（木→火→土→金→水→木）。lunar-python 未暴露此关系，命理小常量自定义。
SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}

# 五行相克：A 克 B（木克土、土克水、水克火、火克金、金克木）
KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}


def relation(a: str, b: str) -> str:
    """返回五行 a 对 b 的**抽象关系**——刻意不下吉凶 / 强弱判断。

    可能值：同 / 生（a 生 b）/ 被生（b 生 a）/ 克（a 克 b）/ 被克（b 克 a）。
    """
    if a == b:
        return "同"
    if SHENG.get(a) == b:
        return "生"
    if SHENG.get(b) == a:
        return "被生"
    if KE.get(a) == b:
        return "克"
    if KE.get(b) == a:
        return "被克"
    return "无"


def count_wuxing(pillars: list[str]) -> dict[str, int]:
    """统计四柱八字（四天干 + 四地支本气）的五行分布。

    用 lunar-python 的五行表查每个字，自己只做计数聚合。
    """
    counts = {w: 0 for w in "木火土金水"}
    for pillar in pillars:
        gan, zhi = pillar[0], pillar[1]
        counts[GAN_WUXING[gan]] += 1
        counts[ZHI_WUXING[zhi]] += 1
    return counts
