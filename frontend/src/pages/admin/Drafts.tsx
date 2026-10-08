import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import clsx from 'clsx'
import { Bot, Check, CircleAlert, CircleCheck, CircleX, FlaskConical, Pencil, ShieldAlert, Sparkles, WandSparkles, X } from 'lucide-react'
import { api } from '@/lib/api'
import { useToast } from '@/lib/toast'
import { EASE } from '@/lib/motion'
import { Alert, Badge, Button, Card, Field, Input, PageHeader, PageLoader, Progress, Select, Tabs, Textarea } from '@/components/ui'
import { CodeBlock, Markdown } from '@/components/Content'

type Check = { level: 'error' | 'warn'; code: string; text: string }
type Review = { verdict: 'ok' | 'problem' | 'unknown'; also_correct: number[]; issues: string[] } | null
type Draft = {
  id: number; batch_id: number | null; source: 'llm' | 'demo'; model: string | null; specialization_name: string; domain: string
  domain_name: string; level: number; level_grade: string; topic: string; prompt: string; code: string | null; code_lang: string | null
  options: string[]; correct: number; explanation: string; checks: { auto: Check[]; review: Review }; status: 'pending' | 'accepted' | 'rejected'
  edited: boolean; original: any; reject_reason: string | null; family_id: string | null
  pilot: { answers: number; status: string | null; needed: number } | null
}
type Batch = { id: number; status: 'running' | 'done' | 'failed'; source: string; model: string | null; requested: number; done: number; failed: number; error: string | null }
type Options = {
  specializations: { code: string; name: string; direction: string; domains: { code: string; name: string; weight: number; families: number }[] }[]
  levels: { level: number; grade: string; description: string }[]; max_batch: number; reject_reasons: string[]; code_langs: string[]
  llm: { mode: 'llm' | 'demo'; model: string | null; reason: string | null; demo_items?: number }
}
type Status = 'pending' | 'accepted' | 'rejected'

const LETTERS = ['A', 'B', 'C', 'D']

function ModeBanner({ llm }: { llm: Options['llm'] }) {
  if (llm.mode === 'llm') return (
    <Alert tone="success" icon={<Bot className="h-4 w-4" />} title={`Модель ${llm.model} подключена`}>
      Черновик и самопроверка — около минуты на вопрос. Модель получает только раздел, уровень и тему, без персональных данных.
    </Alert>
  )
  return (
    <Alert tone="warn" icon={<Bot className="h-4 w-4" />} title="Демо-режим: LLM не подключена">
      Черновики берутся из набора, заранее сгенерированного моделью {llm.model ?? 'qwen3:14b'} этим же конвейером
      ({llm.demo_items ?? 0} шт.){llm.reason ? `; причина: ${llm.reason}` : ''}. Подключить модель — переменная LLM_BASE_URL (например, Ollama).
    </Alert>
  )
}

function GenerateForm({ opts, busy, onStart }: { opts: Options; busy: boolean; onStart: (b: any) => void }) {
  const [spec, setSpec] = useState(opts.specializations[0].code)
  const [domain, setDomain] = useState('')
  const [level, setLevel] = useState(3)
  const [count, setCount] = useState(3)
  const [topic, setTopic] = useState('')
  const sp = opts.specializations.find(s => s.code === spec)!
  const lv = opts.levels.find(l => l.level === level)!
  return (
    <Card title="Новый пакет черновиков" subtitle="Модель предлагает вопросы с выбором одного ответа — решение по каждому принимает эксперт">
      <div className="space-y-4">
        <Field label="Направление (специализация)">
          <Select value={spec} onChange={e => { setSpec(e.target.value); setDomain('') }}>
            {opts.specializations.map(s => <option key={s.code} value={s.code}>{s.name} · {s.direction}</option>)}
          </Select>
        </Field>
        <Field label="Раздел теста" hint="«Любой» — разделы по долям состава теста специализации">
          <Select value={domain} onChange={e => setDomain(e.target.value)}>
            <option value="">Любой — по долям теста</option>
            {sp.domains.map(d => <option key={d.code} value={d.code}>{d.name} · {Math.round(d.weight * 100)}% теста · в банке {d.families}</option>)}
          </Select>
        </Field>
        <div>
          <p className="label">Уровень сложности</p>
          <div className="grid grid-cols-5 gap-1.5">
            {opts.levels.map(l => (
              <button key={l.level} type="button" onClick={() => setLevel(l.level)}
                className={clsx('rounded-xl px-1.5 py-2 text-center text-[11px] font-semibold leading-tight ring-1 transition',
                  level === l.level ? 'bg-fsp-deep text-white ring-fsp-deep' : 'bg-white text-slate-600 ring-slate-200 hover:ring-fsp-lavender')}>
                <span className="block text-base">{l.level}</span>{l.grade.replace('/', '/\u200b')}
              </button>
            ))}
          </div>
          <p className="mt-1.5 text-xs text-slate-400">{lv.description}</p>
        </div>
        <div className="grid grid-cols-[110px_1fr] gap-3">
          <Field label="Вопросов"><Input type="number" min={1} max={opts.max_batch} value={count}
            onChange={e => setCount(Math.max(1, Math.min(opts.max_batch, Number(e.target.value) || 1)))} /></Field>
          <Field label="Тема (необязательно)"><Input value={topic} maxLength={200} onChange={e => setTopic(e.target.value)} placeholder="например, уровни изоляции транзакций" /></Field>
        </div>
        <Button className="w-full" loading={busy} icon={<WandSparkles className="h-4 w-4" />}
          onClick={() => onStart({ specialization: spec, domain: domain || null, level, count, topic: topic.trim() || null })}>
          Подготовить черновики
        </Button>
        <p className="text-xs leading-relaxed text-slate-400">Принятый вопрос попадает в банк пилотным: кандидаты его видят, но на оценку он не влияет,
          пока трудность не откалибрована по 40 ответам («Банк заданий» → «Откалибровать пилотные»).</p>
      </div>
    </Card>
  )
}

function BatchProgress({ batch }: { batch: Batch }) {
  const passed = batch.done + batch.failed
  if (batch.status === 'running') return (
    <div className="rounded-2xl border border-line bg-white p-4">
      <p className="flex items-center gap-2 text-sm font-semibold text-fsp-deep"><Sparkles className="h-4 w-4 animate-pulse text-fsp-pink" />
        {batch.source === 'llm' ? `Модель пишет вопрос ${Math.min(passed + 1, batch.requested)} из ${batch.requested}…` : 'Подбираем черновики из демо-набора…'}</p>
      <Progress className="mt-3" value={passed / batch.requested} />
      <p className="mt-2 text-xs text-slate-400">Готовые черновики сразу появляются в очереди — проверять можно, не дожидаясь конца пакета.</p>
    </div>
  )
  return (
    <div className={clsx('rounded-2xl border p-4 text-sm', batch.status === 'failed' ? 'border-red-100 bg-red-50 text-red-800' : 'border-emerald-100 bg-emerald-50 text-emerald-800')}>
      <p className="font-semibold">{batch.status === 'failed' ? 'Пакет не удался' : `Пакет готов: ${batch.done} черновиков${batch.failed ? `, не получилось ${batch.failed}` : ''}`}</p>
      {batch.error && <p className="mt-1 text-xs opacity-80">{batch.error}</p>}
    </div>
  )
}

function Checks({ d }: { d: Draft }) {
  const r = d.checks.review
  const items = d.checks.auto ?? []
  if (!items.length && (!r || r.verdict === 'ok')) return (
    <p className="flex items-center gap-1.5 text-xs font-medium text-emerald-700"><CircleCheck className="h-3.5 w-3.5" />Автопроверки пройдены{r ? ', самопроверка модели: замечаний нет' : ''}</p>
  )
  return (
    <div className="space-y-1.5">
      {items.map(c => (
        <p key={c.code} className={clsx('flex items-start gap-1.5 text-xs', c.level === 'error' ? 'text-red-700' : 'text-amber-800')}>
          <CircleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />{c.text}</p>
      ))}
      {r && r.verdict !== 'ok' && (
        <div className="rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-900">
          <p className="flex items-center gap-1.5 font-semibold"><ShieldAlert className="h-3.5 w-3.5" />
            {r.verdict === 'unknown' ? 'Самопроверка модели не выполнена' : 'Самопроверка модели сомневается'}
            {r.also_correct.length > 0 && ` — тоже может быть верным: ${r.also_correct.map(i => LETTERS[i]).join(', ')}`}</p>
          {r.issues.map((t, i) => <p key={i} className="mt-1">{t}</p>)}
        </div>
      )}
    </div>
  )
}

function Editor({ d, opts, onCancel, onSave, saving }: { d: Draft; opts: Options; onCancel: () => void; onSave: (v: any) => void; saving: boolean }) {
  const [v, setV] = useState({ topic: d.topic, level: d.level, prompt: d.prompt, code: d.code ?? '', code_lang: d.code_lang ?? '',
    options: [...d.options], correct: d.correct, explanation: d.explanation })
  const set = (k: string, val: any) => setV(s => ({ ...s, [k]: val }))
  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-[1fr_150px]">
        <Field label="Тема"><Input value={v.topic} onChange={e => set('topic', e.target.value)} /></Field>
        <Field label="Уровень"><Select value={v.level} onChange={e => set('level', Number(e.target.value))}>
          {opts.levels.map(l => <option key={l.level} value={l.level}>{l.level} · {l.grade}</option>)}</Select></Field>
      </div>
      <Field label="Вопрос (Markdown)"><Textarea value={v.prompt} onChange={e => set('prompt', e.target.value)} /></Field>
      <div className="grid gap-3 sm:grid-cols-[1fr_150px]">
        <Field label="Код (необязательно)"><Textarea className="font-mono text-xs" value={v.code} onChange={e => set('code', e.target.value)} /></Field>
        <Field label="Язык кода"><Select value={v.code_lang} onChange={e => set('code_lang', e.target.value)}>
          <option value="">—</option>{opts.code_langs.map(l => <option key={l} value={l}>{l}</option>)}</Select></Field>
      </div>
      <div>
        <p className="label">Варианты ответа — отметьте правильный</p>
        <div className="space-y-2">
          {v.options.map((o, i) => (
            <div key={i} className="flex items-center gap-2">
              <button type="button" onClick={() => set('correct', i)} aria-label={`Правильный — ${LETTERS[i]}`}
                className={clsx('grid h-8 w-8 shrink-0 place-items-center rounded-lg text-xs font-bold ring-1 transition',
                  v.correct === i ? 'bg-emerald-500 text-white ring-emerald-500' : 'bg-white text-slate-500 ring-slate-200 hover:ring-emerald-300')}>
                {v.correct === i ? <Check className="h-4 w-4" /> : LETTERS[i]}</button>
              <Input value={o} onChange={e => set('options', v.options.map((x, j) => (j === i ? e.target.value : x)))} />
            </div>
          ))}
        </div>
      </div>
      <Field label="Пояснение для разбора после теста"><Textarea value={v.explanation} onChange={e => set('explanation', e.target.value)} /></Field>
      <div className="flex flex-wrap justify-end gap-2">
        <Button variant="ghost" onClick={onCancel}>Отмена</Button>
        <Button loading={saving} icon={<Check className="h-4 w-4" />}
          onClick={() => onSave({ ...v, code: v.code.trim() || null, code_lang: v.code.trim() ? v.code_lang || null : null })}>Сохранить и принять</Button>
      </div>
    </div>
  )
}

function DraftCard({ d, opts, onDone }: { d: Draft; opts: Options; onDone: (msg: string) => void }) {
  const { push } = useToast()
  const [editing, setEditing] = useState(false)
  const [rejecting, setRejecting] = useState(false)
  const accept = useMutation({
    mutationFn: (body?: any) => api<Draft>(`/admin/item-drafts/${d.id}/accept`, { method: 'POST', body }),
    onSuccess: r => onDone(`Вопрос добавлен в банк пилотным: ${r.family_id}${r.edited ? ' (с правками)' : ''}`),
    onError: (e: any) => push(e.message, 'error'),
  })
  const reject = useMutation({
    mutationFn: (reason: string) => api(`/admin/item-drafts/${d.id}/reject`, { body: { reason } }),
    onSuccess: () => onDone('Черновик отклонён'), onError: (e: any) => push(e.message, 'error'),
  })
  const doubt = new Set(d.checks.review?.also_correct ?? [])
  const blocked = (d.checks.auto ?? []).some(c => c.level === 'error')
  return (
    <motion.div layout initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, x: -30 }} transition={{ duration: 0.3, ease: EASE }}
      className="card overflow-hidden">
      <div className="flex flex-wrap items-center gap-2 border-b border-line px-5 py-3">
        <Badge tone="lavender">{d.domain_name}</Badge>
        <Badge tone="gray">уровень {d.level} · {d.level_grade}</Badge>
        <Badge tone={d.source === 'llm' ? 'blue' : 'amber'} icon={<Bot className="h-3 w-3" />}>{d.source === 'llm' ? d.model : `демо · ${d.model ?? 'LLM'}`}</Badge>
        <span className="ml-auto text-xs text-slate-400">№{d.id} · {d.specialization_name}</span>
      </div>
      <div className="space-y-4 px-5 py-4">
        {editing ? <Editor d={d} opts={opts} saving={accept.isPending} onCancel={() => setEditing(false)} onSave={v => accept.mutate(v)} /> : (<>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">{d.topic}</p>
            <Markdown className="mt-1 !text-[15px]">{d.prompt}</Markdown>
            {d.code && <div className="mt-3"><CodeBlock code={d.code} lang={d.code_lang} /></div>}
          </div>
          <div className="grid gap-2">
            {d.options.map((o, i) => (
              <div key={i} className={clsx('flex items-start gap-3 rounded-xl border px-3 py-2.5 text-sm',
                i === d.correct ? 'border-emerald-300 bg-emerald-50/70' : doubt.has(i) ? 'border-amber-300 bg-amber-50/70' : 'border-line bg-white')}>
                <span className={clsx('grid h-6 w-6 shrink-0 place-items-center rounded-md text-[11px] font-bold',
                  i === d.correct ? 'bg-emerald-500 text-white' : doubt.has(i) ? 'bg-amber-400 text-white' : 'bg-slate-100 text-slate-500')}>{LETTERS[i]}</span>
                <span className="min-w-0 flex-1 text-fsp-ink">{o}</span>
                {i === d.correct && <span className="shrink-0 text-[11px] font-semibold text-emerald-700">правильный по версии модели</span>}
                {i !== d.correct && doubt.has(i) && <span className="shrink-0 text-[11px] font-semibold text-amber-700">возможно, тоже верный</span>}
              </div>
            ))}
          </div>
          {d.explanation && <p className="text-xs leading-relaxed text-slate-500"><b className="text-slate-600">Пояснение:</b> {d.explanation}</p>}
          <Checks d={d} />
        </>)}
      </div>
      {!editing && (
        <div className="border-t border-line bg-surface/50 px-5 py-3">
          <AnimatePresence mode="wait" initial={false}>
            {rejecting ? (
              <motion.div key="reject" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-semibold text-slate-500">Причина:</span>
                {opts.reject_reasons.map(r => (
                  <button key={r} type="button" disabled={reject.isPending} onClick={() => reject.mutate(r)}
                    className="rounded-lg bg-white px-2.5 py-1 text-xs font-medium text-red-700 ring-1 ring-red-100 transition hover:bg-red-50">{r}</button>
                ))}
                <button type="button" onClick={() => setRejecting(false)} className="ml-auto text-xs text-slate-400 hover:text-slate-600">отмена</button>
              </motion.div>
            ) : (
              <motion.div key="actions" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex flex-wrap items-center justify-end gap-2">
                <Button size="sm" variant="danger" icon={<X className="h-4 w-4" />} onClick={() => setRejecting(true)}>Отклонить</Button>
                <Button size="sm" variant="secondary" icon={<Pencil className="h-4 w-4" />} onClick={() => setEditing(true)}>Исправить</Button>
                <Button size="sm" disabled={blocked} loading={accept.isPending} icon={<Check className="h-4 w-4" />} onClick={() => accept.mutate(undefined)}>Принять как есть</Button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}
    </motion.div>
  )
}

function DoneCard({ d }: { d: Draft }) {
  const accepted = d.status === 'accepted'
  return (
    <div className="card flex flex-wrap items-start gap-3 px-5 py-4">
      {accepted ? <CircleCheck className="mt-0.5 h-5 w-5 shrink-0 text-emerald-500" /> : <CircleX className="mt-0.5 h-5 w-5 shrink-0 text-red-400" />}
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-fsp-deep">{d.topic}</p>
        <p className="mt-0.5 line-clamp-2 text-sm text-slate-600">{d.prompt}</p>
        <p className="mt-1.5 flex flex-wrap gap-1.5 text-xs">
          <Badge tone="lavender">{d.domain_name}</Badge><Badge tone="gray">уровень {d.level}</Badge>
          {d.edited && <Badge tone="blue" icon={<Pencil className="h-3 w-3" />}>с правками эксперта</Badge>}
          {!accepted && d.reject_reason && <Badge tone="red">{d.reject_reason}</Badge>}
        </p>
      </div>
      {accepted && d.pilot && (
        <div className="w-full shrink-0 sm:w-56">
          <p className="font-mono text-[11px] text-slate-400">{d.family_id}</p>
          <p className="mt-1 flex items-center gap-1.5 text-xs font-semibold text-fsp-deep"><FlaskConical className="h-3.5 w-3.5 text-amber-500" />
            {d.pilot.status === 'pretest' ? `Пилот: ${d.pilot.answers} из ${d.pilot.needed} ответов` : `В рабочем банке (${d.pilot.status})`}</p>
          {d.pilot.status === 'pretest' && <Progress className="mt-1.5" tone="lavender" value={d.pilot.answers / d.pilot.needed} />}
        </div>
      )}
    </div>
  )
}

export function AdminDrafts() {
  const qc = useQueryClient()
  const { push } = useToast()
  const [tab, setTab] = useState<Status>('pending')
  const { data: opts } = useQuery({ queryKey: ['draft-options'], queryFn: () => api<Options>('/admin/item-drafts/options') })
  const { data } = useQuery({
    queryKey: ['drafts', tab], queryFn: () => api<{ items: Draft[]; counts: Record<Status, number>; batch: Batch | null }>(`/admin/item-drafts?status=${tab}`),
    refetchInterval: q => (q.state.data?.batch?.status === 'running' ? 2500 : false),
  })
  const start = useMutation({
    mutationFn: (body: any) => api<Batch>('/admin/item-drafts/batches', { body }),
    onSuccess: () => { setTab('pending'); qc.invalidateQueries({ queryKey: ['drafts'] }) },
    onError: (e: any) => push(e.message, 'error'),
  })
  const running = data?.batch?.status === 'running'
  useEffect(() => { if (!running) qc.invalidateQueries({ queryKey: ['drafts'] }) }, [running, qc])
  const done = (msg: string) => { push(msg); qc.invalidateQueries({ queryKey: ['drafts'] }); qc.invalidateQueries({ queryKey: ['admin-items'] }) }
  const counts = data?.counts ?? { pending: 0, accepted: 0, rejected: 0 }
  const stats = useMemo(() => {
    const total = counts.accepted + counts.rejected
    return total ? `решено ${total}: принято ${Math.round(counts.accepted / total * 100)}%` : null
  }, [counts])
  if (!opts) return <PageLoader />
  return (
    <div className="space-y-6">
      <PageHeader title="Черновики заданий от LLM"
        subtitle="Пополнение банка: модель предлагает вопросы, эксперт принимает их как есть, правит вопрос и ответы или отклоняет. Принятые вопросы проходят пилот — показываются без влияния на оценку, пока трудность не откалибрована по ответам кандидатов." />
      <ModeBanner llm={opts.llm} />
      <div className="grid items-start gap-6 xl:grid-cols-[380px_1fr]">
        <div className="space-y-4 xl:sticky xl:top-24">
          <GenerateForm opts={opts} busy={start.isPending || running} onStart={b => start.mutate(b)} />
          {data?.batch && <BatchProgress batch={data.batch} />}
        </div>
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Tabs value={tab} onChange={setTab} items={[{ value: 'pending', label: 'На проверке', count: counts.pending },
              { value: 'accepted', label: 'Приняты', count: counts.accepted }, { value: 'rejected', label: 'Отклонены', count: counts.rejected }]} />
            {stats && <span className="text-xs text-slate-400">{stats}</span>}
          </div>
          {!data ? <PageLoader /> : !data.items.length ? (
            <div className="rounded-[20px] border border-dashed border-[#E2DEEE] bg-white/60 px-6 py-12 text-center text-sm text-slate-500">
              {tab === 'pending' ? 'Очередь пуста — подготовьте пакет черновиков слева.' : tab === 'accepted' ? 'Принятых вопросов пока нет.' : 'Отклонённых нет.'}
            </div>
          ) : (
            <AnimatePresence initial={false}>
              {data.items.map(d => tab === 'pending' ? <DraftCard key={d.id} d={d} opts={opts} onDone={done} /> : <DoneCard key={d.id} d={d} />)}
            </AnimatePresence>
          )}
        </div>
      </div>
    </div>
  )
}
