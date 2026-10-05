import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { CircleCheck, Download, FileUp, Plus, Save, Sparkles, Trash2, Upload } from 'lucide-react'
import { api, download } from '@/lib/api'
import { useReference } from '@/lib/reference'
import { useToast } from '@/lib/toast'
import { WORK_FORMATS, rub, years } from '@/lib/format'
import { Alert, Badge, Button, Card, Field, Input, Modal, PageHeader, PageLoader, Textarea, Toggle } from '@/components/ui'
import { SkillPicker } from '@/components/SkillPicker'
import { ResumesCard } from '@/components/Resumes'

type Exp = { company: string | null; position: string | null; start: string | null; end: string | null; description: string | null }
type Edu = { title: string; year?: number | null; level?: string | null; specialty?: string | null }
type Lang = { name: string; level?: string | null }
type Form = {
  full_name: string; phone: string; telegram: string; contact_email: string; city: string; relocation: boolean
  work_formats: string[]; desired_salary: number | null; headline: string; about: string; experience_years: number | null
  experience: Exp[]; education: Edu[]; languages: Lang[]; skills: string[]; roles: string[]; soft_skills: string[]
  links: Record<string, string>; open_to_offers: boolean
}

const toForm = (p: any): Form => ({
  full_name: p.full_name ?? '', phone: p.contacts?.phone ?? '', telegram: p.contacts?.telegram ?? '',
  contact_email: p.contacts?.email ?? '', city: p.city ?? '', relocation: !!p.relocation, work_formats: p.work_formats ?? [],
  desired_salary: p.desired_salary ?? null, headline: p.headline ?? '', about: p.about ?? '',
  experience_years: p.experience_years ?? null, experience: p.experience ?? [], education: p.education ?? [],
  languages: p.languages ?? [],
  skills: p.skills ?? [], roles: p.roles ?? [], soft_skills: p.soft_skills ?? [], links: p.links ?? {}, open_to_offers: p.open_to_offers ?? true,
})

const FIELD_LABEL: Record<string, string> = {
  full_name: 'ФИО', email: 'E-mail', phone: 'Телефон', telegram: 'Telegram', city: 'Город', headline: 'Должность',
  skills: 'Навыки', experience_years: 'Стаж', experience: 'Опыт работы', claimed_grade: 'Грейд по резюме', roles: 'Роли в команде',
  soft_skills: 'Софт-скиллы', education: 'Образование', desired_salary: 'Ожидания по ЗП', work_formats: 'Формат работы',
  specialization: 'Специализация', github: 'GitHub', languages: 'Языки', about: 'О себе', relocation: 'Переезд',
}
const LINK_LABEL: Record<string, string> = { github: 'GitHub', gitlab: 'GitLab', linkedin: 'LinkedIn', habr: 'Хабр Карьера',
  kaggle: 'Kaggle', leetcode: 'LeetCode', vk: 'VK', hh: 'hh.ru' }

export function CandidateProfile() {
  const qc = useQueryClient()
  const { push } = useToast()
  const { ref, skillName, gradeName, specName } = useReference()
  const { data: profile, isLoading } = useQuery({ queryKey: ['cand-profile'], queryFn: () => api('/candidate/profile') })
  const [form, setForm] = useState<Form | null>(null)
  const [parsed, setParsed] = useState<any>(null)
  const [uploading, setUploading] = useState(false)
  const [drag, setDrag] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  useEffect(() => { if (profile && !form) setForm(toForm(profile)) }, [profile, form])

  const save = useMutation({
    mutationFn: (f: Form) => api('/candidate/profile', { method: 'PUT', body: { ...f, contact_email: f.contact_email || null, desired_salary: f.desired_salary || null } }),
    onSuccess: (p) => { qc.setQueryData(['cand-profile'], p); qc.invalidateQueries({ queryKey: ['cand-dashboard'] }); qc.invalidateQueries({ queryKey: ['cand-resumes'] }); push('Профиль сохранён') },
    onError: (e: any) => push(e.message, 'error'),
  })

  if (isLoading || !form || !ref) return <PageLoader />
  const set = <K extends keyof Form>(k: K, v: Form[K]) => setForm(f => f ? { ...f, [k]: v } : f)

  const upload = async (file?: File | null) => {
    if (!file) return
    setUploading(true)
    const fd = new FormData()
    fd.append('file', file)
    try { setParsed(await api('/candidate/resume', { form: fd })) } catch (e: any) { push(e.message, 'error') } finally { setUploading(false) }
  }

  const applyParsed = () => {
    const p = parsed
    setForm(f => {
      if (!f) return f
      return {
        ...f,
        full_name: p.full_name || f.full_name, phone: p.phone || f.phone, telegram: p.telegram || f.telegram,
        contact_email: p.email || f.contact_email, city: p.city || f.city, headline: p.headline || f.headline,
        about: p.about || f.about, relocation: p.relocation ?? f.relocation,
        languages: p.languages?.length ? p.languages : f.languages,
        skills: Array.from(new Set([...f.skills, ...(p.skills ?? [])])),
        roles: Array.from(new Set([...f.roles, ...(p.roles ?? [])])),
        soft_skills: Array.from(new Set([...f.soft_skills, ...(p.soft_skills ?? [])])),
        experience_years: p.experience_years ?? f.experience_years,
        experience: p.experience?.length ? p.experience : f.experience,
        education: p.education?.length ? p.education : f.education,
        desired_salary: p.desired_salary ?? f.desired_salary,
        work_formats: Array.from(new Set([...f.work_formats, ...(p.work_formats ?? [])])),
        links: { ...f.links, ...(p.links ?? {}) },
      }
    })
    setParsed(null)
    push('Поля заполнены из резюме — проверьте и сохраните профиль', 'info')
  }

  const toggle = (arr: string[], v: string) => arr.includes(v) ? arr.filter(x => x !== v) : [...arr, v]

  return (
    <div className="space-y-6 pb-24">
      <PageHeader title="Профиль и резюме"
        subtitle="Резюме помогает работодателю понять ваш опыт, но категорию определяет тест. Навыки, подтверждённые тестом, отмечены ✓."
        actions={<Button variant="secondary" icon={<Download className="h-4 w-4" />} title="Стандартизированный PDF-профиль для работодателя"
          onClick={() => download('/candidate/profile/pdf', `profile-${profile.public_id}.pdf`).catch(e => push(e.message, 'error'))}>Загрузить PDF-профиль</Button>} />

      <div onDragOver={e => { e.preventDefault(); setDrag(true) }} onDragLeave={() => setDrag(false)}
           onDrop={e => { e.preventDefault(); setDrag(false); void upload(e.dataTransfer.files?.[0]) }}
           className={clsx('card flex flex-col items-center gap-4 border-2 border-dashed p-6 text-center sm:flex-row sm:text-left',
             drag ? 'border-fsp-pink bg-fsp-blush/30' : 'border-transparent')}>
        <div className="grid h-14 w-14 shrink-0 place-items-center rounded-2xl bg-fsp-blush text-fsp-pink"><FileUp className="h-7 w-7" /></div>
        <div className="flex-1">
          <p className="font-bold text-fsp-deep">Загрузите резюме в PDF — заполним профиль автоматически</p>
          <p className="mt-1 text-sm text-slate-500">Резюме с hh.ru и обычные PDF: ФИО, контакты и GitHub, желаемую должность и зарплату, формат работы, места работы с датами, стаж, образование, языки, навыки, роли и софт-скиллы.
            {profile.resume_filename && <> Последний файл: <b>{profile.resume_filename}</b>.</>}</p>
        </div>
        <input ref={fileRef} type="file" accept="application/pdf" className="hidden" onChange={e => { void upload(e.target.files?.[0]); e.target.value = '' }} />
        <Button onClick={() => fileRef.current?.click()} loading={uploading} icon={<Upload className="h-4 w-4" />}>Загрузить PDF</Button>
      </div>

      <ResumesCard publicId={profile.public_id}
        onEditMain={() => document.getElementById('main-resume')?.scrollIntoView({ behavior: 'smooth', block: 'start' })} />

      <div id="main-resume" className="grid scroll-mt-24 gap-6 xl:grid-cols-2">
        <Card title="Основное" subtitle="Общие данные и основное резюме: заголовок, навыки и ожидания ниже относятся к нему">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="ФИО" className="sm:col-span-2"><Input value={form.full_name} onChange={e => set('full_name', e.target.value)} /></Field>
            <Field label="Желаемая должность" className="sm:col-span-2"><Input value={form.headline} onChange={e => set('headline', e.target.value)} placeholder="Python-разработчик" /></Field>
            <Field label="Город"><Input value={form.city} onChange={e => set('city', e.target.value)} /></Field>
            <Field label="Стаж, лет" hint={form.experience_years != null ? years(form.experience_years) : undefined}>
              <Input type="number" step="0.5" min={0} value={form.experience_years ?? ''} onChange={e => set('experience_years', e.target.value === '' ? null : Number(e.target.value))} />
            </Field>
            <Field label="Ожидания по доходу, ₽/мес" hint={form.desired_salary ? rub(form.desired_salary) : 'Можно скрыть в настройках приватности'}>
              <Input type="number" min={0} step={5000} value={form.desired_salary ?? ''} onChange={e => set('desired_salary', e.target.value === '' ? null : Number(e.target.value))} />
            </Field>
            <Field label="Формат работы">
              <div className="flex flex-wrap gap-2">
                {Object.entries(WORK_FORMATS).map(([k, v]) => (
                  <button key={k} type="button" onClick={() => set('work_formats', toggle(form.work_formats, k))}
                    className={clsx('rounded-xl px-3 py-2 text-sm font-medium ring-1 transition', form.work_formats.includes(k) ? 'bg-fsp-deep text-white ring-fsp-deep' : 'bg-white ring-[#E4E1EE] hover:ring-fsp-lavender')}>{v}</button>
                ))}
              </div>
            </Field>
            <div className="sm:col-span-2">
              <Toggle checked={form.relocation} onChange={v => set('relocation', v)} label="Готов к переезду" />
              <Toggle checked={form.open_to_offers} onChange={v => set('open_to_offers', v)} label="Открыт к предложениям" hint="Если выключить, работодатели не смогут отправить приглашение" />
            </div>
          </div>
        </Card>

        <Card title="Контакты" subtitle="Работодатель увидит их только после того, как вы примете приглашение или откликнетесь сами">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="E-mail для связи"><Input type="email" value={form.contact_email} onChange={e => set('contact_email', e.target.value)} /></Field>
            <Field label="Телефон"><Input value={form.phone} onChange={e => set('phone', e.target.value)} placeholder="+7 900 000-00-00" /></Field>
            <Field label="Telegram"><Input value={form.telegram} onChange={e => set('telegram', e.target.value)} placeholder="@username" /></Field>
            <Field label="GitHub"><Input value={form.links.github ?? ''} onChange={e => set('links', { ...form.links, github: e.target.value })} placeholder="github.com/username" /></Field>
          </div>
          <Field label="О себе" className="mt-4"><Textarea rows={5} value={form.about} onChange={e => set('about', e.target.value)} placeholder="Чем занимаетесь, какие задачи решали, чем гордитесь" /></Field>
        </Card>
      </div>

      <Card title="Навыки и роли" subtitle={`${form.skills.length} навыков · подтверждено тестом: ${profile.verified_skills.length}`}>
        <Field label="Технический стек"><SkillPicker value={form.skills} onChange={v => set('skills', v)} verified={profile.verified_skills} /></Field>
        <div className="mt-5 grid gap-5 lg:grid-cols-2">
          <Field label="Роли в команде">
            <div className="flex flex-wrap gap-2">
              {Object.entries(ref.team_roles).map(([k, v]) => (
                <button key={k} type="button" onClick={() => set('roles', toggle(form.roles, k))}
                  className={clsx('chip ring-1', form.roles.includes(k) ? 'bg-fsp-deep text-white ring-fsp-deep' : 'bg-white text-slate-600 ring-slate-200')}>{v}</button>
              ))}
            </div>
          </Field>
          <Field label="Софт-скиллы">
            <div className="flex flex-wrap gap-2">
              {Object.entries(ref.soft_skills).map(([k, v]) => (
                <button key={k} type="button" onClick={() => set('soft_skills', toggle(form.soft_skills, k))}
                  className={clsx('chip ring-1', form.soft_skills.includes(k) ? 'bg-fsp-lavender text-white ring-fsp-lavender' : 'bg-white text-slate-600 ring-slate-200')}>{v}</button>
              ))}
            </div>
          </Field>
        </div>
      </Card>

      <Card title="Опыт работы" actions={<Button size="sm" variant="soft" icon={<Plus className="h-4 w-4" />}
        onClick={() => set('experience', [...form.experience, { company: '', position: '', start: '', end: null, description: '' }])}>Добавить</Button>}>
        {!form.experience.length && <p className="muted">Добавьте места работы или загрузите резюме.</p>}
        <div className="space-y-4">
          {form.experience.map((e, i) => {
            const upd = (k: keyof Exp, v: string | null) => set('experience', form.experience.map((x, j) => j === i ? { ...x, [k]: v } : x))
            return (
              <div key={i} className="rounded-2xl bg-surface p-4">
                <div className="grid gap-3 sm:grid-cols-[1fr_1fr_120px_120px_auto]">
                  <Input placeholder="Компания" value={e.company ?? ''} onChange={ev => upd('company', ev.target.value)} />
                  <Input placeholder="Должность" value={e.position ?? ''} onChange={ev => upd('position', ev.target.value)} />
                  <Input placeholder="ГГГГ-ММ" value={e.start ?? ''} onChange={ev => upd('start', ev.target.value)} />
                  <Input placeholder="по н. в." value={e.end ?? ''} onChange={ev => upd('end', ev.target.value || null)} />
                  <Button variant="ghost" size="sm" onClick={() => set('experience', form.experience.filter((_, j) => j !== i))} aria-label="Удалить"><Trash2 className="h-4 w-4" /></Button>
                </div>
                <Textarea className="mt-3 min-h-[64px]" placeholder="Задачи и достижения" value={e.description ?? ''} onChange={ev => upd('description', ev.target.value)} />
              </div>
            )
          })}
        </div>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[1.6fr_1fr]">
        <Card title="Образование и курсы" actions={<Button size="sm" variant="soft" icon={<Plus className="h-4 w-4" />} onClick={() => set('education', [...form.education, { title: '' }])}>Добавить</Button>}>
          <div className="space-y-2">
            {form.education.map((e, i) => {
              const upd = (patch: Partial<Edu>) => set('education', form.education.map((x, j) => j === i ? { ...x, ...patch } : x))
              return (
                <div key={i} className="grid gap-2 rounded-2xl bg-surface p-3 sm:grid-cols-[1.2fr_1.4fr_90px_auto]">
                  <Input value={e.title} placeholder="Вуз или курс" onChange={ev => upd({ title: ev.target.value })} />
                  <Input value={[e.level, e.specialty].filter(Boolean).join(' · ')} placeholder="Уровень · специальность"
                    onChange={ev => { const [lvl, ...rest] = ev.target.value.split(' · '); upd(rest.length ? { level: lvl || null, specialty: rest.join(' · ') || null } : { level: null, specialty: ev.target.value || null }) }} />
                  <Input type="number" value={e.year ?? ''} placeholder="Год" onChange={ev => upd({ year: ev.target.value ? Number(ev.target.value) : null })} />
                  <Button variant="ghost" onClick={() => set('education', form.education.filter((_, j) => j !== i))} aria-label="Удалить"><Trash2 className="h-4 w-4" /></Button>
                </div>
              )
            })}
            {!form.education.length && <p className="muted">Не указано</p>}
          </div>
        </Card>
        <Card title="Языки" actions={<Button size="sm" variant="soft" icon={<Plus className="h-4 w-4" />} onClick={() => set('languages', [...form.languages, { name: '', level: '' }])}>Добавить</Button>}>
          <div className="space-y-2">
            {form.languages.map((l, i) => (
              <div key={i} className="flex gap-2">
                <Input value={l.name} placeholder="Язык" onChange={ev => set('languages', form.languages.map((x, j) => j === i ? { ...x, name: ev.target.value } : x))} />
                <Input value={l.level ?? ''} placeholder="Уровень (B2, родной…)" onChange={ev => set('languages', form.languages.map((x, j) => j === i ? { ...x, level: ev.target.value } : x))} />
                <Button variant="ghost" onClick={() => set('languages', form.languages.filter((_, j) => j !== i))} aria-label="Удалить"><Trash2 className="h-4 w-4" /></Button>
              </div>
            ))}
            {!form.languages.length && <p className="muted">Не указано</p>}
          </div>
        </Card>
      </div>

      <div className="fixed inset-x-0 bottom-0 z-20 border-t border-slate-200 bg-white/90 px-4 py-3 backdrop-blur lg:pl-72">
        <div className="mx-auto flex max-w-[1280px] items-center justify-end gap-3 sm:px-6 lg:px-10">
          <span className="hidden text-xs text-slate-400 sm:block">Изменения профиля не меняют категорию — она определяется тестом</span>
          <Button onClick={() => save.mutate(form)} loading={save.isPending} icon={<Save className="h-4 w-4" />}>Сохранить профиль</Button>
        </div>
      </div>

      <Modal open={!!parsed} onClose={() => setParsed(null)} title="Распознано из резюме" wide
        footer={<><Button variant="secondary" onClick={() => setParsed(null)}>Отмена</Button>
          <Button onClick={applyParsed} icon={<Sparkles className="h-4 w-4" />}>Применить к профилю</Button></>}>
        {parsed && (
          <div className="space-y-4">
            <Alert tone="info">Проверьте найденные данные. После применения не забудьте сохранить профиль.</Alert>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(parsed.found as Record<string, boolean>).filter(([k]) => FIELD_LABEL[k]).map(([k, ok]) => (
                <Badge key={k} tone={ok ? 'green' : 'gray'} icon={ok ? <CircleCheck className="h-3 w-3" /> : undefined}>{FIELD_LABEL[k]}</Badge>
              ))}
            </div>
            <div className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
              <p><span className="text-slate-500">ФИО:</span> <b>{parsed.full_name ?? '—'}</b></p>
              <p><span className="text-slate-500">Должность:</span> {parsed.headline ?? '—'}</p>
              <p><span className="text-slate-500">Контакты:</span> {[parsed.email, parsed.phone, parsed.telegram].filter(Boolean).join(', ') || '—'}</p>
              <p><span className="text-slate-500">Город:</span> {parsed.city ?? '—'}</p>
              <p><span className="text-slate-500">Стаж:</span> {years(parsed.experience_years)}</p>
              <p><span className="text-slate-500">Грейд по резюме:</span> {parsed.claimed_grade ? gradeName(parsed.claimed_grade) : '—'}</p>
              <p><span className="text-slate-500">Зарплата:</span> {parsed.desired_salary ? rub(parsed.desired_salary) : '—'}</p>
              <p><span className="text-slate-500">Формат:</span> {parsed.work_formats?.length ? parsed.work_formats.map((f: string) => WORK_FORMATS[f] ?? f).join(', ') : '—'}
                {parsed.relocation != null && <span className="text-slate-500"> · {parsed.relocation ? 'готов к переезду' : 'без переезда'}</span>}</p>
              {Object.keys(parsed.links ?? {}).length > 0 && <p className="sm:col-span-2"><span className="text-slate-500">Ссылки:</span> {Object.entries(parsed.links).map(([k, v]) => `${LINK_LABEL[k] ?? k}: ${v}`).join(' · ')}</p>}
              <p className="sm:col-span-2"><span className="text-slate-500">Специализация (классификатор):</span> {parsed.specialization ? `${specName(parsed.specialization)} · уверенность ${Math.round(parsed.specialization_confidence * 100)}%` : '—'}</p>
            </div>
            <div>
              <p className="label">Навыки ({parsed.skills.length})</p>
              <div className="flex flex-wrap gap-1.5">{parsed.skills.map((s: string) => <Badge key={s} tone="pink">{skillName(s)}</Badge>)}</div>
            </div>
            {!!parsed.skills_unrecognized?.length && <p className="text-xs text-slate-500">Не нашлось в онтологии навыков: {parsed.skills_unrecognized.join(', ')} — их можно добавить вручную.</p>}
            {!!parsed.soft_skills?.length && (
              <div>
                <p className="label">Софт-скиллы</p>
                <div className="flex flex-wrap gap-1.5">{parsed.soft_skills.map((s: string) => (
                  <Badge key={s} tone="lavender">{ref.soft_skills[s] ?? s}{parsed.soft_skills_evidence?.[s] ? ' · по опыту' : ''}</Badge>))}</div>
                {Object.entries(parsed.soft_skills_evidence ?? {}).map(([k, v]) => (
                  <p key={k} className="mt-1 text-xs text-slate-500"><b>{ref.soft_skills[k] ?? k}:</b> {String(v)}</p>))}
              </div>
            )}
            {!!parsed.roles?.length && <div><p className="label">Роли</p><div className="flex flex-wrap gap-1.5">{parsed.roles.map((r: string) => <Badge key={r} tone="lavender">{ref.team_roles[r] ?? r}</Badge>)}</div></div>}
            {!!parsed.experience?.length && (
              <div>
                <p className="label">Опыт работы</p>
                <ul className="space-y-1.5 text-sm">{parsed.experience.map((e: Exp, i: number) => (
                  <li key={i}><b>{e.position || 'Должность'}</b> · {e.company || 'Компания'} <span className="text-slate-400">({e.start} — {e.end ?? 'н. в.'})</span></li>
                ))}</ul>
              </div>
            )}
            {!!parsed.education?.length && (
              <div>
                <p className="label">Образование</p>
                <ul className="space-y-1 text-sm">{parsed.education.map((e: Edu, i: number) => (
                  <li key={i}><b>{e.title}</b>{[e.level, e.specialty, e.year].filter(Boolean).length ? ` · ${[e.level, e.specialty, e.year].filter(Boolean).join(', ')}` : ''}</li>))}</ul>
              </div>
            )}
            {!!parsed.languages?.length && <p className="text-sm"><span className="text-slate-500">Языки:</span> {parsed.languages.map((l: Lang) => `${l.name}${l.level ? ` (${l.level})` : ''}`).join(', ')}</p>}
            {parsed.about && <p className="line-clamp-3 text-sm text-slate-600"><span className="text-slate-500">О себе:</span> {parsed.about}</p>}
          </div>
        )}
      </Modal>
    </div>
  )
}
