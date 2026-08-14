#!/usr/bin/env node
/**
 * 从 src/ 生成两套安装包：
 *   packages/cursor/              → 丢进论文工作区，或把 .cursor/skills 拷到 ~/.cursor/skills
 *   packages/dsh/paper-reading/   → 拷到 $DSH_HOME/.agent-presets/paper-reading/
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const src = path.join(root, "src");
const outCursor = path.join(root, "packages", "cursor");
const outDsh = path.join(root, "packages", "dsh", "paper-reading");

function rmrf(p) {
  fs.rmSync(p, { recursive: true, force: true });
}

function mkdirp(p) {
  fs.mkdirSync(p, { recursive: true });
}

function write(p, text) {
  mkdirp(path.dirname(p));
  fs.writeFileSync(p, text.replace(/\r\n/g, "\n"), "utf8");
}

function copyDir(from, to) {
  mkdirp(to);
  for (const name of fs.readdirSync(from)) {
    const a = path.join(from, name);
    const b = path.join(to, name);
    if (fs.statSync(a).isDirectory()) copyDir(a, b);
    else fs.copyFileSync(a, b);
  }
}

function indentBlock(text, spaces) {
  const pad = " ".repeat(spaces);
  return text
    .replace(/\r\n/g, "\n")
    .split("\n")
    .map((line) => (line.length ? pad + line : pad.trimEnd()))
    .join("\n");
}

function withCwd(persona, cwdExpr) {
  return persona.replaceAll("<cwd>", cwdExpr);
}

const persona = fs.readFileSync(path.join(src, "persona.md"), "utf8").trim();
const kb = fs.readFileSync(path.join(src, "skills", "knowledge-base.md"), "utf8");
const trans = fs.readFileSync(path.join(src, "skills", "paper-translation.md"), "utf8");
const config = fs.readFileSync(path.join(src, "config.example.yml"), "utf8");
const scriptsSrc = path.join(src, "scripts");

rmrf(path.join(root, "packages"));

// ── Cursor ────────────────────────────────────────────────────────────────
const cursorIntro = [
  "# 论文阅读助手",
  "",
  "你是「论文阅读助手」(Academic Paper-Reading Assistant)，运行在 Cursor 中。工作目录是当前工作区根目录。",
  "",
  withCwd(persona, "当前工作区根目录"),
  "",
  "请按需加载 `knowledge-base` 与 `paper-translation` 技能。",
].join("\n");

write(path.join(outCursor, "AGENTS.md"), cursorIntro + "\n");
write(path.join(outCursor, "config.example.yml"), config);
write(path.join(outCursor, ".cursor", "skills", "knowledge-base", "SKILL.md"), kb);
write(path.join(outCursor, ".cursor", "skills", "paper-translation", "SKILL.md"), trans);
copyDir(scriptsSrc, path.join(outCursor, "scripts"));
copyDir(scriptsSrc, path.join(outCursor, ".cursor", "skills", "knowledge-base", "scripts"));
copyDir(scriptsSrc, path.join(outCursor, ".cursor", "skills", "paper-translation", "scripts"));

// ── DeepSeek Harness ──────────────────────────────────────────────────────
const dshIntro =
  "You are a 论文阅读助手 (Academic Paper-Reading Assistant), powered by the {{model}} model, running on the DeepSeek Harness. 你的工作目录是 {{cwd}}。\n\n" +
  withCwd(persona, "{{cwd}}");

const tpl = fs.readFileSync(path.join(root, "adapters", "dsh", "agent.cordis.yml"), "utf8");
if (!tpl.includes("__PERSONA__")) {
  throw new Error("adapters/dsh/agent.cordis.yml 缺少 __PERSONA__ 占位符");
}
write(
  path.join(outDsh, "agent.cordis.yml"),
  tpl.replace("__PERSONA__", indentBlock(dshIntro, 6)),
);
fs.copyFileSync(path.join(root, "adapters", "dsh", "preset.yml"), path.join(outDsh, "preset.yml"));
write(path.join(outDsh, "skills", "knowledge-base", "SKILL.md"), kb);
write(path.join(outDsh, "skills", "paper-translation", "SKILL.md"), trans);
copyDir(scriptsSrc, path.join(outDsh, "scripts"));
write(path.join(outDsh, "config.example.yml"), config);
const templatesSrc = path.join(src, "templates");
if (fs.existsSync(templatesSrc)) {
  copyDir(templatesSrc, path.join(outCursor, "templates"));
  copyDir(templatesSrc, path.join(outDsh, "templates"));
}

console.log("packed:");
console.log("  " + path.relative(root, outCursor));
console.log("  " + path.relative(root, outDsh));
