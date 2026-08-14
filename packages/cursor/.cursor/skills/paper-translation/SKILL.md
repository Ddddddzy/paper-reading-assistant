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

## 流程
1. 建文件夹并导入：新建 `<slug>/`，把原文 PDF 复制为 `<slug>/<slug>.pdf`。
2. 抽取：`python "<脚本目录>/translate_pdf.py" extract <slug>/<slug>.pdf -o <slug>/translation` → 生成 `extracted.json`、`pages/`（每页渲染 PNG）、`images/`（内嵌位图）。
3. 预处理（脚本化加速，必做）：`python "<脚本目录>/translate_pdf.py" preprocess <slug>/translation/extracted.json --terms <cwd>/paper-kb/terms.json -o <slug>/translation` → 生成 `prepared.json`：已切段、英文术语已预替换为「中文(English)」占位、公式段已标记、参考文献已抽取、术语对照已生成、已译段落从 `cache.json` 自动复用。
4. 翻译：读取 `prepared.json`，**只翻译 `translated` 为空且 `is_formula=false` 的段**（用 `prepped` 文本，译名已定，直接沿用「中文(English)」里的中文）；`is_formula=true` 的段转录为 LaTeX 公式块；插图先跑 `crop-figures` 脚本化裁剪出 `figures/fig-N.png` 并直接引用（pymupdf 坐标：get_image_rects + 文本块 bbox + get_pixmap(clip)），不要对无视觉能力的会话使用读图工具；识别章节组织成 chapters；写回 `translated`，并整理成 `translated.json`（`references`/`glossary` 直接取自 prepared.json）。
5. 缓存：`python "<脚本目录>/translate_pdf.py" cache-save <slug>/translation/prepared.json -o <slug>/translation` → 把已译段落写入 `cache.json`（下次重跑自动复用，跳过已译段）。
6. 汇编编译：`python "<脚本目录>/translate_pdf.py" assemble <slug>/translation/translated.json -o <slug>/translation` → 生成 `paper.tex` 并运行 xelatex 两遍 → `<slug>/translation/paper.pdf`。

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
