import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Send } from 'lucide-react'
import { api } from '@/lib/api'
import { useToast } from '@/lib/toast'
import { ago, salaryRange } from '@/lib/format'
import { Badge, Button, ButtonLink, Card, EmptyState, PageHeader, PageLoader } from '@/components/ui'

const TONE: Record<string, 'blue' | 'lavender' | 'green' | 'red' | 'gray'> = { sent: 'blue', viewed: 'lavender', accepted: 'green', rejected: 'red', withdrawn: 'gray' }

export function Applications() {
  const qc = useQueryClient()
  const { push } = useToast()
  const { data, isLoading } = useQuery({ queryKey: ['applications'], queryFn: () => api<any[]>('/candidate/applications') })
  const withdraw = useMutation({ mutationFn: (id: number) => api(`/candidate/applications/${id}/withdraw`, { method: 'POST' }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['applications'] }); push('Отклик отозван') } })
  if (isLoading || !data) return <PageLoader />
  return (
    <div>
      <PageHeader title="Мои отклики" subtitle="Статусы обновляются, когда работодатель просматривает отклик и принимает решение." />
      {!data.length ? <EmptyState icon={<Send className="h-5 w-5" />} title="Вы ещё не откликались" action={<ButtonLink to="/candidate/vacancies" size="sm">Смотреть вакансии</ButtonLink>} /> : (
        <div className="space-y-3">
          {data.map(a => (
            <Card key={a.id}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <Link to={`/candidate/vacancies/${a.vacancy.id}`} className="text-lg font-bold text-fsp-deep hover:text-fsp-pink">{a.vacancy.title}</Link>
                  <p className="text-sm text-slate-500">{a.company.name} · {salaryRange(a.vacancy.salary_from, a.vacancy.salary_to)} · отправлен {ago(a.created_at)}</p>
                  {a.employer_comment && <p className="mt-2 rounded-xl bg-surface px-3 py-2 text-sm text-slate-700"><b>Комментарий работодателя:</b> {a.employer_comment}</p>}
                </div>
                <div className="flex items-center gap-2">
                  <Badge tone={TONE[a.status]}>{a.status_name}</Badge>
                  {['sent', 'viewed'].includes(a.status) && <Button size="sm" variant="ghost" onClick={() => withdraw.mutate(a.id)}>Отозвать</Button>}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
