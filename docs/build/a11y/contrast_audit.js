// Аудит контраста текста по WCAG 2.1 AA (4,5:1, крупный текст — 3:1) на 25 ключевых страницах обеих ролей и админки.
// Headless Chrome открывает страницы под демо-аккаунтами и для каждого текстового узла считает контраст цвета текста и
// фактического фона (с учётом полупрозрачных подложек).
//
//   node docs/build/a11y/contrast_audit.js [отчёт.json]        (нужен запущенный стенд на http://localhost:8080)
//
// Текст поверх картинки или градиента (шапка над героем), над анимированной подложкой (активная вкладка) и в слое
// подсветки кода проверка не видит и отмечает как белое на белом — такие строки в отчёте ложные.
const { spawn } = require('child_process')
const fs = require('fs'), os = require('os'), path = require('path')
const BASE = 'http://localhost:8080', API = BASE + '/api/v1'
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe', PORT = 9371
const sleep = ms => new Promise(r => setTimeout(r, ms))
const OUT = process.argv[2] || null

const CHECK = `(() => {
  const parse = c => { const m = c && c.match(/rgba?\\(([^)]+)\\)/); if (!m) return null; const p = m[1].split(',').map(parseFloat); return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 } }
  const lum = ({ r, g, b }) => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4) }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b) }
  const blend = (fg, bg) => ({ r: fg.r * fg.a + bg.r * (1 - fg.a), g: fg.g * fg.a + bg.g * (1 - fg.a), b: fg.b * fg.a + bg.b * (1 - fg.a), a: 1 })
  const bgOf = el => { const cols = []; for (let e = el; e; e = e.parentElement) { const cs = getComputedStyle(e)
      if (cs.backgroundImage && cs.backgroundImage !== 'none') return null
      const c = parse(cs.backgroundColor); if (c && c.a > 0) { cols.push(c); if (c.a >= 1) break } }
    let bg = { r: 255, g: 255, b: 255, a: 1 }; for (const c of cols.reverse()) bg = blend(c, bg); return bg }
  const op = el => { let o = 1; for (let e = el; e; e = e.parentElement) o *= +getComputedStyle(e).opacity; return o }
  const out = [], seen = new Set(), w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
  while (w.nextNode()) {
    const t = w.currentNode, el = t.parentElement
    if (!t.textContent.trim() || !el || seen.has(el)) continue
    seen.add(el)
    const r = el.getBoundingClientRect(); if (!r.width || !r.height) continue
    const cs = getComputedStyle(el); if (cs.visibility === 'hidden' || op(el) < 0.99) continue
    if (el.closest('button[disabled], [aria-disabled=true], #__cap, #__cur')) continue
    const fg0 = parse(cs.color), bg = bgOf(el); if (!fg0 || !bg) continue
    const fg = blend(fg0, bg), L1 = lum(fg), L2 = lum(bg), ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05)
    const size = parseFloat(cs.fontSize), large = size >= 24 || (+cs.fontWeight >= 700 && size >= 18.66)
    if (ratio < (large ? 3 : 4.5)) out.push({ ratio: +ratio.toFixed(2), color: cs.color, bg: 'rgb(' + [bg.r, bg.g, bg.b].map(Math.round).join(', ') + ')',
      size, text: t.textContent.trim().slice(0, 50), cls: String(el.className || '').slice(0, 90), tag: el.tagName })
  }
  return out
})()`

async function token(email) {
  const r = await fetch(API + '/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password: 'demo12345' }) })
  return (await r.json()).access_token
}

async function main() {
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'fsp-a11y-'))
  const proc = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`, '--hide-scrollbars', 'about:blank'], { stdio: 'ignore' })
  let targets
  for (let i = 0; i < 50; i++) { try { targets = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); if (targets.length) break } catch { } await sleep(200) }
  const ws = new WebSocket(targets.find(t => t.type === 'page').webSocketDebuggerUrl)
  await new Promise(r => { ws.onopen = r })
  let id = 0; const pending = new Map()
  ws.onmessage = m => { const d = JSON.parse(m.data); if (d.id && pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id) } }
  const send = (method, params = {}) => { const i = ++id; ws.send(JSON.stringify({ id: i, method, params })); return new Promise(r => pending.set(i, r)) }
  const ev = async e => (await send('Runtime.evaluate', { expression: e, awaitPromise: true, returnByValue: true })).result?.result?.value
  await send('Page.enable'); await send('Runtime.enable')
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false })
  await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] })
  const visit = async (url, tok) => {
    await send('Page.navigate', { url: BASE + '/' }); await sleep(800)
    await ev(tok ? `localStorage.setItem('fsp_career_token', ${JSON.stringify(tok)})` : `localStorage.clear()`)
    await send('Page.navigate', { url: BASE + url }); await sleep(3500)
    await ev(`(async () => { for (let y = 0; y < document.body.scrollHeight; y += 700) { scrollTo(0, y); await new Promise(r => setTimeout(r, 120)) } scrollTo(0, 0) })()`)
    await sleep(800)
    return (await ev(CHECK)) || []
  }
  const cand = await token('candidate@demo.ru'), emp = await token('employer@demo.ru'), adm = await token('admin@demo.ru')
  const sel = (await (await fetch(API + '/employer/selections', { headers: { Authorization: 'Bearer ' + emp } })).json())[0]
  const cid = (await (await fetch(API + '/employer/candidates?specialization=backend', { headers: { Authorization: 'Bearer ' + emp } })).json())
  const firstCand = (cid.items || cid)[0]
  const pages = [['/', null], ['/login', null], ['/register', null], ['/methodology', null], ['/evaluate', null],
    ['/candidate', cand], ['/candidate/profile', cand], ['/candidate/testing', cand], ['/candidate/grade', cand], ['/candidate/invitations', cand],
    ['/candidate/vacancies', cand], ['/candidate/applications', cand], ['/candidate/tasks', cand], ['/candidate/settings', cand],
    ['/employer', emp], ['/employer/needs', emp], ['/employer/needs/1', emp], ['/employer/selections', emp],
    ...(sel ? [[`/employer/selections/${sel.id}`, emp]] : []), ['/employer/search', emp], ['/employer/invitations', emp],
    ...(firstCand ? [[`/employer/candidates/${firstCand.id}`, emp]] : []), ['/employer/tasks', emp], ['/employer/company', emp],
    ['/admin', adm], ['/admin/drafts', adm]]
  const report = {}
  for (const [url, tok] of pages) {
    const fails = await visit(url, tok)
    report[url] = fails
    console.log(url.padEnd(34), fails.length)
  }
  if (OUT) fs.writeFileSync(OUT, JSON.stringify(report, null, 1))
  ws.close(); proc.kill()
}
main().catch(e => { console.error(e); process.exit(1) })
