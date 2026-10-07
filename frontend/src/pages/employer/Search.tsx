import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Search as SearchIcon, Users } from 'lucide-react'
import { api, qs } from '@/lib/api'
import { useReference } from '@/lib/reference'
import { WORK_FORMATS } from '@/lib/format'
import { Button, Card, Checkbox, EmptyState, Input, PageHeader, PageLoader, Select } from '@/components/ui'
import { SkillPicker } from '@/components/SkillPicker'
import { InviteModal, inviteTarget, type InviteTarget } from '@/components/InviteModal'
import { CandidateRow, useShortlistToggle } from './Selection'
import { container } from '@/lib/motion'

export function CandidateSearch() {
  const { ref } = useReference()
  const [f, setF] = useState<any>({ q: '', specialization: '', grades: [], skills: [], verified_only: false, has_fsp: false, work_format: '', city: '', salary_max: '', vacancy_id: '', sort: 'strength', confirmed_only: false })
  const [page, setPage] = useState(1)
  const [invite, setInvite] = useState<InviteTarget | null>(null)
  const params = useMemo(() => ({ ...f, page, size: 20 }), [f, page])
  const { data, isLoading, isFetching } = useQuery({ queryKey: ['emp-search', params], queryFn: () => api(`/employer/candidates${qs(params)}`), placeholderData: p => p })
  const { data: vacancies } = useQuery({ queryKey: ['emp-vacancies'], queryFn: () => api<any[]>('/employer/vacancies') })
  const shortlist = useShortlistToggle()
  const set = (patch: any) => { setF((x: any) => ({ ...x, ...patch })); setPage(1) }
  const vac = vacancies?.find(v => String(v.id) === String(f.vacancy_id))

  return (
    <div>
      <PageHeader title="Банк кандидатов" subtitle="Вся база кандидатов с категорией по тесту. Кандидаты, чей заявленный грейд тест не подтвердил, — со статусом «не подтверждён» и после подтверждённых при любой сортировке. Выберите потребность, чтобы ранжировать по совпадению с ней." />
      <Card className="mb-5">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <div className="relative xl:col-span-2"><SearchIcon className="absolute left-3 top-3 h-4 w-4 text-slate-400" />
            <Input className="pl-9" value={f.q} onChange={e => set({ q: e.target.value })} placeholder="Поиск по должности, навыкам, городу" /></div>
          <Select value={f.specialization} onChange={e => set({ specialization: e.target.value })}>
            <option value="">Все специализации</option>{ref?.specializations.map(s => <option key={s.code} value={s.code}>{s.name}</option>)}</Select>
          <Select value={f.grades[0] ?? ''} onChange={e => set({ grades: e.target.value ? [e.target.value] : [] })}>
            <option value="">Любой грейд</option>{ref?.grades.map(g => <option key={g.code} value={g.code}>{g.name}</option>)}</Select>
          <div className="md:col-span-2"><SkillPicker value={f.skills} onChange={v => set({ skills: v })} placeholder="Навыки (все должны быть)" /></div>
          <Select value={f.work_format} onChange={e => set({ work_format: e.target.value })}>
            <option value="">Любой формат</option>{Object.entries(WORK_FORMATS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Select>
          <Input value={f.city} onChange={e => set({ city: e.target.value })} placeholder="Город" />
          <Input type="number" step={10000} value={f.salary_max} onChange={e => set({ salary_max: e.target.value })} placeholder="Ожидания не выше, ₽ (до НДФЛ)" />
          <Select value={f.vacancy_id} onChange={e => set({ vacancy_id: e.target.value })}>
            <option value="">Ранжировать по силе профиля</option>{vacancies?.map(v => <option key={v.id} value={v.id}>Совпадение с: {v.title}</option>)}</Select>
          <Select value={f.sort} onChange={e => set({ sort: e.target.value })}>
            <option value="strength">{f.vacancy_id ? 'По совпадению' : 'По силе профиля'}</option><option value="fresh">По активности</option><option value="salary">По ожиданиям (возр.)</option></Select>
          <div className="flex flex-wrap items-center gap-4">
            <Checkbox checked={f.verified_only} onChange={v => set({ verified_only: v })} label="Навыки подтверждены тестом" />
            <Checkbox checked={f.has_fsp} onChange={v => set({ has_fsp: v })} label="Есть достижения ФСП" />
            <Checkbox checked={f.confirmed_only} onChange={v => set({ confirmed_only: v })} label="Только подтверждённые грейды" />
          </div>
        </div>
      </Card>
      <div className="mb-3 text-sm text-slate-500">{data ? <>Найдено <b className="text-fsp-deep">{data.total}</b></> : ''} {isFetching && '· обновление…'}</div>
      {isLoading || !data ? <PageLoader /> : !data.results.length ? <EmptyState icon={<Users className="h-5 w-5" />} title="Никого не найдено" text="Попробуйте ослабить фильтры." /> : (
        <motion.div className="space-y-3" variants={container(0.05)} initial="hidden" animate="show" key={`${page}-${JSON.stringify(f)}`}>
          {data.results.map((c: any) => (
            <CandidateRow key={c.id} c={c} onShortlist={on => shortlist.mutate({ id: c.id, on, resume_id: c.resume_id })}
              onInvite={() => setInvite(inviteTarget(c))} />
          ))}
          <div className="flex items-center justify-center gap-3 pt-2">
            <Button variant="secondary" size="sm" disabled={page === 1} onClick={() => setPage(p => p - 1)}>Назад</Button>
            <span className="text-sm text-slate-500">стр. {page} из {Math.max(1, Math.ceil(data.total / 20))}</span>
            <Button variant="secondary" size="sm" disabled={page * 20 >= data.total} onClick={() => setPage(p => p + 1)}>Далее</Button>
          </div>
        </motion.div>
      )}
      <InviteModal target={invite} onClose={() => setInvite(null)} vacancyId={vac?.id ?? null} />
    </div>
  )
}
