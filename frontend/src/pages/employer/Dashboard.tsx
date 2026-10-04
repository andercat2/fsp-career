import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Clock, FileText, Inbox, ListChecks, Plus, Send, Sparkles, Users } from 'lucide-react'
import { api } from '@/lib/api'
import { ago } from '@/lib/format'
import { ButtonLink, Card, EmptyState, PageHeader, PageLoader, Stat } from '@/components/ui'

const DECLINE: Record<string, string> = { salary: 'Доход', stack: 'Стек/задачи', format: 'Формат', company: 'Компания', not_looking: 'Не ищет', other: 'Другое' }
const FUNNEL = [['sent', 'Отправлено'], ['viewed', 'Просмотрено'], ['accepted', 'Принято'], ['declined', 'Отклонено'], ['expired', 'Истекло']]
const COLORS: Record<string, string> = { sent: '#8A83D1', viewed: '#B9B3FF', accepted: '#FF0053', declined: '#310F53', expired: '#CBD5E1' }

export function EmployerDashboard() {
  const { data, isLoading } = useQuery({ queryKey: ['emp-dashboard'], queryFn: () => api('/employer/dashboard') })
  const { data: sels } = useQuery({ queryKey: ['emp-selections'], queryFn: () => api<any[]>('/employer/selections') })
  if (isLoading || !data) return <PageLoader />
  const inv = data.invitations
  const funnel = FUNNEL.map(([k, l]) => ({ name: l, key: k, value: inv.by_status[k] ?? 0 }))
  const declines = Object.entries(inv.decline_reasons as Record<string, number>).map(([k, v]) => ({ name: DECLINE[k] ?? k, value: v }))
  return (
    <div className="space-y-6">
      <PageHeader title={data.company.name} subtitle="Обратная механика: вы выбираете категорию и сами выходите на кандидатов с предложением."
        actions={<><ButtonLink to="/employer/needs/new" variant="secondary" icon={<Plus className="h-4 w-4" />}>Новая потребность</ButtonLink>
          <ButtonLink to="/employer/selections" icon={<Sparkles className="h-4 w-4" />}>Подобрать кандидатов</ButtonLink></>} />
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <Stat accent label="Принимают приглашения" value={inv.acceptance_rate != null ? `${Math.round(inv.acceptance_rate * 100)}%` : '—'} hint="от ответивших кандидатов" icon={<Send className="h-5 w-5" />} />
        <Stat label="Среднее время ответа" value={inv.avg_response_hours != null ? `${inv.avg_response_hours} ч` : '—'} icon={<Clock className="h-5 w-5" />} />
        <Stat label="Новые отклики" value={data.applications_new} icon={<Inbox className="h-5 w-5" />} hint={`${data.vacancies_published} опубликованных вакансий`} />
        <Stat label="Решения на проверку" value={data.task_submissions_pending} icon={<ListChecks className="h-5 w-5" />} />
      </div>
      <div className="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
        <Card title="Воронка приглашений" subtitle={`Всего отправлено: ${inv.total}`}>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={funnel} margin={{ left: -20, right: 8, top: 8 }}>
                <XAxis dataKey="name" tick={{ fontSize: 12, fill: '#64748b' }} axisLine={false} tickLine={false} />
                <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                <Tooltip cursor={{ fill: '#F6F4FA' }} contentStyle={{ borderRadius: 12, border: 'none', boxShadow: '0 10px 30px -10px rgba(49,15,83,.3)' }} />
                <Bar dataKey="value" name="Приглашений" radius={[8, 8, 0, 0]}>{funnel.map(f => <Cell key={f.key} fill={COLORS[f.key]} />)}</Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card title="Почему отказываются" subtitle="Структурированная обратная связь от кандидатов">
          {!declines.length ? <p className="muted">Отказов пока нет.</p> : (
            <div className="space-y-3">{declines.sort((a, b) => b.value - a.value).map(d => (
              <div key={d.name}><div className="mb-1 flex justify-between text-sm"><span>{d.name}</span><b className="text-fsp-deep">{d.value}</b></div>
                <div className="h-2 rounded-full bg-slate-100"><div className="h-full rounded-full bg-fsp-deep" style={{ width: `${(d.value / Math.max(...declines.map(x => x.value))) * 100}%` }} /></div></div>))}</div>
          )}
          <p className="mt-4 text-xs text-slate-500">Если чаще всего отказывают по доходу — проверьте медиану ожиданий в карточках категорий подборки.</p>
        </Card>
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Последние подборки" actions={<Link to="/employer/selections" className="link text-sm">Все</Link>}>
          {!sels?.length ? <EmptyState icon={<Sparkles className="h-5 w-5" />} title="Подборок нет" /> : (
            <div className="divide-y divide-slate-100">{sels.slice(0, 5).map(s => (
              <Link key={s.id} to={`/employer/selections/${s.id}`} className="flex items-center justify-between gap-3 py-3 hover:opacity-80">
                <span className="truncate text-sm font-semibold text-fsp-deep">{s.title}</span><span className="shrink-0 text-xs text-slate-500">{s.total} канд. · {ago(s.created_at)}</span></Link>))}</div>
          )}
        </Card>
        <Card title="База кандидатов">
          <div className="flex items-center gap-4">
            <div className="grid h-14 w-14 place-items-center rounded-2xl bg-fsp-blush text-fsp-pink"><Users className="h-7 w-7" /></div>
            <div><p className="text-3xl font-extrabold text-fsp-deep">{data.candidates_in_bank}</p><p className="text-sm text-slate-500">кандидатов с подтверждённой категорией</p></div>
          </div>
          <div className="mt-5 flex flex-wrap gap-2">
            <ButtonLink to="/employer/search" variant="secondary" size="sm" icon={<Users className="h-4 w-4" />}>Открыть банк</ButtonLink>
            <ButtonLink to="/employer/needs" variant="secondary" size="sm" icon={<FileText className="h-4 w-4" />}>Потребности ({data.vacancies_active})</ButtonLink>
          </div>
        </Card>
      </div>
    </div>
  )
}
