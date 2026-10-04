import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { ArrowRight, Check, Download, Eye, EyeOff, ListChecks, Mail, Send, Trophy } from 'lucide-react'
import { api, download } from '@/lib/api'
import { salaryRange, ago } from '@/lib/format'
import { useToast } from '@/lib/toast'
import { Badge, Button, ButtonLink, Card, EmptyState, PageHeader, PageLoader, Progress, Stat } from '@/components/ui'
import { CategoryPill, StatusBadge } from '@/components/Domain'

export function CandidateDashboard() {
  const { push } = useToast()
  const { data, isLoading } = useQuery({ queryKey: ['cand-dashboard'], queryFn: () => api('/candidate/dashboard') })
  const { data: invs } = useQuery({ queryKey: ['cand-invitations'], queryFn: () => api<any[]>('/candidate/invitations') })
  const { data: tasks } = useQuery({ queryKey: ['cand-tasks'], queryFn: () => api<any[]>('/candidate/tasks') })
  if (isLoading || !data) return <PageLoader />
  const p = data.profile
  const cat = p.category
  const steps: any[] = data.steps
  const required = steps.filter(s => s.required)
  const doneCount = required.filter(s => s.done).length
  const next = required.find(s => !s.done)
  const openTask = tasks?.find(t => t.status === 'offered')
  const firstName = (p.full_name ?? '').split(' ')[1] ?? p.full_name ?? ''

  return (
    <div className="space-y-6">
      <PageHeader title={firstName ? `Здравствуйте, ${firstName}!` : 'Добро пожаловать!'}
        subtitle={cat.grade ? 'Ваша категория видна работодателям — предложения приходят без откликов вслепую.' :
          'Пройдите опрос и тест — после присвоения категории работодатели смогут найти вас сами.'}
        actions={<Button variant="secondary" icon={<Download className="h-4 w-4" />}
          onClick={() => download('/candidate/profile/pdf', `profile-${p.public_id}.pdf`).catch(e => push(e.message, 'error'))}>PDF-профиль</Button>} />

      <div className="grid gap-6 lg:grid-cols-[1.35fr_1fr]">
        {cat.grade ? (
          <div className="bg-brand-gradient relative overflow-hidden rounded-3xl p-6 text-white shadow-pop sm:p-8">
            <img src="/brand/fsp-star-white.png" alt="" className="pointer-events-none absolute -right-10 -top-10 h-56 w-56 opacity-[0.07]" />
            <p className="text-xs font-semibold uppercase tracking-wider text-white/60">Ваша категория</p>
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <CategoryPill spec={cat.specialization_name} grade={cat.grade_name} className="bg-white/15 text-sm" />
              <Badge tone="pink">выше {Math.round(cat.percentile)}% кандидатов</Badge>
            </div>
            <div className="mt-6 grid gap-4 sm:grid-cols-3">
              {[['Тест', p.strength.test], ['ФСП', p.strength.fsp], ['Активность', p.strength.activity]].map(([l, v]) => (
                <div key={l as string}>
                  <div className="flex justify-between text-xs text-white/70"><span>{l}</span><b className="text-white">{Math.round((v as number) * 100)}%</b></div>
                  <div className="mt-1.5 h-1.5 rounded-full bg-white/15"><div className="h-full rounded-full bg-fsp-pink" style={{ width: `${Math.max(3, (v as number) * 100)}%` }} /></div>
                </div>
              ))}
            </div>
            <p className="mt-4 text-xs leading-relaxed text-white/60">Сила профиля = 60% положение в грейде по тесту + 25% достижения ФСП + 15% регулярные задания. Внутри категории выше те, у кого она больше.</p>
            <div className="mt-6 flex flex-wrap items-center gap-3">
              <span className={clsx('inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold', data.visible_to_employers ? 'bg-emerald-400/20 text-emerald-200' : 'bg-amber-400/20 text-amber-200')}>
                {data.visible_to_employers ? <Eye className="h-3.5 w-3.5" /> : <EyeOff className="h-3.5 w-3.5" />}
                {data.visible_to_employers ? 'Профиль виден работодателям' : 'Профиль скрыт от работодателей'}
              </span>
              <Link to="/candidate/grade" className="inline-flex items-center gap-1 text-sm font-semibold text-white hover:underline">Подробнее о грейде <ArrowRight className="h-4 w-4" /></Link>
            </div>
          </div>
        ) : (
          <Card title="Путь к категории" subtitle={`${doneCount} из ${required.length} обязательных шагов`}>
            <Progress value={doneCount / required.length} className="mb-5" />
            <ol className="space-y-2">
              {steps.map(s => (
                <li key={s.key}>
                  <Link to={s.link} className={clsx('flex items-center gap-3 rounded-2xl px-3 py-2.5 transition hover:bg-surface', next?.key === s.key && 'bg-fsp-blush/40 ring-1 ring-fsp-pink/30')}>
                    <span className={clsx('grid h-7 w-7 shrink-0 place-items-center rounded-full text-xs font-bold', s.done ? 'bg-emerald-500 text-white' : 'bg-slate-100 text-slate-500')}>
                      {s.done ? <Check className="h-4 w-4" /> : steps.indexOf(s) + 1}
                    </span>
                    <span className={clsx('flex-1 text-sm', s.done ? 'text-slate-400 line-through' : 'font-medium text-fsp-deep')}>{s.title}</span>
                    {!s.required && <Badge>по желанию</Badge>}
                    {next?.key === s.key && <ArrowRight className="h-4 w-4 text-fsp-pink" />}
                  </Link>
                </li>
              ))}
            </ol>
            {next && <ButtonLink to={next.link} className="mt-5 w-full" icon={<ArrowRight className="h-4 w-4" />}>Продолжить: {next.title.toLowerCase()}</ButtonLink>}
          </Card>
        )}

        <div className="grid grid-cols-2 gap-4">
          <Stat label="Новые приглашения" value={data.stats.invitations_new} icon={<Mail className="h-5 w-5" />} hint={`всего ${data.stats.invitations_total}`} />
          <Stat label="Просмотры профиля" value={data.stats.profile_views_30d} icon={<Eye className="h-5 w-5" />} hint="за 30 дней" />
          <Stat label="Мои отклики" value={data.stats.applications} icon={<Send className="h-5 w-5" />} />
          <Stat label="Задания" value={data.stats.tasks_open} icon={<ListChecks className="h-5 w-5" />} hint="ждут решения" />
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Последние приглашения" actions={<Link to="/candidate/invitations" className="link text-sm">Все</Link>}>
          {!invs?.length ? <EmptyState icon={<Mail className="h-5 w-5" />} title="Пока нет приглашений" text={cat.grade ? 'Работодатели увидят вас в подборках своей категории.' : 'Приглашения начнут приходить после присвоения категории.'} /> : (
            <div className="divide-y divide-slate-100">
              {invs.slice(0, 4).map(i => (
                <Link to="/candidate/invitations" key={i.id} className="flex items-center gap-4 py-3 hover:opacity-80">
                  <div className="grid h-10 w-10 shrink-0 place-items-center rounded-2xl bg-surface font-bold text-fsp-deep">{i.company.name[0]}</div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-fsp-deep">{i.title}</p>
                    <p className="truncate text-xs text-slate-500">{i.company.name} · {ago(i.created_at)}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-bold text-fsp-deep">{salaryRange(i.salary_from, i.salary_to)}</p>
                    <StatusBadge status={i.status} />
                  </div>
                </Link>
              ))}
            </div>
          )}
        </Card>
        <div className="space-y-6">
          {openTask && (
            <Card title="Задание недели" subtitle={`от ${openTask.task.company} · ~${openTask.task.time_estimate_min} мин`}
                  actions={<Badge tone="amber">{openTask.task.kind === 'solve' ? 'решить' : 'предложить подход'}</Badge>}>
              <p className="font-semibold text-fsp-deep">{openTask.task.title}</p>
              <p className="mt-1 line-clamp-3 text-sm text-slate-600">{openTask.task.description}</p>
              <ButtonLink to="/candidate/tasks" size="sm" className="mt-4" icon={<ArrowRight className="h-4 w-4" />}>Решить</ButtonLink>
            </Card>
          )}
          <Card title="Достижения ФСП" actions={<Link to="/candidate/settings" className="link text-sm">{p.fsp_id ? 'Управление' : 'Привязать ФСП ID'}</Link>}>
            {p.fsp?.achievements?.length ? (
              <div className="flex items-start gap-4">
                <div className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-fsp-blush text-fsp-pink"><Trophy className="h-6 w-6" /></div>
                <div>
                  <p className="font-semibold text-fsp-deep">{p.fsp.headline}</p>
                  <p className="text-sm text-slate-500">{p.fsp.achievements.length} результатов в реестре · вклад в силу профиля {Math.round(p.fsp.score * 100)}%</p>
                </div>
              </div>
            ) : <p className="muted">{p.fsp_id ? 'ФСП ID привязан, результатов в реестре пока нет.' : 'Привяжите ФСП ID — результаты соревнований подтянутся автоматически и усилят профиль. Без ФСП вы участвуете в подборе на общих основаниях.'}</p>}
          </Card>
        </div>
      </div>
    </div>
  )
}
