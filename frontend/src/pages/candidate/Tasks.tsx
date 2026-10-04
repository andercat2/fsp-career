import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Clock, ListChecks, Send, SkipForward, Star } from 'lucide-react'
import { api } from '@/lib/api'
import { useToast } from '@/lib/toast'
import { ago, date } from '@/lib/format'
import { Alert, Badge, Button, Card, EmptyState, PageHeader, PageLoader, Textarea } from '@/components/ui'
import { StatusBadge } from '@/components/Domain'

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
          <Badge tone="amber">{t.task.kind === 'solve' ? 'решить' : 'предложить подход'}</Badge>
          <StatusBadge status={t.status} />
        </div>
      </div>
      <p className="mt-3 whitespace-pre-line text-sm leading-relaxed text-slate-700">{t.task.description}</p>
      {t.status === 'offered' && (
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
      {t.answer && t.status !== 'offered' && <div className="mt-4 rounded-2xl bg-surface p-4 text-sm"><p className="label">Ваш ответ</p><p className="whitespace-pre-line text-slate-700">{t.answer}</p></div>}
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
      <PageHeader title="Регулярные задания" subtitle="Раз в неделю система предлагает короткую задачу от работодателя вашей категории: решить её или предложить подход. Оценённые решения повышают «свежесть» и силу профиля." />
      {!data.length ? <EmptyState icon={<ListChecks className="h-5 w-5" />} title="Заданий пока нет" text="Задания появляются после присвоения категории — раз в 7 дней." /> :
        <div className="space-y-4">{data.map(t => <TaskCard key={t.id} t={t} />)}</div>}
    </div>
  )
}
