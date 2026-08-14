# 论文对照阅读插件（paper-reader）

动态 Cordis 插件（Host + Client），在 DSH Web UI 里提供「原文 vs 中文译文」双栏 PDF 阅读器，带滚动/翻页锁定同步。

## 激活
1. `cordis_define`：`code.host` 用 `host.js` 内容，`code.client` 用 `client.js` 内容（新插件 `kind:"new"`，idPrefix 如 `pread`）。
2. `cordis_run` 激活（有 Client 半部，需在界面批准一次）。

## 使用
- 左侧栏底部「论文阅读」按钮 → 弹出双栏阅读器。
- 自动扫描工作区各 `<slug>/`（`<slug>/<slug>.pdf` + `<slug>/translation/paper.pdf`）；也可手动填两个 PDF **绝对路径**。
- 「锁定同步」：开 → 页码优先 + 页内滚动比例联动（页码数不同按比例映射，`syncedTop` 守卫防 A↔B 循环）；关 → 两侧独立。
- 缩放 50%–250%。

## 原理
Client 内建符号只有 `React/host/styles/console/ctx`（无 `window/document/fetch/atob`），故由 Host 用 pymupdf 把每页渲染成 PNG + base64，经 `host.call` 以 `data:image/png;base64` 返回；Client 用 `useWorkspaces` 取工作区路径传给 Host（动态插件的 `sandboxPolicy.workspaceRoot` 是 HOME，不能用）。

## 限制
- 动态插件：进程重启后需重新激活。
- 打开一篇论文会渲染全部页（110 DPI，约数秒）；缩放为 CSS 缩放，>100% 略发虚。
- 页码数不同的两侧按比例映射，不做句级对齐。
- 本期不做：选区复制提问、看板、批注。
