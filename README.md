# 知命 · 开源版（zhiming-life）

> [**zhiming.life**](https://zhiming.life) 的开源本地桌面版：自己配置模型，命册、咨询和 RAG 资料保存在自己的电脑上；同时保留完整的多智能体命理系统教学骨架。

---

## 这个项目提供什么

知命不只是给大模型套一层命理提示词，而是把问诊、确定性排盘、资料检索和专家解读拆成可检查的步骤。当前仓库已经提供一条真实可运行的桌面主线：

- **macOS / Windows 桌面壳**：Tauri 2 + React，Python FastAPI 作为 sidecar
- **多人命册**：一个本地使用者管理多位命主，双人咨询可关联两份命册
- **多智能体编排**：问诊分诊（Supervisor）→ 确定性排盘 → 专家解读（Specialist）
- **确定性算法层**：八字排盘基于公开历法，算法只给客观事实，评估交给上层
- **双 RAG 库**：知识库与匿名命例库使用两个独立 SQLite 文件，支持 TXT / Markdown 导入、内容去重、替换和删除
- **本地向量检索**：FastEmbed + ONNX Runtime + sqlite-vec，并增加本地 reranker
- **完整离线资源**：embedding、reranker、预填充知识库和命例库随安装包提供
- **自定义模型**：支持任意 OpenAI 兼容接口；API Key 只写入 macOS Keychain / Windows 凭据库
- **依据可见**：每轮咨询实际命中的本地知识和匿名命例会显示在右栏

深入的设计思路见 **[ARCHITECTURE.md](ARCHITECTURE.md)**。

## 桌面版开发运行

需要 Python 3.10+、Node.js 20+，以及通过 [rustup](https://rustup.rs/) 安装的 Rust stable。

```bash
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e ".[desktop,dev]"

cd desktop
npm install
npm run dev                          # FastAPI + Vite 浏览器开发
# 或 npm run tauri:dev               # Tauri 桌面窗口
```

首次打开先填写 API 地址、模型名和 API Key，再新增命主。内置 ONNX 模型和预填充资料库随安装包提供，不需要首次启动时下载。

### 构建安装包

macOS Apple Silicon DMG 和 Windows x64 NSIS 安装包统一由 GitHub Actions 构建。工作流会先在对应系统运行 Python、React、TypeScript、Rust 和依赖安全检查；全部通过后才构建 sidecar 与安装包，并继续验证离线 RAG、安装包内容和应用启动。验证通过的产物可以在对应 Actions 任务的 Artifacts 中下载。

需要手动构建时，在 GitHub 仓库的 Actions 页面运行 `Desktop validation and packages`。打包配置和验证脚本全部保存在本仓库中，不依赖闭源桌面运行时。

## 保留的终端教学版

```bash
# 1. 安装依赖
pip install -e .

# 2. 配置任意 OpenAI 兼容端点
cp .env.example .env

# 3. 启动终端对话
python -m zhiming_life
```

终端版继续从 `.env` 读取模型配置，用于快速体验「问诊 → 排盘 → 解读」。桌面版在界面中配置模型，不把 API Key 写入 `.env` 或 SQLite。

## 代码导览

```text
zhiming_life/
├── conductor.py          ← 单轮编排，串联问诊、排盘、检索和解读
├── agents/
│   ├── supervisor.py     ← 问诊与路由
│   └── bazi_master.py    ← 在客观盘面与检索依据上解读
├── core/                 ← 确定性八字排盘和五行关系
├── desktop_api/          ← FastAPI、SQLite、双 RAG、系统密钥存储
├── prompts/              ← prompt 结构骨架
├── rag/                  ← 终端版兼容检索接口
└── vendor/               ← 自维护历法库

desktop/
├── src/                  ← React 三栏桌面界面
├── src-tauri/            ← Tauri 2 壳层、平台配置和图标
├── scripts/              ← sidecar、资源构建和安装包烟测
└── e2e/                  ← Windows 安装后原生 E2E
```

## 当前边界

当前实现八字咨询、多命主、本地对话和双 RAG。暂不提供紫微、登录、支付、云同步、后台、OCR/PDF 导入和流式输出。命例必须由用户确认匿名化后才能导入。解读质量取决于接入的模型和资料质量。

## 免责声明

命理内容仅供文化研究与娱乐参考，不构成医疗、法律、投资等任何决策建议。信命不认命——命盘揭示倾向，不预设终局。

## License

MIT。

---

<sub>由 [zhiming.life](https://zhiming.life) 维护</sub>
