// Скриншоты интерфейса для презентации: Chrome headless + DevTools Protocol (Node 22: fetch и WebSocket встроены).
// node shots.js <outDir>
const { spawn } = require('child_process')
const fs = require('fs')
const path = require('path')

const OUT = process.argv[2] || 'shots'
const BASE = 'http://localhost:8080'
const API = BASE + '/api/v1'
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const PORT = 9333
fs.mkdirSync(OUT, { recursive: true })
const sleep = ms => new Promise(r => setTimeout(r, ms))

async function api(method, p, body, token) {
  const r = await fetch(API + p, { method, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: 'Bearer ' + token } : {}) }, body: body ? JSON.stringify(body) : undefined })
  const t = await r.text()
  let j; try { j = JSON.parse(t) } catch { j = t }
  if (!r.ok) throw new Error(`${method} ${p} → ${r.status}: ${t.slice(0, 300)}`)
  return j
}
const login = async email => (await api('POST', '/auth/login', { email, password: 'demo12345' })).access_token

class Page {
  constructor(ws) { this.ws = ws; this.id = 0; this.pending = new Map(); this.events = []
    ws.onmessage = m => { const d = JSON.parse(m.data); if (d.id && this.pending.has(d.id)) { this.pending.get(d.id)(d); this.pending.delete(d.id) } else if (d.method) this.events.push(d) } }
  send(method, params = {}) { const id = ++this.id; this.ws.send(JSON.stringify({ id, method, params })); return new Promise(r => this.pending.set(id, r)) }
  async eval(expr) { const r = await this.send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true }); return r.result && r.result.result && r.result.result.value }
  async goto(url, wait = 2500) { this.events = []; await this.send('Page.navigate', { url })
    for (let i = 0; i < 100 && !this.events.some(e => e.method === 'Page.loadEventFired'); i++) await sleep(100)
    await sleep(wait) }
  async shot(name, { fullHeight = false, clip } = {}) {
    let params = { format: 'png' }
    if (fullHeight) { const h = await this.eval('Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)')
      params = { format: 'png', captureBeyondViewport: true, clip: { x: 0, y: 0, width: 1440, height: Math.min(h, 4000), scale: 1 } } }
    if (clip) params = { format: 'png', captureBeyondViewport: true, clip: { ...clip, scale: 1 } }
    const r = await this.send('Page.captureScreenshot', params)
    fs.writeFileSync(path.join(OUT, name + '.png'), Buffer.from(r.result.data, 'base64'))
    console.log('saved', name)
  }
}

async function main() {
  const proc = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, `--user-data-dir=${path.resolve(OUT, '..', 'chrome_profile')}`,
    '--window-size=1440,900', '--hide-scrollbars', '--force-color-profile=srgb', '--lang=ru-RU', 'about:blank'], { stdio: 'ignore' })
  let targets
  for (let i = 0; i < 50; i++) { try { targets = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); if (targets.length) break } catch { } await sleep(200) }
  const t = targets.find(x => x.type === 'page')
  const ws = new WebSocket(t.webSocketDebuggerUrl)
  await new Promise(r => { ws.onopen = r })
  const page = new Page(ws)
  await page.send('Page.enable')
  await page.send('Runtime.enable')
  await page.send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 900, deviceScaleFactor: 2, mobile: false })
  await page.send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }, { name: 'prefers-color-scheme', value: 'light' }] })
  const as = async token => { await page.goto(BASE + '/', 600); await page.eval(`localStorage.setItem('fsp_career_token', ${JSON.stringify(token || '')}); ${token ? '' : "localStorage.removeItem('fsp_career_token');"} true`) }

  const only = process.argv.slice(3)
  const want = n => !only.length || only.includes(n)

  // 1. Главная
  if (want('landing')) { await as(null); await page.goto(BASE + '/', 3000); await page.shot('landing') }

  // 2. Подборка работодателя
  const emp = await login('employer@demo.ru')
  if (want('selection')) {
    const sel = await api('POST', '/employer/selections', { text: 'Нужен frontend-разработчик уровня Junior: React, TypeScript, HTML/CSS. Удалённо, 90 000 – 140 000 ₽.', title: 'Frontend Junior · удалённо' }, emp)
    await as(emp); await page.goto(`${BASE}/employer/selections/${sel.id}`, 3500)
    await page.shot('selection')
    await page.shot('selection_full', { fullHeight: true })
  }
  // 3. Тест по вакансии
  if (want('testpreview')) {
    const vacs = await api('GET', '/employer/vacancies', null, emp)
    const v = vacs.find(x => (x.specialization === 'backend')) || vacs[0]
    await as(emp); await page.goto(`${BASE}/employer/needs/${v.id}`, 2500)
    await page.eval(`(() => { const b = [...document.querySelectorAll('button')].find(x => x.textContent.includes('Тест по вакансии')); b && b.click(); return !!b })()`)
    await sleep(2500)
    await page.shot('testpreview')
    await page.shot('testpreview_full', { fullHeight: true })
  }
  // 4. Кандидат: категория и приглашения
  const cand = await login('candidate@demo.ru')
  if (want('grade')) { await as(cand); await page.goto(`${BASE}/candidate/grade`, 3000); await page.shot('grade'); await page.shot('grade_full', { fullHeight: true }) }
  if (want('invitations')) {
    await as(cand); await page.goto(`${BASE}/candidate/invitations`, 3000)
    await page.eval(`(() => { const el = [...document.querySelectorAll('button, [role=button], a, li, div')].filter(e => e.textContent.includes('Python-разработчик (платёжный') && e.textContent.includes('₽')).pop(); el && el.click(); return !!el })()`)
    await sleep(2000); await page.shot('invitations')
  }
  if (want('dashboard')) { await as(cand); await page.goto(`${BASE}/candidate`, 3000); await page.shot('cand_dashboard') }
  // 5. Прохождение теста (новый кандидат)
  if (want('runner')) {
    const nb = await login('newbie@demo.ru')
    await api('POST', '/testing/survey', { industries: [], specialization: 'backend', language: 'python', experience: '2-5', roles: ['developer'], work_formats: ['hybrid'], claimed_grade: 'middle', fsp_participant: false }, nb)
    const s = await api('POST', '/testing/sessions', { grade: 'middle' }, nb)
    const token = s.token || (s.session && s.session.token)
    await as(nb); await page.goto(`${BASE}/candidate/testing/${token}`, 3500)
    await page.shot('runner')
  }
  // 6. Методика
  if (want('methodology')) { await as(null); await page.goto(`${BASE}/methodology`, 4000); await page.shot('methodology_full', { fullHeight: true }) }
  // 7. Банк заданий (администратор)
  if (want('admin')) { const adm = await login('admin@demo.ru'); await as(adm); await page.goto(`${BASE}/admin`, 3000); await page.shot('admin') }
  // 8. Работодатель: карточка кандидата с достижениями ФСП
  if (want('fsp')) {
    const res = await api('GET', '/employer/candidates?has_fsp=true&specialization=backend&size=5', null, emp)
    const items = res.items || res.results || res
    const c = items[0]
    await as(emp); await page.goto(`${BASE}/employer/candidates/${c.id}`, 3500)
    await page.shot('fsp_candidate_full', { fullHeight: true })
    await as(cand); await page.goto(`${BASE}/candidate/settings`, 3000)
    await page.shot('cand_settings_full', { fullHeight: true })
  }
  // 9. Мобильная версия
  if (want('mobile')) {
    await page.send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 3, mobile: true })
    await page.send('Emulation.setTouchEmulationEnabled', { enabled: true })
    await as(null); await page.goto(BASE + '/', 3000); await page.shot('m_landing')
    const nb = await login('newbie@demo.ru')
    const sess = await api('POST', '/testing/sessions', { grade: 'middle' }, nb).catch(() => null)
    const tok = sess && (sess.token || (sess.session && sess.session.token))
    if (tok) { await as(nb); await page.goto(`${BASE}/candidate/testing/${tok}`, 3500); await page.shot('m_runner') }
    await as(cand); await page.goto(`${BASE}/candidate/invitations`, 3000)
    await page.eval(`(() => { const el = [...document.querySelectorAll('button, [role=button], a, li, div')].filter(e => e.textContent.includes('Python-разработчик (платёжный') && e.textContent.includes('₽')).pop(); el && el.click(); return !!el })()`)
    await sleep(2000); await page.shot('m_invitation')
    const sels = await api('GET', '/employer/selections', null, emp)
    await as(emp); await page.goto(`${BASE}/employer/selections/${sels[0].id}`, 3500)
    await page.eval('window.scrollTo(0, 0); true')
    await page.shot('m_selection')
    await page.send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 900, deviceScaleFactor: 2, mobile: false })
  }
  ws.close(); proc.kill()
}
main().catch(e => { console.error(e); process.exit(1) })
