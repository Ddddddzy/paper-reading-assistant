return {
  name: 'paper-reader-host',
  inject: ['fs', 'sandboxPolicy', 'subprocess'],
  apply(ctx) {
    const PY = `import sys, os, json, base64
import fitz
pdf, outdir = sys.argv[1], sys.argv[2]
dpi = int(sys.argv[3]) if len(sys.argv) > 3 else 110
os.makedirs(outdir, exist_ok=True)
doc = fitz.open(pdf)
pages = []
for i in range(len(doc)):
    page = doc[i]
    pix = page.get_pixmap(dpi=dpi)
    b64 = base64.b64encode(pix.tobytes('png')).decode('ascii')
    with open(os.path.join(outdir, 'page-%04d.b64' % (i + 1)), 'w', encoding='ascii') as f:
        f.write(b64)
    pages.append({'n': i + 1, 'w': pix.width, 'h': pix.height})
doc.close()
with open(os.path.join(outdir, 'pages.json'), 'w', encoding='utf-8') as f:
    json.dump({'count': len(pages), 'pages': pages}, f, ensure_ascii=False)
print('RENDER_OK')`
    function defRoot(args) {
      return (args && args.root) || ctx.sandboxPolicy.workspaceRoot
    }
    function root(args) {
      return defRoot(args).replace(/\\/g, '/').replace(/\/+$/, '')
    }
    function hashStr(s) {
      let h = 5381
      for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) >>> 0
      return h.toString(16)
    }
    function normalize(p, args) {
      p = (p || '').replace(/\\/g, '/')
      if (/^[a-zA-Z]:\//.test(p) || p.startsWith('/')) return p
      return root(args) + '/' + p
    }
    function cacheDir(absPdf, args) {
      return root(args) + '/.paper-reader-cache/' + hashStr(absPdf)
    }
    async function existsFile(absPath) {
      try {
        const t = await ctx.fs.resolve(absPath)
        const info = await ctx.fs.stat(t)
        return !!(info && info.type === 'file')
      } catch (e) { return false }
    }
    async function renderPdf(absPdf, dpi, args) {
      const dir = cacheDir(absPdf, args)
      const metaPath = dir + '/pages.json'
      if (await existsFile(metaPath)) {
        const t = await ctx.fs.resolve(metaPath)
        return JSON.parse(await ctx.fs.readText(t))
      }
      const handle = ctx.subprocess.spawn({
        argv: ['python', '-c', PY, absPdf, dir, String(dpi || 110)],
        cwd: root(args),
        stdio: { stdin: 'ignore', stdout: 'inherit', stderr: 'inherit' },
        graceMs: 120000,
      })
      const outcome = await handle.done
      if (outcome.exitCode !== 0) throw new Error('PDF render failed (exit ' + outcome.exitCode + ')')
      const t = await ctx.fs.resolve(metaPath)
      return JSON.parse(await ctx.fs.readText(t))
    }
    harness.handle('paper-reader.list', async (args) => {
      const r = root(args)
      const papers = []
      try {
        const rootT = await ctx.fs.resolve(r)
        const entries = await ctx.fs.listDir(rootT)
        for (const e of entries) {
          if (e.type !== 'directory') continue
          const slug = e.name
          if (slug.startsWith('.') || slug === 'paper-kb') continue
          const origRel = slug + '/' + slug + '.pdf'
          const transRel = slug + '/translation/paper.pdf'
          papers.push({
            slug,
            original: r + '/' + origRel,
            translation: r + '/' + transRel,
            hasOriginal: await existsFile(r + '/' + origRel),
            hasTranslation: await existsFile(r + '/' + transRel),
          })
        }
      } catch (e) {}
      return { root: r, papers }
    })
    harness.handle('paper-reader.render', async (args) => {
      const pdf = normalize(args && args.pdf, args)
      const meta = await renderPdf(pdf, (args && args.dpi) || 110, args)
      return { meta, cacheDir: cacheDir(pdf, args) }
    })
    harness.handle('paper-reader.page', async (args) => {
      const pdf = normalize(args && args.pdf, args)
      const n = parseInt(args && args.n, 10) || 1
      const p = cacheDir(pdf, args) + '/page-' + String(n).padStart(4, '0') + '.b64'
      const t = await ctx.fs.resolve(p)
      const b64 = await ctx.fs.readText(t)
      return { dataUrl: 'data:image/png;base64,' + b64 }
    })
  },
}
