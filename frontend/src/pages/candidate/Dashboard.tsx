import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import clsx from 'clsx'
import { ArrowRight, ArrowUpRight, Check, Download, Eye, EyeOff, ListChecks, Mail, Send, Trophy } from 'lucide-react'
import { api, download } from '@/lib/api'
import { salaryRange, ago } from '@/lib/format'
import { useToast } from '@/lib/toast'
import { CountUp, EASE, Item, Stagger } from '@/lib/motion'
import { Badge, Button, ButtonLink, Card, EmptyState, PageHeader, PageLoader, Progress, Stat } from '@/components/ui'
import { CategoryPill, StatusBadge } from '@/components/Domain'

function MiniRing({ value, label }: { value: number; label: ReactNode }) {
  const r = 20
  const c = 2 * Math.PI * r
  return (
    <div className="flex items-center gap-3">
      <div className="relative h-12 w-12">
        <svg width="48" height="48" className="-rotate-90">
          <circle cx="24" cy="24" r={r} stroke="rgba(255,255,255,.14)" strokeWidth="5" fill="none" />
          <motion.circle cx="24" cy="24" r={r} stroke="#FF5C95" strokeWidth="5" fill="none" strokeLinecap="round" strokeDasharray={c}
            initial={{ strokeDashoffset: c }} animate={{ strokeDashoffset: c * (1 - value) }} transition={{ duration: 1.2, ease: EASE, delay: 0.3 }} />
        </svg>
        <span className="absolute inset-0 grid place-items-center text-[11px] font-bold text-white"><CountUp value={Math.round(value * 100)} /></span>
      </div>
      <span className="text-xs leading-tight text-white/70">{label}</span>
    </div>
  )
}

export function CandidateDashboard() {
  const { push } = useToast()
  const { data, isLoading } = useQuery({ queryKey: ['cand-dashboard'], queryFn: () => api('/candidate/dashboard') })
  const { data: invs } = useQuery({ queryKey: ['cand-invitations'], queryFn: () => api<any[]>('/candidate/invitations') })
  const { data: tasks } = useQuery({ queryKey: ['cand-tasks'], queryFn: () => api<any[]>('/candidate/tasks') })
  if (isLoading || !data) return <PageLoader />
  const p = data.profile
  // главная категория — основного резюме; если она не присвоена, — первая подтверждённая из дополнительных
  const graded: any[] = (p.resumes ?? []).filter((r: any) => r.category.grade)
  const shownId = p.category.grade ? 0 : graded[0]?.id
  const cat = p.category.grade ? p.category : graded[0]?.category ?? p.category
  const others = graded.filter((r: any) => r.id !== shownId)
  const steps: any[] = data.steps
  const required = steps.filter(s => s.required)
  const doneCount = required.filter(s => s.done).length
  const next = required.find(s => !s.done)
  const openTask = tasks?.find(t => t.status === 'offered')
  const firstName = (p.full_name ?? '').split(' ')[1] ?? p.full_name ?? ''

  return (
    <div className="space-y-6">
      <PageHeader title={firstName ? `Здравствуйте, ${firstName}` : 'Добро пожаловать'}
        subtitle={cat.grade ? 'Ваша категория видна работодателям — предложения приходят без откликов вслепую.' :
          'Пройдите опрос и тест — после присвоения категории работодатели смогут найти вас сами.'}
        actions={<Button variant="secondary" icon={<Download className="h-4 w-4" />}
          onClick={() => download('/candidate/profile/pdf', `profile-${p.public_id}.pdf`).catch(e => push(e.message, 'error'))}>Загрузить PDF-профиль</Button>} />

      <div className="grid gap-6 lg:grid-cols-[1.35fr_1fr]">
        {cat.grade ? (
          <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.55, ease: EASE }}
            className="bg-brand-gradient noise relative overflow-hidden rounded-[28px] p-7 text-white shadow-lift sm:p-8">
            <div className="pointer-events-none absolute -right-16 -top-20 h-64 w-64 animate-blob rounded-full bg-fsp-pink/35 blur-3xl" />
            <img src="/brand/fsp-star-white.png" alt="" className="pointer-events-none absolute -bottom-10 -right-6 h-48 w-48 animate-spin-slow opacity-[0.06]" />
            <div className="relative">
              <p className="text-xs font-semibold text-white/55">Ваша категория</p>
              <div className="mt-3 flex flex-wrap items-center gap-2.5">
                <CategoryPill spec={cat.specialization_name} grade={cat.grade_name} className="bg-white/15 px-3.5 py-1.5 text-sm" />
                <span className="rounded-full bg-fsp-pink/25 px-3 py-1 text-xs font-semibold text-[#ffc2d6]">выше <CountUp value={Math.round(cat.percentile)} />% кандидатов</span>
              </div>
              {!!others.length && (
                <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-white/60">
                  <span>Ещё {others.length === 1 ? 'категория' : 'категории'}:</span>
                  {others.map((r: any) => (
                    <Link key={r.id} to={`/candidate/grade?resume=${r.id}`} className="rounded-full bg-white/10 px-2.5 py-1 font-semibold text-white/90 transition hover:bg-white/20">
                      {r.category.specialization_name} · {r.category.grade_name}</Link>
                  ))}
                </div>
              )}
              <div className="mt-7 flex flex-wrap gap-x-8 gap-y-4">
                <MiniRing value={p.strength.test} label={<>Тест<br />60% силы</>} />
                <MiniRing value={p.strength.fsp} label={<>ФСП<br />25% силы</>} />
                <MiniRing value={p.strength.activity} label={<>Задания<br />15% силы</>} />
              </div>
              <div className="mt-7 flex flex-wrap items-center gap-3">
                <span className={clsx('inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold', data.visible_to_employers ? 'bg-emerald-400/15 text-emerald-200' : 'bg-amber-400/15 text-amber-200')}>
                  {data.visible_to_employers ? <Eye className="h-3.5 w-3.5" /> : <EyeOff className="h-3.5 w-3.5" />}
                  {data.visible_to_employers ? 'Видна работодателям' : 'Скрыта от работодателей'}
                </span>
                <Link to="/candidate/grade" className="group inline-flex items-center gap-1 text-sm font-semibold text-white/90 hover:text-white">
                  Подробнее о грейде <ArrowUpRight className="h-4 w-4 transition group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
                </Link>
              </div>
            </div>
          </motion.div>
        ) : (
          <Card title="Путь к категории" subtitle={`${doneCount} из ${required.length} обязательных шагов`}>
            {data.visible_as_unconfirmed && (
              <p className="mb-4 rounded-2xl bg-amber-50 px-4 py-3 text-sm text-amber-900">
                Тест пока не подтвердил заявленный грейд. Работодатели видят вас со статусом «не подтверждён» — ниже кандидатов
                с подтверждённым грейдом. <Link to="/candidate/grade" className="link">Подробнее</Link>
              </p>
            )}
            <Progress value={doneCount / required.length} className="mb-5" />
            <Stagger as="ol" className="space-y-1.5" gap={0.06}>
              {steps.map((s, i) => (
                <Item as="li" key={s.key}>
                  <Link to={s.link} className={clsx('group flex items-center gap-3 rounded-2xl px-3 py-3 transition',
                    next?.key === s.key ? 'bg-[#FFF5F8] ring-1 ring-fsp-pink/20' : 'hover:bg-surface')}>
                    <span className={clsx('grid h-8 w-8 shrink-0 place-items-center rounded-full text-xs font-bold transition',
                      s.done ? 'bg-emerald-500 text-white' : next?.key === s.key ? 'bg-fsp-pink text-white shadow-glow' : 'bg-slate-100 text-slate-500')}>
                      {s.done ? <Check className="h-4 w-4" strokeWidth={3} /> : i + 1}
                    </span>
                    <span className={clsx('flex-1 text-sm', s.done ? 'text-slate-400 line-through decoration-slate-300' : 'font-medium text-fsp-deep')}>{s.title}</span>
                    {!s.required && <Badge>по желанию</Badge>}
                    {next?.key === s.key && <ArrowRight className="h-4 w-4 text-fsp-pink transition group-hover:translate-x-1" />}
                  </Link>
                </Item>
              ))}
            </Stagger>
            {next && <ButtonLink to={next.link} className="mt-5 w-full" icon={<ArrowRight className="h-4 w-4" />}>Продолжить: {next.title.toLowerCase()}</ButtonLink>}
          </Card>
        )}

        <div className="grid grid-cols-2 gap-4">
          <Stat label="Новые приглашения" value={data.stats.invitations_new} icon={<Mail className="h-5 w-5" />} hint={`всего ${data.stats.invitations_total}`} />
          <Stat label="Просмотры профиля" value={data.stats.profile_views_30d} icon={<Eye className="h-5 w-5" />} hint="за 30 дней · контакты скрыты" />
          <Stat label="Мои отклики" value={data.stats.applications} icon={<Send className="h-5 w-5" />} />
          <Stat label="Задания" value={data.stats.tasks_open} icon={<ListChecks className="h-5 w-5" />} hint="ждут решения" />
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Последние приглашения" actions={<Link to="/candidate/invitations" className="link text-sm">Все</Link>}>
          {!invs?.length ? <EmptyState icon={<Mail className="h-5 w-5" />} title="Пока нет приглашений" text={cat.grade ? 'Работодатели увидят вас в подборках своей категории.' : 'Приглашения начнут приходить после присвоения категории.'} /> : (
            <Stagger className="-mx-2 space-y-1" gap={0.06}>
              {invs.slice(0, 4).map(i => (
                <Item key={i.id}>
                  <Link to="/candidate/invitations" className="group flex items-center gap-4 rounded-2xl px-2 py-2.5 transition hover:bg-surface">
                    <div className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-[#F2F1FC] to-[#FFF0F5] text-base font-bold text-fsp-deep ring-1 ring-line">{i.company.name[0]}</div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold text-fsp-deep">{i.title}</p>
                      <p className="truncate text-xs text-slate-400">{i.company.name} · {ago(i.created_at)}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-bold tabular-nums text-fsp-deep">{salaryRange(i.salary_from, i.salary_to)}</p>
                      <div className="mt-1"><StatusBadge status={i.status} side="candidate" /></div>
                    </div>
                  </Link>
                </Item>
              ))}
            </Stagger>
          )}
        </Card>
        <div className="space-y-6">
          {openTask && (
            <Card title="Задание недели" subtitle={`от ${openTask.task.company} · ~${openTask.task.time_estimate_min} мин`} hover
                  actions={<Badge tone="amber">{openTask.task.kind === 'solve' ? 'решить' : 'предложить подход'}</Badge>}>
              <p className="font-semibold text-fsp-deep">{openTask.task.title}</p>
              <p className="mt-1.5 line-clamp-3 text-sm leading-relaxed text-slate-500">{openTask.task.description}</p>
              <ButtonLink to="/candidate/tasks" size="sm" className="mt-4" icon={<ArrowRight className="h-4 w-4" />}>Решить</ButtonLink>
            </Card>
          )}
          <Card title="Достижения ФСП" actions={<Link to="/candidate/settings" className="link text-sm">{p.fsp_id ? 'Управление' : 'Привязать ФСП ID'}</Link>}>
            {p.fsp?.achievements?.length ? (
              <div className="flex items-start gap-4">
                <div className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-fsp-pink to-[#ff5c95] text-white shadow-glow"><Trophy className="h-6 w-6" /></div>
                <div>
                  <p className="font-semibold text-fsp-deep">{p.fsp.headline}</p>
                  <p className="mt-0.5 text-sm text-slate-500">{p.fsp.achievements.length} результатов в реестре · вклад в силу профиля <CountUp value={Math.round(p.fsp.score * 100)} suffix="%" /></p>
                </div>
              </div>
            ) : <p className="muted leading-relaxed">{p.fsp_id ? 'ФСП ID привязан, результатов в реестре пока нет.' : 'Привяжите ФСП ID — результаты соревнований подтянутся автоматически и усилят профиль. Без ФСП вы участвуете в подборе на общих основаниях.'}</p>}
          </Card>
        </div>
      </div>
    </div>
  )
}
