# paper-reading-assistant

DeepSeek Harness 的自控论文阅读助手：一个 agent 预设 + 一个 Web UI 双栏阅读插件。

## 组成
- `preset/paper-reading/` — agent 预设（persona、两个技能、翻译/知识库脚本、术语种子表）
- `ui-plugin/` — 「论文对照阅读」双栏 PDF 阅读器插件（动态 Cordis 插件）

## 预设安装
1. 把 `preset/paper-reading/` 整个目录复制到 `${DSH_HOME:-$HOME/.dsh}/.agent-presets/paper-reading/`。
2. 在 DSH 新建会话时选择「自控论文阅读助手」。

## UI 插件激活
见 `ui-plugin/README.md`（动态插件，用 `cordis_define` / `cordis_run` 激活）。

## 依赖
- Python 3.8+ 与 pymupdf（翻译抽取 + 阅读器页渲染）
- TeX Live（xelatex + ctex，翻译编译中文 PDF）

## 功能一览（预设）
- PDF 英文文献 → 全中文 LaTeX/PDF（术语单源锁定、公式插图正常插入、结构化精读笔记、参考文献提取）
- 术语知识库 + 知识图谱（`paper-kb/terms.json` 单源，别名归一、来源/提及追踪）
- 名词解释、段落含义解释、公式逐步推导、论文推荐
