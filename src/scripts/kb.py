#!/usr/bin/env python3
"""
paper-kb 知识库工具。terms.json 是翻译与名词解释共享的唯一术语源。

子命令：
  init                  初始化 paper-kb/（terms.json 从种子表 seed_terms.json 生成、papers.json、README.md）
  graph [--render]      由 terms.json 重新生成 graph.mmd（可选 --render 用 mmdc 出图）
  term <term>           按 term/english/aliases 匹配并打印单个术语
  lookup <key>          按 english/term/aliases 匹配，打印译名锁定所需字段（english/preferred_zh/term/aliases/field）

用法：python kb.py --root <paper-kb目录> <子命令>
"""
import argparse
import json
import os
import subprocess


def seed_terms(seed_path=None):
    if not seed_path:
        seed_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seed_terms.json")
    if os.path.exists(seed_path):
        with open(seed_path, encoding="utf-8-sig") as f:
            return json.load(f)
    return []


def init_kb(root, seed=None):
    os.makedirs(root, exist_ok=True)
    tp = os.path.join(root, "terms.json")
    if not os.path.exists(tp):
        terms = seed_terms(seed)
        with open(tp, "w", encoding="utf-8") as f:
            json.dump(terms, f, ensure_ascii=False, indent=2)
        print("已从种子表生成 terms.json（%d 条）" % len(terms))
    pp = os.path.join(root, "papers.json")
    if not os.path.exists(pp):
        with open(pp, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)
    readme = os.path.join(root, "README.md")
    if not os.path.exists(readme):
        with open(readme, "w", encoding="utf-8") as f:
            f.write(
                "# 术语知识库 (paper-kb)\n\n"
                "- terms.json：术语唯一权威源（term/english/field/aliases/preferred_zh/definition/sources/mentions）\n"
                "- papers.json：论文条目\n"
                "- graph.mmd：知识图谱（Mermaid）\n"
            )
    print("已初始化 ->", root)


def load(root, name):
    p = os.path.join(root, name)
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8-sig") as f:
        return json.load(f)


def q(s):
    return '"' + str(s).replace('"', "'") + '"'


def make_mermaid(terms, papers):
    lines = ["graph TD"]
    for t in terms:
        tq = q(t.get("term", "?"))
        lines.append("  %s[%s]" % (tq, q(t.get("term", "?"))))
        for s in t.get("sources", []):
            pn = s.get("paper")
            if pn:
                lines.append("  %s -->|来源| %s" % (tq, q(pn)))
        for m in t.get("mentions", []):
            pn = m.get("paper")
            if pn:
                lines.append("  %s -.提及.-> %s" % (tq, q(pn)))
        for a in t.get("aliases", []):
            lines.append("  %s ---|别名| %s" % (tq, q(a)))
    return "\n".join(lines)


def cmd_graph(args):
    terms = load(args.root, "terms.json")
    papers = load(args.root, "papers.json")
    mmd = make_mermaid(terms, papers)
    out = os.path.join(args.root, "graph.mmd")
    with open(out, "w", encoding="utf-8") as f:
        f.write(mmd)
    print("已生成 ->", out)
    if args.render:
        try:
            subprocess.run(
                ["mmdc", "-i", out, "-o", os.path.join(args.root, "graph.svg")],
                check=True,
            )
            print("已渲染 -> graph.svg")
        except Exception:
            print("未找到 mmdc（mermaid-cli），跳过渲染；可安装: npm i -g @mermaid-js/mermaid-cli")


def cmd_term(args):
    terms = load(args.root, "terms.json")
    key = args.term.lower()
    for t in terms:
        names = [t.get("term", ""), t.get("english", "")] + list(t.get("aliases", []))
        if key in [str(n).lower() for n in names]:
            print(json.dumps(t, ensure_ascii=False, indent=2))
            return
    print("未找到术语:", args.term)


def cmd_lookup(args):
    terms = load(args.root, "terms.json")
    key = args.key.lower()
    hits = []
    for t in terms:
        names = [t.get("english", ""), t.get("term", "")] + list(t.get("aliases", []))
        if key in [str(n).lower() for n in names]:
            hits.append(t)
    if not hits:
        print(json.dumps({"found": False, "key": args.key}, ensure_ascii=False, indent=2))
        return
    for t in hits:
        out = {
            "english": t.get("english"),
            "preferred_zh": t.get("preferred_zh") or t.get("term"),
            "term": t.get("term"),
            "aliases": t.get("aliases", []),
            "field": t.get("field", ""),
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))


def main():
    p = argparse.ArgumentParser(description="paper-kb 知识库工具")
    p.add_argument("--root", default=None, help="paper-kb 目录；默认 <cwd>/paper-kb")
    sp = p.add_subparsers(dest="cmd", required=True)
    i = sp.add_parser("init")
    i.add_argument("--seed", default=None, help="自定义术语种子 JSON 文件路径")
    g = sp.add_parser("graph")
    g.add_argument("--render", action="store_true")
    t = sp.add_parser("term")
    t.add_argument("term")
    l = sp.add_parser("lookup")
    l.add_argument("key")
    args = p.parse_args()
    root = args.root or os.path.join(os.getcwd(), "paper-kb")
    if args.cmd == "init":
        init_kb(root, args.seed)
    elif args.cmd == "graph":
        cmd_graph(args)
    elif args.cmd == "term":
        cmd_term(args)
    elif args.cmd == "lookup":
        cmd_lookup(args)


if __name__ == "__main__":
    main()
