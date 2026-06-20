# vendor/ —— 自维护的历法库

排盘是推命的地基。这里把历法库**复制进项目**、固定版本、自己维护，不走 `pip`——
地基的东西，自己掌控版本更稳。

## lunar_python/

- 来源：[6tail/lunar-python](https://github.com/6tail/lunar-python)（MIT License）
- 用途：八字四柱 / 大运流年 / 取干支五行（寿星万年历算法，分钟级节气）
- 纯 Python，无外部依赖

排盘相关的边界情况（越界日校验、晚子时时柱）在
`zhiming_life/core/bazi.py` 的 wrapper 里统一处理。

### License

lunar-python 为 MIT License，版权归 [6tail](https://github.com/6tail) 所有，随源码保留。
