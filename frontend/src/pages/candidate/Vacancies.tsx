import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Briefcase, CircleCheck, MapPin, Search, Send, Wallet } from 'lucide-react'
import { api, qs } from '@/lib/api'
import { useReference } from '@/lib/reference'
import { useToast } from '@/lib/toast'
import { ago, salaryRange } from '@/lib/format'
import { Alert, Badge, Button, Card, EmptyState, Field, Input, Modal, PageHeader, PageLoader, Select, Textarea } from '@/components/ui'
import { Components, MatchRing, Reasons } from '@/components/Domain'
import { Markdown } from '@/components/Content'
import { useResumes } from '@/components/Resumes'

export function VacancyList() {
  const { ref, skillName } = useReference()
  const [f, setF] = useState({ q: '', specialization: '', grade: '', work_format: '' })
  const { data, isLoading } = useQuery({ queryKey: ['vacancies', f], queryFn: () => api<any[]>(`/vacancies${qs(f)}`) })
  const { data: resumes } = useResumes()
  const multi = (resumes?.filter(r => r.category.grade).length ?? 0) > 1
  return (
    <div>
      <PageHeader title="Вакансии" subtitle="Классический сценарий: если подходящих приглашений пока нет, проявите инициативу сами. Вакансии отсортированы по совпадению с вашим профилем." />
      <div className="card mb-5 grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="relative"><Search className="absolute left-3 top-3 h-4 w-4 text-slate-400" /><Input className="pl-9" placeholder="Поиск по названию, компании" value={f.q} onChange={e => setF({ ...f, q: e.target.value })} /></div>
        <Select value={f.specialization} onChange={e => setF({ ...f, specialization: e.target.value })}>
          <option value="">Все специализации</option>{ref?.specializations.map(s => <option key={s.code} value={s.code}>{s.name}</option>)}</Select>
        <Select value={f.grade} onChange={e => setF({ ...f, grade: e.target.value })}>
          <option value="">Любой грейд</option>{ref?.grades.map(g => <option key={g.code} value={g.code}>{g.name}</option>)}</Select>
        <Select value={f.work_format} onChange={e => setF({ ...f, work_format: e.target.value })}>
          <option value="">Любой формат</option>{Object.entries(ref?.work_formats ?? {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Select>
      </div>
      {isLoading ? <PageLoader /> : !data?.length ? <EmptyState icon={<Briefcase className="h-5 w-5" />} title="Вакансий не найдено" text="Попробуйте изменить фильтры." /> : (
        <div className="grid gap-4 lg:grid-cols-2">
          {data.map(v => (
            <Link key={v.id} to={`/candidate/vacancies/${v.id}`} className="card card-pad flex gap-4 transition hover:ring-fsp-lavender">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone="lavender">{v.specialization_name}</Badge>
                  {v.grade_names.map((g: string) => <Badge key={g}>{g}</Badge>)}
                  {v.applied && <Badge tone="green" icon={<CircleCheck className="h-3 w-3" />}>вы откликнулись</Badge>}
                </div>
                <p className="mt-2 text-lg font-bold text-fsp-deep">{v.title}</p>
                <p className="text-sm text-slate-500">{v.company.name} · {ago(v.created_at)}</p>
                {multi && v.match_resume && <p className="mt-1 text-xs font-medium text-fsp-lavender">лучше подходит резюме «{v.match_resume.title}»</p>}
                <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm">
                  <span className="inline-flex items-center gap-1.5 font-bold text-fsp-deep"><Wallet className="h-4 w-4 text-fsp-pink" />{salaryRange(v.salary_from, v.salary_to)}</span>
                  <span className="inline-flex items-center gap-1.5 text-slate-600"><MapPin className="h-4 w-4 text-slate-400" />{v.work_format_name}{v.city && `, ${v.city}`}</span>
                </div>
                <div className="mt-3 flex flex-wrap gap-1.5">{v.must_skills.slice(0, 6).map((s: string) => <Badge key={s} tone="pink">{skillName(s)}</Badge>)}</div>
              </div>
              {v.match != null && <MatchRing value={v.match} />}
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

export function VacancyDetail() {
  const { id } = useParams()
  const qc = useQueryClient()
  const { push } = useToast()
  const { skillName } = useReference()
  const [open, setOpen] = useState(false)
  const [letter, setLetter] = useState('')
  const [resumeId, setResumeId] = useState<string>('')
  const { data: v, isLoading } = useQuery({ queryKey: ['vacancy', id], queryFn: () => api(`/vacancies/${id}`) })
  const apply = useMutation({
    mutationFn: () => api(`/vacancies/${id}/apply`, { body: { cover_letter: letter || null, resume_id: resumeId === '' ? null : Number(resumeId) } }),
    onSuccess: () => { setOpen(false); qc.invalidateQueries({ queryKey: ['vacancy', id] }); qc.invalidateQueries({ queryKey: ['vacancies'] }); push('Отклик отправлен. Работодатель увидит ваш профиль и контакты.') },
    onError: (e: any) => push(e.message, 'error'),
  })
  if (isLoading || !v) return <PageLoader />
  return (
    <div>
      <Link to="/candidate/vacancies" className="mb-4 inline-flex items-center gap-1.5 text-sm font-semibold text-slate-500 hover:text-fsp-pink"><ArrowLeft className="h-4 w-4" /> Все вакансии</Link>
      <div className="grid gap-6 lg:grid-cols-[1.5fr_1fr]">
        <Card>
          <div className="flex flex-wrap gap-2"><Badge tone="lavender">{v.specialization_name}</Badge>{v.grade_names.map((g: string) => <Badge key={g}>{g}</Badge>)}</div>
          <h1 className="mt-3 text-2xl font-bold">{v.title}</h1>
          <p className="text-slate-500">{v.company.name}{v.company.industry && ` · ${v.company.industry}`}</p>
          <div className="mt-4 flex flex-wrap gap-3">
            <span className="rounded-xl bg-fsp-blush/50 px-3 py-2 text-base font-extrabold text-fsp-deep">{salaryRange(v.salary_from, v.salary_to)} <span className="text-xs font-semibold text-slate-500">в месяц, до вычета НДФЛ</span></span>
            <span className="rounded-xl bg-surface px-3 py-2 text-sm text-slate-600">{v.work_format_name}{v.city && `, ${v.city}`}</span>
          </div>
          <div className="mt-6"><Markdown>{v.description}</Markdown></div>
          {v.team_description && <p className="mt-4 text-sm text-slate-600"><b className="text-fsp-deep">Команда:</b> {v.team_description}</p>}
          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            <div><p className="label">Обязательно</p><div className="flex flex-wrap gap-1.5">{v.must_skills.map((s: string) => <Badge key={s} tone="pink">{skillName(s)}</Badge>)}</div></div>
            {!!v.nice_skills.length && <div><p className="label">Будет плюсом</p><div className="flex flex-wrap gap-1.5">{v.nice_skills.map((s: string) => <Badge key={s} tone="lavender">{skillName(s)}</Badge>)}</div></div>}
          </div>
        </Card>
        <div className="space-y-6 lg:sticky lg:top-24 lg:self-start">
          <Card title="Ваше совпадение">
            {v.match ? (<>
              <div className="flex items-center gap-4"><MatchRing value={v.match.match} size={76} /><div className="flex-1"><Components components={v.match.components} /></div></div>
              {v.resumes?.length > 1 && <p className="mt-3 text-xs text-slate-500">Посчитано по лучшему для вакансии резюме: <b className="text-fsp-deep">{v.match.resume_title}</b></p>}
              <div className="mt-4"><Reasons reasons={v.match.reasons} /></div>
            </>) : <Alert tone="info">Совпадение рассчитывается после присвоения категории по тесту. Откликнуться можно и без неё.</Alert>}
          </Card>
          {v.applied ? <Alert tone="success" icon={<CircleCheck className="h-4 w-4" />} title="Вы уже откликнулись">Статус — в разделе «Мои отклики».</Alert> :
            <Button size="lg" className="w-full" onClick={() => { setResumeId(v.match ? String(v.match.resume_id) : ''); setOpen(true) }} icon={<Send className="h-5 w-5" />}>Откликнуться</Button>}
        </div>
      </div>
      <Modal open={open} onClose={() => setOpen(false)} title="Отклик на вакансию"
        footer={<><Button variant="secondary" onClick={() => setOpen(false)}>Отмена</Button><Button loading={apply.isPending} onClick={() => apply.mutate()}>Отправить</Button></>}>
        <Alert tone="info">При отклике работодатель увидит ваш профиль и контакты — так же, как после принятия приглашения.</Alert>
        {v.resumes?.length > 1 && (
          <Field label="Каким резюме откликнуться" className="mt-4" hint="Работодатель увидит категорию и навыки выбранного резюме">
            <Select value={resumeId} onChange={e => setResumeId(e.target.value)}>
              {v.resumes.map((r: any) => <option key={r.resume_id} value={r.resume_id}>{r.title} — {r.specialization_name} · {r.grade_name}{v.match?.resume_id === r.resume_id ? ' (лучшее совпадение)' : ''}</option>)}
            </Select>
          </Field>
        )}
        <Field label="Сопроводительное письмо (необязательно)" className="mt-4"><Textarea rows={5} value={letter} onChange={e => setLetter(e.target.value)} /></Field>
      </Modal>
    </div>
  )
}
