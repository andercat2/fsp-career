import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Send } from 'lucide-react'
import { api } from '@/lib/api'
import { useToast } from '@/lib/toast'
import { ago, dateTime, salaryRange } from '@/lib/format'
import { Button, ButtonLink, Card, EmptyState, PageHeader, PageLoader, Tabs } from '@/components/ui'
import { CategoryPill, StatusBadge } from '@/components/Domain'

const DECLINE: Record<string, string> = { salary: 'Не устраивает доход', stack: 'Не подходит стек/задачи', format: 'Формат или локация',
  company: 'Не интересна компания', not_looking: 'Не ищет работу', other: 'Другое' }

export function EmployerInvitations() {
  const qc = useQueryClient()
  const { push } = useToast()
  const [tab, setTab] = useState('all')
  const { data, isLoading } = useQuery({ queryKey: ['emp-invitations'], queryFn: () => api<any[]>('/employer/invitations') })
  const withdraw = useMutation({ mutationFn: (id: number) => api(`/employer/invitations/${id}/withdraw`, { method: 'POST' }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['emp-invitations'] }); push('Приглашение отозвано') } })
  if (isLoading || !data) return <PageLoader />
  const counts = (s: string) => data.filter(i => s === 'all' || i.status === s).length
  const items = data.filter(i => tab === 'all' || i.status === tab)
  return (
    <div>
      <PageHeader title="Приглашения" subtitle="Статусы обновляются в реальном времени: отправлено → просмотрено → принято / отклонено. Причины отказов помогают скорректировать предложение." />
      <Tabs value={tab} onChange={setTab} items={[
        { value: 'all', label: 'Все', count: counts('all') }, { value: 'sent', label: 'Отправлено', count: counts('sent') },
        { value: 'viewed', label: 'Прочитано', count: counts('viewed') }, { value: 'accepted', label: 'Принято', count: counts('accepted') },
        { value: 'declined', label: 'Отклонено', count: counts('declined') }, { value: 'expired', label: 'Истекло', count: counts('expired') },
      ]} />
      <div className="mt-5 space-y-3">
        {!items.length && <EmptyState icon={<Send className="h-5 w-5" />} title="Приглашений нет" action={<ButtonLink to="/employer/selections" size="sm">Перейти к подборкам</ButtonLink>} />}
        {items.map(i => (
          <Card key={i.id}>
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <Link to={`/employer/candidates/${i.candidate.id}`} className="font-bold text-fsp-deep hover:text-fsp-pink">{i.candidate.display_name}</Link>
                  <CategoryPill spec={i.candidate.specialization_name} grade={i.candidate.grade_name} />
                  {i.match != null && <span className="text-xs text-slate-500">совпадение {i.match}%</span>}
                </div>
                <p className="mt-1 text-sm text-slate-600"><b>{i.title}</b> · {salaryRange(i.salary_from, i.salary_to)}{i.vacancy ? ` · по вакансии «${i.vacancy.title}»` : ' · без привязки к вакансии'}</p>
                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
                  <span>Отправлено {dateTime(i.created_at)}</span>
                  {i.viewed_at && <span>кандидат прочитал {ago(i.viewed_at)}</span>}
                  {i.responded_at && <span>ответ {ago(i.responded_at)}</span>}
                </div>
                {i.status === 'declined' && <p className="mt-2 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-800">Причина отказа: <b>{DECLINE[i.decline_reason] ?? i.decline_reason}</b>{i.decline_comment && ` — «${i.decline_comment}»`}</p>}
                {i.status === 'accepted' && <p className="mt-2 rounded-xl bg-emerald-50 px-3 py-2 text-sm text-emerald-800">Кандидат принял приглашение — контакты открыты в карточке.</p>}
              </div>
              <div className="flex items-center gap-2">
                <StatusBadge status={i.status} side="employer" />
                {['sent', 'viewed'].includes(i.status) && <Button size="sm" variant="ghost" onClick={() => withdraw.mutate(i.id)}>Отозвать</Button>}
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}
