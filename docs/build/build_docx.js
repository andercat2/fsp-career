// Сборка сопроводительной документации: docs/documentation.md → DOCX (обложка, оглавление, таблицы, рисунки).
// Запуск: node build_docx.js <documentation.md> <out.docx> [pages.json]
//   pages.json — номера страниц заголовков для оглавления (второй проход, см. build_pdf.py).
// Поддерживаемая разметка: #/##/### заголовки, абзацы, списки (- и 1.), таблицы, ![подпись](файл), блоки ```,
// **жирный**, `код`, [текст](ссылка) и служебные комментарии <!-- toc -->, <!-- pagebreak -->,
// <!-- include: файл.md -->, <!-- md-only --> (следующий блок только для Markdown).
const fs = require('fs')
const path = require('path')
const {
  AlignmentType, BorderStyle, Bookmark, Document, ExternalHyperlink, Footer, Header, HeadingLevel, ImageRun,
  InternalHyperlink, LeaderType, LevelFormat, Packer, PageBreak, PageNumber, Paragraph, ShadingType, Tab,
  TabStopType, Table, TableCell, TableRow, TextRun, VerticalAlign, WidthType,
} = require('docx')

const [mdPath, outPath, pagesPath] = process.argv.slice(2)
const MD_DIR = path.dirname(path.resolve(mdPath))
const ROOT = path.resolve(MD_DIR, '..')
const PAGES = pagesPath && fs.existsSync(pagesPath) ? JSON.parse(fs.readFileSync(pagesPath, 'utf8')) : {}

const C = { deep: '310F53', pink: 'FF0053', purple: '8E24AA', lav: '8A83D1', ink: '1C1D22', muted: '5B6475', soft: 'F6F4FA', line: 'DDD8EA' }
const FONT = 'Arial'
const MONO = 'Consolas'
const PAGE_W = 11906, MARGIN_X = 1134, MARGIN_Y = 1020
const CONTENT_W = PAGE_W - 2 * MARGIN_X // 9638 DXA
const PX_PER_DXA = 96 / 1440

// ---------------------------------------------------------------- инлайн-разметка
function inline(text, base = {}) {
  const out = []
  const re = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g
  let last = 0, m
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), ...base }))
    const t = m[0]
    if (t.startsWith('**')) out.push(...inline(t.slice(2, -2), { ...base, bold: true }))
    else if (t.startsWith('`')) out.push(new TextRun({ text: t.slice(1, -1), ...base, font: MONO, size: Math.round((base.size || 20) * 0.92), color: base.color || C.purple }))
    else {
      const [, label, url] = t.match(/\[([^\]]+)\]\(([^)]+)\)/)
      if (/^https?:/.test(url)) out.push(new ExternalHyperlink({ link: url, children: [new TextRun({ text: label, ...base, color: C.purple, underline: {} })] }))
      else out.push(new TextRun({ text: label, ...base }))
    }
    last = m.index + t.length
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), ...base }))
  return out
}

// ---------------------------------------------------------------- разбор Markdown на блоки
function parseBlocks(src) {
  const lines = src.replace(/\r/g, '').split('\n')
  const blocks = []
  let i = 0
  while (i < lines.length) {
    const line = lines[i]
    if (!line.trim()) { i++; continue }
    let m
    if ((m = line.match(/^<!--\s*(toc|pagebreak|md-only)\s*-->$/))) { blocks.push({ type: m[1] }); i++; continue }
    if ((m = line.match(/^<!--\s*widths:\s*([\d,\s]+)-->$/))) { blocks.push({ type: 'widths', value: m[1].split(',').map(Number) }); i++; continue }
    if ((m = line.match(/^<!--\s*include:\s*(\S+)\s*-->$/))) {
      blocks.push(...parseBlocks(fs.readFileSync(path.join(MD_DIR, m[1]), 'utf8'))); i++; continue
    }
    if ((m = line.match(/^(#{1,3})\s+(.*)$/))) { blocks.push({ type: 'h', level: m[1].length, text: m[2].trim() }); i++; continue }
    if (line.startsWith('```')) {
      const code = []
      i++
      while (i < lines.length && !lines[i].startsWith('```')) code.push(lines[i++])
      i++
      blocks.push({ type: 'code', lines: code }); continue
    }
    if ((m = line.match(/^!\[([^\]]*)\]\(([^)]+)\)\s*$/))) { blocks.push({ type: 'img', alt: m[1], src: m[2] }); i++; continue }
    if (line.startsWith('|')) {
      const rows = []
      while (i < lines.length && lines[i].startsWith('|')) {
        const cells = lines[i].trim().replace(/^\||\|$/g, '').split('|').map(s => s.trim())
        if (!cells.every(c => /^:?-{3,}:?$/.test(c))) rows.push(cells)
        i++
      }
      blocks.push({ type: 'table', rows }); continue
    }
    if (/^(\s*)[-*]\s+/.test(line) || /^\s*\d+\.\s+/.test(line)) {
      const ordered = /^\s*\d+\.\s+/.test(line)
      const items = []
      while (i < lines.length && (/^\s*([-*]|\d+\.)\s+/.test(lines[i]) || (/^\s{2,}\S/.test(lines[i]) && items.length))) {
        const l = lines[i]
        const mm = l.match(/^(\s*)([-*]|\d+\.)\s+(.*)$/)
        if (mm) items.push({ level: mm[1].length >= 2 ? 1 : 0, text: mm[3] })
        else items[items.length - 1].text += ' ' + l.trim()
        i++
      }
      blocks.push({ type: 'list', ordered, items }); continue
    }
    const para = [line.trim()]
    i++
    while (i < lines.length && lines[i].trim() && !/^(#|\||!\[|```|<!--|\s*[-*]\s|\s*\d+\.\s)/.test(lines[i])) para.push(lines[i++].trim())
    blocks.push({ type: 'p', text: para.join(' ') })
  }
  return blocks
}

// ---------------------------------------------------------------- элементы документа
const slug = (() => { let n = 0; return () => `h${++n}` })()
const headings = []

function heading(level, text) {
  const id = slug()
  if (level <= 2) headings.push({ id, level, text })
  const sizes = { 1: 34, 2: 26, 3: 22 }
  return new Paragraph({
    heading: [HeadingLevel.HEADING_1, HeadingLevel.HEADING_2, HeadingLevel.HEADING_3][level - 1],
    keepNext: true,
    spacing: { before: level === 1 ? 120 : 280, after: level === 1 ? 200 : 120 },
    border: level === 1 ? { bottom: { style: BorderStyle.SINGLE, size: 12, color: C.pink, space: 6 } } : undefined,
    children: [new Bookmark({ id, children: [new TextRun({ text, bold: true, font: FONT, size: sizes[level], color: C.deep })] })],
  })
}

function para(text, opts = {}) {
  const align = text.includes('`') ? AlignmentType.LEFT : AlignmentType.JUSTIFIED
  const keepNext = /:$/.test(text.trim()) // подводка к таблице, списку или примеру не отрывается от него
  return new Paragraph({ spacing: { after: 120, line: 290 }, alignment: align, keepNext, ...opts, children: inline(text, { size: 20, color: C.ink }) })
}

let listInstance = 0
function list(block) {
  listInstance++
  return block.items.map(it => new Paragraph({
    numbering: block.ordered ? { reference: 'num', level: it.level, instance: listInstance } : { reference: 'bul', level: it.level },
    spacing: { after: 70, line: 280 },
    children: inline(it.text, { size: 20, color: C.ink }),
  }))
}

function code(block) {
  const runs = []
  block.lines.forEach((l, k) => runs.push(new TextRun({ text: l || ' ', font: MONO, size: 16, color: C.ink, break: k ? 1 : 0 })))
  return new Paragraph({
    shading: { type: ShadingType.CLEAR, fill: C.soft, color: 'auto' },
    border: { left: { style: BorderStyle.SINGLE, size: 18, color: C.lav, space: 8 } },
    spacing: { before: 60, after: 160, line: 250 }, indent: { left: 140, right: 140 }, keepLines: true,
    children: runs,
  })
}

let figN = 0
function image(block) {
  const file = path.join(MD_DIR, block.src)
  const buf = fs.readFileSync(file)
  const w = buf.readUInt32BE(16), h = buf.readUInt32BE(20) // заголовок IHDR PNG
  const maxW = Math.round(CONTENT_W * PX_PER_DXA)
  const width = maxW, height = Math.round((h / w) * width)
  figN++
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 }, keepNext: true,
      children: [new ImageRun({ type: 'png', data: buf, transformation: { width, height } })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 220 },
      children: [new TextRun({ text: `Рисунок ${figN}. `, bold: true, size: 17, color: C.muted }), new TextRun({ text: block.alt, size: 17, color: C.muted, italics: true })] }),
  ]
}

function colWidths(rows) {
  const n = rows[0].length
  const lens = Array.from({ length: n }, (_, j) => rows.map(r => (r[j] || '').replace(/[*`]/g, '').length))
  const w = lens.map(ls => {
    const avg = ls.reduce((a, b) => a + b, 0) / ls.length
    const mx = Math.max(...ls)
    return Math.max(5, Math.min(70, 0.55 * avg + 0.45 * Math.min(mx, 90)))
  })
  const total = w.reduce((a, b) => a + b, 0)
  const dxa = w.map(x => Math.max(700, Math.round((x / total) * CONTENT_W)))
  const diff = CONTENT_W - dxa.reduce((a, b) => a + b, 0)
  dxa[dxa.indexOf(Math.max(...dxa))] += diff
  return dxa
}

function scaleWidths(parts) {
  const total = parts.reduce((a, b) => a + b, 0)
  const dxa = parts.map(x => Math.round((x / total) * CONTENT_W))
  dxa[dxa.length - 1] += CONTENT_W - dxa.reduce((a, b) => a + b, 0)
  return dxa
}

function table(block, hint) {
  const rows = block.rows
  const widths = hint && hint.length === rows[0].length ? scaleWidths(hint) : colWidths(rows)
  const border = { style: BorderStyle.SINGLE, size: 4, color: C.line }
  const borders = { top: border, bottom: border, left: border, right: border }
  const small = rows[0].length >= 6 || rows.length > 30
  const size = small ? 15 : 17
  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: widths,
    rows: rows.map((r, ri) => new TableRow({
      tableHeader: ri === 0,
      cantSplit: true,
      children: widths.map((wd, ci) => new TableCell({
        width: { size: wd, type: WidthType.DXA },
        borders,
        verticalAlign: VerticalAlign.CENTER,
        shading: ri === 0 ? { type: ShadingType.CLEAR, fill: C.deep, color: 'auto' }
          : ri % 2 === 0 ? { type: ShadingType.CLEAR, fill: C.soft, color: 'auto' } : undefined,
        margins: { top: 50, bottom: 50, left: 90, right: 90 },
        children: [new Paragraph({ spacing: { after: 0, line: 250 },
          children: inline(r[ci] || '', ri === 0 ? { size, bold: true, color: 'FFFFFF' } : { size, color: C.ink }) })],
      })),
    })),
  })
}

// ---------------------------------------------------------------- обложка и оглавление
function cover() {
  const logo = fs.readFileSync(path.join(ROOT, 'frontend/public/brand/fsp-logo-black.png'))
  const kpi = (v, l) => [new TextRun({ text: v, bold: true, size: 30, color: C.deep }), new TextRun({ text: '  ' + l, size: 18, color: C.muted })]
  // версия, дата и команда — из аннотации Markdown (до оглавления), чтобы обложка не расходилась с текстом
  const head = fs.readFileSync(mdPath, 'utf8').split('<!-- toc -->')[0]
  const [, version, date] = head.match(/Версия ([\d.]+), (\d+ \S+ \d{4}) г\./) || []
  const [team] = head.match(/Команда(?: «[^»]+»)?: [^.]+(?=\.)/) || []
  return [
    new Paragraph({ spacing: { after: 1800 }, children: [new ImageRun({ type: 'png', data: logo, transformation: { width: 300, height: 38 } })] }),
    new Paragraph({ spacing: { after: 160 }, children: [new TextRun({ text: 'СОПРОВОДИТЕЛЬНАЯ ДОКУМЕНТАЦИЯ', bold: true, size: 22, color: C.pink, characterSpacing: 40 })] }),
    new Paragraph({ spacing: { after: 200 }, children: [new TextRun({ text: 'ФСП Карьера', bold: true, size: 80, color: C.deep })] }),
    new Paragraph({ spacing: { after: 400 }, border: { bottom: { style: BorderStyle.SINGLE, size: 18, color: C.pink, space: 14 } },
      children: [new TextRun({ text: 'Платформа подбора ИТ-специалистов с обратной механикой: категория по тесту, выход на кандидата по инициативе работодателя, профиль с достижениями ФСП', size: 28, color: C.muted })] }),
    new Paragraph({ spacing: { after: 80 }, children: [new TextRun({ text: 'Специальный трек ФСП · хакатон «Лидеры цифровой трансформации — 2026»', size: 22, color: C.ink })] }),
    ...(team ? [new Paragraph({ spacing: { after: 80 }, children: [new TextRun({ text: team, size: 22, color: C.ink })] })] : []),
    new Paragraph({ spacing: { after: 1400 }, children: [new TextRun({ text: `Версия ${version} · ${date} г.`, size: 22, color: C.muted })] }),
    new Paragraph({ spacing: { after: 100 }, children: kpi('359', 'семейств заданий с уникальными вариантами для каждого кандидата') }),
    new Paragraph({ spacing: { after: 100 }, children: kpi('0,835', 'доля релевантных в топ-10 подборки (фильтры по резюме — 0,750)') }),
    new Paragraph({ spacing: { after: 100 }, children: kpi('3,1%', 'завышения грейда по тесту против 35,7% в самооценке резюме') }),
    new Paragraph({ spacing: { after: 100 }, children: kpi('800', 'одновременных пользователей без ошибок в нагрузочном тесте на одной машине') }),
    new Paragraph({ spacing: { after: 100 }, children: kpi('105', 'методов API в OpenAPI, 525 автотестов, запуск одной командой Docker') }),
  ]
}

function toc() {
  const out = [new Paragraph({ spacing: { after: 160 }, children: [new TextRun({ text: 'Содержание', bold: true, size: 34, color: C.deep })] })]
  for (const h of headings) {
    const page = PAGES[h.id] != null ? String(PAGES[h.id]) : '00'
    out.push(new Paragraph({
      tabStops: [{ type: TabStopType.RIGHT, position: CONTENT_W, leader: LeaderType.DOT }],
      indent: { left: h.level === 1 ? 0 : 360 },
      spacing: { before: h.level === 1 ? 60 : 0, after: 0, line: 240 },
      children: [new InternalHyperlink({ anchor: h.id, children: [
        new TextRun({ text: h.text, bold: h.level === 1, size: h.level === 1 ? 20 : 18, color: h.level === 1 ? C.deep : C.ink }),
        new TextRun({ children: [new Tab(), page], bold: h.level === 1, size: h.level === 1 ? 20 : 18, color: C.muted }),
      ] })],
    }))
  }
  return out
}

// ---------------------------------------------------------------- сборка
const src = fs.readFileSync(mdPath, 'utf8')
let blocks = parseBlocks(src)
const tocAt = blocks.findIndex(b => b.type === 'toc')
blocks = blocks.slice(tocAt + 1) // заголовок и аннотация Markdown заменяются обложкой

const body = []
let skipNext = false
let widthHint = null
for (const b of blocks) {
  if (b.type === 'md-only') { skipNext = true; continue }
  if (skipNext) { skipNext = false; continue }
  if (b.type === 'pagebreak') body.push(new Paragraph({ children: [new PageBreak()] }))
  else if (b.type === 'h') body.push(heading(b.level, b.text))
  else if (b.type === 'p') body.push(para(b.text))
  else if (b.type === 'list') body.push(...list(b))
  else if (b.type === 'code') body.push(code(b))
  else if (b.type === 'img') body.push(...image(b))
  else if (b.type === 'widths') widthHint = b.value
  else if (b.type === 'table') { body.push(table(b, widthHint)); widthHint = null; body.push(new Paragraph({ spacing: { after: 120 }, children: [] })) }
}

const headerPara = new Paragraph({
  border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: C.line, space: 4 } },
  tabStops: [{ type: TabStopType.RIGHT, position: CONTENT_W }],
  children: [new TextRun({ text: 'ФСП Карьера', bold: true, size: 16, color: C.deep }),
    new TextRun({ children: [new Tab(), 'Сопроводительная документация'], size: 16, color: C.muted })],
})
const footerPara = new Paragraph({ alignment: AlignmentType.RIGHT,
  children: [new TextRun({ children: ['стр. ', PageNumber.CURRENT, ' из ', PageNumber.TOTAL_PAGES], size: 16, color: C.muted })] })

const bulletLevels = [0, 1].map(l => ({ level: l, format: LevelFormat.BULLET, text: l ? '–' : '•', alignment: AlignmentType.LEFT,
  style: { paragraph: { indent: { left: 360 + l * 360, hanging: 260 } }, run: { color: l ? C.muted : C.pink } } }))
const numLevels = [0, 1].map(l => ({ level: l, format: LevelFormat.DECIMAL, text: `%${l + 1}.`, alignment: AlignmentType.LEFT,
  style: { paragraph: { indent: { left: 360 + l * 360, hanging: 300 } }, run: { bold: true, color: C.deep } } }))

const doc = new Document({
  creator: 'Команда «ФСП Карьера»',
  title: 'ФСП Карьера — сопроводительная документация',
  description: 'Архитектура, механики тестирования и подбора, валидация, интеграция с ФСП, API, запуск',
  styles: {
    default: { document: { run: { font: FONT, size: 20, color: C.ink } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: FONT, size: 34, bold: true, color: C.deep }, paragraph: { outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: FONT, size: 26, bold: true, color: C.deep }, paragraph: { outlineLevel: 1 } },
      { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: FONT, size: 22, bold: true, color: C.deep }, paragraph: { outlineLevel: 2 } },
    ],
  },
  numbering: { config: [{ reference: 'bul', levels: bulletLevels }, { reference: 'num', levels: numLevels }] },
  features: { updateFields: false },
  sections: [
    { properties: { page: { size: { width: PAGE_W, height: 16838 }, margin: { top: 1400, bottom: 1200, left: 1300, right: 1300 } } }, children: cover() },
    { properties: { page: { size: { width: PAGE_W, height: 16838 }, margin: { top: MARGIN_Y, bottom: MARGIN_Y, left: MARGIN_X, right: MARGIN_X, header: 500, footer: 500 } } },
      headers: { default: new Header({ children: [headerPara] }) },
      footers: { default: new Footer({ children: [footerPara] }) },
      children: [...toc(), new Paragraph({ children: [new PageBreak()] }), ...body] },
  ],
})

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(outPath, buf)
  fs.writeFileSync(outPath.replace(/\.docx$/, '.headings.json'), JSON.stringify(headings, null, 1))
  console.log(`DOCX: ${outPath} · заголовков в оглавлении: ${headings.length} · рисунков: ${figN}`)
})
