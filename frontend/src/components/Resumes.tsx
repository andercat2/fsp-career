import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import clsx from 'clsx'
import { Download, EyeOff, FileUp, Layers, Pencil, Play, Plus, Trash2 } from 'lucide-react'
import { api, download } from '@/lib/api'
import { useToast } from '@/lib/toast'
import { rub } from '@/lib/format'
import { EASE } from '@/lib/motion'
import { Alert, Badge, Button, ButtonLink, Card, Field, Input, Modal, Textarea, Toggle } from './ui'
import { CategoryPill } from './Domain'
import { SkillPicker } from './SkillPicker'

export type Resume = {
  id: number; main: boolean; title: string | null; specialization: string | null; specialization_name: string | null
  primary_language: string | null; language_name: string | null; claimed_grade: string | null; claimed_grade_name: string | null
  survey_completed_at: string | null; industries: string[]
  category: { specialization: string | null; specialization_name: string | null; grade: string | null; grade_name: string | null; percentile: number | null
    theta: number | null; se: number | null; assigned_at: string | null; changed_at: string | null }
  domains: Record<string, { score: number; n: number; correct: number; theta?: number }>
  strength: number; skills: string[]; verified_skills: string[]; desired_salary: number | null; about: string | null
  visible: boolean; resume_filename: string | null
}

/** Основная + до двух дополнительных специализаций. */
export const MAX_RESUMES = 3

export function useResumes(enabled = true) {
  return useQuery({ queryKey: ['cand-resumes'], queryFn: () => api<Resume[]>('/candidate/resumes'), enabled })
}

export function resumeLabel(r: Resume) {
  return r.title || r.specialization_name || 'Резюме'
}

function ResumeEditModal({ resume, onClose }: { resume: Resume | null; onClose: () => void }) {
  const qc = useQueryClient()
  const { push } = useToast()
  const fileRef = useRef<HTMLInputElement>(null)
  const [f, setF] = useState({ title: '', skills: [] as string[], desired_salary: '', about: '', visible: true })
  const [parsing, setParsing] = useState(false)
  useEffect(() => {
    if (resume) setF({ title: resume.title ?? '', skills: resume.skills, desired_salary: resume.desired_salary ? String(resume.desired_salary) : '', about: resume.about ?? '', visible: resume.visible })
  }, [resume])
  const save = useMutation({
    mutationFn: () => api(`/candidate/resumes/${resume!.id}`, { method: 'PUT', body: { title: f.title || null, skills: f.skills, desired_salary: Number(f.desired_salary) || null, about: f.about || null, visible: f.visible } }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['cand-resumes'] }); qc.invalidateQueries({ queryKey: ['cand-profile'] }); qc.invalidateQueries({ queryKey: ['cand-dashboard'] }); push('Резюме сохранено'); onClose() },
    onError: (e: any) => push(e.message, 'error'),
  })
  // PDF этого резюме: заголовок, навыки, зарплата и «о себе» — в форму; общие данные профиля не меняются
  const fromPdf = async (file?: File | null) => {
    if (!file || !resume) return
    setParsing(true)
    const fd = new FormData()
    fd.append('file', file)
    try {
      const p = await api<any>(`/candidate/resume?resume_id=${resume.id}`, { form: fd })
      setF(s => ({ ...s, title: p.headline || s.title, skills: Array.from(new Set([...s.skills, ...(p.skills ?? [])])),
        desired_salary: p.desired_salary ? String(p.desired_salary) : s.desired_salary, about: p.about || s.about }))
      push('Поля резюме заполнены из PDF — проверьте и сохраните', 'info')
    } catch (e: any) { push(e.message, 'error') } finally { setParsing(false) }
  }
  return (
    <Modal open={!!resume} onClose={onClose} wide title={`Резюме: ${resume ? resumeLabel(resume) : ''}`}
      footer={<><Button variant="secondary" onClick={onClose}>Отмена</Button><Button loading={save.isPending} onClick={() => save.mutate()}>Сохранить резюме</Button></>}>
      {resume && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-surface px-4 py-3 text-sm">
            <span>Специализация: <b className="text-fsp-deep">{resume.specialization_name}</b>{resume.language_name && ` · ${resume.language_name}`}
              {resume.category.grade && <> · категория <b className="text-fsp-deep">{resume.category.grade_name}</b></>}</span>
            <input ref={fileRef} type="file" accept="application/pdf" className="hidden" onChange={e => { void fromPdf(e.target.files?.[0]); e.target.value = '' }} />
            <Button size="sm" variant="soft" loading={parsing} onClick={() => fileRef.current?.click()} icon={<FileUp className="h-4 w-4" />}>Загрузить PDF</Button>
          </div>
          <Field label="Заголовок резюме" hint="Так резюме увидит работодатель в подборке"><Input value={f.title} onChange={e => setF({ ...f, title: e.target.value })} placeholder="DevOps-инженер (Kubernetes, CI/CD)" /></Field>
          <Field label="Навыки этого резюме" hint="✓ — подтверждены тестом по этой специализации">
            <SkillPicker value={f.skills} onChange={v => setF({ ...f, skills: v })} verified={resume.verified_skills} />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Ожидания, ₽/мес до вычета НДФЛ" hint="Пусто — как в основном профиле"><Input type="number" step={5000} value={f.desired_salary} onChange={e => setF({ ...f, desired_salary: e.target.value })} /></Field>
            <div className="pt-6"><Toggle checked={f.visible} onChange={v => setF({ ...f, visible: v })} label="Показывать работодателям" hint="Скрытое резюме не участвует в подборе" /></div>
          </div>
          <Field label="О себе в этой специализации" hint="Пусто — используется текст из профиля"><Textarea rows={4} value={f.about} onChange={e => setF({ ...f, about: e.target.value })} /></Field>
        </div>
      )}
    </Modal>
  )
}

/** Резюме кандидата: у каждого своя специализация, свой опрос, свой тест и своя категория. */
export function ResumesCard({ publicId, onEditMain }: { publicId: string; onEditMain?: () => void }) {
  const qc = useQueryClient()
  const { push } = useToast()
  const { data: list } = useResumes()
  const [edit, setEdit] = useState<Resume | null>(null)
  const [del, setDel] = useState<Resume | null>(null)
  const remove = useMutation({
    mutationFn: (id: number) => api<any>(`/candidate/resumes/${id}`, { method: 'DELETE' }),
    onSuccess: (r) => { qc.invalidateQueries({ queryKey: ['cand-resumes'] }); qc.invalidateQueries({ queryKey: ['cand-profile'] }); qc.invalidateQueries({ queryKey: ['eligibility'] }); push(r.detail); setDel(null) },
    onError: (e: any) => push(e.message, 'error'),
  })
  if (!list) return null
  const canAdd = list.length < MAX_RESUMES && !!list[0]?.survey_completed_at
  const pdf = (r: Resume) => download(`/candidate/profile/pdf${r.id ? `?resume_id=${r.id}` : ''}`, `profile-${publicId}${r.id ? `-${r.id}` : ''}.pdf`).catch(e => push(e.message, 'error'))
  return (
    <Card title="Мои резюме и категории"
      subtitle="Одно резюме — одна специализация: свой опрос, свой тест и своя категория. Работодатель находит вас в каждой подтверждённой категории и приглашает по конкретному резюме."
      actions={<span className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-400"><Layers className="h-4 w-4" />{list.length} из {MAX_RESUMES}</span>}>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {list.map((r, i) => (
          <motion.div key={r.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, delay: i * 0.05, ease: EASE }}
            className={clsx('flex min-w-0 flex-col rounded-2xl border p-4', r.main ? 'border-fsp-pink/25 bg-[#FFF8FA]' : 'border-line bg-white', !r.visible && 'opacity-75')}>
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="truncate text-[11px] font-semibold uppercase tracking-wide text-slate-400">{r.main ? 'Основное' : 'Дополнительное'}{r.specialization_name && ` · ${r.specialization_name}`}{r.language_name && ` · ${r.language_name}`}</p>
                <p className="mt-1 truncate font-bold text-fsp-deep" title={resumeLabel(r)}>{resumeLabel(r)}</p>
              </div>
              <div className="flex shrink-0 items-center gap-1">
                {!r.visible && <Badge tone="gray" icon={<EyeOff className="h-3 w-3" />}>скрыто</Badge>}
                {!r.main && <button onClick={() => setDel(r)} aria-label="Удалить резюме" title="Удалить резюме"
                  className="grid h-7 w-7 place-items-center rounded-lg text-slate-300 transition hover:bg-red-50 hover:text-red-500"><Trash2 className="h-3.5 w-3.5" /></button>}
              </div>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              {r.category.grade ? <CategoryPill spec={r.category.specialization_name} grade={r.category.grade_name} />
                : <Badge tone="amber">{r.survey_completed_at ? `заявлен ${r.claimed_grade_name ?? '—'}, нужен тест` : 'нужен опрос'}</Badge>}
              {r.category.percentile != null && <span className="text-xs font-semibold text-emerald-600">выше {Math.round(r.category.percentile)}%</span>}
            </div>
            <p className="mt-3 text-xs text-slate-500">{r.skills.length} навыков · ✓ {r.verified_skills.length} подтверждено тестом{r.desired_salary ? ` · от ${rub(r.desired_salary)}` : ''}</p>
            <div className="mt-auto flex flex-wrap gap-1.5 pt-4">
              <ButtonLink to={`/candidate/testing?resume=${r.id}`} size="sm" icon={<Play className="h-3.5 w-3.5" />}>Тест</ButtonLink>
              <Button size="sm" variant="secondary" onClick={() => (r.main ? onEditMain?.() : setEdit(r))} icon={<Pencil className="h-3.5 w-3.5" />}>Изменить</Button>
              <Button size="sm" variant="ghost" className="!px-2" onClick={() => pdf(r)} title="Стандартизированный PDF-профиль по этому резюме" aria-label="PDF-профиль по резюме" icon={<Download className="h-3.5 w-3.5" />}>PDF</Button>
            </div>
          </motion.div>
        ))}
        {canAdd && (
          <Link to="/candidate/testing?new=1" className="group grid min-h-[176px] place-items-center rounded-2xl border-2 border-dashed border-line p-4 text-center transition hover:border-fsp-pink/40 hover:bg-[#FFF8FA]">
            <div>
              <span className="mx-auto grid h-11 w-11 place-items-center rounded-2xl bg-fsp-blush text-fsp-pink transition group-hover:scale-105"><Plus className="h-5 w-5" /></span>
              <p className="mt-2 font-semibold text-fsp-deep">Добавить резюме</p>
              <p className="mt-0.5 text-xs text-slate-500">под другую специализацию: опрос → тест → ещё одна категория</p>
            </div>
          </Link>
        )}
      </div>
      {!list[0]?.survey_completed_at && <p className="mt-3 text-xs text-slate-500">Дополнительные резюме станут доступны после опроса по основной специализации.</p>}
      <ResumeEditModal resume={edit} onClose={() => setEdit(null)} />
      <Modal open={!!del} onClose={() => setDel(null)} title="Удалить резюме?"
        footer={<><Button variant="secondary" onClick={() => setDel(null)}>Отмена</Button><Button variant="danger" loading={remove.isPending} onClick={() => del && remove.mutate(del.id)}>Удалить</Button></>}>
        {del && <Alert tone="warn">Резюме «{resumeLabel(del)}» и его категория {del.category.grade ? `«${del.category.specialization_name} · ${del.category.grade_name}» ` : ''}перестанут быть видны работодателям. История тестов сохранится.</Alert>}
      </Modal>
    </Card>
  )
}

/** Переключатель резюме (специализаций): у каждого своя категория. */
export function ResumeTabs({ resumes, active, onSelect, onNew, canAdd }: {
  resumes: Resume[]; active: number | 'new'; onSelect: (id: number) => void; onNew?: () => void; canAdd?: boolean
}) {
  return (
    <div className="scrollbar-thin -mx-1 mb-6 flex gap-2 overflow-x-auto px-1 pb-1">
      {resumes.map(r => {
        const on = active === r.id
        return (
          <button key={r.id} onClick={() => onSelect(r.id)}
            className={clsx('flex min-w-[200px] max-w-[280px] shrink-0 flex-col items-start rounded-2xl border px-4 py-3 text-left transition',
              on ? 'border-fsp-deep bg-fsp-deep text-white shadow-lift' : 'border-line bg-white hover:border-[#D9D4E7]')}>
            <span className={clsx('text-[11px] font-semibold uppercase tracking-wide', on ? 'text-white/60' : 'text-slate-400')}>{r.main ? 'Основное резюме' : 'Дополнительное'}</span>
            <span className="mt-0.5 w-full truncate text-sm font-bold">{resumeLabel(r)}</span>
            <span className={clsx('mt-1 text-xs', on ? 'text-white/75' : 'text-slate-500')}>
              {r.category.grade ? `✓ ${r.category.specialization_name} · ${r.category.grade_name}` : r.survey_completed_at ? `${r.specialization_name} · тест не пройден` : 'нужен опрос'}</span>
          </button>
        )
      })}
      {canAdd && onNew && (
        <button onClick={onNew}
          className={clsx('flex min-w-[200px] shrink-0 items-center gap-3 rounded-2xl border-2 border-dashed px-4 py-3 text-left transition',
            active === 'new' ? 'border-fsp-pink bg-[#FFF5F8]' : 'border-line hover:border-fsp-pink/40')}>
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-fsp-blush text-fsp-pink"><Plus className="h-4 w-4" /></span>
          <span><span className="block text-sm font-bold text-fsp-deep">Новая специализация</span><span className="text-xs text-slate-500">ещё одно резюме и категория</span></span>
        </button>
      )}
    </div>
  )
}
