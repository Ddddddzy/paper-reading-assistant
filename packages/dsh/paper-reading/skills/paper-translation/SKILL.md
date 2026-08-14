---
name: paper-translation
description: Use when the user asks to translate an English PDF paper into Chinese, or to produce a Chinese reading version of a PDF — the PDF → LaTeX → PDF translation pipeline for academic papers.
---

# Paper Translation（PDF → 全中文 LaTeX/PDF）

把英文论文 PDF 翻译成**全中文**，最终交付 LaTeX 编译的中文 PDF。

## 脚本目录

运行 `translate_pdf.py` / `kb.py` 前先定位「脚本目录」，按下面顺序取第一个存在的路径：

1. 与 `skills/` 同级的 `scripts/`（DeepSeek Harness 预设安装位置）
2. 本技能目录内的 `scripts/`（Cursor 技能包）
3. 工作区根目录的 `scripts/`

## 目录约定
- 每篇论文一个文件夹 `<slug>/`（slug 取 PDF 文件名去掉 `.pdf`，如 `Yang_Realtime-VLA_V2`）。
- 原文 PDF 复制为 `<slug>/<slug>.pdf`。
- 翻译归档全部放在 `<slug>/translation/`（extracted.json、translated.json、paper.tex、paper.pdf、pages/、images/）。
- 知识库在**根目录**（会话工作目录）的 `paper-kb/`，与论文文件夹同级。

## 前置依赖
- Python 3.8+ 与 pymupdf：`python -m pip install -r "<脚本目录>/requirements.txt"`
- XeLaTeX + ctex（TeX Live）

## 硬性纪律（违反即视为流程错误）

1. **extract / preprocess / crop-figures / cache-save / assemble 只允许各执行一条对应脚本命令**；禁止用多轮 shell 手搓版面、dump bbox、矢量分析、手工裁图替代脚本。
2. **禁止为「通读全文」而反复 Read 整个 `prepared.json`**（尤其禁止按 2000 行切片读完上千段）。翻译时只读**当前分块文件**或当前需要的段落子集。
3. **无视觉能力时禁止调用 read_image / 读图工具**（会立刻报错且浪费步骤）；插图一律 `crop-figures` 一次出图后直接引用。
4. **pymupdf 不可用时**：允许**一次** poppler 兜底（`pdftotext`/`pdfimages`/`pdftoppm`）生成等价 `extracted.json`；仍禁止深度版面逆向。
5. 使用子代理时：每个子代理**只读自己的 chunk 文件、只写自己的结果文件**；主代理禁止再通读全文 JSON。
6. 模型只负责：翻译空段、公式文本→LaTeX、中文图题/章节归纳、精读笔记、术语入库；其余确定性步骤交给脚本。

## 流程
1. 建文件夹并导入：新建 `<slug>/`，把原文 PDF 复制为 `<slug>/<slug>.pdf`。
2. 抽取（仅脚本）：`python "<脚本目录>/translate_pdf.py" extract <slug>/<slug>.pdf -o <slug>/translation` → `extracted.json`、`pages/`、`images/`。成功即进入下一步，不要额外探测。
3. 预处理（仅脚本）：`python "<脚本目录>/translate_pdf.py" preprocess <slug>/translation/extracted.json --terms <cwd>/paper-kb/terms.json -o <slug>/translation` → `prepared.json`。
4. 插图（仅脚本，一次）：`python "<脚本目录>/translate_pdf.py" crop-figures <slug>/<slug>.pdf -o <slug>/translation` → `figures/`。裁坏的图最多再跑**一次**脚本或按用户指定图号重裁；禁止多轮坐标 dump。
5. 翻译（模型，按块）：
   - 用脚本或少量命令把待译段切成 `translation/chunks/chunk-XX.json`（每块几十段即可）。
   - **只翻译 `translated` 为空且 `is_formula=false` 的段**（用 `prepped`）；`is_formula=true` 转 LaTeX 公式块。
   - 主代理/子代理每次只处理一个 chunk；合并为 `translated.json`（`references`/`glossary` 取自 prepared；插图引用 `figures/fig-N.png` + 中文 caption）。
   - 识别章节组织成 chapters；精读笔记在合并阶段写一次即可。
6. 缓存（仅脚本）：`python "<脚本目录>/translate_pdf.py" cache-save <slug>/translation/prepared.json -o <slug>/translation`（若 cache-save 需已填入译文的 prepared/翻译结果，按脚本实际参数为准；把已译段落写入 `cache.json`）。
7. 汇编（仅脚本）：`python "<脚本目录>/translate_pdf.py" assemble <slug>/translation/translated.json -o <slug>/translation` → `paper.tex` → xelatex 两遍 → `paper.pdf`。

## 输出要求（全中文论文格式）
- ctex 文档类；正文宋体、标题黑体（ctex 默认处理）。
- 每大章 `\clearpage` 分页。
- **全中文正文，按英文段落分段，不并列英文原文**。
- 公式自动编号（equation 环境）；插图 figure 环境 + 中文 caption。
- 文末附：术语对照表、结构化精读笔记、参考文献。

## 术语规范（单源：paper-kb/terms.json）
- 翻译前先读取根目录 `paper-kb/terms.json`；不存在则先 `python "<脚本目录>/kb.py" --root <cwd>/paper-kb init`。
- 译名锁定：英文 → `preferred_zh`（缺省用 `term`）；`aliases` 视为同一术语的别称，不另造新译名。
- 命中表内术语一律用表内中文；表外术语按领域主流翻译，首次出现标英文，翻译完成后写入 terms.json。
- 文末「术语对照表」（glossary）由同一份 terms.json 生成，勿手写第二份。

## 限制
- 图片型公式在无视觉能力时无法转录，需 OCR 或 Mathpix 类服务（需用户提供）；文本公式直接转录为 LaTeX。
- 无文本层的扫描 PDF：pymupdf 抽不到文字，需先 OCR（如 tesseract）再处理。
