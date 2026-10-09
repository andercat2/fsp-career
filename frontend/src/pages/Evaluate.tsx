import { useRef, useState, type ReactNode } from 'react'
import { useMutation } from '@tanstack/react-query'
import clsx from 'clsx'
import { motion } from 'framer-motion'
import { ChevronDown, Download, FileUp, FlaskConical, Info, Play } from 'lucide-react'
import { Blobs, EASE } from '@/lib/motion'
import { api } from '@/lib/api'
import { Alert, Badge, Button, Card, Checkbox } from '@/components/ui'
import { PublicHeader } from './Landing'

/**
 * Стенд проверки подбора на чужом наборе пар «вакансия — кандидат» (критерий оценки: доля релевантных кандидатов
 * в топе выдачи). Набор загружается JSON или CSV, считается на сервере (POST /eval/dataset) и не сохраняется.
 */
type Dataset = { vacancies: any[]; candidates: any[]; labels: any[]; k?: number }

const CSV_COLUMNS = ['vacancy_id', 'vacancy_title', 'vacancy_text', 'candidate_id', 'candidate_text', 'relevance',
  'candidate_specialization', 'candidate_grade']
const CSV_TEMPLATE = [CSV_COLUMNS.join(';'),
  'v1;Python-разработчик (Middle);"Ищем Python-разработчика уровня Middle: FastAPI, PostgreSQL, Docker. Удалённо, 250–320 тыс. руб.";c1;"Backend-разработчик, Python, 4 года: FastAPI, PostgreSQL, Docker, Kafka. Middle. Москва, удалённо";3;backend;middle',
  'v1;Python-разработчик (Middle);"Ищем Python-разработчика уровня Middle: FastAPI, PostgreSQL, Docker. Удалённо, 250–320 тыс. руб.";c2;"Frontend-разработчик: React, TypeScript, 2 года. Junior. Санкт-Петербург, офис";0;;',
].join('\n')

/** CSV по RFC 4180: кавычки, переносы строк внутри поля; разделитель — «;», «,» или табуляция (по заголовку). */
function parseCsv(src: string): string[][] {
  const text = src.replace(/^﻿/, '')
  const head = text.split(/\r?\n/, 1)[0]
  const delim = [';', '\t', ','].sort((a, b) => head.split(b).length - head.split(a).length)[0]
  const rows: string[][] = []
  let row: string[] = [], cell = '', quoted = false
  for (let i = 0; i < text.length; i++) {
    const ch = text[i]
    if (quoted) {
      if (ch === '"') { if (text[i + 1] === '"') { cell += '"'; i++ } else quoted = false } else cell += ch
    } else if (ch === '"') quoted = true
    else if (ch === delim) { row.push(cell); cell = '' }
    else if (ch === '\n' || ch === '\r') {
      if (ch === '\r' && text[i + 1] === '\n') i++
      row.push(cell); rows.push(row); row = []; cell = ''
    } else cell += ch
  }
  if (cell || row.length) { row.push(cell); rows.push(row) }
  return rows.filter(r => r.some(c => c.trim()))
}

function csvToDataset(rows: string[][]): Dataset {
  const cols = rows[0].map(c => c.trim().toLowerCase())
  const need = ['vacancy_id', 'vacancy_text', 'candidate_id', 'candidate_text', 'relevance']
  const missing = need.filter(c => !cols.includes(c))
  if (missing.length) throw new Error(`В CSV нет столбцов: ${missing.join(', ')}`)
  const at = (r: string[], c: string) => (cols.includes(c) ? (r[cols.indexOf(c)] ?? '').trim() : '')
  const vac = new Map<string, any>(), cand = new Map<string, any>(), labels: any[] = []
  for (const r of rows.slice(1)) {
    const v = at(r, 'vacancy_id'), c = at(r, 'candidate_id')
    if (!v || !c) continue
    if (!vac.has(v)) vac.set(v, { id: v, title: at(r, 'vacancy_title'), text: at(r, 'vacancy_text') })
    if (!cand.has(c)) {
      const spec = at(r, 'candidate_specialization'), grade = at(r, 'candidate_grade').toLowerCase()
      cand.set(c, { id: c, text: at(r, 'candidate_text'), ...(spec && grade ? { specialization: spec, grade } : {}) })
    }
    const rel = Number(at(r, 'relevance'))
    if (Number.isFinite(rel) && rel > 0) labels.push({ vacancy: v, candidate: c, relevance: Math.min(3, Math.round(rel)) })
  }
  return { vacancies: [...vac.values()], candidates: [...cand.values()], labels }
}

async function readDataset(file: File): Promise<Dataset> {
  const text = await file.text()
  if (/\.json$/i.test(file.name) || text.trimStart().startsWith('{')) {
    const d = JSON.parse(text)
    if (!d.vacancies || !d.candidates) throw new Error('В JSON нужны поля vacancies, candidates и labels')
    return { vacancies: d.vacancies, candidates: d.candidates, labels: d.labels ?? [], k: d.k }
  }
  return csvToDataset(parseCsv(text))
}

function saveText(name: string, text: string, type: string) {
  const url = URL.createObjectURL(new Blob([text], { type }))
  const a = document.createElement('a')
  a.href = url; a.download = name; a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

const num = (x?: number | null) => (x == null ? '—' : x.toFixed(2).replace('.', ','))
const REL_TONE = ['gray', 'amber', 'green', 'green'] as const

function Label({ value }: { value: number }) {
  return <Badge tone={REL_TONE[value] ?? 'gray'} className="!px-1.5 tabular-nums">{value || '—'}</Badge>
}

function Kpi({ label, ours, keyword }: { label: string; ours?: number | null; keyword?: number | null }) {
  return (
    <div className="rounded-2xl bg-surface p-5">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-3xl font-extrabold text-fsp-deep">{num(ours)}</p>
      <p className="mt-1 text-xs text-slate-500">поиск по ключевым словам — {num(keyword)}</p>
    </div>
  )
}

function VacancyRow({ v, k }: { v: any; k: number }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="border-t border-slate-100 first:border-t-0">
      <button type="button" onClick={() => setOpen(o => !o)}
        className="grid w-full grid-cols-[1fr_auto] items-center gap-4 px-5 py-4 text-left transition hover:bg-surface/60 sm:grid-cols-[1fr_8.5rem_6rem_6rem_auto]">
        <span className="min-w-0">
          <span className="block truncate font-semibold text-fsp-deep">{v.title}</span>
          <span className="block truncate text-xs text-slate-500">{v.need.specialization} · {v.need.grades.join(' / ')}
            {v.need.must_skills.length > 0 && <> · {v.need.must_skills.slice(0, 4).join(', ')}</>}</span>
          <span className="mt-1 block text-xs text-slate-600 sm:hidden">{v.relevant_total} релевантных · P@{k} <b className="text-fsp-deep">{num(v.ours.p_at_k)}</b> · ключевые слова {num(v.keyword.p_at_k)}</span>
        </span>
        <span className="hidden whitespace-nowrap text-sm text-slate-600 sm:block">{v.relevant_total} релевантных</span>
        <span className="hidden text-sm sm:block"><b className="text-fsp-deep">{num(v.ours.p_at_k)}</b> <span className="text-slate-400">P@{k}</span></span>
        <span className="hidden text-sm text-slate-500 sm:block">{num(v.keyword.p_at_k)} <span className="text-slate-400">ключ.</span></span>
        <ChevronDown className={clsx('h-4 w-4 text-slate-400 transition', open && 'rotate-180')} />
      </button>
      {open && (
        <div className="grid gap-4 px-5 pb-5 lg:grid-cols-[1.6fr_1fr]">
          <div>
            <p className="label">Выдача платформы · nDCG@{k} {num(v.ours.ndcg)} · MRR {num(v.ours.mrr)} · в выдаче {v.returned}</p>
            <ol className="space-y-1.5">
              {v.ours.top.map((c: any, i: number) => (
                <li key={c.id} className="rounded-xl bg-surface px-3 py-2 text-sm">
                  <div className="flex items-center gap-2">
                    <span className="w-5 text-right text-xs text-slate-400">{i + 1}</span><Label value={c.label} />
                    <b className="text-fsp-deep">{c.id}</b><span className="truncate text-xs text-slate-500">{c.category}</span>
                    <span className="ml-auto text-xs tabular-nums text-slate-400">{num(c.score)}</span>
                  </div>
                  {c.reasons[0] && <p className="mt-1 pl-7 text-xs text-slate-500">{c.reasons[0]}</p>}
                </li>))}
            </ol>
          </div>
          <div>
            <p className="label">Поиск по ключевым словам · nDCG@{k} {num(v.keyword.ndcg)} · MRR {num(v.keyword.mrr)}</p>
            <ol className="space-y-1.5">
              {v.keyword.top.map((c: any, i: number) => (
                <li key={c.id} className="flex items-center gap-2 rounded-xl bg-surface px-3 py-2 text-sm">
                  <span className="w-5 text-right text-xs text-slate-400">{i + 1}</span><Label value={c.label} />
                  <b className="text-fsp-deep">{c.id}</b><span className="truncate text-xs text-slate-500">{c.category}</span>
                </li>))}
            </ol>
          </div>
        </div>
      )}
    </div>
  )
}

function Format({ title, children }: { title: string; children: ReactNode }) {
  return <div className="rounded-2xl bg-surface p-4 text-sm leading-relaxed text-slate-600"><p className="mb-1 font-semibold text-fsp-deep">{title}</p>{children}</div>
}

export function Evaluate() {
  const fileRef = useRef<HTMLInputElement>(null)
  const [source, setSource] = useState<string | null>(null)
  const [dataset, setDataset] = useState<Dataset | null>(null)
  const [textOnly, setTextOnly] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const run = useMutation({
    mutationFn: (d: Dataset) => api('/eval/dataset', {
      body: textOnly ? { ...d, candidates: d.candidates.map(({ specialization, grade, theta, verified_skills, ...c }) => c) } : d,
    }),
    onError: (e: any) => setError(e.message),
  })
  const start = (d: Dataset, name: string) => { setError(null); setDataset(d); setSource(name); run.mutate(d) }
  const sample = async () => {
    try { start(await fetch('/eval-sample.json').then(r => r.json()), 'пример из собственной валидации') } catch (e: any) { setError(e.message) }
  }
  const upload = async (file?: File) => {
    if (!file) return
    try { start(await readDataset(file), file.name) } catch (e: any) { setError(`Не удалось прочитать файл: ${e.message}`) }
  }
  const r = run.data as any

  return (
    <div className="min-h-screen bg-white">
      <PublicHeader />
      <section className="bg-hero noise relative overflow-hidden pb-16 pt-32">
        <Blobs className="opacity-50" />
        <div className="relative mx-auto max-w-6xl px-4 text-white sm:px-6">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-fsp-blush">Стенд оценки подбора</p>
          <motion.h1 initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, ease: EASE }}
            className="mt-3 max-w-3xl text-4xl font-extrabold leading-tight tracking-tightest text-white sm:text-[52px]">Проверьте подбор <span className="text-gradient">на своих данных</span></motion.h1>
          <p className="mt-4 max-w-3xl text-white/75">Загрузите набор пар «вакансия — кандидат» с разметкой релевантности. Платформа построит выдачу по каждой
            вакансии тем же ранжированием, что и для работодателя, и посчитает долю релевантных кандидатов в топ-10, nDCG и MRR — рядом с поиском
            по ключевым словам на тех же данных. Данные не сохраняются.</p>
        </div>
      </section>

      <div className="mx-auto max-w-6xl space-y-6 px-4 py-10 sm:px-6">
        <Card title="Запуск" subtitle="Пример — синтетический набор из собственной валидации; свой набор — JSON или CSV">
          <div className="flex flex-wrap items-center gap-3">
            <Button icon={<Play className="h-4 w-4" />} loading={run.isPending && source?.startsWith('пример')} onClick={sample}>Запустить на примере</Button>
            <Button variant="secondary" icon={<FileUp className="h-4 w-4" />} loading={run.isPending && !source?.startsWith('пример')}
              onClick={() => fileRef.current?.click()}>Загрузить свой набор</Button>
            <input ref={fileRef} type="file" accept=".json,.csv,.tsv,.txt,application/json,text/csv" className="hidden"
              onChange={e => { void upload(e.target.files?.[0]); e.target.value = '' }} />
            <a href="/eval-sample.json" download className="inline-flex items-center gap-1.5 text-sm font-semibold text-fsp-lavender hover:text-fsp-deep">
              <Download className="h-4 w-4" />Пример (JSON)</a>
            <button type="button" onClick={() => saveText('eval-template.csv', '﻿' + CSV_TEMPLATE, 'text/csv;charset=utf-8')}
              className="inline-flex items-center gap-1.5 text-sm font-semibold text-fsp-lavender hover:text-fsp-deep"><Download className="h-4 w-4" />Шаблон CSV</button>
          </div>
          <div className="mt-4">
            <Checkbox checked={textOnly} onChange={v => { setTextOnly(v); run.reset() }}
              label="Только текст резюме — без категорий по тесту (NLP определит специализацию и заявленный грейд)" />
          </div>
          {dataset && <p className="mt-3 text-xs text-slate-500">Набор: {source} · вакансий {dataset.vacancies.length}, кандидатов {dataset.candidates.length}, меток {dataset.labels.length}
            {!run.isPending && r && <button type="button" className="ml-2 font-semibold text-fsp-lavender hover:text-fsp-deep" onClick={() => run.mutate(dataset)}>пересчитать</button>}</p>}
          {error && <div className="mt-4"><Alert tone="error">{error}</Alert></div>}
        </Card>

        {r && (<>
          <div className="grid gap-4 sm:grid-cols-3">
            <Kpi label={`Доля релевантных в топ-${r.k}`} ours={r.summary.ours.p_at_k} keyword={r.summary.keyword.p_at_k} />
            <Kpi label={`nDCG@${r.k}`} ours={r.summary.ours.ndcg} keyword={r.summary.keyword.ndcg} />
            <Kpi label="MRR" ours={r.summary.ours.mrr} keyword={r.summary.keyword.mrr} />
          </div>
          <Alert tone="info" icon={<Info className="h-4 w-4" />}>
            Вакансий с разметкой: {r.vacancies_scored} из {r.vacancies.length}. Кандидатов {r.candidates.total}: с категорией по тесту — {r.candidates.with_category},
            только по резюме — {r.candidates.text_only} (статус «не подтверждён»). Релевантным считается метка ≥ {r.threshold}. Платформа показывает только
            кандидатов рекомендованных категорий, поэтому выдача может быть короче топа — недостающие места считаются нерелевантными.
          </Alert>
          <Card title="По вакансиям" subtitle="Нажмите на вакансию, чтобы сравнить топ платформы и поиска по ключевым словам с метками релевантности" pad={false}>
            <div className="mt-2">{r.vacancies.map((v: any) => <VacancyRow key={v.id} v={v} k={r.k} />)}</div>
          </Card>
        </>)}

        <Card title="Формат набора" subtitle="Кандидат задаётся категорией по тесту или только текстом резюме">
          <div className="grid gap-4 lg:grid-cols-2">
            <Format title="JSON">
              <code className="text-xs">{'{ "vacancies": [{ "id", "title", "text" }], "candidates": [{ "id", "text", "specialization"?, "grade"?, "theta"?, "skills"? }], "labels": [{ "vacancy", "candidate", "relevance" }] }'}</code>
              <p className="mt-2">specialization — код справочника (backend, frontend, fullstack, ml, data_analyst, devops, qa), grade — intern, junior, middle, senior.
                Без них категорию из текста резюме определит NLP.</p>
            </Format>
            <Format title="CSV — строка на пару">
              <code className="text-xs">{CSV_COLUMNS.join('; ')}</code>
              <p className="mt-2">Последние два столбца необязательны. Разделитель — «;», «,» или табуляция, кодировка UTF-8. Тексты вакансии и кандидата
                повторяются в каждой строке пары.</p>
            </Format>
            <Format title="Разметка">Метки 0–3 (релевантен при ≥ 2) или бинарные 0/1. Не размеченные пары считаются нерелевантными.</Format>
            <Format title="Ограничения">До 50 вакансий и 2000 кандидатов; набор 8 × 240 считается около 5 секунд. API: <code className="text-xs">POST /api/v1/eval/dataset</code>,
              описание — в Swagger (/docs).</Format>
          </div>
        </Card>
        <p className="flex items-center gap-2 text-xs text-slate-400"><FlaskConical className="h-3.5 w-3.5" />Наша собственная проверка подбора на 900 кандидатах
          и 60 потребностях с базовыми линиями и абляциями — на странице <a href="/methodology#matching" className="link">«Методика»</a>.</p>
      </div>
    </div>
  )
}
