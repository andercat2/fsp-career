import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Download, Lock, Mail, Phone, Send, Star, Unlock } from 'lucide-react'
import { api, download } from '@/lib/api'
import { useReference } from '@/lib/reference'
import { useToast } from '@/lib/toast'
import { ago, date, rub, WORK_FORMATS, years } from '@/lib/format'
import { Alert, Badge, Button, Card, KV, PageLoader } from '@/components/ui'
import { CategoryPill, DomainBars, FspAchievements, StatusBadge } from '@/components/Domain'
import { InviteModal, type InviteTarget } from '@/components/InviteModal'
import { useShortlistToggle } from './Selection'

export function CandidateView() {
  const { id } = useParams()
  const nav = useNavigate()
  const { push } = useToast()
  const { ref } = useReference()
  const [invite, setInvite] = useState<InviteTarget | null>(null)
  const { data: c, isLoading } = useQuery({ queryKey: ['emp-candidate', id], queryFn: () => api(`/employer/candidates/${id}`) })
  const shortlist = useShortlistToggle()
  if (isLoading || !c) return <PageLoader />
  const cat = c.category
  const active = c.invitations?.find((i: any) => ['sent', 'viewed'].includes(i.status))
  return (
    <div>
      <button onClick={() => nav(-1)} className="mb-4 inline-flex items-center gap-1.5 text-sm font-semibold text-slate-500 hover:text-fsp-pink"><ArrowLeft className="h-4 w-4" /> Назад</button>
      <div className="bg-brand-gradient relative mb-6 overflow-hidden rounded-3xl p-6 text-white sm:p-8">
        <img src="/brand/fsp-star-white.png" alt="" className="pointer-events-none absolute -right-8 -top-8 h-48 w-48 opacity-[0.07]" />
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <CategoryPill spec={cat.specialization_name} grade={cat.grade_name} className="bg-white/15" />
              {cat.percentile != null && <Badge tone="pink">выше {Math.round(cat.percentile)}% кандидатов</Badge>}
              {c.name_hidden && <Badge tone="lavender" icon={<Lock className="h-3 w-3" />}>имя скрыто до согласия</Badge>}
            </div>
            <h1 className="mt-3 text-3xl font-extrabold text-white">{c.display_name}</h1>
            <p className="mt-1 text-white/75">{c.headline}{c.city && ` · ${c.city}`}{c.relocation && ' · готов к переезду'}</p>
            <p className="mt-1 text-sm text-white/60">Был(а) активен {ago(c.last_active_at)} · {c.open_to_offers ? 'открыт к предложениям' : 'сейчас не ищет работу'}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => shortlist.mutate({ id: c.id, on: !c.shortlisted })} icon={<Star className={c.shortlisted ? 'h-4 w-4 fill-amber-400 text-amber-400' : 'h-4 w-4'} />}>{c.shortlisted ? 'В избранном' : 'В избранное'}</Button>
            <Button variant="secondary" onClick={() => download(`/employer/candidates/${c.id}/pdf`, `candidate-${c.public_id}.pdf`).catch(e => push(e.message, 'error'))} icon={<Download className="h-4 w-4" />}>PDF</Button>
            <Button disabled={!c.open_to_offers || !!active || c.contacts_unlocked} icon={<Send className="h-4 w-4" />}
              onClick={() => setInvite({ id: c.id, display_name: c.display_name, grade_name: cat.grade_name, specialization_name: cat.specialization_name })}>
              {c.contacts_unlocked ? 'Контакт открыт' : active ? 'Приглашение отправлено' : 'Пригласить'}</Button>
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.25fr_1fr]">
        <div className="space-y-6">
          <Card title="Результаты тестирования" subtitle="Оценки по доменам из адаптивного теста — источник категории">
            <DomainBars domains={Object.fromEntries(Object.entries(c.test.domains).map(([k, v]: any) => [k, { ...v, name: ref?.domains[k] }]))} />
            <div className="mt-4 grid gap-2 rounded-2xl bg-surface p-4 text-sm sm:grid-cols-3">
              <p>Сила профиля: <b className="text-fsp-deep">{Math.round(c.strength.total * 100)}%</b></p>
              <p>θ = <b className="text-fsp-deep">{cat.theta?.toFixed(2)}</b> ± {cat.se?.toFixed(2)}</p>
              <p>Категория с {date(cat.assigned_at)}</p>
            </div>
          </Card>
          <Card title="Навыки">
            <p className="label">Подтверждены тестом</p>
            <div className="flex flex-wrap gap-1.5">{c.verified_skills.length ? c.skills_detail.filter((s: any) => c.verified_skills.includes(s.id)).concat(
              c.verified_skills.filter((v: string) => !c.skills.includes(v)).map((v: string) => ({ id: v, name: ref?.skills.find(s => s.id === v)?.name ?? v })))
              .map((s: any) => <Badge key={s.id} tone="pink">✓ {s.name}</Badge>) : <span className="muted">—</span>}</div>
            <p className="label mt-4">Заявлены в резюме</p>
            <div className="flex flex-wrap gap-1.5">{c.skills_detail.filter((s: any) => !c.verified_skills.includes(s.id)).map((s: any) => <Badge key={s.id}>{s.name}</Badge>)}</div>
            {!!c.roles.length && <><p className="label mt-4">Роли в команде</p><div className="flex flex-wrap gap-1.5">{c.roles.map((r: string) => <Badge key={r} tone="lavender">{ref?.team_roles[r] ?? r}</Badge>)}</div></>}
          </Card>
          <Card title="Опыт">
            {c.about && <p className="mb-4 whitespace-pre-line text-sm leading-relaxed text-slate-700">{c.about}</p>}
            <div className="space-y-3">
              {c.experience.map((e: any, i: number) => (
                <div key={i} className="rounded-2xl bg-surface p-4">
                  <p className="font-semibold text-fsp-deep">{e.position || 'Должность'} · {e.company ?? <span className="text-slate-400">компания скрыта</span>}</p>
                  <p className="text-xs text-slate-500">{e.start} — {e.end ?? 'н. в.'}</p>
                  {e.description && <p className="mt-1.5 text-sm text-slate-600">{e.description}</p>}
                </div>
              ))}
              {!c.experience.length && <p className="muted">Не указан</p>}
            </div>
            {!!c.education.length && <div className="mt-4"><p className="label">Образование</p>{c.education.map((e: any, i: number) => <p key={i} className="text-sm">{e.title}</p>)}</div>}
          </Card>
        </div>
        <div className="space-y-6">
          <Card title="Контакты">
            {c.contacts_unlocked ? (
              <div className="space-y-2 text-sm">
                <Alert tone="success" icon={<Unlock className="h-4 w-4" />}>{c.unlock_reason === 'applied' ? 'Кандидат откликнулся на вашу вакансию' : 'Кандидат принял ваше приглашение'}</Alert>
                {c.contacts.email && <p className="flex items-center gap-2"><Mail className="h-4 w-4 text-fsp-pink" />{c.contacts.email}</p>}
                {c.contacts.phone && <p className="flex items-center gap-2"><Phone className="h-4 w-4 text-fsp-pink" />{c.contacts.phone}</p>}
                {c.contacts.telegram && <p className="flex items-center gap-2"><Send className="h-4 w-4 text-fsp-pink" />{c.contacts.telegram}</p>}
              </div>
            ) : <Alert tone="info" icon={<Lock className="h-4 w-4" />} title="Контакты скрыты">Откроются, когда кандидат примет приглашение или откликнется на вашу вакансию.</Alert>}
          </Card>
          <Card title="Условия">
            <div className="divide-y divide-slate-100">
              <KV k="Ожидания" v={c.salary_hidden ? 'скрыты кандидатом' : c.desired_salary ? `от ${rub(c.desired_salary)}` : '—'} />
              <KV k="Формат" v={c.work_formats.map((f: string) => WORK_FORMATS[f]).join(', ') || '—'} />
              <KV k="Опыт" v={years(c.experience_years)} />
              <KV k="Заданий работодателей решено" v={c.tasks_done} />
            </div>
          </Card>
          <Card title="Достижения ФСП"><FspAchievements fsp={c.fsp} /></Card>
          {!!c.invitations?.length && (
            <Card title="Ваши приглашения">
              <div className="space-y-2">{c.invitations.map((i: any) => (
                <div key={i.id} className="flex items-center justify-between gap-2 text-sm"><span className="truncate">{i.title}</span><StatusBadge status={i.status} /></div>))}</div>
            </Card>
          )}
        </div>
      </div>
      <InviteModal target={invite} onClose={() => setInvite(null)} />
    </div>
  )
}
