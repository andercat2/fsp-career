import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import {
  ArrowLeft, ChevronDown, ChevronUp, Filter, MapPin, RefreshCw, Send, Sparkles, Star, Trophy, Users, Wallet, Wand2, X,
} from 'lucide-react'
import { api, qs } from '@/lib/api'
import { useReference } from '@/lib/reference'
import { useToast } from '@/lib/toast'
import { ago, rub, salaryRange, WORK_FORMATS } from '@/lib/format'
import { Badge, Button, Card, Checkbox, EmptyState, Field, Input, PageHeader, PageLoader, Select, Textarea } from '@/components/ui'
import { CategoryPill, Components, MatchRing, Reasons, StatusBadge } from '@/components/Domain'
import { SkillPicker } from '@/components/SkillPicker'
import { InviteModal, type InviteTarget } from '@/components/InviteModal'

export function useShortlistToggle() {
  const qc = useQueryClient()
  const { push } = useToast()
  return useMutation({
    mutationFn: ({ id, on }: { id: number; on: boolean }) => on ? api('/employer/shortlist', { body: { candidate_id: id } }) : api(`/employer/shortlist/${id}`, { method: 'DELETE' }),
    onSuccess: (_d, v) => { push(v.on ? 'Добавлено в избранное' : 'Убрано из избранного'); qc.invalidateQueries({ queryKey: ['selection'] }); qc.invalidateQueries({ queryKey: ['emp-search'] }); qc.invalidateQueries({ queryKey: ['shortlist'] }) },
  })
}

export function CandidateRow({ c, onInvite, onShortlist }: { c: any; onInvite: () => void; onShortlist: (on: boolean) => void }) {
  const [more, setMore] = useState(false)
  const lhTone = c.likelihood?.label === 'высокая' ? 'green' : c.likelihood?.label === 'средняя' ? 'amber' : 'red'
  return (
    <div className="card p-4 sm:p-5">
      <div className="flex flex-col gap-4 sm:flex-row">
        {c.match != null && <MatchRing value={c.match} size={68} />}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Link to={`/employer/candidates/${c.id}`} className="text-lg font-bold text-fsp-deep hover:text-fsp-pink">{c.display_name}</Link>
            <CategoryPill spec={c.specialization_name} grade={c.grade_name} />
            {c.percentile != null && <Badge tone="pink">выше {Math.round(c.percentile)}%</Badge>}
            {c.invitation_status && <StatusBadge status={c.invitation_status} label={`приглашение: ${({ sent: 'отправлено', viewed: 'просмотрено', accepted: 'принято', declined: 'отклонено', expired: 'истекло', withdrawn: 'отозвано' } as any)[c.invitation_status]}`} />}
          </div>
          <p className="mt-1 text-sm text-slate-600">{c.headline}</p>
          <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
            {c.city && <span className="inline-flex items-center gap-1"><MapPin className="h-3.5 w-3.5" />{c.city}{c.relocation && ' · готов к переезду'}</span>}
            {!!c.work_formats?.length && <span>{c.work_formats.map((f: string) => WORK_FORMATS[f]).join(' / ')}</span>}
            {c.experience_years != null && <span>опыт {String(c.experience_years).replace('.', ',')} г.</span>}
            {c.desired_salary ? <span className="inline-flex items-center gap-1"><Wallet className="h-3.5 w-3.5" />ожидания от {rub(c.desired_salary)}</span> : <span>ожидания скрыты</span>}
          </p>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {c.verified_skills.slice(0, 8).map((s: string) => <Badge key={s} tone="pink">✓ {s}</Badge>)}
            {c.declared_skills.slice(0, 5).map((s: string) => <Badge key={s} tone="gray">{s}</Badge>)}
            {c.fsp_headline && <Badge tone="purple" icon={<Trophy className="h-3 w-3" />}>{c.fsp_headline}</Badge>}
          </div>
          {c.components && <div className="mt-4 max-w-xl"><Components components={c.components} /></div>}
          {c.reasons && (
            <div className="mt-3">
              <Reasons reasons={c.reasons} limit={more ? undefined : 3} />
              {c.reasons.length > 3 && <button onClick={() => setMore(m => !m)} className="mt-1 inline-flex items-center gap-1 text-xs font-semibold text-fsp-lavender">
                {more ? <>Свернуть <ChevronUp className="h-3 w-3" /></> : <>Почему в подборке — все причины ({c.reasons.length}) <ChevronDown className="h-3 w-3" /></>}</button>}
            </div>
          )}
        </div>
        <div className="flex shrink-0 flex-row items-center gap-2 sm:flex-col sm:items-end">
          {c.likelihood && <Badge tone={lhTone as any}>отклик: {c.likelihood.label}</Badge>}
          <div className="flex gap-2 sm:mt-auto">
            <button onClick={() => onShortlist(!c.shortlisted)} title={c.shortlisted ? 'Убрать из избранного' : 'В избранное'}
              className={clsx('grid h-10 w-10 place-items-center rounded-xl ring-1 transition', c.shortlisted ? 'bg-amber-50 text-amber-500 ring-amber-200' : 'bg-white text-slate-400 ring-slate-200 hover:text-amber-500')}>
              <Star className={clsx('h-4 w-4', c.shortlisted && 'fill-amber-400')} />
            </button>
            <Button onClick={onInvite} disabled={!c.open_to_offers || ['sent', 'viewed', 'accepted'].includes(c.invitation_status)} icon={<Send className="h-4 w-4" />}>
              {c.invitation_status === 'accepted' ? 'Контакт открыт' : ['sent', 'viewed'].includes(c.invitation_status) ? 'Приглашён' : c.open_to_offers ? 'Пригласить' : 'Не ищет'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

const REL: Record<string, string> = { '1': 'основная', '0.6': 'ступень выше / смежная', '0.55': 'смежная', '0.5': 'смежная', '0.45': 'ступень ниже', '0.4': 'смежная', '0.3': 'смежная' }

export function SelectionPage() {
  const { id } = useParams()
  const qc = useQueryClient()
  const { push } = useToast()
  const { gradeName } = useReference()
  const [f, setF] = useState<any>({ grades: [], skills: [], verified_only: false, has_fsp: false, work_format: '', city: '', salary_max: '', min_match: '', specialization: '' })
  const [size, setSize] = useState(20)
  const [invite, setInvite] = useState<InviteTarget | null>(null)
  const [showFilters, setShowFilters] = useState(true)
  const params = useMemo(() => ({ ...f, size }), [f, size])
  const { data: s, isLoading, isFetching } = useQuery({ queryKey: ['selection', id, params], queryFn: () => api(`/employer/selections/${id}${qs(params)}`), placeholderData: p => p })
  const refresh = useMutation({ mutationFn: () => api(`/employer/selections/${id}/refresh`, { method: 'POST' }), onSuccess: () => { qc.invalidateQueries({ queryKey: ['selection', id] }); push('Подборка пересчитана на актуальной базе') } })
  const shortlist = useShortlistToggle()
  if (isLoading || !s) return <PageLoader />
  const need = s.need
  const activeCat = (c: any) => f.specialization === c.specialization && f.grades.length === 1 && f.grades[0] === c.grade
  const toggleCat = (c: any) => setF((x: any) => activeCat(c) ? { ...x, specialization: '', grades: [] } : { ...x, specialization: c.specialization, grades: [c.grade] })
  const reset = () => setF({ grades: [], skills: [], verified_only: false, has_fsp: false, work_format: '', city: '', salary_max: '', min_match: '', specialization: '' })
  const filtersOn = Object.entries(f).some(([, v]) => Array.isArray(v) ? v.length : !!v)

  return (
    <div>
      <PageHeader back={<Link to="/employer/selections" className="mb-2 inline-flex items-center gap-1.5 text-sm font-semibold text-slate-500 hover:text-fsp-pink"><ArrowLeft className="h-4 w-4" /> Подборки</Link>}
        title={s.title}
        subtitle={<span className="flex flex-wrap items-center gap-1.5">
          <Badge tone="lavender">{need.specialization_name}</Badge>{need.grade_names.map((g: string) => <Badge key={g}>{g}</Badge>)}
          {need.must_skill_names.map((n: string) => <Badge key={n} tone="pink">{n}</Badge>)}
          {need.nice_skill_names.map((n: string) => <Badge key={n} tone="gray">+ {n}</Badge>)}
          {(need.salary_from || need.salary_to) && <span className="ml-1">· {salaryRange(need.salary_from, need.salary_to)}</span>}
          {need.work_format && <span>· {WORK_FORMATS[need.work_format]}{need.city && `, ${need.city}`}</span>}
          <span className="text-slate-400">· сформирована {ago(s.created_at)}</span></span>}
        actions={<Button variant="secondary" loading={refresh.isPending} onClick={() => refresh.mutate()} icon={<RefreshCw className="h-4 w-4" />}>Пересчитать</Button>} />

      <section className="mb-6">
        <h2 className="mb-3 flex items-center gap-2 text-base font-bold"><Users className="h-4 w-4 text-fsp-pink" /> Рекомендованные категории</h2>
        <div className="scrollbar-thin -mx-1 flex gap-3 overflow-x-auto px-1 pb-2">
          {s.categories.map((c: any) => (
            <button key={`${c.specialization}-${c.grade}`} onClick={() => toggleCat(c)}
              className={clsx('w-60 shrink-0 rounded-2xl p-4 text-left ring-1 transition',
                activeCat(c) ? 'bg-fsp-deep text-white ring-fsp-deep' : c.primary ? 'bg-white ring-fsp-pink/40 hover:ring-fsp-pink' : 'bg-white ring-slate-200 hover:ring-fsp-lavender')}>
              <div className="flex items-center justify-between gap-2">
                <span className={clsx('text-[11px] font-semibold uppercase tracking-wide', activeCat(c) ? 'text-white/60' : c.primary ? 'text-fsp-pink' : 'text-slate-400')}>{REL[String(c.relevance)] ?? 'смежная'}</span>
                <span className={clsx('text-2xl font-extrabold', activeCat(c) ? 'text-white' : 'text-fsp-deep')}>{c.count}</span>
              </div>
              <p className={clsx('mt-1 font-bold leading-tight', activeCat(c) ? 'text-white' : 'text-fsp-deep')}>{c.specialization_name}<br />{c.grade_name}</p>
              <div className={clsx('mt-3 space-y-0.5 text-xs', activeCat(c) ? 'text-white/75' : 'text-slate-500')}>
                <p>Медиана ожиданий: <b>{c.median_salary ? rub(c.median_salary) : '—'}</b></p>
                <p>В вашей вилке: <b>{c.share_in_budget != null ? `${Math.round(c.share_in_budget * 100)}%` : '—'}</b></p>
                <p>С достижениями ФСП: <b>{c.with_fsp}</b> · открыты: <b>{c.open_to_offers}</b></p>
              </div>
            </button>
          ))}
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[300px_1fr]">
        <aside className="xl:sticky xl:top-24 xl:self-start">
          <Card title={<span className="flex items-center gap-2"><Filter className="h-4 w-4" /> Уточнить</span>}
            actions={<button className="text-xs font-semibold text-slate-500 xl:hidden" onClick={() => setShowFilters(v => !v)}>{showFilters ? 'скрыть' : 'показать'}</button>}>
            <div className={clsx('space-y-4', !showFilters && 'hidden xl:block')}>
              <p className="rounded-xl bg-surface px-3 py-2 text-xs text-slate-500">Фильтры применяются к сохранённой подборке — исходный результат не теряется.</p>
              <Field label="Грейды">
                <div className="flex flex-wrap gap-1.5">{['intern', 'junior', 'middle', 'senior'].map(g => (
                  <button key={g} onClick={() => setF((x: any) => ({ ...x, grades: x.grades.includes(g) ? x.grades.filter((y: string) => y !== g) : [...x.grades, g] }))}
                    className={clsx('chip px-3 py-1.5 ring-1', f.grades.includes(g) ? 'bg-fsp-deep text-white ring-fsp-deep' : 'bg-white ring-slate-200')}>{gradeName(g)}</button>))}</div>
              </Field>
              <Field label="Навыки"><SkillPicker value={f.skills} onChange={v => setF({ ...f, skills: v })} placeholder="Python, Kafka…" /></Field>
              <Checkbox checked={f.verified_only} onChange={v => setF({ ...f, verified_only: v })} label="Только подтверждённые тестом" />
              <Checkbox checked={f.has_fsp} onChange={v => setF({ ...f, has_fsp: v })} label="Есть достижения ФСП" />
              <Field label="Формат"><Select value={f.work_format} onChange={e => setF({ ...f, work_format: e.target.value })}>
                <option value="">Любой</option>{Object.entries(WORK_FORMATS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Select></Field>
              <Field label="Город"><Input value={f.city} onChange={e => setF({ ...f, city: e.target.value })} placeholder="Казань" /></Field>
              <Field label="Ожидания не выше, ₽"><Input type="number" step={10000} value={f.salary_max} onChange={e => setF({ ...f, salary_max: e.target.value })} /></Field>
              <Field label={`Совпадение от ${f.min_match || 0}%`}><input type="range" min={0} max={90} step={5} value={f.min_match || 0} onChange={e => setF({ ...f, min_match: Number(e.target.value) || '' })} className="w-full accent-[#FF0053]" /></Field>
              {filtersOn && <Button variant="ghost" size="sm" onClick={reset} icon={<X className="h-4 w-4" />}>Сбросить фильтры</Button>}
            </div>
          </Card>
        </aside>

        <div>
          <div className="mb-3 flex items-center justify-between text-sm text-slate-500">
            <span>Показано <b className="text-fsp-deep">{s.results.length}</b> из <b className="text-fsp-deep">{s.total}</b>{s.total !== s.total_in_selection && <> (в подборке {s.total_in_selection})</>}</span>
            {isFetching && <span className="text-xs">обновление…</span>}
          </div>
          {!s.results.length ? <EmptyState icon={<Filter className="h-5 w-5" />} title="Никого не осталось" text="Ослабьте фильтры — исходная подборка сохранена." action={<Button size="sm" variant="secondary" onClick={reset}>Сбросить</Button>} /> : (
            <div className="space-y-3">
              {s.results.map((c: any) => (
                <CandidateRow key={c.id} c={c} onShortlist={on => shortlist.mutate({ id: c.id, on })}
                  onInvite={() => setInvite({ id: c.id, display_name: c.display_name, grade_name: c.grade_name, specialization_name: c.specialization_name, reasons: c.reasons })} />
              ))}
              {s.total > s.results.length && <div className="pt-2 text-center"><Button variant="secondary" onClick={() => setSize(x => x + 20)}>Показать ещё</Button></div>}
            </div>
          )}
        </div>
      </div>
      <InviteModal target={invite} onClose={() => setInvite(null)} vacancyId={s.vacancy_id}
        defaults={{ salary_from: need.salary_from, salary_to: need.salary_to, title: s.vacancy_id ? undefined : s.title, work_format: need.work_format }} />
    </div>
  )
}

export function Selections() {
  const nav = useNavigate()
  const { push } = useToast()
  const [text, setText] = useState('')
  const [title, setTitle] = useState('')
  const { data, isLoading } = useQuery({ queryKey: ['emp-selections'], queryFn: () => api<any[]>('/employer/selections') })
  const create = useMutation({ mutationFn: () => api('/employer/selections', { body: { text, title: title || null } }), onSuccess: (s: any) => nav(`/employer/selections/${s.id}`), onError: (e: any) => push(e.message, 'error') })
  const examples = [
    'Нужен сильный Go-разработчик для микросервисов скоринга: PostgreSQL, Kafka, gRPC. Senior, удалённо, до 420 000 ₽.',
    'Ищем джуна-тестировщика: тест-дизайн, Postman, SQL. Офис в Казани, 90–120 тыс.',
    'Data Scientist для рекомендательной системы: Python, PyTorch, A/B-тесты. Middle+, гибрид, Москва, 280–350 тыс.',
  ]
  return (
    <div>
      <PageHeader title="Подборки" subtitle="Опишите потребность своими словами — система определит категорию, покажет рынок и ранжирует кандидатов с объяснением." />
      <Card className="mb-6">
        <div className="grid gap-4 lg:grid-cols-[1fr_auto]">
          <div className="space-y-3">
            <Input value={title} onChange={e => setTitle(e.target.value)} placeholder="Название подборки (необязательно)" />
            <Textarea rows={4} value={text} onChange={e => setText(e.target.value)} placeholder="Кого вы ищете? Стек, уровень, формат, город, вилка…" />
            <div className="flex flex-wrap gap-2">{examples.map((e, i) => (
              <button key={i} onClick={() => setText(e)} className="chip bg-surface text-left text-slate-600 ring-1 ring-slate-200 hover:ring-fsp-lavender"><Wand2 className="h-3 w-3 text-fsp-pink" /> пример {i + 1}</button>))}</div>
          </div>
          <div className="flex items-end"><Button size="lg" disabled={text.trim().length < 10} loading={create.isPending} onClick={() => create.mutate()} icon={<Sparkles className="h-5 w-5" />}>Подобрать</Button></div>
        </div>
      </Card>
      {isLoading ? <PageLoader /> : !data?.length ? <EmptyState icon={<Sparkles className="h-5 w-5" />} title="Подборок пока нет" /> : (
        <div className="grid gap-3 md:grid-cols-2">
          {data.map(s => (
            <Link key={s.id} to={`/employer/selections/${s.id}`} className="card card-pad block hover:ring-fsp-lavender">
              <p className="font-bold text-fsp-deep">{s.title}</p>
              <p className="mt-1 text-sm text-slate-500">{s.specialization_name} · {s.grade_names.join(', ')} · {s.total} кандидатов · {ago(s.created_at)}</p>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
