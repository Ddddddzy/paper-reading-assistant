return {
  name: 'paper-reader-client',
  apply(ctx) {
    const slots = ctx.get('slots')
    if (slots === undefined) return
    const store = { visible: false, subs: [] }
    function setVisible(v) { if (store.visible !== v) { store.visible = v; store.subs.forEach(f => f()) } }
    function toggle() { setVisible(!store.visible) }
    function useVisible() {
      const [, setTick] = React.useState(0)
      React.useEffect(() => {
        const f = () => setTick(t => t + 1)
        store.subs.push(f)
        return () => { store.subs = store.subs.filter(x => x !== f) }
      }, [])
      return store.visible
    }
    function computeTops(meta, zoom) {
      if (!meta || !meta.pages) return []
      const tops = [0]
      let acc = 0
      for (const pg of meta.pages) { acc += pg.h * zoom + 8; tops.push(acc) }
      return tops
    }
    function Pane(props) {
      const side = props.side, zoom = props.zoom
      const meta = side && side.meta, pages = side && side.pages
      const style = Object.assign({ overflow: 'auto', background: '#2b2b2b', flex: 1, minWidth: 0 }, props.style)
      return React.createElement('div', { ref: props.scrollRef, onScroll: props.onScroll, style: style },
        side && side.error
          ? React.createElement('div', { style: { color: '#f88', padding: 16 } }, String(side.error))
          : (meta && pages
            ? meta.pages.map(pg => React.createElement('img', {
                key: pg.n, src: pages[pg.n] || '', alt: 'page ' + pg.n,
                style: { display: 'block', width: (pg.w * zoom) + 'px', height: (pg.h * zoom) + 'px', margin: '0 auto 8px auto', background: pages[pg.n] ? '#fff' : '#202020' },
              }))
            : (side && side.loading
              ? React.createElement('div', { style: { color: '#ccc', padding: 16 } }, '渲染/加载中…')
              : React.createElement('div', { style: { color: '#777', padding: 16 } }, '未选择')))
      )
    }
    function ReaderWindow(props) {
      const useWs = (props && props.useWorkspaces) || function () { return undefined }
      const items = useWs(s => s.items) || []
      const recentId = useWs(s => s.recentWorkspaceId)
      const currentWs = items.find(w => w.id === recentId) || items[0]
      const wsRoot = currentWs ? currentWs.path : ''
      const visible = useVisible()
      const [papers, setPapers] = React.useState([])
      const [slug, setSlug] = React.useState('')
      const [manualOrig, setManualOrig] = React.useState('')
      const [manualTrans, setManualTrans] = React.useState('')
      const [left, setLeft] = React.useState(null)
      const [right, setRight] = React.useState(null)
      const [zoom, setZoom] = React.useState(1)
      const [lock, setLock] = React.useState(false)
      const [status, setStatus] = React.useState('')
      const leftRef = React.useRef(null)
      const rightRef = React.useRef(null)
      const lockRef = React.useRef(false)
      const syncedRef = React.useRef({ left: null, right: null })
      React.useEffect(() => {
        host.call('paper-reader.list', { root: wsRoot }).then(r => {
          setPapers(r.papers || [])
          if (!(r.papers && r.papers.length)) setStatus('未找到论文（需 <slug>/<slug>.pdf 与 <slug>/translation/paper.pdf）')
        }).catch(e => setStatus('list failed: ' + (e && e.message)))
      }, [wsRoot])
      React.useEffect(() => { lockRef.current = lock }, [lock])
      async function loadSide(pdf, setSide) {
        setSide({ pdf, meta: null, pages: {}, loading: true })
        try {
          const r = await host.call('paper-reader.render', { pdf, dpi: 110, root: wsRoot })
          const meta = r.meta
          const pages = {}
          let next = 1
          const worker = async () => {
            while (next <= meta.count) {
              const n = next++
              const p = await host.call('paper-reader.page', { pdf, n, root: wsRoot })
              pages[n] = p.dataUrl
              setSide({ pdf, meta, pages: Object.assign({}, pages), loading: next <= meta.count })
            }
          }
          const wc = Math.min(8, Math.max(1, meta.count))
          const ws = []
          for (let i = 0; i < wc; i++) ws.push(worker())
          await Promise.all(ws)
          setSide({ pdf, meta, pages, loading: false })
        } catch (e) {
          setSide({ pdf, meta: null, pages: {}, loading: false, error: String(e && e.message || e) })
        }
      }
      function openPaper(s) {
        const paper = papers.find(p => p.slug === s)
        if (!paper) return
        setSlug(s)
        setStatus('')
        loadSide(paper.original, setLeft)
        if (paper.hasTranslation) loadSide(paper.translation, setRight)
        else { setRight(null); setStatus('该论文无译文') }
      }
      function openManual() {
        if (!manualOrig) return
        setStatus('')
        loadSide(manualOrig, setLeft)
        if (manualTrans) loadSide(manualTrans, setRight)
      }
      function handleScroll(isLeft) {
        return function () {
          if (!lockRef.current) return
          const srcEl = isLeft ? leftRef.current : rightRef.current
          const dstEl = isLeft ? rightRef.current : leftRef.current
          const srcMeta = isLeft ? (left && left.meta) : (right && right.meta)
          const dstMeta = isLeft ? (right && right.meta) : (left && left.meta)
          if (!srcEl || !dstEl || !srcMeta || !dstMeta) return
          const srcKey = isLeft ? 'left' : 'right'
          const dstKey = isLeft ? 'right' : 'left'
          const syncedTop = syncedRef.current[srcKey]
          if (syncedTop != null && Math.abs(srcEl.scrollTop - syncedTop) < 2) {
            syncedRef.current[srcKey] = null
            return
          }
          const st = srcEl.scrollTop
          const srcTops = computeTops(srcMeta, zoom)
          let page = 0
          for (let i = 0; i < srcMeta.count; i++) {
            if (st >= srcTops[i] && st < srcTops[i + 1]) { page = i; break }
          }
          const ph = srcTops[page + 1] - srcTops[page]
          const ratio = ph > 0 ? (st - srcTops[page]) / ph : 0
          const dstTops = computeTops(dstMeta, zoom)
          const dstCount = Math.max(1, dstMeta.count)
          const dstPage = Math.max(0, Math.min(dstCount - 1, Math.round(page / Math.max(1, srcMeta.count) * dstCount)))
          const dstTop = dstTops[dstPage] + ratio * (dstTops[dstPage + 1] - dstTops[dstPage])
          syncedRef.current[dstKey] = dstTop
          dstEl.scrollTop = dstTop
        }
      }
      if (!visible) return null
      const options = papers.map(p => React.createElement('option', { key: p.slug, value: p.slug }, p.slug + (p.hasTranslation ? '' : '（无译文）')))
      const hdr = { display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderBottom: '1px solid #333', flexWrap: 'wrap' }
      const btn = { background: '#3a3a3a', color: '#eee', border: '1px solid #555', borderRadius: 4, padding: '4px 10px', cursor: 'pointer' }
      const field = { background: '#111', color: '#eee', border: '1px solid #444', borderRadius: 4, padding: '4px 6px' }
      return React.createElement('div', {
        style: { position: 'fixed', top: '6%', left: '5%', width: '90%', height: '88%', background: '#1e1e1e', color: '#eee', border: '1px solid #444', borderRadius: 10, zIndex: 9999, boxShadow: '0 10px 40px rgba(0,0,0,0.5)', display: 'flex', flexDirection: 'column', pointerEvents: 'auto' },
      },
        React.createElement('div', { style: hdr },
          React.createElement('strong', null, '论文对照阅读'),
          React.createElement('select', { value: slug, onChange: e => openPaper(e.target.value), style: field },
            React.createElement('option', { value: '' }, '选择论文…'), ...options),
          React.createElement('span', null, '手动:'),
          React.createElement('input', { placeholder: '原文 PDF 路径（绝对路径）', value: manualOrig, onChange: e => setManualOrig(e.target.value), style: Object.assign({ flex: '1 1 180px', minWidth: 160 }, field) }),
          React.createElement('input', { placeholder: '译文 PDF 路径（绝对路径）', value: manualTrans, onChange: e => setManualTrans(e.target.value), style: Object.assign({ flex: '1 1 180px', minWidth: 160 }, field) }),
          React.createElement('button', { onClick: openManual, style: btn }, '加载'),
          React.createElement('label', { style: { display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer' } },
            React.createElement('input', { type: 'checkbox', checked: lock, onChange: e => setLock(e.target.checked) }), '锁定同步'),
          React.createElement('button', { onClick: () => setZoom(z => Math.max(0.5, +(z - 0.1).toFixed(1))), style: btn }, '−'),
          React.createElement('span', null, Math.round(zoom * 100) + '%'),
          React.createElement('button', { onClick: () => setZoom(z => Math.min(2.5, +(z + 0.1).toFixed(1))), style: btn }, '+'),
          React.createElement('button', { onClick: () => setVisible(false), style: btn }, '关闭')
        ),
        status ? React.createElement('div', { style: { padding: '2px 12px', color: '#f88', fontSize: 12 } }, status) : null,
        React.createElement('div', { style: { flex: 1, display: 'flex', gap: 8, padding: 8, minHeight: 0 } },
          React.createElement(Pane, { side: left, zoom: zoom, scrollRef: leftRef, onScroll: handleScroll(true), style: { border: '1px solid #333', borderRadius: 6 } }),
          React.createElement(Pane, { side: right, zoom: zoom, scrollRef: rightRef, onScroll: handleScroll(false), style: { border: '1px solid #333', borderRadius: 6 } })
        )
      )
    }
    function ToggleButton() {
      const visible = useVisible()
      return React.createElement('button', {
        onClick: toggle,
        style: { background: 'transparent', color: 'inherit', border: 'none', cursor: 'pointer' },
      }, visible ? '关闭论文阅读' : '论文阅读')
    }
    slots.inject('shell.overlay', () => slots.register(
      { name: 'shell.overlay', id: 'paper-reader' },
      (props) => React.createElement(ReaderWindow, props),
    ))
    slots.inject('sidebar.footer.action', () => slots.register(
      { name: 'sidebar.footer.action', id: 'paper-reader', label: '论文阅读' },
      () => React.createElement(ToggleButton, null),
    ))
  },
}
