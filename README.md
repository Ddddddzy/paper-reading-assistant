# paper-reading-assistant

通用学术论文阅读助手。**说明书和脚本只维护一份**（`src/`），再打包成 Cursor 与 DeepSeek Harness 两套安装包。不含 Web UI。

研究领域由工作目录下的 `paper-reading.config.yml` 配置，不硬编码学科。

## 仓库结构

```text
src/                          ← 唯一真相：人设、技能正文、Python 脚本、领域配置模板
  persona.md
  skills/
  scripts/
  config.example.yml
adapters/dsh/                 ← Harness 外壳（工具组合 agent.cordis.yml）
scripts/pack.mjs              ← 把 src 填进两套包
packages/cursor/              ← 生成物：给 Cursor 用
packages/dsh/paper-reading/   ← 生成物：给 Harness 用
```

改 `src/` 或 `adapters/` 之后执行：

```bash
npm run pack
```

不要手改 `packages/`，下次 pack 会被覆盖。

## 安装：DeepSeek Harness

1. `npm run pack`（若 `packages/` 已是最新可跳过）
2. 把 `packages/dsh/paper-reading/` 整个目录复制到：
   - Windows：`%USERPROFILE%\.dsh\.agent-presets\paper-reading\`
   - macOS / Linux：`$HOME/.dsh/.agent-presets/paper-reading/`
3. 在 DSH 新建会话时选择「论文阅读助手」
4. 把 `src/config.example.yml`（或包内同名文件）复制为**工作目录**下的 `paper-reading.config.yml` 并改领域

## 安装：Cursor

把 `packages/cursor/` 的内容拷进你的论文工作区（或本仓库当工作区）：

```text
你的论文工作区/
  AGENTS.md
  config.example.yml
  scripts/
  .cursor/skills/knowledge-base/
  .cursor/skills/paper-translation/
```

再复制 `config.example.yml` → `paper-reading.config.yml`。

若要装成 Cursor 用户级技能：把 `.cursor/skills/` 下两个目录拷到 `~/.cursor/skills/`（每个技能目录内已带 `scripts/` 副本）。

## 领域配置

`paper-reading.config.yml` 字段：

- `field` / `field_en` / `subfield`：研究领域
- `seed_terms`：术语种子 JSON（`kb.py init --seed`）
- `journals`：推荐刊物/会议
- `textbooks`：名词解释权威教材

## 依赖

- Python 3.8+ 与 pymupdf（`packages/*/scripts/requirements.txt`）
- TeX Live（xelatex + ctex，翻译编译中文 PDF）

## 功能

- PDF 英文文献 → 全中文 LaTeX/PDF（术语单源锁定、公式插图、精读笔记、参考文献）
- 术语知识库 + 知识图谱（`paper-kb/terms.json` 单源）
- 名词解释、段落含义解释、公式逐步推导、论文推荐
