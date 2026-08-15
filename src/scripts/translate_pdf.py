#!/usr/bin/env python3
"""
论文 PDF -> 中文 LaTeX/PDF 翻译流水线工具。

抽取使用 pymupdf（fitz）。

子命令：
  extract  <pdf> -o <outdir>            抽取文本与图片 -> extracted.json + pages/ + images/
  crop-figures <pdf> -o <outdir>        程序化裁剪插图（get_image_rects + 文本块 bbox + get_pixmap(clip)）-> figures/
  preprocess <extracted.json> -o <outdir> 切段/术语预替换/公式标记/参考文献/术语对照/增量缓存 -> prepared.json
  cache-save <prepared.json> -o <outdir> 把 prepared.json 里已译段落写入 cache.json
  assemble <translated.json> -o <outdir> [--template PATH] [--cwd DIR]
      由翻译结果生成 paper.tex 并编译为 paper.pdf。
      若工作区 paper-reading.config.yml 配置了 latex_template（或传入 --template），
      则必须使用该模板（文件不存在则报错）；模板需含 {{body}}，可选
      {{title}} {{authors}} {{glossary}} {{notes}} {{references}}。

translated.json schema（assemble 的输入，由翻译阶段产出）：
{
  "title": "中文标题",
  "authors": "作者",
  "chapters": [
    {
      "heading": "第1章 引言",
      "blocks": [
        {"kind": "text", "translated": "中文译文段落（按英文段落分段）"},
        {"kind": "formula", "latex": "a=b+c", "label": "eq:1"},
        {"kind": "image", "path": "pages/page-3.png", "caption": "图1 ...", "width": "0.85"}
      ]
    }
  ],
  "glossary": [{"en": "state", "cn": "状态", "field": "系统理论"}],
  "notes": {"problem": "", "method": "", "contribution": "", "experiments": "", "limitations": ""},
  "references": ["[1] ..."]
}
输出为全中文（不并列英文原文），按英文段落分段。
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys


def require_pymupdf():
    try:
        import fitz
        return fitz
    except ImportError:
        sys.exit("缺少 pymupdf。请先运行: python -m pip install -r requirements.txt")


def md5(s):
    return hashlib.md5(s.encode("utf-8")).hexdigest()[:16]


def load_terms(terms_path):
    if not terms_path or not os.path.exists(terms_path):
        return []
    with open(terms_path, encoding="utf-8-sig") as f:
        return json.load(f)


def build_term_map(terms):
    """english/aliases -> preferred_zh；按英文长度降序（长词优先替换）。"""
    pairs = []
    for t in terms:
        zh = t.get("preferred_zh") or t.get("term") or ""
        if not zh:
            continue
        en = t.get("english", "")
        if en:
            pairs.append((en, zh))
        for a in t.get("aliases", []):
            pairs.append((a, zh))
    seen = set()
    uniq = []
    for en, zh in pairs:
        k = en.lower()
        if k in seen:
            continue
        seen.add(k)
        uniq.append((en, zh))
    uniq.sort(key=lambda x: -len(x[0]))
    return uniq


def build_term_index(terms):
    idx = {}
    for t in terms:
        zh = t.get("preferred_zh") or t.get("term") or ""
        en = t.get("english", "")
        if en:
            idx[en.lower()] = {"en": en, "zh": zh, "field": t.get("field", "")}
        for a in t.get("aliases", []):
            idx[a.lower()] = {"en": en or a, "zh": zh, "field": t.get("field", "")}
    return idx


def _term_pattern(term_map):
    if not term_map:
        return None
    alt = "|".join(re.escape(en) for en, _zh in term_map)
    return re.compile(r"(?<![A-Za-z0-9])(" + alt + r")(?![A-Za-z0-9])", re.IGNORECASE)


def replace_terms(text, term_map):
    pattern = _term_pattern(term_map)
    if pattern is None:
        return text
    mapping = {en.lower(): zh for en, zh in term_map}

    def repl(m):
        en = m.group(1)
        return "%s(%s)" % (mapping.get(en.lower(), en), en)
    return pattern.sub(repl, text)


def find_terms(text, term_map):
    pattern = _term_pattern(term_map)
    if pattern is None:
        return []
    hits = []
    for m in pattern.finditer(text):
        k = m.group(1).lower()
        if k not in hits:
            hits.append(k)
    return hits


def split_paragraphs(text):
    parts = re.split(r"\n\s*\n", text)
    return [p.strip() for p in parts if p.strip()]


_MATH_TOKENS = re.compile(r"[=≤≥≈≠∑∏∫∂∇√±×·→←↔∈∉⊂⊆∪∩]|\\[a-zA-Z]+")
_FORMULA_KW = re.compile(
    r"\b(min|max|argmin|argmax|arg\s*min|arg\s*max|subject\s*to|s\.t\.|st\.|such\s*that)\b",
    re.IGNORECASE,
)


def is_formula_like(text):
    t = text.strip()
    if not t or len(t) > 250:
        return False
    if len(t.split()) > 35:
        return False
    if _FORMULA_KW.search(t):
        return True
    return len(_MATH_TOKENS.findall(t)) >= 3


def extract_references(text):
    refs = []
    current = None
    for line in text.splitlines():
        s = line.strip()
        m = re.match(r"^\[(\d+)\]\s*(.*)$", s)
        if m:
            if current:
                refs.append(current)
            current = "[%s] %s" % (m.group(1), m.group(2))
        elif current and s:
            current += " " + s
    if current:
        refs.append(current)
    return refs


def load_cache(path):
    if path and os.path.exists(path):
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    return {}


def save_cache(path, cache):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def esc_text(s):
    if s is None:
        return ""
    s = str(s)
    for a, b in [
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
    ]:
        s = s.replace(a, b)
    return s


def esc_with_math(s):
    """按 $ 切分：偶数段是文本（转义），奇数段是行内数学（原样包回 $...$）。"""
    if s is None:
        return ""
    parts = str(s).split("$")
    out = []
    for i, seg in enumerate(parts):
        if i % 2 == 0:
            out.append(esc_text(seg))
        else:
            out.append("$" + seg + "$")
    return "".join(out)


def cmd_extract(args):
    fitz = require_pymupdf()
    pdf = args.pdf
    outdir = args.outdir
    os.makedirs(outdir, exist_ok=True)
    imgdir = os.path.join(outdir, "images")
    pagedir = os.path.join(outdir, "pages")
    os.makedirs(imgdir, exist_ok=True)
    os.makedirs(pagedir, exist_ok=True)
    doc = fitz.open(pdf)
    pages = []
    img_idx = 0
    for pno in range(len(doc)):
        page = doc[pno]
        text = page.get_text().strip()
        blocks = [b[4].strip() for b in page.get_text("blocks") if b[6] == 0 and b[4].strip()]
        pages.append({"page": pno + 1, "text": text, "blocks": blocks})
        # 页面渲染（用于查看插图/裁剪）
        pix = page.get_pixmap(dpi=150)
        pix.save(os.path.join(pagedir, "page-%d.png" % (pno + 1)))
        # 内嵌位图
        for img in page.get_images(full=True):
            xref = img[0]
            try:
                p = fitz.Pixmap(doc, xref)
                if p.colorspace and p.colorspace.n > 3:  # CMYK 等转 RGB
                    p = fitz.Pixmap(fitz.csRGB, p)
                fname = "img-%03d.png" % img_idx
                img_idx += 1
                p.save(os.path.join(imgdir, fname))
            except Exception:
                pass
    doc.close()
    out = {
        "title": "",
        "pages": pages,
        "images_dir": "images",
        "pages_dir": "pages",
    }
    path = os.path.join(outdir, "extracted.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("已抽取 %d 页文本 -> %s；页面渲染 pages/，内嵌图片 images/" % (len(pages), path))


def render_block(b):
    k = b.get("kind", "text")
    if k == "text":
        # 全中文：只输出译文，按英文段落分段
        tr = esc_with_math(b.get("translated", ""))
        return tr + "\n\n"
    if k == "formula":
        latex = b.get("latex", "")
        label = b.get("label", "")
        lab = (r"\label{" + label + "}") if label else ""
        return r"\begin{equation}" + "\n" + latex + " " + lab + "\n" + r"\end{equation}" + "\n"
    if k == "image":
        path = b.get("path", "")
        cap = esc_text(b.get("caption", ""))
        width = b.get("width", "0.85")
        return (
            r"\begin{figure}[htbp]" + "\n"
            + r"\centering" + "\n"
            + r"\includegraphics[width=" + str(width) + r"\linewidth]{" + path + "}" + "\n"
            + r"\caption{" + cap + "}" + "\n"
            + r"\end{figure}" + "\n"
        )
    return ""


def build_body_sections(data):
    """章节正文（不含导言区 / maketitle）。"""
    L = []
    for i, ch in enumerate(data.get("chapters", [])):
        heading = ch.get("heading", "第%d章" % (i + 1))
        L.append(r"\clearpage")
        L.append(r"\section*{" + esc_text(heading) + "}")
        L.append(r"\addcontentsline{toc}{section}{" + esc_text(heading) + "}")
        for b in ch.get("blocks", []):
            L.append(render_block(b))
    return "\n".join(L)


def build_glossary_tex(data):
    gl = data.get("glossary", [])
    if not gl:
        return ""
    L = [
        r"\clearpage",
        r"\section*{术语对照表}",
        r"\begin{tabular}{lll}",
        r"\toprule 英文 & 中文 & 领域 \\ \midrule",
    ]
    for g in gl:
        L.append(
            esc_text(g.get("en", "")) + " & " + esc_text(g.get("cn", ""))
            + " & " + esc_text(g.get("field", "")) + r" \\"
        )
    L.append(r"\bottomrule")
    L.append(r"\end{tabular}")
    return "\n".join(L)


def build_notes_tex(data):
    notes = data.get("notes", {})
    if not notes:
        return ""
    L = [r"\clearpage", r"\section*{结构化精读笔记}"]
    for key, label in [
        ("problem", "研究问题"),
        ("method", "方法"),
        ("contribution", "贡献"),
        ("experiments", "实验"),
        ("limitations", "局限"),
    ]:
        v = notes.get(key)
        if v:
            L.append(r"\subsection*{" + label + "}")
            L.append(esc_with_math(v))
    return "\n".join(L)


def build_references_tex(data):
    refs = data.get("references", [])
    if not refs:
        return ""
    L = [r"\clearpage", r"\section*{参考文献}", r"\begin{enumerate}"]
    for r in refs:
        L.append(r"\item " + esc_text(r))
    L.append(r"\end{enumerate}")
    return "\n".join(L)


def build_default_tex(data):
    L = []
    L.append(r"\documentclass[12pt]{ctexart}")
    L.append(r"\usepackage[margin=2.5cm]{geometry}")
    L.append(r"\usepackage{amsmath,amssymb}")
    L.append(r"\usepackage{graphicx}")
    L.append(r"\usepackage{booktabs,array}")
    L.append(r"\usepackage[hidelinks]{hyperref}")
    L.append(r"\usepackage{xcolor}")
    L.append(r"\setlength{\parskip}{0.6em}")
    L.append(r"\begin{document}")
    L.append(r"\title{" + esc_text(data.get("title", "")) + "}")
    L.append(r"\author{" + esc_text(data.get("authors", "")) + "}")
    L.append(r"\date{}")
    L.append(r"\maketitle")
    L.append("")
    L.append(build_body_sections(data))
    L.append(build_glossary_tex(data))
    L.append(build_notes_tex(data))
    L.append(build_references_tex(data))
    L.append(r"\end{document}")
    return "\n".join(L)


def read_config_latex_template(cwd=None):
    """从工作区 paper-reading.config.yml 读取 latex_template 字段（无 PyYAML 依赖）。"""
    cwd = cwd or os.getcwd()
    path = os.path.join(cwd, "paper-reading.config.yml")
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8-sig") as f:
        text = f.read()
    m = re.search(r"(?m)^\s*latex_template\s*:\s*[\"']?([^\"'#\n]+?)[\"']?\s*(?:#.*)?$", text)
    if not m:
        return ""
    return m.group(1).strip()


def resolve_template_path(explicit=None, cwd=None):
    """
    解析模板路径。优先级：命令行 --template > config latex_template。
    配置了路径但文件不存在 → 报错（必须使用用户模板）。
    未配置 → 返回 None（使用内置模板）。
    """
    cwd = cwd or os.getcwd()
    raw = (explicit or "").strip() or read_config_latex_template(cwd)
    if not raw:
        return None
    path = raw if os.path.isabs(raw) else os.path.join(cwd, raw)
    path = os.path.normpath(path)
    if not os.path.isfile(path):
        sys.exit("已配置 latex_template=%s，但文件不存在：%s（工作区根目录相对路径）" % (raw, path))
    return path


def apply_latex_template(template_text, data):
    """用占位符填充用户模板。必须含 {{body}}。"""
    if "{{body}}" not in template_text:
        sys.exit("LaTeX 模板缺少必填占位符 {{body}}")
    body = build_body_sections(data)
    # 若模板未单独留 glossary/notes/references 占位，则并入 body 末尾（与内置行为一致）
    extras = []
    if "{{glossary}}" not in template_text:
        extras.append(build_glossary_tex(data))
    if "{{notes}}" not in template_text:
        extras.append(build_notes_tex(data))
    if "{{references}}" not in template_text:
        extras.append(build_references_tex(data))
    if extras:
        body = body + "\n" + "\n".join(x for x in extras if x)

    repl = {
        "{{title}}": esc_text(data.get("title", "")),
        "{{authors}}": esc_text(data.get("authors", "")),
        "{{body}}": body,
        "{{glossary}}": build_glossary_tex(data),
        "{{notes}}": build_notes_tex(data),
        "{{references}}": build_references_tex(data),
    }
    out = template_text
    for k, v in repl.items():
        out = out.replace(k, v)
    return out


def build_tex(data, template_path=None):
    if template_path:
        with open(template_path, encoding="utf-8-sig") as f:
            tpl = f.read()
        print("使用 LaTeX 模板 -> " + template_path)
        return apply_latex_template(tpl, data)
    return build_default_tex(data)


def copy_template_assets(template_path, outdir):
    """把模板同目录的 .cls/.sty 等依赖复制到编译目录（如 bithesis.cls）。"""
    if not template_path:
        return
    src_dir = os.path.dirname(os.path.abspath(template_path))
    if not os.path.isdir(src_dir):
        return
    exts = {".cls", ".sty", ".bst", ".clo", ".cfg"}
    for name in os.listdir(src_dir):
        src = os.path.join(src_dir, name)
        if not os.path.isfile(src):
            continue
        ext = os.path.splitext(name)[1].lower()
        if ext not in exts and name.lower() != "latexmkrc":
            continue
        dst = os.path.join(outdir, name)
        shutil.copy2(src, dst)
        print("已复制模板依赖 -> " + dst)


def cmd_assemble(args):
    with open(args.translated_json, encoding="utf-8-sig") as f:
        data = json.load(f)
    outdir = args.outdir
    os.makedirs(outdir, exist_ok=True)
    cwd = args.cwd or os.getcwd()
    template_path = resolve_template_path(getattr(args, "template", None), cwd=cwd)
    copy_template_assets(template_path, outdir)
    tex = build_tex(data, template_path=template_path)
    texpath = os.path.join(outdir, "paper.tex")
    with open(texpath, "w", encoding="utf-8") as f:
        f.write(tex)
    print("已生成 " + texpath)
    for _ in range(2):
        subprocess.run(
            ["xelatex", "-interaction=nonstopmode", "-halt-on-error", "paper.tex"],
            cwd=outdir,
            capture_output=True,
            text=True,
        )
    pdf = os.path.join(outdir, "paper.pdf")
    if os.path.exists(pdf):
        print("编译成功 -> " + pdf)
    else:
        print("编译失败，请查看 " + os.path.join(outdir, "paper.log"))
        sys.exit(1)


def cmd_preprocess(args):
    with open(args.extracted_json, encoding="utf-8-sig") as f:
        ext = json.load(f)
    outdir = args.outdir or os.path.dirname(args.extracted_json)
    os.makedirs(outdir, exist_ok=True)
    terms_path = args.terms or os.path.join(os.getcwd(), "paper-kb", "terms.json")
    terms = load_terms(terms_path)
    term_map = build_term_map(terms)
    term_index = build_term_index(terms)
    cache_path = args.cache or os.path.join(outdir, "cache.json")
    cache = load_cache(cache_path)

    pages = ext.get("pages", [])
    all_text = "\n\n".join(p.get("text", "") for p in pages)
    paragraphs = []
    pid = 0
    for page in pages:
        pno = page.get("page", 1)
        paras = page.get("blocks") or split_paragraphs(page.get("text", ""))
        for para in paras:
            is_f = is_formula_like(para)
            if is_f:
                prepped = para
                hits = []
            else:
                prepped = replace_terms(para, term_map)
                hits = find_terms(para, term_map)
            h = md5(para)
            paragraphs.append({
                "id": "p%04d" % pid,
                "page": pno,
                "original": para,
                "prepped": prepped,
                "is_formula": is_f,
                "terms": hits,
                "hash": h,
                "translated": cache.get(h),
            })
            pid += 1

    references = extract_references(all_text)
    glossary = []
    for k in find_terms(all_text, term_map):
        info = term_index.get(k)
        if info:
            glossary.append({"en": info["en"], "cn": info["zh"], "field": info["field"]})

    out = {
        "title_hint": "",
        "paragraphs": paragraphs,
        "references": references,
        "glossary": glossary,
    }
    path = os.path.join(outdir, "prepared.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    n_f = sum(1 for p in paragraphs if p["is_formula"])
    n_c = sum(1 for p in paragraphs if p.get("translated"))
    print("预处理完成：%d 段（%d 公式段，%d 已缓存）；参考文献 %d 条；术语命中 %d -> %s"
          % (len(paragraphs), n_f, n_c, len(references), len(glossary), path))


def cmd_cache_save(args):
    with open(args.prepared_json, encoding="utf-8-sig") as f:
        prep = json.load(f)
    outdir = args.outdir or os.path.dirname(args.prepared_json)
    cache_path = os.path.join(outdir, "cache.json")
    cache = load_cache(cache_path)
    for p in prep.get("paragraphs", []):
        if p.get("translated"):
            cache[p.get("hash")] = p["translated"]
    save_cache(cache_path, cache)
    print("已保存缓存 %d 条 -> %s" % (len(cache), cache_path))


def cmd_crop_figures(args):
    fitz = require_pymupdf()
    doc = fitz.open(args.pdf)
    outdir = args.outdir
    figdir = os.path.join(outdir, "figures")
    os.makedirs(figdir, exist_ok=True)
    cap_re = re.compile(r"^\s*(fig\.?|figure\.?|table\.?)\s*\d+", re.IGNORECASE)
    figures = []
    fig_no = 0
    for pno in range(len(doc)):
        page = doc[pno]
        blocks = [b for b in page.get_text("blocks") if b[6] == 0 and b[4].strip()]
        img_rects = []
        for img in page.get_images(full=True):
            for r in page.get_image_rects(img[0]):
                img_rects.append(fitz.Rect(r))
        # 以图注为准：只有带 Fig/Figure/Table 图注的才是正文插图
        for b in blocks:
            text = b[4].strip()
            if not cap_re.match(text):
                continue
            c = fitz.Rect(b[:4])
            above_imgs = [r for r in img_rects
                          if r.y1 <= c.y0 + 3 and fitz.Rect(c.x0 - 20, 0, c.x1 + 20, c.y0).intersects(r)]
            if above_imgs:
                clip = above_imgs[0]
                for r in above_imgs[1:]:
                    clip = clip | r
                clip = clip | c
                kind = "image"
            else:
                tops = [bb[3] for bb in blocks
                        if bb[3] <= c.y0 and fitz.Rect(c.x0 - 20, 0, c.x1 + 20, c.y0).intersects(fitz.Rect(bb[:4]))]
                top = max(tops) if tops else max(0, c.y0 - page.rect.height * 0.5)
                clip = fitz.Rect(c.x0, top, c.x1, c.y1)
                kind = "vector"
            fig_no += 1
            pix = page.get_pixmap(dpi=args.dpi, clip=clip)
            fname = "fig-%d.png" % fig_no
            pix.save(os.path.join(figdir, fname))
            figures.append({"page": pno + 1, "file": "figures/" + fname, "kind": kind, "caption": text[:40]})
    doc.close()
    path = os.path.join(outdir, "figures.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"figures": figures}, f, ensure_ascii=False, indent=2)
    print("已裁剪 %d 张插图 -> %s" % (len(figures), path))


def main():
    p = argparse.ArgumentParser(description="论文 PDF 翻译流水线（pymupdf 抽取 + xelatex 编译）")
    sp = p.add_subparsers(dest="cmd", required=True)
    e = sp.add_parser("extract", help="抽取 PDF 文本与图片（pymupdf）")
    e.add_argument("pdf")
    e.add_argument("-o", "--outdir", default="out")
    cf = sp.add_parser("crop-figures", help="程序化裁剪插图（pymupdf 坐标）")
    cf.add_argument("pdf")
    cf.add_argument("-o", "--outdir", default="out")
    cf.add_argument("--dpi", type=int, default=150)
    pp = sp.add_parser("preprocess", help="切段/术语预替换/公式标记/参考文献/术语对照/增量缓存")
    pp.add_argument("extracted_json")
    pp.add_argument("-o", "--outdir", default="")
    pp.add_argument("--terms", default=None)
    pp.add_argument("--cache", default=None)
    cs = sp.add_parser("cache-save", help="把已译段落写入 cache.json")
    cs.add_argument("prepared_json")
    cs.add_argument("-o", "--outdir", default="")
    a = sp.add_parser("assemble", help="由 translated.json 生成并编译 PDF")
    a.add_argument("translated_json")
    a.add_argument("-o", "--outdir", default="out")
    a.add_argument(
        "--template",
        default=None,
        help="LaTeX 模板路径（默认读工作区 paper-reading.config.yml 的 latex_template）",
    )
    a.add_argument(
        "--cwd",
        default=None,
        help="工作区根目录（用于解析 config 与相对模板路径，默认当前目录）",
    )
    args = p.parse_args()
    if args.cmd == "extract":
        cmd_extract(args)
    elif args.cmd == "crop-figures":
        cmd_crop_figures(args)
    elif args.cmd == "preprocess":
        cmd_preprocess(args)
    elif args.cmd == "cache-save":
        cmd_cache_save(args)
    elif args.cmd == "assemble":
        cmd_assemble(args)


if __name__ == "__main__":
    main()
