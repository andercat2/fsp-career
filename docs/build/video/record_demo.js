// Запись демонстрационного видео: headless Chrome проходит сценарий по стенду (CDP screencast), кадры собираются
// в MP4. На экране — подписи шагов и курсор; долгие ожидания (генерация вопроса моделью) вырезаются.
//
//   node docs/build/video/record_demo.js <out.mp4> --ffmpeg <путь к ffmpeg> [--base http://localhost:8080]
//                                         [--project fsp-career]
//
// Нужен запущенный стенд (docker compose) с чистыми демо-данными; для сцены с LLM — Ollama на хосте (иначе демо-режим).
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
  async login(label) {
    await this.ev(`localStorage.clear(); sessionStorage.removeItem('__cur'); true`)
    await this.goto(BASE + '/login', 1500)
    await this.click(label, { tags: 'button' })
    await this.click('Войти', { tags: 'button[type=submit]', wait: 2200 })
  }
}

function card(title, lines, small) {
  return `<div class="w"><img src="/brand/fsp-logo-white.png" alt=""><h1>${title}</h1>${lines.map(l => `<p>${l}</p>`).join('')}` +
    (small ? `<p class="s">${small}</p>` : '') + '</div>'
}

// ----------------------------------------------------------------- сценарий
const TEAM = 'Команда: Мурехин Ярослав Андреевич, Воронин Артём Тимофеевич'
const TITLE = card('ФСП Карьера', ['Подбор ИТ-специалистов с обратной механикой:', 'уровень подтверждает тест, работодатель приходит к кандидату сам'],
  `${TEAM}<br>Хакатон «Лидеры цифровой трансформации — 2026» · специальный трек ФСП`)

async function scenario(b) {
  // 1. Титульная карточка (уже на экране поверх главной — см. main) растворяется и открывает главную
  await sleep(5500)
  await b.card(null)
  await sleep(1200)

  // 2. Главная
  await b.caption('Главная страница', 'Работодатель находит кандидата сам — с предложением и вилкой зарплаты')
  await sleep(3500)
  await b.scrollTo(`[...document.querySelectorAll('h2')].find(h => h.textContent.includes('Инициатива'))`)
  await b.caption('Как это работает', 'Кандидат один раз подтверждает уровень — дальше предложения приходят сами')
  await sleep(4000)
  await b.scrollTo(`[...document.querySelectorAll('h2')].find(h => h.textContent.includes('Доверие к уровню'))`)
  await b.caption('Тест, который бесполезно «сливать»', 'У каждого кандидата свои данные, код и ответы; общая шкала IRT')
  await sleep(4000)
  await b.scrollTo(`[...document.querySelectorAll('h2')].find(h => h.textContent.includes('Цифры'))`)
  await b.caption('Проверено валидацией', 'Грейд по тесту завышен у 3% кандидатов против 36% в резюме')
  await sleep(4000)
  await b.ev('__demo.scrollTo(0, 1200)'); await sleep(1300)

  // 3. Экспресс-тест без регистрации
  await b.caption('Попробовать без регистрации', 'Демо-кандидат в один клик и экспресс-тест: 8 заданий, около 7 минут')
  await sleep(2000)
  await b.click('Без регистрации: экспресс-тест', { wait: 1200 })
  const dlg = `document.querySelector('[role=dialog]')`
  await b.click('Middle', { scope: dlg, tags: 'button', wait: 500 })
  await b.click('Согласен', { scope: dlg, tags: 'label', wait: 800 })
  await b.click('Начать тест', { scope: dlg, tags: 'button', wait: 3000 })
  await b.caption('Адаптивный тест', 'Свой вариант задания каждому, время на ответ — по сложности задания')
  await sleep(3500)
  const q = await b.ev(`(() => { const o = document.querySelector('[data-proctored] button'); const i = document.querySelector('[data-proctored] input'); return o ? 'option' : i ? 'input' : null })()`)
  if (q === 'option') await b.clickSel('[data-proctored] button', 500)
  else if (q === 'input') { await b.clickSel('[data-proctored] input', 300); await b.type('42', 120) }
  await sleep(600)
  await b.click('Ответить', { tags: 'button', wait: 2500 })
  await b.caption('Прокторинг в браузере', 'Снимок экрана — предупреждение, повтор — досрочное завершение со штрафом')
  await b.key('PrintScreen', 'PrintScreen', 44)
  await sleep(4000)
  await b.click('Понятно, продолжить тест', { tags: 'button', wait: 800 })
  const token = await b.ev('location.pathname.split("/").pop()')
  await b.caption('⏩ Ускорено: остальные задания', '')
  await b.cut(async () => {
    execFileSync('docker', ['compose', '-p', PROJECT, 'exec', '-T', 'backend', 'python', '-', token, '1110111'],
      { input: fs.readFileSync(path.join(__dirname, 'finish_session.py')), cwd: ROOT })
    await b.goto(`${BASE}/candidate/testing/${token}`, 2500)
  })
  await b.caption('Результат экспресс-теста', 'Вероятный грейд и вероятности всех грейдов; категорию присваивает полный тест')
  await sleep(4500)
  await b.scrollTo(`[...document.querySelectorAll('h3')].find(h => h.textContent.includes('Вероятности грейдов'))`, 1200, 140)
  await sleep(3500)

  // 4. Работодатель: подборка по тексту потребности и приглашение
  await b.login('Работодатель «ТехноПульс»')
  await b.caption('Кабинет работодателя', 'Демо-компания «ТехноПульс»')
  await sleep(2500)
  await b.click('Подборки', { tags: 'a', wait: 1500 })
  await b.caption('Потребность — обычным текстом', 'NLP определит специализацию, грейд, навыки, вилку и формат работы')
  await b.clickSel('textarea', 300)
  await b.type('Ищем Python-разработчика уровня Middle в команду платежей: FastAPI, PostgreSQL, Docker. Удалённо, 250–320 тыс. руб.', 22)
  await sleep(800)
  await b.click('Подобрать', { tags: 'button', wait: 3500 })
  await b.caption('Подборка', 'Рекомендованные категории с аналитикой рынка: медиана ожиданий, доля в вашей вилке, ФСП')
  await sleep(4500)
  await b.scrollTo(`[...document.querySelectorAll('div.card.card-hover')][0]`, 1400, 120)
  await b.caption('Кандидаты с объяснением', 'Совпадение, навыки со статусом «подтверждён тестом», причины «за» и «против»')
  await sleep(5000)
  await b.click('Пригласить', { tags: 'button', wait: 1500 })
  await b.caption('Приглашение', 'Вилка «от–до» обязательна, видна вероятность отклика; контакты — после согласия')
  await sleep(4500)
  await b.click('Отправить приглашение', { tags: 'button', wait: 2500 })

  // 5. Кандидат: приглашение, принятие, категория
  await b.login('Кандидат с категорией')
  await b.caption('Кабинет кандидата', 'Две специализации — две категории: Backend · Middle и DevOps · Junior')
  await sleep(3500)
  await b.click('Приглашения', { tags: 'a', wait: 1800 })
  await b.clickSel('button.card.card-hover', 1500)
  await b.caption('Предложение с условиями — до общения', 'Компания, вилка, формат, описание; принять или отклонить с причиной')
  await sleep(4000)
  const canAccept = await b.ev(`!![...document.querySelectorAll('button')].find(e => e.textContent.includes('Принять и открыть контакты'))`)
  if (canAccept) {
    await b.click('Принять и открыть контакты', { tags: 'button', wait: 2500 })
    await b.caption('Контакты открыты', 'Обеим сторонам и только после согласия кандидата')
    await sleep(3500)
  }
  await b.click('Категория и грейд', { tags: 'a', wait: 2000 })
  await b.caption('Категория и грейд', 'Специализация × грейд по тесту, профиль компетенций и история тестов')
  await sleep(5000)

  // 6. Администратор: черновики заданий от LLM
  await b.login('Администратор')
  await b.caption('Банк заданий', '359 семейств: экспозиция, дрейф решаемости, калибровка пилотных заданий')
  await sleep(3500)
  await b.click('Черновики от LLM', { tags: 'a', wait: 2000 })
  await b.caption('Черновики заданий от LLM', 'Модель предлагает вопрос — эксперт принимает, правит или отклоняет')
  await sleep(3000)
  await b.ev(`(() => { const s = [...document.querySelectorAll('select')][1]; const o = s && [...s.options].find(o => o.value === 'sql');
    if (!o) return false
    const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set; set.call(s, o.value);
    s.dispatchEvent(new Event('change', { bubbles: true })); return true })()`)
  await sleep(700)
  await b.click('3', { tags: 'button', wait: 400 })
  await b.ev(`(() => { const i = document.querySelector('input[type=number]'); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    set.call(i, '1'); i.dispatchEvent(new Event('input', { bubbles: true })); return true })()`)
  await sleep(600)
  await b.click('Подготовить черновики', { tags: 'button', wait: 1500 })
  await b.caption('⏩ Ускорено: модель пишет вопрос и перепроверяет его', 'Qwen3-14B локально через Ollama, около минуты')
  await b.cut(async () => {
    for (let i = 0; i < 120; i++) {
      const st = await b.ev(`fetch('/api/v1/admin/item-drafts?status=pending', { headers: { Authorization: 'Bearer ' + localStorage.getItem('fsp_career_token') } })
        .then(r => r.json()).then(d => d.batch && d.batch.status)`)
      if (st && st !== 'running') break
      await sleep(3000)
    }
    await b.goto(BASE + '/admin/drafts', 2500)
  })
  await b.scrollTo(`document.querySelector('main .card.overflow-hidden')`, 1000, 110)
  await b.caption('Проверка экспертом', 'Правильный ответ отмечен; автопроверки и самопроверка модели подсказывают, где ошибка')
  await sleep(6000)
  await b.click('Принять как есть', { tags: 'button', wait: 2500 })
  await b.caption('Вопрос в банке — пилотный', 'На оценку не влияет, пока трудность не откалибрована по 40 ответам')
  await sleep(3500)

  // 7. Методика
  await b.goto(BASE + '/methodology', 2500)
  await b.caption('Методика и валидация', 'Синтетическая популяция с известной истиной, базовые линии и абляции')
  await sleep(3500)
  for (const t of ['сопоставимый', 'Слитые ответы', 'Доля релевантных']) {
    await b.scrollTo(`[...document.querySelectorAll('h2')].find(h => h.textContent.includes(${JSON.stringify(t)}))`, 1500)
    await sleep(3200)
  }

  // 8. Финальная карточка
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
