# paper-reading-assistant

DeepSeek Harness 的通用学术论文阅读助手：一个 agent 预设 + 一个 Web UI 双栏阅读插件。研究领域由用户自定义的 `paper-reading.config.yml` 配置，不硬编码任何具体学科。

## 组成
- `preset/paper-reading/` — agent 预设（persona、两个技能、翻译/知识库脚本）
- `ui-plugin/` — 「论文对照阅读」双栏 PDF 阅读器插件（动态 Cordis 插件）
- `config.example.yml` — 领域配置模板（复制到工作目录并改名 `paper-reading.config.yml`）

## 预设安装
1. 把 `preset/paper-reading/` 整个目录复制到 `${DSH_HOME:-$HOME/.dsh}/.agent-presets/paper-reading/`。
2. 在 DSH 新建会话时选择「论文阅读助手」。

## 领域配置
把 `config.example.yml` 复制为**工作目录下的 `paper-reading.config.yml`**，填你的领域：
- `field` / `field_en` / `subfield`：研究领域（中英文名、子方向）
- `seed_terms`：可选，术语种子 JSON 路径（`kb.py init --seed` 用它初始化术语库）
- `journals`：论文推荐的权威刊物/会议
- `textbooks`：名词解释的权威教材

助手会在每次会话读取该配置，术语译名、权威来源、推荐刊物都以它为准；不填则用通用方式。

## UI 插件激活
见 `ui-plugin/README.md`（动态插件，用 `cordis_define` / `cordis_run` 激活）。

## 依赖
- Python 3.8+ 与 pymupdf（翻译抽取 + 阅读器页渲染）
- TeX Live（xelatex + ctex，翻译编译中文 PDF）

## 功能一览（预设）
- PDF 英文文献 → 全中文 LaTeX/PDF（术语单源锁定、公式插图正常插入、结构化精读笔记、参考文献提取）
- 术语知识库 + 知识图谱（`paper-kb/terms.json` 单源，别名归一、来源/提及追踪）
- 名词解释、段落含义解释、公式逐步推导、论文推荐
