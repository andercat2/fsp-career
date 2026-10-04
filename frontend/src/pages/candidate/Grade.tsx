import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Award, Clock, History, Lock, Play } from 'lucide-react'
import { api } from '@/lib/api'
import { date, dateTime } from '@/lib/format'
import { Badge, ButtonLink, Card, EmptyState, KV, PageHeader, PageLoader } from '@/components/ui'
import { CategoryPill, DomainBars } from '@/components/Domain'

const DECISION_RU: Record<string, [string, 'green' | 'pink' | 'amber' | 'gray']> = {
  confirmed: ['подтверждён', 'green'], confirmed_strong: ['подтверждён уверенно', 'pink'], not_confirmed: ['не подтверждён', 'amber'],
}

export function GradePage() {
  const { data: p, isLoading } = useQuery({ queryKey: ['cand-profile'], queryFn: () => api('/candidate/profile') })
  const { data: el } = useQuery({ queryKey: ['eligibility'], queryFn: () => api('/testing/eligibility') })
  const { data: hist } = useQuery({ queryKey: ['test-history'], queryFn: () => api('/testing/history') })
  const { data: surveys } = useQuery({ queryKey: ['survey-history'], queryFn: () => api<any[]>('/testing/survey/history') })
  if (isLoading || !p) return <PageLoader />
  const cat = p.category
  const locked = el?.grades?.filter((g: any) => !g.allowed) ?? []
  return (
    <div className="space-y-6">
      <PageHeader title="Категория и грейд" subtitle="Текущий статус, история опросов и тестов. Грейд не понижается принудительно; смена грейда — не чаще раза в 90 дней."
        actions={<ButtonLink to="/candidate/testing" icon={<Play className="h-4 w-4" />}>Пройти тест</ButtonLink>} />
      <div className="grid gap-6 lg:grid-cols-[1fr_1.2fr]">
        <Card title="Текущий статус">
          <CategoryPill spec={cat.specialization_name} grade={cat.grade_name} className="text-sm" />
          <div className="mt-4 divide-y divide-slate-100">
            <KV k="Специализация из опроса" v={p.specialization_name ?? '—'} />
            <KV k="Заявленный грейд" v={p.claimed_grade ? <Badge tone="lavender">{p.claimed_grade}</Badge> : '—'} />
            <KV k="Отрасли" v={p.industries?.join(', ') || '—'} />
            <KV k="Оценка уровня θ" v={cat.theta != null ? `${cat.theta.toFixed(2)} ± ${cat.se?.toFixed(2)}` : '—'} />
            <KV k="Выше рынка" v={cat.percentile != null ? `${Math.round(cat.percentile)}%` : '—'} />
            <KV k="Присвоена" v={date(cat.assigned_at)} />
            <KV k="Последняя смена грейда" v={date(cat.changed_at)} />
          </div>
          {!!locked.length && (
            <div className="mt-4 space-y-2 rounded-2xl bg-surface p-4">
              <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500"><Clock className="h-3.5 w-3.5" /> Ограничения</p>
              {locked.map((g: any) => (
                <p key={g.grade} className="flex items-start gap-2 text-sm text-slate-600"><Lock className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
                  <span><b className="text-fsp-deep">{g.name}:</b> {g.reason}{g.available_from && ` (с ${date(g.available_from)})`}</span></p>
              ))}
            </div>
          )}
        </Card>
        <Card title="Профиль компетенций" subtitle="По последнему тесту, подтвердившему грейд">
          {Object.keys(p.test?.domains ?? {}).length ? <DomainBars domains={p.test.domains} /> :
            <EmptyState icon={<Award className="h-5 w-5" />} title="Тест ещё не пройден" action={<ButtonLink to="/candidate/testing" size="sm">Перейти к тестированию</ButtonLink>} />}
        </Card>
      </div>

      <Card title="История тестов" actions={<History className="h-4 w-4 text-slate-400" />}>
        {!hist?.sessions?.length ? <p className="muted">Тестов пока не было.</p> : (
          <div className="scrollbar-thin overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead><tr className="text-left text-xs uppercase tracking-wide text-slate-400">
                <th className="pb-2 font-semibold">Дата</th><th className="pb-2 font-semibold">Специализация</th><th className="pb-2 font-semibold">Уровень</th>
                <th className="pb-2 font-semibold">Заданий</th><th className="pb-2 font-semibold">Выше рынка</th><th className="pb-2 font-semibold">Решение</th><th /></tr></thead>
              <tbody className="divide-y divide-slate-100">
                {hist.sessions.map((s: any) => {
                  const d = DECISION_RU[s.decision] ?? [s.status === 'abandoned' ? 'прерван' : s.status === 'in_progress' ? 'в процессе' : '—', 'gray']
                  return (
                    <tr key={s.token}>
                      <td className="py-2.5">{dateTime(s.started_at)}</td><td>{s.specialization_name}</td><td>{s.target_grade_name}</td>
                      <td>{s.n_items ? `${s.n_correct}/${s.n_items}` : '—'}</td><td>{s.percentile != null ? `${Math.round(s.percentile)}%` : '—'}</td>
                      <td><Badge tone={d[1]}>{d[0]}</Badge></td>
                      <td className="text-right">{(s.status === 'completed' || s.status === 'in_progress') && <Link to={`/candidate/testing/${s.token}`} className="link text-xs">{s.status === 'in_progress' ? 'продолжить' : 'результат'}</Link>}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Смены грейда">
          {!hist?.grade_changes?.length ? <p className="muted">Грейд ещё не присваивался.</p> : (
            <ul className="space-y-2">{hist.grade_changes.map((g: any, i: number) => (
              <li key={i} className="flex items-center justify-between rounded-xl bg-surface px-3 py-2 text-sm">
                <span>{g.specialization_name}: {g.old_grade ? `${g.old_grade} → ` : ''}<b className="text-fsp-deep">{g.new_grade_name}</b></span>
                <span className="text-xs text-slate-500">{date(g.created_at)}</span>
              </li>))}
            </ul>
          )}
        </Card>
        <Card title="История опросов">
          {!surveys?.length ? <p className="muted">Опрос не пройден.</p> : (
            <ul className="space-y-2">{surveys.map(s => (
              <li key={s.id} className="rounded-xl bg-surface px-3 py-2 text-sm">
                <div className="flex justify-between gap-3"><span><b className="text-fsp-deep">{s.specialization_name}</b> · заявлен {s.claimed_grade}</span><span className="text-xs text-slate-500">{date(s.created_at)}</span></div>
                {s.warnings?.map((w: string, i: number) => <p key={i} className="mt-1 text-xs text-amber-700">{w}</p>)}
              </li>))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  )
}
