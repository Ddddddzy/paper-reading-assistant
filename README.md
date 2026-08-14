# paper-reading-assistant

学术论文阅读助手：在 Cursor 或 DeepSeek Harness 中使用的 Agent 预设与本地脚本。人设、技能说明与 Python 脚本统一维护在 `src/`，经打包生成两套安装包。研究领域由工作目录下的 `paper-reading.config.yml` 配置，不在代码中硬编码学科。

## 功能

- 英文 PDF → 全中文 LaTeX / PDF（按英文段落分段；术语表、精读笔记、参考文献）
- 术语知识库与知识图谱（工作区 `paper-kb/`；`terms.json` 为翻译与名词解释的唯一术语源）
- 名词解释、段落含义解释、公式逐步推导、按配置刊物名单的论文推荐

翻译流程中，PDF 抽取、切段、术语预替换、插图裁剪、LaTeX 编译由脚本完成；模型负责段落翻译、公式转写、图题与笔记，以及上述答疑类任务。

## 仓库结构

```text
src/                          源内容：人设、技能、脚本、配置模板
  persona.md
  skills/
  scripts/
  config.example.yml
adapters/dsh/                 DeepSeek Harness 适配（agent.cordis.yml 等）
scripts/pack.mjs              将 src 填入 packages/
packages/cursor/              生成物：Cursor
packages/dsh/paper-reading/   生成物：DeepSeek Harness 预设
```

修改 `src/` 或 `adapters/` 后执行：

```bash
npm run pack
```

`packages/` 为生成结果，请勿手改（再次 pack 会覆盖）。

## 依赖

- Python 3.8+，安装 `pymupdf`：  
  `python -m pip install -r packages/dsh/paper-reading/scripts/requirements.txt`  
  （Cursor 包内路径同理。）
- TeX Live：`xelatex` 与 `ctex`（用于编译中文译文 PDF）
- 运行环境各自配置的模型 API（DeepSeek 或其他兼容接口）

## 安装：DeepSeek Harness

1. 在本仓库根目录执行 `npm run pack`（若已包含最新 `packages/` 可跳过）。
2. 将 `packages/dsh/paper-reading/` 复制为：
   - Windows：`%USERPROFILE%\.dsh\.agent-presets\paper-reading\`
   - macOS / Linux：`$HOME/.dsh/.agent-presets/paper-reading/`
3. 启动 Harness，新建会话，选择预设「论文阅读助手」。
4. 将会话工作目录设为论文库根目录；复制 `config.example.yml` 为该目录下的 `paper-reading.config.yml` 并填写领域等信息。

更新预设文件后，建议新开会话再使用。

## 安装：Cursor

1. `npm run pack`。
2. 将 `packages/cursor/` 内容放入论文工作区（也可直接以本仓库为工作区）：

```text
工作区/
  AGENTS.md
  config.example.yml
  scripts/
  .cursor/skills/knowledge-base/
  .cursor/skills/paper-translation/
```

3. 复制 `config.example.yml` → `paper-reading.config.yml`。

若安装为 Cursor 用户级技能：将 `.cursor/skills/` 下两个技能目录复制到 `~/.cursor/skills/`（技能目录内已含 `scripts/`）。

## 工作目录约定

```text
工作区/
  paper-reading.config.yml
  paper-kb/
    terms.json
    papers.json
    graph.mmd
  <slug>/
    <slug>.pdf                 原文
    translation/
      extracted.json
      prepared.json
      translated.json
      paper.tex
      paper.pdf                全中文译文
      pages/ images/ figures/
      cache.json
```

`paper-kb/` 位于工作区根目录，跨论文累积。每篇论文使用独立 `<slug>/` 目录存放原文与翻译产物。

## 翻译流程概要

1. 创建 `<slug>/` 并复制原文 PDF。  
2. 脚本 `extract`：抽取文本与页面/内嵌图。  
3. 脚本 `preprocess`：切段、按 `terms.json` 预替换术语、标记公式段、抽取参考文献。  
4. 脚本 `crop-figures`：按坐标裁剪插图至 `figures/`。  
5. 模型：按分块翻译空段落，整理为 `translated.json`。  
6. 脚本 `cache-save`、`assemble`：写入缓存并用 xelatex 生成 `paper.pdf`。  
7. 将新术语与论文条目写入 `paper-kb/`；需要时运行 `kb.py graph` 更新图谱。

技能说明要求：不要通读整份 `prepared.json`；无视觉能力时不要调用读图工具做插图定位；抽取/预处理/裁图/汇编以对应脚本为准。

## 领域配置

`paper-reading.config.yml` 主要字段：

| 字段 | 说明 |
|------|------|
| `field` / `field_en` / `subfield` | 研究领域与子方向 |
| `seed_terms` | 术语种子 JSON 路径，供 `kb.py init --seed` 使用 |
| `journals` | 论文推荐时的刊物/会议名单 |
| `textbooks` | 名词解释时的权威教材参考 |

模板见 `src/config.example.yml`。

## 局限

- 无文本层的扫描版 PDF 需先 OCR。  
- 复杂表格可能仅能作为图像或非结构化文本处理。  
- 公式图像在无多模态视觉时难以可靠转为 LaTeX；文本公式与脚本裁图更稳定。  
- 本仓库提供 Agent 预设与脚本，不包含独立的 Web 对照阅读界面。

## 许可与版权

代码按仓库许可使用。请勿将受版权保护的论文 PDF 或未获授权的译文发布到公开仓库。
