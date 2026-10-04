import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { Eye, EyeOff, FileText, Plus, Save, Sparkles, Wand2 } from 'lucide-react'
import { api } from '@/lib/api'
import { useReference } from '@/lib/reference'
import { useToast } from '@/lib/toast'
import { ago, salaryRange } from '@/lib/format'
import { Alert, Badge, Button, ButtonLink, Card, EmptyState, Field, Input, PageHeader, PageLoader, Select, Textarea, Toggle } from '@/components/ui'
import { SkillPicker } from '@/components/SkillPicker'

export function Needs() {
  const { data, isLoading } = useQuery({ queryKey: ['emp-vacancies'], queryFn: () => api<any[]>('/employer/vacancies') })
  if (isLoading || !data) return <PageLoader />
  return (
    <div>
      <PageHeader title="Потребности и вакансии"
        subtitle="Потребность — описание того, кого вы ищете. Её можно держать приватной (только для подбора) или опубликовать как вакансию для самостоятельных откликов."
        actions={<ButtonLink to="/employer/needs/new" icon={<Plus className="h-4 w-4" />}>Новая потребность</ButtonLink>} />
      {!data.length ? <EmptyState icon={<FileText className="h-5 w-5" />} title="Потребностей пока нет" text="Вставьте текст вакансии — система сама определит специализацию, грейд и навыки."
        action={<ButtonLink to="/employer/needs/new" size="sm">Создать</ButtonLink>} /> : (
        <div className="grid gap-4 lg:grid-cols-2">
          {data.map(v => (
            <Link key={v.id} to={`/employer/needs/${v.id}`} className="card card-pad block transition hover:ring-fsp-lavender">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={v.is_published ? 'green' : 'gray'} icon={v.is_published ? <Eye className="h-3 w-3" /> : <EyeOff className="h-3 w-3" />}>{v.is_published ? 'опубликована' : 'приватная'}</Badge>
                {v.status === 'closed' && <Badge tone="red">закрыта</Badge>}
                <Badge tone="lavender">{v.specialization_name}</Badge>
                {v.grade_names.map((g: string) => <Badge key={g}>{g}</Badge>)}
              </div>
              <p className="mt-3 text-lg font-bold text-fsp-deep">{v.title}</p>
              <p className="text-sm text-slate-500">{salaryRange(v.salary_from, v.salary_to)} · {v.work_format_name}{v.city && `, ${v.city}`} · {ago(v.created_at)}</p>
              <div className="mt-3 flex flex-wrap gap-1.5">{v.must_skill_names.slice(0, 7).map((s: string) => <Badge key={s} tone="pink">{s}</Badge>)}</div>
              <div className="mt-4 flex gap-4 text-xs text-slate-500"><span><b className="text-fsp-deep">{v.applications_count}</b> откликов</span><span><b className="text-fsp-deep">{v.invitations_count}</b> приглашений</span></div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

type VForm = {
  title: string; description: string; team_description: string; specialization: string; grades: string[]; must_skills: string[]
  nice_skills: string[]; language: string; work_format: string; city: string; employment: string; salary_from: string; salary_to: string
  require_fsp: boolean; is_published: boolean
}
const EMPTY: VForm = { title: '', description: '', team_description: '', specialization: '', grades: [], must_skills: [], nice_skills: [], language: '',
  work_format: 'hybrid', city: '', employment: 'full', salary_from: '', salary_to: '', require_fsp: false, is_published: false }

export function NeedForm() {
  const { id } = useParams()
  const nav = useNavigate()
  const qc = useQueryClient()
  const { push } = useToast()
  const { ref, specName } = useReference()
  const [f, setF] = useState<VForm>(EMPTY)
  const [parsed, setParsed] = useState<any>(null)
  const { data: existing } = useQuery({ queryKey: ['emp-vacancy', id], queryFn: () => api(`/employer/vacancies/${id}`), enabled: !!id })
  useEffect(() => {
    if (existing) setF({ ...EMPTY, ...existing, team_description: existing.team_description ?? '', city: existing.city ?? '', language: existing.language ?? '',
      salary_from: String(existing.salary_from), salary_to: String(existing.salary_to) })
  }, [existing])
  const parse = useMutation({
    mutationFn: () => api('/employer/vacancies/parse', { body: { title: f.title, text: f.description } }),
    onSuccess: (r: any) => {
      setParsed(r)
      setF(s => ({ ...s, specialization: r.specialization, grades: r.grades, must_skills: r.must_skills, nice_skills: r.nice_skills,
        language: r.language ?? '', work_format: r.work_format ?? s.work_format, city: r.city ?? s.city,
        salary_from: r.salary_from ? String(r.salary_from) : s.salary_from, salary_to: r.salary_to ? String(r.salary_to) : s.salary_to,
        require_fsp: r.require_fsp }))
    },
    onError: (e: any) => push(e.message, 'error'),
  })
  const save = useMutation({
    mutationFn: async (andMatch: boolean) => {
      const body = { ...f, salary_from: Number(f.salary_from), salary_to: Number(f.salary_to), city: f.city || null, language: f.language || null, team_description: f.team_description || null }
      const v = id ? await api(`/employer/vacancies/${id}`, { method: 'PUT', body }) : await api('/employer/vacancies', { body })
      if (andMatch) { const s = await api('/employer/selections', { body: { vacancy_id: v.id } }); return { v, s } }
      return { v, s: null }
    },
    onSuccess: ({ v, s }: any) => {
      qc.invalidateQueries({ queryKey: ['emp-vacancies'] }); qc.invalidateQueries({ queryKey: ['emp-vacancy'] })
      push(id ? 'Изменения сохранены' : 'Потребность создана')
      nav(s ? `/employer/selections/${s.id}` : `/employer/needs/${v.id}`)
    },
    onError: (e: any) => push(e.message, 'error'),
  })
  if (!ref) return <PageLoader />
  const spec = ref.specializations.find(s => s.code === f.specialization)
  const valid = f.title.length >= 3 && !!f.specialization && f.grades.length > 0 && Number(f.salary_from) > 0 && Number(f.salary_to) >= Number(f.salary_from)
  const toggleGrade = (g: string) => setF(s => ({ ...s, grades: s.grades.includes(g) ? s.grades.filter(x => x !== g) : [...s.grades, g] }))

  return (
    <div className="pb-8">
      <PageHeader title={id ? 'Редактирование потребности' : 'Новая потребность'}
        subtitle="Опишите, кто нужен, своими словами или вставьте готовый текст вакансии — NLP-модуль разберёт его в структурированный запрос на подбор." />
      <div className="grid gap-6 xl:grid-cols-[1fr_1fr]">
        <Card title="1. Описание" subtitle="Чем занимается команда, какие задачи, требования и условия">
          <div className="space-y-4">
            <Field label="Название позиции" required><Input value={f.title} onChange={e => setF({ ...f, title: e.target.value })} placeholder="Middle Python-разработчик в платёжный сервис" /></Field>
            <Field label="Текст потребности / вакансии"><Textarea rows={12} value={f.description} onChange={e => setF({ ...f, description: e.target.value })}
              placeholder={'Например:\nИщем Python-разработчика уровня Middle в команду платежей.\nТребования: FastAPI, PostgreSQL, опыт от 3 лет.\nБудет плюсом: Kafka, Kubernetes.\nГибрид, Казань, от 230 000 до 320 000 ₽.'} /></Field>
            <Button variant="dark" onClick={() => parse.mutate()} loading={parse.isPending} disabled={f.description.length < 10} icon={<Wand2 className="h-4 w-4" />}>Распознать и заполнить</Button>
            {parsed && (
              <Alert tone="success" icon={<Sparkles className="h-4 w-4" />} title="Распознано">
                Специализация: <b>{specName(parsed.specialization)}</b> (уверенность {Math.round(parsed.specialization_confidence * 100)}%
                {parsed.specialization_alternatives?.[1] && <>, альтернатива — {specName(parsed.specialization_alternatives[1].code)} {Math.round(parsed.specialization_alternatives[1].p * 100)}%</>}),
                грейд {parsed.grades_detected ? 'найден в тексте' : 'не указан — по умолчанию Middle'}{parsed.experience_years != null && ` (опыт от ${parsed.experience_years} лет)`},
                навыков: {parsed.must_skills.length} обязательных и {parsed.nice_skills.length} желательных. Проверьте и при необходимости поправьте поля справа.
              </Alert>
            )}
            <Field label="О команде (необязательно)"><Textarea rows={3} value={f.team_description} onChange={e => setF({ ...f, team_description: e.target.value })} /></Field>
          </div>
        </Card>

        <Card title="2. Структурированный запрос" subtitle="По этим полям формируется подборка и тест под вакансию">
          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Специализация" required>
                <Select value={f.specialization} onChange={e => setF({ ...f, specialization: e.target.value, language: '' })}>
                  <option value="">Выберите…</option>{ref.specializations.map(s => <option key={s.code} value={s.code}>{s.name}</option>)}</Select>
              </Field>
              {spec && spec.languages.length > 1 && (
                <Field label="Основной язык"><Select value={f.language} onChange={e => setF({ ...f, language: e.target.value })}>
                  {spec.languages.map(l => <option key={l} value={l}>{ref.languages[l]}</option>)}</Select></Field>
              )}
            </div>
            <Field label="Грейды" required>
              <div className="flex flex-wrap gap-2">
                {ref.grades.map(g => (
                  <button key={g.code} type="button" onClick={() => toggleGrade(g.code)}
                    className={clsx('rounded-xl px-4 py-2 text-sm font-semibold ring-1 transition', f.grades.includes(g.code) ? 'bg-fsp-deep text-white ring-fsp-deep' : 'bg-white ring-slate-200 hover:ring-fsp-lavender')}>{g.name}</button>
                ))}
              </div>
            </Field>
            <Field label="Обязательные навыки"><SkillPicker value={f.must_skills} onChange={v => setF({ ...f, must_skills: v })} /></Field>
            <Field label="Желательные навыки"><SkillPicker value={f.nice_skills} onChange={v => setF({ ...f, nice_skills: v })} tone="lavender" /></Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Зарплата от, ₽" required><Input type="number" step={5000} value={f.salary_from} onChange={e => setF({ ...f, salary_from: e.target.value })} /></Field>
              <Field label="Зарплата до, ₽" required><Input type="number" step={5000} value={f.salary_to} onChange={e => setF({ ...f, salary_to: e.target.value })} /></Field>
              <Field label="Формат"><Select value={f.work_format} onChange={e => setF({ ...f, work_format: e.target.value })}>
                {Object.entries(ref.work_formats).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Select></Field>
              <Field label="Город"><Input value={f.city} onChange={e => setF({ ...f, city: e.target.value })} /></Field>
            </div>
            <div className="divide-y divide-slate-100 rounded-2xl bg-surface px-4">
              <Toggle checked={f.require_fsp} onChange={v => setF({ ...f, require_fsp: v })} label="Важен опыт соревнований ФСП" hint="Кандидаты без истории ФСП не исключаются, но ранжируются чуть ниже" />
              <Toggle checked={f.is_published} onChange={v => setF({ ...f, is_published: v })} label="Опубликовать как вакансию" hint="Кандидаты смогут откликаться сами. Иначе потребность видна только вам" />
            </div>
          </div>
        </Card>
      </div>
      <div className="mt-6 flex flex-wrap justify-end gap-2">
        <Button variant="secondary" disabled={!valid} loading={save.isPending && save.variables === false} onClick={() => save.mutate(false)} icon={<Save className="h-4 w-4" />}>Сохранить</Button>
        <Button disabled={!valid} loading={save.isPending && save.variables === true} onClick={() => save.mutate(true)} icon={<Sparkles className="h-4 w-4" />}>Сохранить и подобрать кандидатов</Button>
      </div>
    </div>
  )
}
