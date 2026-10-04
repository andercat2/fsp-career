import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { ListChecks, Plus, Star } from 'lucide-react'
import { api } from '@/lib/api'
import { useReference } from '@/lib/reference'
import { useToast } from '@/lib/toast'
import { ago } from '@/lib/format'
import { Alert, Badge, Button, Card, EmptyState, Field, Input, Modal, PageHeader, PageLoader, Select, Tabs, Textarea } from '@/components/ui'

function Review({ ta }: { ta: any }) {
  const qc = useQueryClient()
  const { push } = useToast()
  const [score, setScore] = useState(ta.score ?? 0)
  const [feedback, setFeedback] = useState(ta.feedback ?? '')
  const save = useMutation({ mutationFn: () => api(`/employer/submissions/${ta.id}/review`, { body: { score, feedback } }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['emp-subs'] }); push('Оценка сохранена — профиль кандидата обновлён') }, onError: (e: any) => push(e.message, 'error') })
  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-bold text-fsp-deep">{ta.task.title}</p>
          <p className="text-sm text-slate-500"><Link to={`/employer/candidates/${ta.candidate.id}`} className="link">{ta.candidate.public_id}</Link> · {ta.candidate.specialization_name} · {ta.candidate.grade_name} · {ago(ta.submitted_at)}</p>
        </div>
        {ta.auto_score != null && <Badge tone="lavender">автооценка по рубрике: {Math.round(ta.auto_score * 100)}%</Badge>}
      </div>
      <p className="mt-3 whitespace-pre-line rounded-2xl bg-surface p-4 text-sm text-slate-700">{ta.answer}</p>
      <div className="mt-4 flex flex-wrap items-end gap-3">
        <div>
          <p className="label">Оценка</p>
          <div className="flex gap-1">{[1, 2, 3, 4, 5].map(n => (
            <button key={n} onClick={() => setScore(n)} aria-label={`${n}`}><Star className={clsx('h-7 w-7', n <= score ? 'fill-amber-400 text-amber-400' : 'text-slate-300')} /></button>))}</div>
        </div>
        <Input className="min-w-[240px] flex-1" placeholder="Комментарий кандидату" value={feedback} onChange={e => setFeedback(e.target.value)} />
        <Button disabled={!score} loading={save.isPending} onClick={() => save.mutate()}>{ta.status === 'reviewed' ? 'Обновить' : 'Оценить'}</Button>
      </div>
    </Card>
  )
}

export function EmployerTasks() {
  const qc = useQueryClient()
  const { push } = useToast()
  const { ref } = useReference()
  const [tab, setTab] = useState<'submitted' | 'reviewed' | 'tasks'>('submitted')
  const [open, setOpen] = useState(false)
  const [f, setF] = useState({ title: '', description: '', specialization: 'backend', kind: 'approach', expected_answer: '', time_estimate_min: 30 })
  const { data: tasks } = useQuery({ queryKey: ['emp-tasks'], queryFn: () => api<any[]>('/employer/tasks') })
  const { data: subs, isLoading } = useQuery({ queryKey: ['emp-subs', tab], queryFn: () => api<any[]>(`/employer/tasks/submissions?status=${tab}`), enabled: tab !== 'tasks' })
  const create = useMutation({ mutationFn: () => api('/employer/tasks', { body: { ...f, expected_answer: f.expected_answer || null } }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['emp-tasks'] }); setOpen(false); push('Задание создано — система будет предлагать его кандидатам категории') }, onError: (e: any) => push(e.message, 'error') })
  return (
    <div>
      <PageHeader title="Регулярные задания" subtitle="Короткие задачи от вашей команды. Раз в неделю система предлагает их кандидатам подходящей категории — вы получаете свежий сигнал об уровне, а кандидаты поддерживают профиль актуальным."
        actions={<Button onClick={() => setOpen(true)} icon={<Plus className="h-4 w-4" />}>Новое задание</Button>} />
      <Tabs value={tab} onChange={setTab} items={[{ value: 'submitted', label: 'На проверке' }, { value: 'reviewed', label: 'Проверенные' }, { value: 'tasks', label: 'Мои задания', count: tasks?.length }]} />
      <div className="mt-5 space-y-3">
        {tab === 'tasks' ? (
          !tasks?.length ? <EmptyState icon={<ListChecks className="h-5 w-5" />} title="Заданий пока нет" /> : tasks.map(t => (
            <Card key={t.id}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div><p className="font-bold text-fsp-deep">{t.title}</p><p className="text-sm text-slate-500">{t.specialization_name} · {t.kind === 'solve' ? 'решить' : 'предложить подход'} · ~{t.time_estimate_min} мин</p></div>
                <div className="flex gap-2 text-xs"><Badge tone="amber">предложено {t.counts.offered}</Badge><Badge tone="blue">ответов {t.counts.submitted}</Badge><Badge tone="green">проверено {t.counts.reviewed}</Badge></div>
              </div>
              <p className="mt-2 text-sm text-slate-600">{t.description}</p>
            </Card>
          ))
        ) : isLoading ? <PageLoader /> : !subs?.length ? <EmptyState icon={<ListChecks className="h-5 w-5" />} title={tab === 'submitted' ? 'Новых решений нет' : 'Проверенных решений нет'} /> : subs.map(ta => <Review key={ta.id} ta={ta} />)}
      </div>
      <Modal open={open} onClose={() => setOpen(false)} title="Новое задание" wide
        footer={<><Button variant="secondary" onClick={() => setOpen(false)}>Отмена</Button><Button loading={create.isPending} disabled={f.title.length < 3 || f.description.length < 10} onClick={() => create.mutate()}>Создать</Button></>}>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Название" required className="sm:col-span-2"><Input value={f.title} onChange={e => setF({ ...f, title: e.target.value })} /></Field>
          <Field label="Специализация"><Select value={f.specialization} onChange={e => setF({ ...f, specialization: e.target.value })}>
            {ref?.specializations.map(s => <option key={s.code} value={s.code}>{s.name}</option>)}</Select></Field>
          <Field label="Тип"><Select value={f.kind} onChange={e => setF({ ...f, kind: e.target.value })}><option value="approach">Предложить подход</option><option value="solve">Решить</option></Select></Field>
          <Field label="Условие" required className="sm:col-span-2"><Textarea rows={5} value={f.description} onChange={e => setF({ ...f, description: e.target.value })} /></Field>
          <Field label="Эталон / рубрика (для предварительной автооценки)" className="sm:col-span-2"><Textarea rows={3} value={f.expected_answer} onChange={e => setF({ ...f, expected_answer: e.target.value })} /></Field>
          <Field label="Оценка времени, мин"><Input type="number" value={f.time_estimate_min} onChange={e => setF({ ...f, time_estimate_min: Number(e.target.value) })} /></Field>
        </div>
        <div className="mt-4"><Alert tone="info">Решения оцениваются по шкале 1–5. Оценка влияет на компонент «активность» в силе профиля кандидата.</Alert></div>
      </Modal>
    </div>
  )
}
