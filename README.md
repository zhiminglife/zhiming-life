# 知命 · 开源版（zhiming-life）

> 一个**懂行的人愿意用**的命理 AI 该怎么搭？这是 [**zhiming.life**](https://zhiming.life)
> 的开源版——把多智能体命理系统的**构建思路**讲清楚，并附一个能跑的**简单对话 demo**。

---

## 这个项目想给你什么

市面上的「AI 算命」大多是 GPT 套个壳：丢一句生辰，让大模型自由发挥。知命想做的是
另一种东西——**推理流程看得见**的多智能体系统。这个开源版给你一个能跑起来、能改、
能学的最小实现：

- ✅ **多智能体编排骨架**：前台问诊分诊（Supervisor）→ 确定性排盘 → 专家解读（Specialist）怎么咬合
- ✅ **确定性算法层**：八字排盘（基于公开历法）+「算法只给客观事实、评估交给上层」的边界设计
- ✅ **prompt 工程思路**：身份 / 铁律 / 结构化分段输出的**骨架**
- ✅ **RAG 设计思路**：怎么给师傅投喂参考资料
- ✅ **一个能跑的终端对话 demo**

深入的设计思路看 **[ARCHITECTURE.md](ARCHITECTURE.md)**。

## 快速开始

```bash
# 1. 装依赖（建议用虚拟环境）
pip install -e .

# 2. 配好 LLM（任意 OpenAI 兼容端点：OpenAI / DeepSeek / 本地 Ollama / 中转）
cp .env.example .env        # 然后编辑 .env 填上你的 API key
#   或直接 export ZHIMING_LIFE_API_KEY=sk-...

# 3. 跑起来——终端对话
python -m zhiming_life
```

然后报上生辰（公历农历都行），或直接问问题，看完整的「问诊 → 排盘 → 解读」链路。

> 启动时会用 `python-dotenv` 自动加载当前目录的 `.env`，不用手动 `export`。

## 代码导览（建议阅读顺序）

```
zhiming_life/
├── conductor.py          ← 先看这个：单轮编排，一眼看懂多智能体怎么协作
├── agents/
│   ├── supervisor.py     ← 问诊 + 路由，输出结构化决策
│   └── bazi_master.py    ← 在算好的盘面上做分段解读
├── core/
│   ├── bazi.py           ← 八字排盘（真能跑，历法库在 vendor/ 自带）
│   └── wuxing.py         ← 五行生克映射 +「只给关系不给方向」的边界
├── prompts/              ← prompt 结构骨架（见 prompts/README.md）
├── rag/                  ← RAG 接口（自己接语料，见 rag/README.md）
├── vendor/               ← 自维护的历法库（见 vendor/README.md）
└── cli.py                ← 终端对话入口
```

## 说明

- 这是一个**最小骨架**，不是生产级：没有鉴权、限流、持久化、流式、并发控制——
  那些工程设施会把骨架淹没，这里有意省掉，专心讲清「多智能体怎么搭」。
- 解读质量取决于你接的模型 + 你自己往 prompt / RAG 里填的内容。

## 免责声明

命理内容仅供文化研究与娱乐参考，不构成医疗、法律、投资等任何决策建议。
信命不认命——命盘揭示倾向，不预设终局。

## License

MIT。算法与骨架随便用、随便改，拿去搭你自己的东西。

---

<sub>由 [zhiming.life](https://zhiming.life) 维护</sub>
