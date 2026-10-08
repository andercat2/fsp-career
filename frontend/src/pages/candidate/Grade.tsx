import { Link, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Award, Clock, History, Lock, Play, ShieldAlert, Zap } from 'lucide-react'
import { api } from '@/lib/api'
import { date, dateTime } from '@/lib/format'
import { Badge, ButtonLink, Card, EmptyState, KV, PageHeader, PageLoader } from '@/components/ui'
import { CategoryPill, DomainBars } from '@/components/Domain'
import { ResumeTabs, useResumes } from '@/components/Resumes'
import { useReference } from '@/lib/reference'

const DECISION_RU: Record<string, [string, 'green' | 'pink' | 'amber' | 'gray']> = {
  confirmed: ['подтверждён', 'green'], confirmed_strong: ['подтверждён уверенно', 'pink'], not_confirmed: ['не подтверждён', 'amber'],
}

export function GradePage() {
  const [params, setParams] = useSearchParams()
  const { gradeName, ref } = useReference()
  const rid = Number(params.get('resume') ?? 0) || 0
  const { data: resumes, isLoading } = useResumes()
  const { data: el } = useQuery({ queryKey: ['eligibility', rid], queryFn: () => api(`/testing/eligibility?resume_id=${rid}`) })
  const { data: hist } = useQuery({ queryKey: ['test-history'], queryFn: () => api('/testing/history') })
  const { data: surveys } = useQuery({ queryKey: ['survey-history'], queryFn: () => api<any[]>('/testing/survey/history') })
  if (isLoading || !resumes) return <PageLoader />
  const r = resumes.find(x => x.id === rid) ?? resumes[0]
  const cat = r.category
  const locked = el?.grades?.filter((g: any) => !g.allowed) ?? []
  const titles = Object.fromEntries(resumes.map(x => [x.id, x.title || x.specialization_name]))
  return (
    <div className="space-y-6">
      <PageHeader title="Категория и грейд" subtitle="Текущий статус по каждому резюме, история опросов и тестов. Грейд не понижается принудительно; смена грейда — не чаще раза в месяц для каждой категории."
        actions={<ButtonLink to={`/candidate/testing${r.id ? `?resume=${r.id}` : ''}`} icon={<Play className="h-4 w-4" />}>Пройти тест</ButtonLink>} />
      {resumes.length > 1 && <ResumeTabs resumes={resumes} active={r.id} onSelect={id => setParams(id ? { resume: String(id) } : {})} />}
      <div className="grid gap-6 lg:grid-cols-[1fr_1.2fr]">
        <Card title="Текущий статус" subtitle={resumes.length > 1 ? `Резюме: ${r.title || r.specialization_name}` : undefined}>
          <CategoryPill spec={cat.specialization_name} grade={cat.grade_name} status={cat.status} claimed={cat.claimed_grade_name} className="text-sm" />
          {cat.status === 'unconfirmed' && (
            <p className="mt-3 rounded-2xl bg-amber-50 px-4 py-3 text-sm text-amber-900">
              Тест не подтвердил грейд {cat.claimed_grade_name}{cat.measured_grade_name && cat.measured_grade_name !== cat.claimed_grade_name ? ` — он показал уровень ${cat.measured_grade_name}` : ''}.
              Работодатели видят вас со статусом «не подтверждён» ниже кандидатов с подтверждённым грейдом, поэтому вы не выпадаете из поиска.
              Подтвердите уровень тестом — уровнем ниже можно сразу — или отключите показ в <Link to="/candidate/settings" className="link">настройках приватности</Link>.
            </p>
          )}
          <div className="mt-4 divide-y divide-slate-100">
            <KV k="Специализация из опроса" v={r.specialization_name ? `${r.specialization_name}${r.language_name ? ` · ${r.language_name}` : ''}` : '—'} />
            <KV k="Заявленный грейд" v={r.claimed_grade_name ? <Badge tone="lavender">{r.claimed_grade_name}</Badge> : '—'} />
            <KV k="Отрасль (ИТ-направление)" v={ref?.specializations.find(s => s.code === r.specialization)?.direction ?? '—'} />
            <KV k="Предметные области" v={r.industries?.join(', ') || '—'} />
            <KV k="Оценка уровня θ" v={cat.theta != null ? `${cat.theta.toFixed(2)} ± ${cat.se?.toFixed(2)}` : '—'} />
            <KV k="Выше рынка" v={cat.percentile != null ? `${Math.round(cat.percentile)}%` : '—'} />
            <KV k={cat.status === 'unconfirmed' ? 'Тест, не подтвердивший грейд' : 'Присвоена'} v={date(cat.status === 'unconfirmed' ? cat.tested_at : cat.assigned_at)} />
            <KV k="Последняя смена грейда" v={date(cat.changed_at)} />
          </div>
          {!!locked.length && (
            <div className="mt-4 space-y-2 rounded-2xl bg-surface p-4">
              <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500"><Clock className="h-3.5 w-3.5" /> Ограничения этой категории</p>
              {locked.map((g: any) => (
                <p key={g.grade} className="flex items-start gap-2 text-sm text-slate-600"><Lock className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
                  <span><b className="text-fsp-deep">{g.name}:</b> {g.reason}{g.available_from && ` (с ${date(g.available_from)})`}</span></p>
              ))}
            </div>
          )}
        </Card>
        <Card title="Профиль компетенций" subtitle={cat.status === 'unconfirmed' ? 'По тесту, который грейд не подтвердил' : 'По последнему тесту, подтвердившему грейд этой категории'}>
          {Object.keys(r.domains ?? {}).length ? <DomainBars domains={r.domains} /> :
            <EmptyState icon={<Award className="h-5 w-5" />} title="Тест ещё не пройден" action={<ButtonLink to={`/candidate/testing${r.id ? `?resume=${r.id}` : ''}`} size="sm">Перейти к тестированию</ButtonLink>} />}
        </Card>
      </div>

      <Card title="История тестов" actions={<History className="h-4 w-4 text-slate-400" />}>
        {!hist?.sessions?.length ? <p className="muted">Тестов пока не было.</p> : (
          <div className="scrollbar-thin overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm">
              <thead><tr className="text-left text-xs uppercase tracking-wide text-slate-400">
                <th className="pb-2 font-semibold">Дата</th><th className="pb-2 font-semibold">Резюме · специализация</th><th className="pb-2 font-semibold">Уровень</th>
                <th className="pb-2 font-semibold">Заданий</th><th className="pb-2 font-semibold">Выше рынка</th><th className="pb-2 font-semibold">Решение</th><th /></tr></thead>
              <tbody className="divide-y divide-slate-100">
                {hist.sessions.map((s: any) => {
                  const d = DECISION_RU[s.decision] ?? [s.status === 'abandoned' ? 'прерван' : s.status === 'in_progress' ? 'в процессе' : '—', 'gray']
                  return (
                    <tr key={s.token}>
                      <td className="py-2.5">{dateTime(s.started_at)}</td>
                      <td>{resumes.length > 1 && titles[s.resume_id] ? <><span className="text-slate-400">{titles[s.resume_id]} · </span>{s.specialization_name}</> : s.specialization_name}</td>
                      <td>{s.target_grade_name}</td>
                      <td>{s.n_items ? `${s.n_correct}/${s.n_items}` : '—'}</td><td>{s.percentile != null ? `${Math.round(s.percentile)}%` : '—'}</td>
                      <td className="space-x-1">{s.mode === 'express'
                        ? <Badge tone="blue" icon={<Zap className="h-3 w-3" />}>экспресс{s.estimated_grade ? ` · ≈ ${gradeName(s.estimated_grade)}` : ''}</Badge>
                        : <Badge tone={d[1]}>{d[0]}</Badge>}
                        {s.violation && <Badge tone="red" icon={<ShieldAlert className="h-3 w-3" />}>нарушение</Badge>}</td>
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
                <span>{g.specialization_name}: {g.old_grade ? `${gradeName(g.old_grade)} → ` : ''}<b className="text-fsp-deep">{g.new_grade_name}</b></span>
                <span className="text-xs text-slate-500">{date(g.created_at)}</span>
              </li>))}
            </ul>
          )}
        </Card>
        <Card title="История опросов">
          {!surveys?.length ? <p className="muted">Опрос не пройден.</p> : (
            <ul className="space-y-2">{surveys.map(s => (
              <li key={s.id} className="rounded-xl bg-surface px-3 py-2 text-sm">
                <div className="flex justify-between gap-3"><span><b className="text-fsp-deep">{s.specialization_name}</b> · заявлен {gradeName(s.claimed_grade)}</span><span className="text-xs text-slate-500">{date(s.created_at)}</span></div>
                {s.warnings?.map((w: string, i: number) => <p key={i} className="mt-1 text-xs text-amber-700">{w}</p>)}
              </li>))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  )
}
