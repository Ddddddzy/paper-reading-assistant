---
name: knowledge-base
description: Use when adding, updating, or querying the term knowledge base and knowledge graph (paper-kb), or when recording a term's meaning, source paper, and mention papers.
---

# 知识库与知识图谱（paper-kb）

术语知识库 + 知识图谱，长期累积，位于会话工作目录（cwd，即 agent 的 working directory）下的 `paper-kb\` 文件夹。

脚本目录：`C:\Users\Lenovo\.dsh\.agent-presets\paper-reading\scripts\`（若预设目录被移动，请同步改此路径）。

## 结构
- `terms.json`：术语条目数组（术语源）。
- `papers.json`：论文条目数组。
- `graph.mmd`：由 terms.json 生成的知识图谱（Mermaid 文本）。
- `README.md`：说明。

## 术语条目 schema（术语唯一权威源）
```json
{
  "term": "状态反馈",
  "english": "state feedback",
  "field": "示例领域",
  "aliases": ["状态回授"],
  "preferred_zh": "状态反馈",
  "definition": "...",
  "sources": [{"paper": "某教材/论文名", "location": "Sec 3.2"}],
  "mentions": [{"paper": "另一篇论文名", "context": "..."}]
}
```
- `preferred_zh`：首选中文译名（译名锁定的依据；缺省用 `term`）。
- `term`：条目主键，通常与 `preferred_zh` 相同。
- `aliases`：别名归一（如「状态反馈」与「状态回授」合并为一条，主条目用领域主流译法）。
- `sources`：该术语「首次/主要出现」的论文或教材。
- `mentions`：还有哪些论文提及（累积）。
- **本文件是翻译与名词解释共享的唯一术语源**：翻译锁定译名、名词解释写定义，都读写这一份 terms.json。

## 流程
1. 初始化：若 `paper-kb\` 不存在，运行 `python "<脚本目录>\kb.py" --root <cwd>\paper-kb init`。
2. 新增/更新术语：
   - `read` 读 `terms.json`；按 `english` 或 `aliases` 去重。
   - 命中：更新 definition、追加 sources/mentions、补 aliases。
   - 未命中：追加新条目。
   - 写回 `terms.json`。
3. 记录论文：把涉及论文写入 `papers.json`（title/authors/year/venue/abstract/key terms）。
4. 生成图谱：`python "<脚本目录>\kb.py" --root <cwd>\paper-kb graph` → 重写 `graph.mmd`（节点=术语/论文，边=来源/提及/别名）。
5. 可视化：若装有 mermaid-cli，`kb.py graph --render` 额外生成 SVG；否则把 `graph.mmd` 粘贴到在线 Mermaid 渲染器查看。

## 查询
回答名词解释时：先 `grep`/`read` `paper-kb\terms.json`（含 aliases），命中则引用已有定义；未命中则联网检索并随后写入。
