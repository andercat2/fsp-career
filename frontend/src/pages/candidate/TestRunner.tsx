import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { ArrowRight, Award, Check, CircleAlert, CircleCheck, CircleX, Flag, Info, Sparkles, Timer, TrendingUp } from 'lucide-react'
import { api } from '@/lib/api'
import { useToast } from '@/lib/toast'
import { Alert, Badge, Button, ButtonLink, Card, Input, PageLoader, Progress } from '@/components/ui'
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
  const danger = left <= 15
  const mm = String(Math.floor(left / 60)).padStart(1, '0')
  const ss = String(left % 60).padStart(2, '0')

  return (
    <Card>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="purple">Задание {q.seq}</Badge>
          <Badge tone="lavender">{q.domain_name}</Badge>
        </div>
        <div className={clsx('flex items-center gap-2 rounded-xl px-3 py-1.5 text-sm font-bold tabular-nums', danger ? 'bg-red-50 text-red-600' : 'bg-surface text-fsp-deep')}>
          <Timer className="h-4 w-4" /> {mm}:{ss}
        </div>
      </div>
      <Progress value={left / q.time_limit} tone={danger ? 'pink' : 'lavender'} className="mb-6 h-1" />
      <Markdown>{q.prompt}</Markdown>
      {q.code && <div className="mt-4"><CodeBlock code={q.code} lang={q.code_lang} /></div>}

      <div className="mt-6">
        {q.kind === 'single' && (
          <div className="grid gap-2.5">
            {q.options!.map(o => (
              <button key={o.id} type="button" onClick={() => setSingle(o.id)}
                className={clsx('flex items-start gap-3 rounded-2xl px-4 py-3 text-left ring-1 transition',
                  single === o.id ? 'bg-fsp-blush/40 ring-2 ring-fsp-pink' : 'bg-white ring-[#E4E1EE] hover:ring-fsp-lavender')}>
                <span className={clsx('mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full ring-1', single === o.id ? 'bg-fsp-pink ring-fsp-pink' : 'ring-slate-300')}>
                  {single === o.id && <span className="h-2 w-2 rounded-full bg-white" />}
                </span>
                <Markdown className="!text-sm [&_p]:!my-0">{o.text}</Markdown>
              </button>
            ))}
          </div>
        )}
        {q.kind === 'multi' && (
          <div className="grid gap-2.5">
            {q.options!.map(o => {
              const on = multi.includes(o.id)
              return (
                <button key={o.id} type="button" onClick={() => setMulti(m => on ? m.filter(x => x !== o.id) : [...m, o.id])}
                  className={clsx('flex items-start gap-3 rounded-2xl px-4 py-3 text-left ring-1 transition',
                    on ? 'bg-fsp-blush/40 ring-2 ring-fsp-pink' : 'bg-white ring-[#E4E1EE] hover:ring-fsp-lavender')}>
                  <span className={clsx('mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-md ring-1', on ? 'bg-fsp-pink text-white ring-fsp-pink' : 'ring-slate-300')}>
                    {on && <Check className="h-3.5 w-3.5" />}
                  </span>
                  <Markdown className="!text-sm [&_p]:!my-0">{o.text}</Markdown>
                </button>
              )
            })}
          </div>
        )}
        {(q.kind === 'input' || q.kind === 'numeric') && (
          <div className="max-w-md">
            <Input autoFocus value={text} onChange={e => setText(e.target.value)} inputMode={q.kind === 'numeric' ? 'decimal' : 'text'}
              placeholder={q.placeholder ?? (q.kind === 'numeric' ? 'Введите число' : 'Введите ответ')}
              onKeyDown={e => { if (e.key === 'Enter' && ready && !busy) send(value) }}
              className="h-12 font-mono text-base" />
            <p className="mt-1.5 text-xs text-slate-400">{q.kind === 'numeric' ? 'Дробную часть можно отделять точкой или запятой' : 'Регистр и лишние пробелы не важны'}</p>
          </div>
        )}
      </div>

      <div className="mt-8 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-5">
        <p className="text-xs text-slate-400">Вернуться к заданию после ответа нельзя. При истечении времени ответ отправится автоматически.</p>
        <div className="flex gap-2">
          <Button variant="ghost" disabled={busy} onClick={() => send(null)}>Не знаю</Button>
          <Button disabled={!ready} loading={busy} onClick={() => send(value)} icon={<ArrowRight className="h-4 w-4" />}>Ответить</Button>
        </div>
      </div>
    </Card>
  )
}

const DECISION = {
  confirmed: { tone: 'success' as const, icon: <CircleCheck className="h-6 w-6" />, title: (g: string) => `Грейд ${g} подтверждён` },
  confirmed_strong: { tone: 'success' as const, icon: <Sparkles className="h-6 w-6" />, title: (g: string) => `Грейд ${g} подтверждён уверенно` },
  not_confirmed: { tone: 'warn' as const, icon: <CircleAlert className="h-6 w-6" />, title: (g: string) => `Грейд ${g} пока не подтверждён` },
}

function Result({ view }: { view: any }) {
  const r = view.result
  const nav = useNavigate()
  const { push } = useToast()
  const qc = useQueryClient()
  const d = DECISION[r.decision as keyof typeof DECISION]
  const start = useMutation({
    mutationFn: (g: string) => api('/testing/sessions', { body: { grade: g } }),
    onSuccess: (s: any) => { qc.invalidateQueries(); nav(`/candidate/testing/${s.token}`) },
    onError: (e: any) => push(e.message, 'error'),
  })
  return (
    <div className="space-y-6">
      <div className={clsx('rounded-3xl p-6 sm:p-8', r.decision === 'not_confirmed' ? 'bg-amber-50' : 'bg-brand-gradient text-white')}>
        <div className="flex flex-wrap items-start gap-4">
          <div className={clsx('grid h-12 w-12 place-items-center rounded-2xl', r.decision === 'not_confirmed' ? 'bg-amber-100 text-amber-700' : 'bg-white/15 text-white')}>{d.icon}</div>
          <div className="min-w-0 flex-1">
            <h2 className={clsx('text-2xl font-extrabold', r.decision !== 'not_confirmed' && 'text-white')}>{d.title(r.target_grade_name)}</h2>
            <p className={clsx('mt-1 text-sm', r.decision === 'not_confirmed' ? 'text-amber-900' : 'text-white/75')}>
              {r.review_required ? 'Результат отправлен на перепроверку: часть ответов совпала с ответами других вариантов заданий. Категория не изменена — пройдите тест повторно под наблюдением.' :
                r.assigned_grade ? `Категория «${view.specialization_name} · ${r.target_grade_name}» присвоена и видна работодателям.` :
                r.kept_grade ? 'Ваш текущий грейд сохранён — грейд не понижается по результатам теста.' :
                  r.decision === 'not_confirmed' ? 'Категория пока не присвоена. Это не приговор: пройдите тест уровнем ниже — сразу, без ожидания.' : 'Результат учтён в профиле.'}
            </p>
          </div>
          <div className="flex gap-6 text-center">
            <div><p className="text-3xl font-extrabold">{Math.round(r.percentile)}%</p><p className="text-xs opacity-70">выше кандидатов</p></div>
            <div><p className="text-3xl font-extrabold">{r.n_correct}/{r.n_items}</p><p className="text-xs opacity-70">верных ответов</p></div>
          </div>
        </div>
        <div className="mt-6 flex flex-wrap gap-2">
          {r.next_grade && <Button onClick={() => start.mutate(r.next_grade)} loading={start.isPending} icon={<TrendingUp className="h-4 w-4" />}>Пройти тест на {r.next_grade_name} сейчас</Button>}
          {r.decision === 'not_confirmed' && r.suggested_grade && <Button onClick={() => start.mutate(r.suggested_grade)} loading={start.isPending} icon={<ArrowRight className="h-4 w-4" />}>Пройти тест на {r.suggested_grade_name}</Button>}
          <ButtonLink to="/candidate/grade" variant={r.decision === 'not_confirmed' ? 'secondary' : 'soft'} icon={<Award className="h-4 w-4" />}>Категория и грейд</ButtonLink>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_1.1fr]">
        <Card title="Результаты по доменам" subtitle="Вероятность решить типичное задание уровня заявленного грейда">
          <DomainBars domains={r.domains} />
        </Card>
        <Card title="Разбор заданий" subtitle="Темы и объяснения. Сами варианты уникальны и не публикуются">
          <div className="divide-y divide-slate-100">
            {r.review.map((x: any) => (
              <div key={x.seq} className="flex gap-3 py-2.5">
                {x.correct ? <CircleCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" /> : <CircleX className="mt-0.5 h-4 w-4 shrink-0 text-red-400" />}
                <div className="min-w-0">
                  <p className="text-sm font-medium text-fsp-deep">{x.seq}. {x.topic}{!x.scored && <Badge className="ml-2" tone="gray">пилотное, не влияет на оценку</Badge>}</p>
                  <p className="text-xs text-slate-500">{x.domain}{x.explanation && <> · {x.explanation}</>}</p>
                </div>
              </div>
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
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Тест на грейд</p>
          <h1 className="text-2xl font-bold">{view.specialization_name} · {view.target_grade.charAt(0).toUpperCase() + view.target_grade.slice(1)}</h1>
        </div>
        {inProgress && (
          <div className="w-full max-w-xs">
            <div className="mb-1 flex justify-between text-xs text-slate-500"><span>Ответов: {view.answered}</span><span>обычно {view.min_items}–{view.max_items}</span></div>
            <Progress value={view.answered / view.max_items} tone="deep" />
          </div>
        )}
      </div>
      {inProgress && view.question ? <QuestionView q={view.question} onSubmit={onSubmit} busy={answer.isPending} /> : view.result ? <Result view={view} /> :
        <Alert tone="info" icon={<Flag className="h-4 w-4" />}>Тест завершён.</Alert>}
    </div>
  )
}
