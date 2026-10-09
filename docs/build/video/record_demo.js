// Запись демонстрационного видео: headless Chrome проходит сквозной сценарий из ТЗ (раздел 3.3) по стенду
// (CDP screencast), кадры собираются в MP4. На экране — подписи шагов и курсор; остаток теста ускоряется и вырезается.
//
//   node docs/build/video/record_demo.js <out.mp4> --ffmpeg <путь к ffmpeg> [--base http://localhost:8080]
//                                         [--project fsp-career] [--resume <pdf из demo_resume.py>]
//
// Нужен запущенный стенд (docker compose) с чистыми демо-данными: сценарий регистрирует нового кандидата.
const { spawn, execFileSync } = require('child_process')
const fs = require('fs')
const os = require('os')
const path = require('path')

const args = process.argv.slice(2)
const opt = (name, def) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : def }
const OUT = path.resolve(args[0] || 'fsp-career-demo.mp4')
const FFMPEG = opt('--ffmpeg', 'ffmpeg')
const BASE = opt('--base', 'http://localhost:8080')
const PROJECT = opt('--project', 'fsp-career')
const RESUME = path.resolve(opt('--resume', 'docs/build/video/out/demo_resume.pdf'))  // demo_resume.py
const ROOT = path.resolve(__dirname, '..', '..', '..')
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const PORT = 9351
const W = 1536, H = 864, DPR = 1.25 // кадр 1920×1080
const WORK = fs.mkdtempSync(path.join(os.tmpdir(), 'fsp-video-'))
const sleep = ms => new Promise(r => setTimeout(r, ms))

// ----------------------------------------------------------------- оверлей: подписи, курсор, плавная прокрутка
const OVERLAY = `(() => {
  if (window.__demo) return
  const css = \`
  #__cap{position:fixed;left:50%;bottom:28px;transform:translateX(-50%) translateY(16px);z-index:2147483647;opacity:0;
    transition:opacity .35s, transform .35s;max-width:78vw;padding:14px 24px 15px;border-radius:18px;
    background:rgba(29,8,52,.92);color:#fff;font:600 19px/1.35 Montserrat,system-ui,sans-serif;
    box-shadow:0 18px 40px -12px rgba(29,8,52,.55);backdrop-filter:blur(6px);text-align:center;pointer-events:none}
  #__cap.on{opacity:1;transform:translateX(-50%) translateY(0)}
  #__cap small{display:block;margin-top:4px;font:500 15px/1.4 Montserrat,system-ui,sans-serif;color:rgba(255,255,255,.78)}
  #__cap i{position:absolute;left:24px;right:24px;bottom:6px;height:2px;border-radius:2px;background:rgba(255,255,255,.12);overflow:hidden}
  #__cap i:after{content:'';position:absolute;inset:0;width:30%;background:#FF0053;animation:__run 2.4s linear infinite}
  @keyframes __run{from{transform:translateX(-100%)}to{transform:translateX(340%)}}
  #__cur{position:fixed;left:0;top:0;width:26px;height:26px;z-index:2147483647;pointer-events:none;
    transition:transform .6s cubic-bezier(.22,.8,.32,1);filter:drop-shadow(0 2px 3px rgba(0,0,0,.35))}
  .__rip{position:fixed;width:36px;height:36px;margin:-18px 0 0 -18px;border-radius:50%;border:3px solid #FF0053;
    z-index:2147483646;pointer-events:none;animation:__rip .55s ease-out forwards}
  @keyframes __rip{from{transform:scale(.3);opacity:1}to{transform:scale(1.6);opacity:0}}
  #__card{position:fixed;inset:0;z-index:2147483645;display:grid;place-items:center;opacity:0;transition:opacity .7s;
    pointer-events:none;color:#fff;font-family:Montserrat,system-ui,sans-serif;background:
    radial-gradient(1200px 600px at 20% 10%,#7a1a8a 0,transparent 60%),radial-gradient(900px 600px at 90% 90%,#ff0053 0,transparent 55%),#1d0834}
  #__card.on{opacity:1}
  #__card .w{text-align:center;max-width:1100px;padding:0 40px}
  #__card img{height:64px;opacity:.95;display:inline-block}
  #__card h1{font-size:76px;font-weight:800;margin:28px 0 10px;letter-spacing:-1.5px;color:#fff}
  #__card p{font-size:26px;line-height:1.45;margin:8px 0;color:rgba(255,255,255,.85)}
  #__card .s{margin-top:34px;font-size:20px;color:rgba(255,255,255,.65)}\`
  const mount = () => {
    if (document.getElementById('__cap')) return
    const st = document.createElement('style'); st.textContent = css; document.head.appendChild(st)
    const cap = document.createElement('div'); cap.id = '__cap'; document.body.appendChild(cap)
    const cur = document.createElement('div'); cur.id = '__cur'
    cur.innerHTML = '<svg viewBox="0 0 24 24" width="26" height="26"><path d="M4 2l15 9-6.5 1.5L9 19z" fill="#fff" stroke="#1d0834" stroke-width="1.6" stroke-linejoin="round"/></svg>'
    document.body.appendChild(cur)
    const p = JSON.parse(sessionStorage.getItem('__cur') || '[760,430]')
    cur.style.transition = 'none'; cur.style.transform = 'translate(' + p[0] + 'px,' + p[1] + 'px)'
  }
  window.__demo = {
    caption(title, sub) {
      mount(); const c = document.getElementById('__cap')
      if (!title) { c.classList.remove('on'); return }
      c.innerHTML = title + (sub ? '<small>' + sub + '</small>' : '') + '<i></i>'; c.classList.add('on')
    },
    cursor(x, y, ms) {
      mount(); const c = document.getElementById('__cur')
      c.style.transition = 'transform ' + ms + 'ms cubic-bezier(.22,.8,.32,1)'
      c.style.transform = 'translate(' + x + 'px,' + y + 'px)'; sessionStorage.setItem('__cur', JSON.stringify([x, y]))
    },
    ripple(x, y) { const r = document.createElement('div'); r.className = '__rip'; r.style.left = x + 'px'; r.style.top = y + 'px';
      document.body.appendChild(r); setTimeout(() => r.remove(), 700) },
    // полноэкранная карточка (титул, финал) поверх страницы приложения — со шрифтами приложения
    card(html, instant) {
      mount(); let c = document.getElementById('__card'); const cur = document.getElementById('__cur')
      if (!html) { if (c) { c.classList.remove('on'); setTimeout(() => c.remove(), 800) } cur.style.opacity = 1; return }
      if (!c) { c = document.createElement('div'); c.id = '__card'; document.body.appendChild(c) }
      c.innerHTML = html; cur.style.opacity = 0
      if (instant) c.style.transition = 'none'
      void c.offsetWidth; c.classList.add('on'); void c.offsetWidth; c.style.transition = ''
    },
    scrollTo(top, ms) { return new Promise(res => { const y0 = scrollY, t0 = performance.now(), d = top - y0
      const step = t => { const k = Math.min(1, (t - t0) / ms), e = k < .5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2
        scrollTo(0, y0 + d * e); k < 1 ? requestAnimationFrame(step) : res() }; requestAnimationFrame(step) }) },
  }
  document.readyState === 'loading' ? document.addEventListener('DOMContentLoaded', mount) : mount()
})()`

// ----------------------------------------------------------------- CDP
class Browser {
  constructor(ws) {
    this.ws = ws; this.id = 0; this.pending = new Map(); this.frames = []; this.cuts = []; this.loaded = false
    ws.onmessage = m => {
      const d = JSON.parse(m.data)
      if (d.id && this.pending.has(d.id)) { this.pending.get(d.id)(d); this.pending.delete(d.id); return }
      if (d.method === 'Page.screencastFrame') {
        const f = path.join(WORK, String(this.frames.length).padStart(6, '0') + '.jpg')
        fs.writeFileSync(f, Buffer.from(d.params.data, 'base64'))
        this.frames.push({ f, ts: d.params.metadata.timestamp })
        this.send('Page.screencastFrameAck', { sessionId: d.params.sessionId })
      } else if (d.method === 'Page.loadEventFired') this.loaded = true
      else if (d.method === 'Page.javascriptDialogOpening') this.send('Page.handleJavaScriptDialog', { accept: true })
    }
  }
  send(method, params = {}) { const id = ++this.id; this.ws.send(JSON.stringify({ id, method, params })); return new Promise(r => this.pending.set(id, r)) }
  async ev(expr) {
    const r = await this.send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true })
    if (r.result?.exceptionDetails) throw new Error('eval: ' + JSON.stringify(r.result.exceptionDetails).slice(0, 300))
    return r.result?.result?.value
  }
  async goto(url, wait = 1800) {
    this.loaded = false; await this.send('Page.navigate', { url })
    for (let i = 0; i < 150 && !this.loaded; i++) await sleep(100)
    await sleep(wait)
  }
  caption(t, s = '') { return this.ev(`window.__demo && __demo.caption(${JSON.stringify(t)}, ${JSON.stringify(s)})`) }
  card(html, instant = false) { return this.ev(`__demo.card(${JSON.stringify(html)}, ${instant})`) }
  // центр элемента без прокрутки (null — элемента нет)
  pos(js) {
    return this.ev(`(() => { const el = ${js}; if (!el) return null; const r = el.getBoundingClientRect()
      return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) } })()`).catch(() => null)
  }
  // ждём элемент (данные подгружаются асинхронно); если он вне кадра или под подписью — плавная прокрутка окна
  // (в модальном окне — прокрутка до элемента)
  async rect(js, timeout = 4000) {
    for (let waited = 0; waited <= timeout; waited += 200) {
      const p = await this.ev(`(async () => { const el = ${js}; if (!el) return null
        let r = el.getBoundingClientRect()
        if (r.top < 90 || r.bottom > innerHeight - 150) {
          if (!el.closest('[role=dialog]')) {
            await __demo.scrollTo(Math.max(0, scrollY + r.top + r.height / 2 - innerHeight / 2), 800)
            r = el.getBoundingClientRect()
          }
          if (r.top < 0 || r.bottom > innerHeight) { el.scrollIntoView({ block: 'center', behavior: 'instant' }); r = el.getBoundingClientRect() }
        }
        return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) } })()`).catch(() => null)
      if (p) return p
      await sleep(200)
    }
    return null
  }
  async moveTo(x, y, ms = 650) { await this.ev(`__demo.cursor(${x}, ${y}, ${ms})`); await sleep(ms + 60) }
  async press(x, y) {
    await this.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x, y })
    await this.send('Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: 'left', clickCount: 1 })
    await this.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x, y, button: 'left', clickCount: 1 })
    await this.ev(`__demo.ripple(${x}, ${y})`)
  }
  // курсор плавно идёт к элементу; перед нажатием позиция уточняется — пока курсор двигался, страница могла сместиться
  // (подгрузка данных, анимации)
  async clickEl(js, what, wait) {
    const p = await this.rect(js)
    if (!p) throw new Error('нет элемента: ' + what)
    await sleep(250)
    await this.moveTo(p.x, p.y)
    const q = (await this.pos(js)) || p
    if (Math.abs(q.x - p.x) > 3 || Math.abs(q.y - p.y) > 3) await this.moveTo(q.x, q.y, 250)
    await this.press(q.x, q.y)
    await sleep(wait)
  }
  // клик по видимому элементу с текстом (точное совпадение начала), внутри scope
  click(text, { scope = 'document', tags = 'button,a,label,[role=tab]', wait = 700 } = {}) {
    const js = `[...${scope}.querySelectorAll(${JSON.stringify(tags)})].find(e => e.offsetParent !== null &&
      e.textContent.replace(/\\s+/g, ' ').trim().startsWith(${JSON.stringify(text)}))`
    return this.clickEl(js, text, wait)
  }
  clickSel(css, wait = 600) { return this.clickEl(`document.querySelector(${JSON.stringify(css)})`, css, wait) }
  async type(text, delay = 28) { for (const ch of text) { await this.send('Input.insertText', { text: ch }); await sleep(delay) } }
  async scrollTo(js, ms = 1400, offset = 90) {
    await this.ev(`(() => { const el = ${js}; const top = el ? el.getBoundingClientRect().top + scrollY - ${offset} : 0; return __demo.scrollTo(top, ${ms}) })()`)
  }
  async key(key, code, vk) {
    await this.send('Input.dispatchKeyEvent', { type: 'keyDown', key, code, windowsVirtualKeyCode: vk })
    await this.send('Input.dispatchKeyEvent', { type: 'keyUp', key, code, windowsVirtualKeyCode: vk })
  }
  // вырезать из видео ожидание: кадры между началом и концом не попадут в ролик
  async cut(fn) { const t0 = Date.now() / 1000; await fn(); this.cuts.push([t0 + 0.8, Date.now() / 1000]) }
  // клик по видимому элементу, текст которого содержит фрагмент
  clickText(fragment, { scope = 'document', tags = 'a,button', wait = 700 } = {}) {
    const js = `[...${scope}.querySelectorAll(${JSON.stringify(tags)})].find(e => e.offsetParent !== null &&
      e.textContent.replace(/\\s+/g, ' ').includes(${JSON.stringify(fragment)}))`
    return this.clickEl(js, fragment, wait)
  }
  // выбор в <select> по значению или по началу текста варианта (React слушает событие change)
  async choose(selectJs, option) {
    const ok = await this.ev(`(() => { const s = ${selectJs}; if (!s) return false
      const o = [...s.options].find(o => o.value === ${JSON.stringify(option)} || o.text.trim().startsWith(${JSON.stringify(option)}))
      if (!o) return false
      Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set.call(s, o.value)
      s.dispatchEvent(new Event('change', { bubbles: true })); return true })()`)
    if (!ok) throw new Error('нет варианта: ' + option)
  }
  async fill(css, text, delay = 40) { await this.clickSel(css, 250); await this.type(text, delay) }
  // файл в <input type=file> без системного диалога: курсор и «клик» по кнопке — для зрителя
  async upload(buttonText, file) {
    const p = await this.rect(`[...document.querySelectorAll('button')].find(e => e.offsetParent !== null && e.textContent.trim() === ${JSON.stringify(buttonText)})`)
    if (p) { await this.moveTo(p.x, p.y); await this.ev(`__demo.ripple(${p.x}, ${p.y})`) }
    const doc = await this.send('DOM.getDocument', { depth: 0 })
    const node = await this.send('DOM.querySelector', { nodeId: doc.result.root.nodeId, selector: 'input[type=file]' })
    await this.send('DOM.setFileInputFiles', { nodeId: node.result.nodeId, files: [file] })
  }
  api(path) {
    return this.ev(`fetch('/api/v1${path}', { headers: { Authorization: 'Bearer ' + localStorage.getItem('fsp_career_token') } }).then(r => r.json())`)
  }
  async login(label) {
    await this.ev(`localStorage.clear(); sessionStorage.removeItem('__cur'); true`)
    await this.goto(BASE + '/login', 1500)
    await this.click(label, { tags: 'button' })
    await this.click('Войти', { tags: 'button[type=submit]', wait: 2200 })
  }
  async loginAs(email, password) {
    await this.ev(`localStorage.clear(); sessionStorage.removeItem('__cur'); true`)
    await this.goto(BASE + '/login', 1500)
    await this.fill('input[type=email]', email)
    await this.fill('input[type=password]', password, 25)
    await this.click('Войти', { tags: 'button[type=submit]', wait: 2200 })
  }
}

function card(title, lines, small) {
  return `<div class="w"><img src="/brand/fsp-logo-white.png" alt=""><h1>${title}</h1>${lines.map(l => `<p>${l}</p>`).join('')}` +
    (small ? `<p class="s">${small}</p>` : '') + '</div>'
}

// ----------------------------------------------------------------- сценарий
const TEAM = 'Команда «Рекрут 2»: Мурехин Ярослав Андреевич, Воронин Артём Тимофеевич'
const TITLE = card('ФСП Карьера', ['Подбор ИТ-специалистов с обратной механикой:', 'уровень подтверждает тест, работодатель приходит к кандидату сам'],
  `${TEAM}<br>Хакатон «Лидеры цифровой трансформации — 2026» · специальный трек ФСП`)

// Сквозной сценарий из ТЗ (раздел 3.3): регистрация соискателя → опрос → тест → присвоение категории → поиск
// работодателем нужной категории → приглашение конкретному человеку → контакт; классический отклик на вакансию;
// механика тестирования (тест по вакансии, уникальные варианты) и механика подбора (потребность текстом → подборка).
const CANDIDATE = { email: 'anna.smirnova@example.com', password: 'Demo-2026!', name: 'Смирнова' }
const VACANCY = 'Middle Python-разработчик (платёжный сервис)'  // вакансия «ТехноПульса»: приглашение и тест по вакансии
const APPLY_TO = 'Go-разработчик (Middle+)'  // вакансия другой компании: классический отклик

async function answerCurrent(b) {
  const kind = await b.ev(`(() => { const o = document.querySelector('[data-proctored] button'); const i = document.querySelector('[data-proctored] input');
    return o ? 'option' : i ? 'input' : null })()`)
  if (kind === 'option') await b.clickSel('[data-proctored] button', 500)
  else if (kind === 'input') { await b.clickSel('[data-proctored] input', 300); await b.type('42', 120) }
  await sleep(500)
  await b.click(kind ? 'Ответить' : 'Не знаю', { tags: 'button', wait: 2300 })
}

async function scenario(b) {
  // 0. Титульная карточка (уже на экране поверх главной — см. main) растворяется и открывает главную
  await sleep(5500)
  await b.card(null)
  await sleep(1000)
  await b.caption('Обратная механика найма', 'Кандидат один раз подтверждает уровень тестом — работодатель сам приходит к нему с предложением и вилкой')
  await sleep(4000)
  await b.scrollTo(`[...document.querySelectorAll('h2')].find(h => h.textContent.includes('Инициатива'))`)
  await b.caption('Сквозной сценарий', 'Регистрация → опрос → тест → категория → поиск работодателем → приглашение → контакт')
  await sleep(4500)
  await b.ev('__demo.scrollTo(0, 1000)'); await sleep(1100)

  // 1. Регистрация соискателя с подтверждением e-mail
  await b.caption('1. Регистрация соискателя', 'E-mail, пароль и согласие на обработку персональных данных (152-ФЗ)')
  await b.click('Я кандидат', { tags: 'a', wait: 1800 })
  await b.fill('input[type=email]', CANDIDATE.email)
  await b.fill('input[type=password]', CANDIDATE.password, 25)
  await b.click('Даю согласие', { tags: 'label', wait: 500 })
  await b.click('Создать аккаунт', { tags: 'button', wait: 2200 })
  await b.caption('Подтверждение e-mail', 'Код приходит письмом; в демо-режиме стенда он показан на экране')
  await sleep(2800)
  await b.click('Подтвердить', { tags: 'button', wait: 2600 })

  // 2. Профиль из PDF-резюме с автораспознаванием
  await b.click('Профиль и резюме', { tags: 'a', wait: 2000 })
  await b.caption('Профиль из PDF-резюме', 'Загрузка резюме — поля распознаются автоматически (NER Natasha, разбор вёрстки hh.ru)')
  await sleep(1500)
  await b.upload('Загрузить PDF', RESUME)
  await sleep(4500)
  await b.caption('Распознано автоматически', 'ФИО, контакты, стек, роли, стаж, ожидания и формат работы — кандидат только проверяет')
  await sleep(5000)
  await b.click('Применить к профилю', { tags: 'button', wait: 1200 })
  await b.click('Сохранить профиль', { tags: 'button', wait: 2000 })
  const PID = (await b.api('/candidate/profile')).public_id

  // 3. Опрос по специализации и выбор предполагаемого грейда
  await b.click('Опрос и тест', { tags: 'a', wait: 2000 })
  await b.caption('2. Опрос', 'Специализация и стек, опыт, предполагаемый грейд: категорию определяет не резюме, а этот путь')
  await b.click('Backend-разработчик', { tags: 'button', wait: 500 })
  await b.click('Python', { tags: 'button', wait: 500 })
  await b.click('Далее', { tags: 'button', wait: 900 })
  await b.click('2–5 лет', { tags: 'button', wait: 400 })
  await b.click('Middle', { tags: 'button', wait: 700 })
  await b.click('Далее', { tags: 'button', wait: 900 })
  await b.click('Финтех и банки', { tags: 'button', wait: 300 })
  await b.click('Разработка', { tags: 'button', wait: 300 })
  await b.click('Код-ревью', { tags: 'button', wait: 300 })
  await b.click('Удалённо', { tags: 'button', wait: 500 })
  await b.click('Далее', { tags: 'button', wait: 900 })
  await b.caption('Нет истории ФСП — без штрафа', 'Достижения ФСП поднимают кандидата внутри категории, их отсутствие не наказывается')
  await b.click('Нет', { tags: 'button', wait: 1000 })
  await b.click('Сохранить ответы', { tags: 'button', wait: 2500 })

  // 4. Адаптивный тест на заявленный грейд → категория
  await b.caption('3. Тест на заявленный грейд', 'Полный адаптивный тест: 12–24 задания под прокторингом')
  await sleep(3000)
  await b.click('Начать тест', { tags: 'button', wait: 1000 })
  const dlg = `document.querySelector('[role=dialog]')`
  await b.click('Я готов', { scope: dlg, tags: 'label', wait: 500 })
  await b.click('Начать тест', { scope: dlg, tags: 'button', wait: 3000 })
  await b.caption('Адаптивный тест (IRT)', 'Следующее задание подбирается по ответам; время на ответ зависит от сложности')
  await sleep(2500)
  await answerCurrent(b)
  await b.caption('Свой вариант у каждого кандидата', 'Данные, код и ответы уникальны: слитая база бесполезна, сложность сопоставима по IRT')
  await sleep(2000)
  await answerCurrent(b)
  const token = await b.ev('location.pathname.split("/").pop()')
  await b.caption('⏩ Ускорено: остальные задания теста', '')
  await b.cut(async () => {
    execFileSync('docker', ['compose', '-p', PROJECT, 'exec', '-T', 'backend', 'python', '-', token, '1101111'],
      { input: fs.readFileSync(path.join(__dirname, 'finish_session.py')), cwd: ROOT })
    await b.goto(`${BASE}/candidate/testing/${token}`, 2500)
  })
  await b.caption('4. Категория присвоена', 'Грейд подтверждён тестом — категория «специализация × грейд» видна работодателям')
  await sleep(5500)
  await b.scrollTo(`[...document.querySelectorAll('h3')].find(h => h.textContent.includes('Результаты по доменам'))`, 1200, 140)
  await sleep(3000)
  await b.click('Категория и грейд', { tags: 'a', wait: 2200 })
  await b.caption('Категория и грейд', 'Текущий статус, профиль компетенций, история опроса и тестов; пересдача — с ограничением частоты')
  await sleep(4500)

  // 5. Отдельное согласие на публикацию профиля
  await b.click('Настройки и ФСП ID', { tags: 'a', wait: 2000 })
  await b.scrollTo(`[...document.querySelectorAll('h3')].find(h => h.textContent.includes('Согласия'))`, 1000, 160)
  await b.caption('Согласие на публикацию профиля', 'Отдельно от согласия на обработку ПДн (152-ФЗ): без него работодатели профиль не видят')
  await sleep(2000)
  await b.click('Публикация профиля для работодателей', { tags: 'label', wait: 2200 })

  // 6. Классический сценарий: отклик на вакансию
  await b.click('Вакансии', { tags: 'a', wait: 2200 })
  await b.caption('Классический сценарий: отклик на вакансию', 'Вакансии с оценкой совпадения; вилка «от–до» указана всегда')
  await sleep(3000)
  await b.clickText(APPLY_TO, { tags: 'a', wait: 2500 })
  await sleep(1500)
  await b.click('Откликнуться', { tags: 'button', wait: 1300 })
  await b.click('Отправить', { scope: dlg, tags: 'button', wait: 2200 })
  await b.click('Мои отклики', { tags: 'a', wait: 2200 })
  await b.caption('Статусы откликов', 'Отправлен → просмотрен → принят или отклонён — обе стороны видят актуальный статус')
  await sleep(4000)

  // 7. Работодатель: механика подбора — потребность обычным текстом
  await b.login('Работодатель «ТехноПульс»')
  await b.caption('5. Кабинет работодателя', 'Работодатель сам ищет кандидатов: по тексту потребности или в банке с фильтрами')
  await sleep(2500)
  await b.click('Подборки', { tags: 'a', wait: 1600 })
  await b.caption('Механика подбора: потребность обычным текстом', 'NLP определит специализацию, грейд, навыки, вилку и формат работы')
  await b.clickSel('textarea', 300)
  await b.type('Ищем Python-разработчика уровня Middle в команду платежей: FastAPI, PostgreSQL, Docker. Удалённо, 250–320 тыс. руб.', 18)
  await sleep(600)
  await b.click('Подобрать', { tags: 'button', wait: 3500 })
  await b.caption('Рекомендованные категории и рынок', 'Сколько кандидатов в категории, медиана ожиданий, доля в вашей вилке')
  await sleep(4500)
  await b.scrollTo(`[...document.querySelectorAll('div.card.card-hover')][0]`, 1400, 120)
  await b.caption('Ранжирование с объяснением', 'Выше — сильнее подтверждённый профиль и достижения ФСП; у каждого — причины «за» и «против»')
  await sleep(5500)

  // 8. Поиск нужной категории в банке кандидатов
  await b.click('Банк кандидатов', { tags: 'a', wait: 2200 })
  await b.caption('6. Поиск нужной категории', 'Банк кандидатов: специализация, грейд, навыки, ФСП — выдача только по категориям из теста')
  const sel = v => `[...document.querySelectorAll('select')].find(s => [...s.options].some(o => o.value === '${v}'))`
  await b.choose(sel('backend'), 'backend'); await sleep(1000)
  await b.choose(sel('middle'), 'middle'); await sleep(1000)
  await b.choose(sel('fresh'), 'fresh'); await sleep(2500)
  const cardLink = `[...document.querySelectorAll('a[href^="/employer/candidates/"]')].find(a => a.textContent.includes(${JSON.stringify(PID)}) || a.textContent.includes(${JSON.stringify(CANDIDATE.name)}))`
  await b.scrollTo(cardLink, 1000, 220)
  await b.caption('Наш кандидат — в категории «Backend · Middle»', 'Категория из теста; среди недавно активных — сверху')
  await sleep(3500)
  await b.clickEl(cardLink, CANDIDATE.name, 2500)
  await b.caption('Карточка кандидата', 'Грейд и навыки подтверждены тестом; контакты скрыты до согласия кандидата')
  await sleep(3500)
  await b.scrollTo(`[...document.querySelectorAll('h3')].find(h => h.textContent.trim() === 'Контакты')`, 1000, 260)
  await sleep(3000)

  // 9. Приглашение конкретному человеку
  await b.click('Пригласить', { tags: 'button', wait: 1500 })
  await b.caption('7. Приглашение с вилкой', 'Описание, компания, способ связи и обязательная вилка «от–до»; вакансия — по желанию')
  await b.choose(`document.querySelector('[role=dialog] select')`, VACANCY)
  await sleep(4500)
  await b.click('Отправить приглашение', { tags: 'button', wait: 2500 })

  // 10. Механика тестирования: как по вакансии формируется тест
  await b.click('Потребности', { tags: 'a', wait: 2000 })
  await b.clickText(VACANCY, { tags: 'a', wait: 2500 })
  await b.click('Тест по вакансии', { tags: 'button', wait: 2800 })
  await b.caption('Механика тестирования: тест по вакансии', 'Блюпринт по доменам из требований вакансии; навыки вакансии усиливают свои разделы')
  await sleep(5500)
  await b.scrollTo(`[...document.querySelectorAll('h3')].find(h => h.textContent.includes('Уникальность вариантов'))`, 1200, 140)
  await b.caption('Одно семейство — разные варианты', 'Три кандидата получают разные данные и ответы при одинаковой сложности')
  await sleep(5500)

  // 11. Кандидат принимает приглашение — контакты открываются
  await b.loginAs(CANDIDATE.email, CANDIDATE.password)
  await b.click('Приглашения', { tags: 'a', wait: 2000 })
  await b.caption('8. Приглашение у кандидата', 'Условия видны до общения: компания, вилка, формат, описание')
  await b.clickSel('button.card.card-hover', 1600)
  await sleep(3500)
  await b.click('Принять и открыть контакты', { tags: 'button', wait: 2500 })
  await b.caption('Контакты открыты', 'Обеим сторонам и только после согласия кандидата')
  await sleep(4000)

  // 12. Работодатель: статус «принято» и контакты кандидата
  await b.login('Работодатель «ТехноПульс»')
  await b.click('Приглашения', { tags: 'a', wait: 2200 })
  await b.caption('Статус видят обе стороны', 'Отправлено → прочитано → принято; контакты кандидата открыты в карточке')
  await sleep(3500)
  await b.clickEl(`[...document.querySelectorAll('a[href^="/employer/candidates/"]')].find(a => a.textContent.includes(${JSON.stringify(CANDIDATE.name)}) || a.textContent.includes(${JSON.stringify(PID)}))`, CANDIDATE.name, 2500)
  await b.scrollTo(`[...document.querySelectorAll('h3')].find(h => h.textContent.trim() === 'Контакты')`, 1000, 260)
  await b.caption('Выход на контакт состоялся', 'Работодатель видит контакты кандидата — дальше общение напрямую')
  await sleep(4500)

  // 13. Методика и валидация
  await b.goto(BASE + '/methodology', 2500)
  await b.caption('Как мы проверили механики', 'Собственная валидация на популяции с известной истиной: тест, подбор, устойчивость к утечкам')
  await sleep(3500)
  for (const t of ['сопоставимый', 'Слитые ответы', 'Доля релевантных']) {
    await b.scrollTo(`[...document.querySelectorAll('h2')].find(h => h.textContent.includes(${JSON.stringify(t)}))`, 1500)
    await sleep(3200)
  }

  // 14. Проверка подбора на своих данных (критерий оценки: доля релевантных в топе на наборе пар)
  await b.goto(BASE + '/evaluate', 2200)
  await b.caption('Проверьте подбор на своих данных', 'Набор пар «вакансия — кандидат» в JSON или CSV: метрики рядом с поиском по ключевым словам')
  await sleep(3000)
  await b.click('Запустить на примере', { tags: 'button', wait: 7000 })
  await b.scrollTo(`[...document.querySelectorAll('p')].find(p => p.textContent.includes('Доля релевантных'))`, 1000, 160)
  await b.caption('Доля релевантных в топ-10: 0,70 против 0,38', 'Та же выдача, что у работодателя, против поиска по ключевым словам на тех же данных')
  await sleep(4000)
  await b.clickSel('div.border-t > button', 1500)
  await sleep(4500)

  // 15. Финальная карточка
  await b.caption('')
  await b.card(card('Спасибо!', ['github.com/andercat2/fsp-career', 'docker compose up --build → localhost:8080'], TEAM))
  await sleep(6000)
}

// ----------------------------------------------------------------- сборка MP4
function encode(frames, cuts) {
  const inCut = t => cuts.some(([a, b]) => t > a && t < b)
  const shift = t => cuts.filter(([, b]) => b <= t).reduce((s, [a, b]) => s + (b - a), 0)
  const kept = frames.filter(f => !inCut(f.ts)).map(f => ({ ...f, t: f.ts - shift(f.ts) }))
  const lines = []
  kept.forEach((f, i) => {
    const d = i + 1 < kept.length ? Math.max(1 / 60, kept[i + 1].t - f.t) : 1.5
    lines.push(`file '${f.f.replace(/\\/g, '/')}'`, `duration ${d.toFixed(4)}`)
  })
  lines.push(`file '${kept[kept.length - 1].f.replace(/\\/g, '/')}'`)
  const list = path.join(WORK, 'frames.txt')
  fs.writeFileSync(list, lines.join('\n'))
  execFileSync(FFMPEG, ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', list,
    '-vf', 'fps=30,scale=1920:1080:flags=lanczos,format=yuv420p', '-c:v', 'libx264', '-preset', 'medium', '-crf', '21',
    '-movflags', '+faststart', OUT], { stdio: 'inherit' })
  const dur = kept[kept.length - 1].t - kept[0].t
  console.log(`видео: ${OUT} · ${kept.length} кадров · ${Math.round(dur)} с`)
}

async function main() {
  const profile = path.join(WORK, 'profile')
  const proc = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`,
    `--window-size=${W},${H}`, '--hide-scrollbars', '--force-color-profile=srgb', '--lang=ru-RU', 'about:blank'], { stdio: 'ignore' })
  let targets
  for (let i = 0; i < 50; i++) { try { targets = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); if (targets.length) break } catch { } await sleep(200) }
  const ws = new WebSocket(targets.find(x => x.type === 'page').webSocketDebuggerUrl)
  await new Promise(r => { ws.onopen = r })
  const b = new Browser(ws)
  await b.send('Page.enable')
  await b.send('Runtime.enable')
  await b.send('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: DPR, mobile: false })
  await b.send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: 'light' }] })
  await b.send('Page.addScriptToEvaluateOnNewDocument', { source: OVERLAY })
  // запись начинается с титульной карточки: главная загружена под ней, шрифты готовы
  await b.goto(BASE + '/', 1500)
  await b.card(TITLE, true)
  await b.ev('document.fonts.ready.then(() => true)')
  await sleep(500)
  await b.send('Page.startScreencast', { format: 'jpeg', quality: 82, maxWidth: W * DPR, maxHeight: H * DPR, everyNthFrame: 2 })
  try {
    await scenario(b)
  } finally {
    await b.send('Page.stopScreencast')
    await sleep(500)
    ws.close(); proc.kill()
  }
  encode(b.frames, b.cuts)
  fs.rmSync(WORK, { recursive: true, force: true })
}
main().catch(e => { console.error(e); process.exit(1) })
