"""排盘 / 五行的单元测试——不需要 LLM key 就能跑：

    pip install -e ".[dev]"
    pytest

确定性算法层先有纯函数 + 单元测试，再接 agent——这是项目的开发铁律。
"""

import pytest

from zhiming_life.core import paipan
from zhiming_life.core.bazi import BirthDateError
from zhiming_life.core.wuxing import count_wuxing, relation


def test_paipan_solar():
    c = paipan(1990, 6, 15, 14, calendar="solar")
    assert c.pillars == ["庚午", "壬午", "辛亥", "乙未"]
    assert c.day_master == "辛"
    assert c.day_master_wuxing == "金"


def test_rejects_out_of_range_solar_date():
    # 越界公历日应被拒绝（2 月没有 30 号），不被无声算成错的四柱
    with pytest.raises(BirthDateError):
        paipan(1991, 2, 30, 10, calendar="solar")


def test_rejects_out_of_range_lunar_date():
    # 农历八月只有 30 天，没有第 31 天
    with pytest.raises(BirthDateError):
        paipan(2007, 8, 31, 10, calendar="lunar")


def test_late_zi_hour():
    # 晚子时（23:xx）时支应为「子」
    assert paipan(1990, 6, 15, 23, calendar="solar").hour[1] == "子"


def test_paipan_lunar_matches_solar():
    # 1990 公历 6/15 == 农历五月廿三
    solar = paipan(1990, 6, 15, 14, calendar="solar")
    lunar = paipan(1990, 5, 23, 14, calendar="lunar")
    assert solar.pillars == lunar.pillars


def test_wuxing_counts_sum_to_eight():
    c = paipan(1990, 6, 15, 14, calendar="solar")
    counts = c.wuxing_counts
    assert sum(counts.values()) == 8  # 四干 + 四支本气


def test_relation_is_abstract_not_judgement():
    # 只给抽象关系，不给「受损 / 受益」方向
    assert relation("金", "木") == "克"
    assert relation("木", "金") == "被克"
    assert relation("水", "木") == "生"
    assert relation("木", "水") == "被生"
    assert relation("金", "金") == "同"


def test_count_wuxing_helper():
    assert count_wuxing(["甲子", "甲子"]) == {"木": 2, "火": 0, "土": 0, "金": 0, "水": 2}
