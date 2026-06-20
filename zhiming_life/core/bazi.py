"""八字排盘 —— 确定性纯函数。

排盘只是把生辰按传统历法换算成四柱干支，规则是公开的、千年不变的——花功夫的
地方在「怎么解读这盘」，不在「怎么排这盘」。所以这一层很干净，放心拿去学。

历法换算用 `zhiming_life/vendor/` 里自维护的 lunar_python（6tail，MIT）——地基
的东西，固定版本自己掌控更稳。本文件再兜两处边界：越界日校验、晚子时时柱。

设计原则：
  · 只输出**客观干支 + 五行计数**，不在这一层下任何「旺衰 / 吉凶」judgement。
    为什么？因为「金克木」是抽象关系，落到具体盘上是「木受损」还是「木坚金缺」，
    取决于旺衰 + 用神 + 时位——那是解读层（师傅）的事，不是排盘层的事。
    这条「算法只给事实、评估交给上层」的边界，是整个系统能讲清楚的关键。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from zhiming_life.core.wuxing import GAN_WUXING, count_wuxing
from zhiming_life.vendor.lunar_python import Lunar, LunarMonth, Solar

Calendar = Literal["solar", "lunar"]

_GAN = "甲乙丙丁戊己庚辛壬癸"


class BirthDateError(ValueError):
    """生辰日期越界 / 非法。

    message 是面向用户的安全中文，可直接示人——上层据此友好追问。专设子类，是为
    让调用方能与「内部技术 ValueError」区分捕获。仍是 ValueError 子类，既有
    `except ValueError` 的调用方不受影响。
    """


def _validate_solar(year: int, month: int, day: int) -> None:
    """公历日期合法性——用标准库兜住越界日（如「2月30日」），拒绝它，
    防越界日期被无声算成错的四柱。"""
    from calendar import monthrange
    if not (1 <= month <= 12):
        raise BirthDateError(f"月份非法：{month}")
    max_day = monthrange(year, month)[1]
    if not (1 <= day <= max_day):
        raise BirthDateError(f"公历 {year}-{month:02d} 没有第 {day} 天")


def _validate_lunar(year: int, month: int, day: int, is_leap_month: bool) -> None:
    """农历日期合法性——与 _validate_solar 对称。

    越界农历日（某农历月并无的日、或某年并无的闰某月）先用 LunarMonth 兜住、
    给可读的中文错（在产生处拦，不把脏日期喂进下游）。
    """
    if not (1 <= month <= 12):
        raise BirthDateError(f"农历月份非法：{month}")
    # 负月 = 闰月（与 paipan 一致）；该年无此（闰）月时 fromYm 返回 None
    lm = LunarMonth.fromYm(year, -month if is_leap_month else month)
    if lm is None:
        raise BirthDateError(
            f"农历 {year} 年没有闰{month}月" if is_leap_month
            else f"农历 {year} 年无此月：{month}"
        )
    max_day = lm.getDayCount()
    if not (1 <= day <= max_day):
        kind = f"闰{month}月" if is_leap_month else f"{month}月"
        raise BirthDateError(f"农历 {year} 年{kind}只有 {max_day} 天，没有第 {day} 天")


def _fix_late_zi_hour(day_gz: str, hour_pillar: str) -> str:
    """晚子时（23:xx）时柱修正。

    实战派主流（sect=2）晚子时日柱归当日，时干也应以**当日**日干五鼠遁起子时。
    这里按当日日干重起子时的时干，时支不变（实测癸日子时为「壬子」）。
    """
    day_gan_idx = _GAN.index(day_gz[0])
    correct_gan = _GAN[(day_gan_idx * 2) % 10]  # 五鼠遁：甲己→甲子 / 戊癸→壬子 …
    return correct_gan + hour_pillar[1:]


@dataclass
class Chart:
    """一张排好的八字盘——只装客观事实。"""

    year: str   # 年柱，如「庚午」
    month: str  # 月柱
    day: str    # 日柱
    hour: str   # 时柱

    @property
    def day_master(self) -> str:
        """日主（日干）——命主本人，解读的圆心。"""
        return self.day[0]

    @property
    def day_master_wuxing(self) -> str:
        return GAN_WUXING[self.day_master]

    @property
    def pillars(self) -> list[str]:
        return [self.year, self.month, self.day, self.hour]

    @property
    def wuxing_counts(self) -> dict[str, int]:
        """全盘八字（四干 + 四支本气）的五行分布——看偏枯还是中和的第一眼。"""
        return count_wuxing(self.pillars)

    def render(self) -> str:
        """排盘结果的纯文本呈现——注入师傅 prompt 用，也方便调试肉眼看。"""
        lines = ["四柱：", f"  年 {self.year}", f"  月 {self.month}",
                 f"  日 {self.day}（日主 {self.day_master}·{self.day_master_wuxing}）",
                 f"  时 {self.hour}"]
        counts = self.wuxing_counts
        dist = "  ".join(f"{w}{counts.get(w, 0)}" for w in "木火土金水")
        lines.append(f"五行分布：{dist}")
        return "\n".join(lines)


def paipan(
    year: int,
    month: int,
    day: int,
    hour: int,
    *,
    minute: int = 0,
    calendar: Calendar = "solar",
    is_leap_month: bool = False,
) -> Chart:
    """排盘主入口。

    Args:
        year/month/day/hour: 生辰（hour 为 24 小时制）
        calendar: "solar"（公历）或 "lunar"（农历）
        is_leap_month: 农历闰月标志（calendar="lunar" 时有效）

    Returns:
        Chart——四柱 + 日主 + 五行分布。

    Raises:
        BirthDateError: 生辰日期越界 / 非法（面向用户的中文消息）。
    """
    if calendar == "lunar":
        _validate_lunar(year, month, day, is_leap_month)
        # lunar-python 约定：负月份表示闰月
        lunar_month = -month if is_leap_month else month
        lunar = Lunar.fromYmdHms(year, lunar_month, day, hour, minute, 0)
    elif calendar == "solar":
        _validate_solar(year, month, day)
        solar = Solar.fromYmdHms(year, month, day, hour, minute, 0)
        lunar = solar.getLunar()
    else:
        raise ValueError(f"calendar 必须是 'solar' 或 'lunar'，收到：{calendar!r}")

    ec = lunar.getEightChar()

    hour_pillar = ec.getTime()
    if hour == 23:  # 晚子时：修正时干偏移（见 _fix_late_zi_hour）
        hour_pillar = _fix_late_zi_hour(ec.getDay(), hour_pillar)

    return Chart(
        year=ec.getYear(),
        month=ec.getMonth(),
        day=ec.getDay(),
        hour=hour_pillar,
    )
