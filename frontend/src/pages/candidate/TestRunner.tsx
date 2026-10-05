import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import clsx from 'clsx'
import { ArrowRight, Award, Check, CircleAlert, CircleCheck, CircleX, Flag, Info, Sparkles, TrendingUp } from 'lucide-react'
import { api } from '@/lib/api'
import { useToast } from '@/lib/toast'
import { CountUp, EASE, SPRING } from '@/lib/motion'
import { Alert, Badge, Button, ButtonLink, Card, Input, PageLoader } from '@/components/ui'
import { CodeBlock, Markdown } from '@/components/Content'
import { DomainBars } from '@/components/Domain'

type Question = {
  id: number; seq: number; prompt: string; kind: 'single' | 'multi' | 'input' | 'numeric'
  options: { id: string; text: string }[] | null; code: string | null; code_lang: string | null
  placeholder: string | null; time_limit: number; time_left: number; domain_name: string
}

function useCountdown(seconds: number, key: number) {
  const [left, setLeft] = useState(seconds)
  useEffect(() => {
    setLeft(seconds)
    const started = Date.now()
    const t = setInterval(() => setLeft(Math.max(0, seconds - Math.floor((Date.now() - started) / 1000))), 250)
    return () => clearInterval(t)
  }, [seconds, key])
  return left
}

function TimerRing({ left, total }: { left: number; total: number }) {
  const r = 18
  const c = 2 * Math.PI * r
  const danger = left <= 15
  return (
    <div className={clsx('flex items-center gap-2.5 rounded-2xl border px-3 py-1.5 transition-colors', danger ? 'border-red-100 bg-red-50' : 'border-line bg-white')}>
      <svg width="44" height="44" className="-rotate-90">
        <circle cx="22" cy="22" r={r} stroke={danger ? '#FECACA' : '#F1EFF6'} strokeWidth="4" fill="none" />
        <motion.circle cx="22" cy="22" r={r} stroke={danger ? '#ef4444' : '#8A83D1'} strokeWidth="4" fill="none" strokeLinecap="round"
          strokeDasharray={c} animate={{ strokeDashoffset: c * (1 - left / total) }} transition={{ duration: 0.3, ease: 'linear' }} />
      </svg>
      <div className="leading-tight">
        <p className="text-[11px] text-slate-400">осталось</p>
        <p className={clsx('text-base font-bold tabular-nums', danger ? 'text-red-600' : 'text-fsp-deep')}>{Math.floor(left / 60)}:{String(left % 60).padStart(2, '0')}</p>
      </div>
    </div>
  )
}

function QuestionView({ q, onSubmit, busy }: { q: Question; onSubmit: (answer: unknown) => void; busy: boolean }) {
  const [single, setSingle] = useState<string | null>(null)
  const [multi, setMulti] = useState<string[]>([])
  const [text, setText] = useState('')
  const left = useCountdown(q.time_left, q.id)
  const submitted = useRef(false)
  useEffect(() => { setSingle(null); setMulti([]); setText(''); submitted.current = false }, [q.id])
  const value = q.kind === 'single' ? single : q.kind === 'multi' ? multi : text.trim() || null
  const ready = q.kind === 'multi' ? multi.length > 0 : value !== null
  const send = useCallback((v: unknown) => {
    if (submitted.current) return
    submitted.current = true
    onSubmit(v)
  }, [onSubmit])
  useEffect(() => { if (left === 0) send(value) }, [left]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <motion.div key={q.id} initial={{ opacity: 0, x: 48 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -48 }} transition={{ duration: 0.38, ease: EASE }}
      className="card overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-4 sm:px-7">
        <div className="flex flex-wrap items-center gap-2">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-fsp-deep text-sm font-bold text-white">{q.seq}</span>
          <Badge tone="lavender">{q.domain_name}</Badge>
        </div>
        <TimerRing left={left} total={q.time_limit} />
      </div>
      <div className="px-5 py-6 sm:px-7">
        <Markdown className="!text-[15.5px]">{q.prompt}</Markdown>
        {q.code && <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.12 }} className="mt-4"><CodeBlock code={q.code} lang={q.code_lang} /></motion.div>}

        <div className="mt-6">
          {(q.kind === 'single' || q.kind === 'multi') && (
            <div className="grid gap-2.5">
              {q.options!.map((o, i) => {
                const on = q.kind === 'single' ? single === o.id : multi.includes(o.id)
                const toggle = () => q.kind === 'single' ? setSingle(o.id) : setMulti(m => on ? m.filter(x => x !== o.id) : [...m, o.id])
                return (
                  <motion.button key={o.id} type="button" onClick={toggle} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3, delay: 0.08 + i * 0.05, ease: EASE }} whileTap={{ scale: 0.99 }}
                    className={clsx('flex items-start gap-3 rounded-2xl border px-4 py-3.5 text-left transition-colors duration-200',
                      on ? 'border-fsp-pink bg-[#FFF5F8] shadow-[0_0_0_3px_rgba(255,0,83,.08)]' : 'border-line bg-white hover:border-[#D9D4E7] hover:bg-[#FCFBFE]')}>
                    <span className={clsx('mt-0.5 grid h-5 w-5 shrink-0 place-items-center border transition-colors',
                      q.kind === 'single' ? 'rounded-full' : 'rounded-md', on ? 'border-fsp-pink bg-fsp-pink text-white' : 'border-[#D6D1E4]')}>
                      <AnimatePresence>{on && (
                        <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }} transition={SPRING}>
                          {q.kind === 'single' ? <span className="block h-2 w-2 rounded-full bg-white" /> : <Check className="h-3.5 w-3.5" strokeWidth={3} />}
                        </motion.span>
                      )}</AnimatePresence>
                    </span>
                    <Markdown className="!text-sm [&_p]:!my-0">{o.text}</Markdown>
                  </motion.button>
                )
              })}
            </div>
          )}
          {(q.kind === 'input' || q.kind === 'numeric') && (
            <div className="max-w-md">
              <Input autoFocus value={text} onChange={e => setText(e.target.value)} inputMode={q.kind === 'numeric' ? 'decimal' : 'text'}
                placeholder={q.placeholder ?? (q.kind === 'numeric' ? 'Введите число' : 'Введите ответ')}
                onKeyDown={e => { if (e.key === 'Enter' && ready && !busy) send(value) }} className="h-12 font-mono text-base" />
              <p className="mt-2 text-xs text-slate-400">{q.kind === 'numeric' ? 'Дробную часть можно отделять точкой или запятой. Enter — ответить' : 'Регистр и лишние пробелы не важны. Enter — ответить'}</p>
            </div>
          )}
        </div>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line bg-surface/50 px-5 py-4 sm:px-7">
        <p className="text-xs text-slate-400">Вернуться к заданию нельзя. По истечении времени ответ отправится автоматически.</p>
        <div className="flex gap-2">
          <Button variant="ghost" disabled={busy} onClick={() => send(null)}>Не знаю</Button>
          <Button disabled={!ready} loading={busy} onClick={() => send(value)} icon={<ArrowRight className="h-4 w-4" />}>Ответить</Button>
        </div>
      </div>
    </motion.div>
  )
}

/** Конфетти без зависимостей: частицы разлетаются из центра. */
function Confetti() {
  const parts = useMemo(() => Array.from({ length: 36 }, (_, i) => ({
    id: i, x: (Math.random() - 0.5) * 520, y: -120 - Math.random() * 260, r: Math.random() * 360,
    c: ['#FF0053', '#8A83D1', '#FFD6E4', '#ffc56b', '#ffffff'][i % 5], d: Math.random() * 0.25,
  })), [])
  return (
    <div className="pointer-events-none absolute left-1/2 top-1/2" aria-hidden>
      {parts.map(p => (
        <motion.span key={p.id} className="absolute h-2.5 w-1.5 rounded-sm" style={{ background: p.c }}
          initial={{ x: 0, y: 0, opacity: 1, rotate: 0 }} animate={{ x: p.x, y: [0, p.y, p.y + 420], opacity: [1, 1, 0], rotate: p.r * 3 }}
          transition={{ duration: 2.2, ease: 'easeOut', delay: p.d }} />
      ))}
    </div>
  )
}

const DECISION = {
  confirmed: { icon: <CircleCheck className="h-6 w-6" />, title: (g: string) => `Грейд ${g} подтверждён` },
  confirmed_strong: { icon: <Sparkles className="h-6 w-6" />, title: (g: string) => `Грейд ${g} подтверждён уверенно` },
  not_confirmed: { icon: <CircleAlert className="h-6 w-6" />, title: (g: string) => `Грейд ${g} пока не подтверждён` },
}

function PercentileRing({ value }: { value: number }) {
  const r = 52
  const c = 2 * Math.PI * r
  return (
    <div className="relative h-32 w-32 shrink-0">
      <svg width="128" height="128" className="-rotate-90">
        <circle cx="64" cy="64" r={r} stroke="rgba(255,255,255,.15)" strokeWidth="10" fill="none" />
        <motion.circle cx="64" cy="64" r={r} stroke="url(#pct)" strokeWidth="10" fill="none" strokeLinecap="round" strokeDasharray={c}
          initial={{ strokeDashoffset: c }} animate={{ strokeDashoffset: c * (1 - value / 100) }} transition={{ duration: 1.6, ease: EASE, delay: 0.2 }} />
        <defs><linearGradient id="pct" x1="0" x2="1"><stop offset="0%" stopColor="#FF0053" /><stop offset="100%" stopColor="#ffb3cd" /></linearGradient></defs>
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">
        <div><p className="text-3xl font-extrabold leading-none"><CountUp value={value} duration={1.6} />%</p><p className="mt-1 text-[11px] opacity-70">выше рынка</p></div>
      </div>
    </div>
  )
}

function Result({ view }: { view: any }) {
  const r = view.result
  const nav = useNavigate()
  const { push } = useToast()
  const qc = useQueryClient()
  const d = DECISION[r.decision as keyof typeof DECISION]
  const ok = r.decision !== 'not_confirmed' && !r.review_required
  const start = useMutation({
    mutationFn: (g: string) => api('/testing/sessions', { body: { grade: g } }),
    onSuccess: (s: any) => { qc.invalidateQueries(); nav(`/candidate/testing/${s.token}`) },
    onError: (e: any) => push(e.message, 'error'),
  })
  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: 16, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ duration: 0.6, ease: EASE }}
        className={clsx('relative overflow-hidden rounded-[28px] p-6 sm:p-8', ok ? 'bg-brand-gradient text-white shadow-lift' : 'border border-amber-100 bg-amber-50/70')}>
        {ok && <Confetti />}
        {ok && <div className="pointer-events-none absolute -right-20 -top-24 h-72 w-72 rounded-full bg-fsp-pink/30 blur-3xl" />}
        <div className="relative flex flex-col gap-6 sm:flex-row sm:items-center">
          {ok ? <PercentileRing value={Math.round(r.percentile)} /> : (
            <div className="grid h-14 w-14 place-items-center rounded-2xl bg-amber-100 text-amber-700">{d.icon}</div>
          )}
          <div className="min-w-0 flex-1">
            <motion.h2 initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25, duration: 0.5, ease: EASE }}
              className={clsx('text-[26px] font-extrabold tracking-tight', ok && 'text-white')}>{d.title(r.target_grade_name)}</motion.h2>
            <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.4 }}
              className={clsx('mt-2 max-w-2xl text-sm leading-relaxed', ok ? 'text-white/75' : 'text-amber-900')}>
              {r.review_required ? 'Результат отправлен на перепроверку: часть ответов совпала с ответами других вариантов заданий. Категория не изменена — пройдите тест повторно под наблюдением.' :
                r.assigned_grade ? `Категория «${view.specialization_name} · ${r.target_grade_name}» присвоена и видна работодателям.` :
                  r.kept_grade ? 'Ваш текущий грейд сохранён — грейд не понижается по результатам теста.' :
                    r.decision === 'not_confirmed' ? 'Категория пока не присвоена. Это не приговор: пройдите тест уровнем ниже — сразу, без ожидания.' : 'Результат учтён в профиле.'}
            </motion.p>
            <div className="mt-5 flex flex-wrap items-center gap-2">
              {r.next_grade && <Button onClick={() => start.mutate(r.next_grade)} loading={start.isPending} icon={<TrendingUp className="h-4 w-4" />}>Пройти тест на {r.next_grade_name} сейчас</Button>}
              {r.decision === 'not_confirmed' && r.suggested_grade && <Button onClick={() => start.mutate(r.suggested_grade)} loading={start.isPending} icon={<ArrowRight className="h-4 w-4" />}>Пройти тест на {r.suggested_grade_name}</Button>}
              <ButtonLink to="/candidate/grade" variant="secondary" icon={<Award className="h-4 w-4" />}>Категория и грейд</ButtonLink>
              <span className={clsx('ml-1 text-sm', ok ? 'text-white/70' : 'text-amber-800')}>{r.n_correct} из {r.n_items} верно</span>
            </div>
          </div>
        </div>
      </motion.div>

      <div className="grid gap-6 lg:grid-cols-[1fr_1.1fr]">
        <Card title="Результаты по доменам" subtitle="Вероятность решить типичное задание уровня заявленного грейда">
          <DomainBars domains={r.domains} />
        </Card>
        <Card title="Разбор заданий" subtitle="Темы и объяснения. Сами варианты уникальны и не публикуются">
          <div className="divide-y divide-line">
            {r.review.map((x: any, i: number) => (
              <motion.div key={x.seq} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.03 * i }} className="flex gap-3 py-2.5">
                {x.correct ? <CircleCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" /> : <CircleX className="mt-0.5 h-4 w-4 shrink-0 text-red-400" />}
                <div className="min-w-0">
                  <p className="text-sm font-medium text-fsp-deep">{x.seq}. {x.topic}{!x.scored && <Badge className="ml-2" tone="gray">пилотное</Badge>}</p>
                  <p className="text-xs text-slate-500">{x.domain}{x.explanation && <> · {x.explanation}</>}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </Card>
      </div>
      <Alert tone="info" icon={<Info className="h-4 w-4" />} title="Как считается результат">
        Оценка уровня θ = {r.theta} (± {r.se}) на общей шкале модели IRT: задания разной трудности дают сопоставимый результат.
        Грейд подтверждается, если с вероятностью ≥ 60% ваш уровень не ниже порога грейда; уверенный результат — если с вероятностью ≥ 80% вы выше верхней границы уровня.
      </Alert>
    </div>
  )
}

export function TestRunner() {
  const { token } = useParams()
  const qc = useQueryClient()
  const { push } = useToast()
  const { data: view, isLoading } = useQuery({ queryKey: ['session', token], queryFn: () => api(`/testing/sessions/${token}`) })
  const answer = useMutation({
    mutationFn: (p: { response_id: number; answer: unknown }) => api(`/testing/sessions/${token}/answer`, { body: p }),
    onSuccess: (v: any) => {
      qc.setQueryData(['session', token], v)
      if (v.status === 'completed') { qc.invalidateQueries({ queryKey: ['eligibility'] }); qc.invalidateQueries({ queryKey: ['cand-dashboard'] }); qc.invalidateQueries({ queryKey: ['cand-profile'] }) }
    },
    onError: (e: any) => { push(e.message, 'error'); qc.invalidateQueries({ queryKey: ['session', token] }) },
  })
  const inProgress = view?.status === 'in_progress'
  useEffect(() => {
    if (!inProgress) return
    const h = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = '' }
    window.addEventListener('beforeunload', h)
    return () => window.removeEventListener('beforeunload', h)
  }, [inProgress])
  const onSubmit = useCallback((a: unknown) => {
    const q = (qc.getQueryData(['session', token]) as any)?.question
    if (q) answer.mutate({ response_id: q.id, answer: a })
  }, [answer, qc, token])

  if (isLoading || !view) return <PageLoader />
  if (view.status === 'abandoned') return <Alert tone="warn" title="Сессия прервана">Тест был прерван. <Link to="/candidate/testing" className="link">Вернуться к выбору уровня</Link></Alert>
  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">Тест на грейд</p>
          <h1 className="mt-1.5 text-[26px] font-bold tracking-tight">{view.specialization_name} · {view.target_grade.charAt(0).toUpperCase() + view.target_grade.slice(1)}</h1>
        </div>
        {inProgress && (
          <div className="w-full max-w-sm">
            <div className="mb-2 flex justify-between text-xs text-slate-500"><span>Отвечено: <b className="text-fsp-deep">{view.answered}</b></span><span>обычно {view.min_items}–{view.max_items}</span></div>
            <div className="flex gap-1">
              {Array.from({ length: view.max_items }).map((_, i) => (
                <motion.span key={i} className="h-1.5 flex-1 rounded-full" initial={false}
                  animate={{ backgroundColor: i < view.answered ? '#FF0053' : i === view.answered ? '#8A83D1' : '#ECEAF2' }} transition={{ duration: 0.4 }} />
              ))}
            </div>
          </div>
        )}
      </div>
      <AnimatePresence mode="wait">
        {inProgress && view.question ? <QuestionView key={view.question.id} q={view.question} onSubmit={onSubmit} busy={answer.isPending} /> : view.result ? (
          <motion.div key="result" initial={{ opacity: 0 }} animate={{ opacity: 1 }}><Result view={view} /></motion.div>
        ) : <Alert tone="info" icon={<Flag className="h-4 w-4" />}>Тест завершён.</Alert>}
      </AnimatePresence>
    </div>
  )
}
