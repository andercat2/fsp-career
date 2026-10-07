import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Clock, Code2, ListChecks, Play, RotateCcw, Send, ShieldCheck, SkipForward, Star } from 'lucide-react'
import { api } from '@/lib/api'
import { useToast } from '@/lib/toast'
import { ago, date } from '@/lib/format'
import { Alert, Badge, Button, Card, EmptyState, PageHeader, PageLoader, Textarea } from '@/components/ui'
import { StatusBadge } from '@/components/Domain'
import { CodeEditor, TestResults } from '@/components/CodeEditor'
import { Markdown } from '@/components/Content'

const fmt = (v: unknown) => JSON.stringify(v)

/** Задача с кодом: редактор, запуск на открытых примерах в песочнице, отправка — на всех тестах. */
function CodeTask({ t, onSkip }: { t: any; onSkip: () => void }) {
  const qc = useQueryClient()
  const { push } = useToast()
  const task = t.task
  const [code, setCode] = useState<string>(t.code ?? task.starter_code ?? '')
  const [results, setResults] = useState<any>(t.results)
  const [confirm, setConfirm] = useState(false)
  const pastes = useRef<{ chars: number }[]>([])
  const away = useRef(0)
  const started = useRef(Date.now())
  const editable = t.status === 'offered'
  useEffect(() => {
    const h = () => { if (document.hidden) away.current += 1 }
    document.addEventListener('visibilitychange', h)
    return () => document.removeEventListener('visibilitychange', h)
  }, [])
  const run = useMutation({ mutationFn: () => api(`/candidate/tasks/${t.id}/run`, { body: { code } }),
    onSuccess: (r: any) => setResults(r), onError: (e: any) => push(e.message, 'error') })
  const submit = useMutation({
    mutationFn: () => api(`/candidate/tasks/${t.id}/submit-code`, { body: { code, signals: { pastes: pastes.current, away_count: away.current, elapsed_ms: Date.now() - started.current } } }),
    onSuccess: (v: any) => { setConfirm(false); setResults(v.results); qc.invalidateQueries({ queryKey: ['cand-tasks'] }); qc.invalidateQueries({ queryKey: ['cand-dashboard'] }); push(`Решение отправлено: пройдено ${v.results.passed} из ${v.results.total} тестов`) },
    onError: (e: any) => { setConfirm(false); push(e.message, 'error') },
  })
  return (
    <div className="mt-4 space-y-4">
      <div className="rounded-2xl bg-surface p-4">
        <p className="label">Функция <code className="rounded bg-white px-1.5 py-0.5 font-mono text-[12px] text-fsp-deep">{task.entrypoint}</code> · примеры (ещё {task.hidden_count} скрытых тестов проверят при отправке)</p>
        <div className="space-y-1 break-all font-mono text-[12px] text-slate-600">
          {task.examples.map((x: any) => <p key={x.index}>{task.entrypoint}({x.args.map(fmt).join(', ')}) → {fmt(x.expected)}{x.name && <span className="font-sans text-slate-400"> · {x.name}</span>}</p>)}
        </div>
      </div>
      <CodeEditor value={code} onChange={setCode} language={task.code_language} readOnly={!editable} onPaste={n => pastes.current.push({ chars: n })} />
      {editable && (
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="flex items-center gap-1.5 text-xs text-slate-400"><ShieldCheck className="h-3.5 w-3.5 shrink-0" />Код выполняется в изолированной песочнице: без сети, с лимитами времени ({task.time_limit_ms} мс) и памяти. Вставки из буфера видны работодателю.</p>
          <div className="flex flex-wrap gap-2">
            <Button variant="ghost" onClick={onSkip} icon={<SkipForward className="h-4 w-4" />}>Пропустить</Button>
            <Button variant="ghost" onClick={() => setCode(task.starter_code ?? '')} icon={<RotateCcw className="h-4 w-4" />}>К шаблону</Button>
            <Button variant="secondary" loading={run.isPending} onClick={() => run.mutate()} icon={<Play className="h-4 w-4" />}>Запустить примеры</Button>
            <Button disabled={!code.trim()} onClick={() => setConfirm(true)} icon={<Send className="h-4 w-4" />}>Отправить решение</Button>
          </div>
        </div>
      )}
      {confirm && (
        <Alert tone="warn" title="Отправить решение?">
          Код проверят на всех тестах, включая скрытые; после отправки изменить его нельзя. Работодатель увидит результат тестов и оценит решение.
          <div className="mt-3 flex gap-2"><Button size="sm" loading={submit.isPending} onClick={() => submit.mutate()}>Отправить</Button><Button size="sm" variant="ghost" onClick={() => setConfirm(false)}>Продолжить работу</Button></div>
        </Alert>
      )}
      <TestResults res={results} />
    </div>
  )
}

function TaskCard({ t }: { t: any }) {
  const qc = useQueryClient()
  const { push } = useToast()
  const [answer, setAnswer] = useState('')
  const submit = useMutation({ mutationFn: () => api(`/candidate/tasks/${t.id}/submit`, { body: { answer } }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['cand-tasks'] }); qc.invalidateQueries({ queryKey: ['cand-dashboard'] }); push('Решение отправлено работодателю') },
    onError: (e: any) => push(e.message, 'error') })
  const skip = useMutation({ mutationFn: () => api(`/candidate/tasks/${t.id}/skip`, { method: 'POST' }), onSuccess: () => qc.invalidateQueries({ queryKey: ['cand-tasks'] }) })
  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm text-slate-500">{t.task.company} · {t.task.specialization_name} · предложено {ago(t.offered_at)}</p>
          <h3 className="mt-0.5 text-lg font-bold">{t.task.title}</h3>
        </div>
        <div className="flex items-center gap-2">
          <Badge tone="lavender" icon={<Clock className="h-3 w-3" />}>~{t.task.time_estimate_min} мин</Badge>
          {t.task.kind === 'code' ? <Badge tone="pink" icon={<Code2 className="h-3 w-3" />}>код · {t.task.code_language === 'python' ? 'Python' : 'JavaScript'}</Badge>
            : <Badge tone="amber">{t.task.kind === 'solve' ? 'решить' : 'предложить подход'}</Badge>}
          <StatusBadge status={t.status} />
        </div>
      </div>
      {t.task.kind === 'code' ? <div className="mt-3"><Markdown className="!text-sm">{t.task.description}</Markdown></div>
        : <p className="mt-3 whitespace-pre-line text-sm leading-relaxed text-slate-700">{t.task.description}</p>}
      {t.task.kind === 'code' && <CodeTask t={t} onSkip={() => skip.mutate()} />}
      {t.task.kind !== 'code' && t.status === 'offered' && (
        <div className="mt-4 space-y-3">
          <Textarea rows={6} placeholder="Ваше решение или подход: ключевые шаги, компромиссы, риски" value={answer} onChange={e => setAnswer(e.target.value)} />
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs text-slate-400">{t.due_at && `Желательно до ${date(t.due_at)}. `}Решённые задания поддерживают профиль в актуальном состоянии.</p>
            <div className="flex gap-2">
              <Button variant="ghost" onClick={() => skip.mutate()} icon={<SkipForward className="h-4 w-4" />}>Пропустить</Button>
              <Button disabled={answer.trim().length < 10} loading={submit.isPending} onClick={() => submit.mutate()} icon={<Send className="h-4 w-4" />}>Отправить</Button>
            </div>
          </div>
        </div>
      )}
      {t.task.kind !== 'code' && t.answer && t.status !== 'offered' && <div className="mt-4 rounded-2xl bg-surface p-4 text-sm"><p className="label">Ваш ответ</p><p className="whitespace-pre-line text-slate-700">{t.answer}</p></div>}
      {t.status === 'reviewed' && (
        <Alert tone="success" title={<span className="flex items-center gap-1.5">Оценка работодателя: {Array.from({ length: 5 }).map((_, i) => <Star key={i} className={`h-4 w-4 ${i < t.score ? 'fill-amber-400 text-amber-400' : 'text-slate-300'}`} />)}</span>}>
          {t.feedback}
        </Alert>
      )}
    </Card>
  )
}

export function CandidateTasks() {
  const { data, isLoading } = useQuery({ queryKey: ['cand-tasks'], queryFn: () => api<any[]>('/candidate/tasks') })
  if (isLoading || !data) return <PageLoader />
  return (
    <div>
      <PageHeader title="Регулярные задания" subtitle="Раз в неделю система предлагает короткую задачу от работодателя вашей категории: решить её (задачи с кодом проверяются тестами в песочнице) или предложить подход. Оценённые решения повышают «свежесть» и силу профиля." />
      {!data.length ? <EmptyState icon={<ListChecks className="h-5 w-5" />} title="Заданий пока нет" text="Задания появляются после присвоения категории — раз в 7 дней." /> :
        <div className="space-y-4">{data.map(t => <TaskCard key={t.id} t={t} />)}</div>}
    </div>
  )
}
