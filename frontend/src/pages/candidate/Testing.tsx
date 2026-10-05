import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { ArrowLeft, ArrowRight, Camera, Clock, Fingerprint, Layers, Lock, Play, Repeat, RotateCcw, ShieldCheck, Sparkles, Timer } from 'lucide-react'
import { api } from '@/lib/api'
import { useReference } from '@/lib/reference'
import { useToast } from '@/lib/toast'
import { date } from '@/lib/format'
import { Alert, Badge, Button, Card, ChoiceCard, Field, Input, PageHeader, PageLoader, Progress } from '@/components/ui'
import { MAX_RESUMES, ResumeTabs, resumeLabel, useResumes } from '@/components/Resumes'
import { StartTestModal } from '@/components/StartTestModal'

type Survey = {
  industries: string[]; specialization: string; language: string | null; experience: string; roles: string[]
  work_formats: string[]; claimed_grade: string; fsp_participant: boolean
}

type Mode = 'main' | 'resume' | 'new'

/** Опрос по специализации. mode: main — основное резюме; resume — дополнительное (специализация фиксирована);
 *  new — новое резюме под другую специализацию (создаётся вместе с ответами). */
function SurveyWizard({ onDone, initial, mode = 'main', resumeId = 0, taken = [] }: {
  onDone: (warnings: string[], resumeId: number) => void; initial?: Partial<Survey>; mode?: Mode; resumeId?: number; taken?: string[]
}) {
  const { data: survey } = useQuery({ queryKey: ['survey'], queryFn: () => api('/testing/survey') })
  const { push } = useToast()
  const [step, setStep] = useState(0)
  const [title, setTitle] = useState('')
  const [a, setA] = useState<Survey>({
    industries: [], specialization: '', language: null, experience: '', roles: [], work_formats: [], claimed_grade: '',
    fsp_participant: false, ...initial,
  })
  const submit = useMutation({
    mutationFn: () => mode === 'new'
      ? api('/candidate/resumes', { body: { ...a, title: title.trim() || null } })
      : api('/testing/survey', { body: { ...a, resume_id: resumeId } }),
    onSuccess: (r: any) => onDone(r.warnings, mode === 'new' ? r.resume.id : resumeId),
    onError: (e: any) => push(e.message, 'error'),
  })
  if (!survey) return <PageLoader />
  const q = Object.fromEntries(survey.questions.map((x: any) => [x.id, x]))
  const langs = a.specialization ? q.language.options_by[a.specialization] : []
  const steps = [
    { title: 'Специализация', valid: !!a.specialization },
    { title: 'Опыт и грейд', valid: !!a.experience && !!a.claimed_grade },
    { title: 'Отрасль и формат', valid: true },
    { title: 'ФСП', valid: true },
  ]
  const groups = Array.from(new Set(q.specialization.options.map((o: any) => o.group))) as string[]
  const tog = (arr: string[], v: string, max?: number) => arr.includes(v) ? arr.filter(x => x !== v) : max && arr.length >= max ? arr : [...arr, v]

  return (
    <Card>
      <div className="mb-6">
        <div className="mb-2 flex items-center justify-between text-xs font-semibold text-slate-500">
          <span>Шаг {step + 1} из {steps.length}: {steps[step].title}</span><span>{Math.round(((step + 1) / steps.length) * 100)}%</span>
        </div>
        <Progress value={(step + 1) / steps.length} />
      </div>

      {step === 0 && (
        <div className="space-y-6">
          <h3 className="text-lg font-bold">{mode === 'new' ? 'Специализация нового резюме' : q.specialization.title}</h3>
          {mode === 'new' && <p className="-mt-3 text-sm text-slate-500">По ней пройдёте отдельный тест и получите ещё одну категорию. Основная категория не изменится.</p>}
          {mode === 'resume' && <p className="-mt-3 text-sm text-slate-500">Специализация резюме фиксирована — для другой добавьте новое резюме.</p>}
          {groups.map(g => (
            <div key={g}>
              <p className="label">{g}</p>
              <div className="grid gap-3 sm:grid-cols-2">
                {q.specialization.options.filter((o: any) => o.group === g).map((o: any) => {
                  const busy = mode === 'new' && taken.includes(o.value)
                  const locked = mode === 'resume' && o.value !== a.specialization
                  return (
                    <ChoiceCard key={o.value} selected={a.specialization === o.value} title={o.label} hint={o.hint} disabled={busy || locked}
                      badge={busy ? <Badge tone="gray">уже есть резюме</Badge> : undefined}
                      onClick={() => setA(s => ({ ...s, specialization: o.value, language: q.language.options_by[o.value][0].value }))} />
                  )
                })}
              </div>
            </div>
          ))}
          {mode === 'new' && a.specialization && (
            <Field label="Заголовок резюме (необязательно)" hint="Так его увидит работодатель; навыки и ожидания можно уточнить в профиле">
              <Input value={title} onChange={e => setTitle(e.target.value)} placeholder="Например, «DevOps-инженер (Kubernetes, CI/CD)»" />
            </Field>
          )}
          {langs.length > 1 && (
            <div>
              <p className="label">{q.language.title} — задания с кодом будут на этом языке</p>
              <div className="flex flex-wrap gap-2">
                {langs.map((l: any) => (
                  <button key={l.value} onClick={() => setA(s => ({ ...s, language: l.value }))}
                    className={clsx('rounded-xl px-4 py-2 text-sm font-semibold ring-1', a.language === l.value ? 'bg-fsp-deep text-white ring-fsp-deep' : 'bg-white ring-slate-200')}>{l.label}</button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {step === 1 && (
        <div className="space-y-6">
          <div>
            <h3 className="text-lg font-bold">{q.experience.title}</h3>
            <div className="mt-3 flex flex-wrap gap-2">
              {q.experience.options.map((o: any) => (
                <button key={o.value} onClick={() => setA(s => ({ ...s, experience: o.value }))}
                  className={clsx('rounded-xl px-4 py-2.5 text-sm font-semibold ring-1', a.experience === o.value ? 'bg-fsp-deep text-white ring-fsp-deep' : 'bg-white ring-slate-200 hover:ring-fsp-lavender')}>{o.label}</button>
              ))}
            </div>
          </div>
          <div>
            <h3 className="text-lg font-bold">{q.claimed_grade.title}</h3>
            <p className="mt-1 text-sm text-slate-500">Выберите честно: тест покажет реальный уровень. Если не получится — можно пройти тест уровнем ниже, грейд не понижается принудительно.</p>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              {q.claimed_grade.options.map((o: any) => (
                <ChoiceCard key={o.value} selected={a.claimed_grade === o.value} title={o.label} hint={o.hint} onClick={() => setA(s => ({ ...s, claimed_grade: o.value }))} />
              ))}
            </div>
          </div>
        </div>
      )}

      {step === 2 && (
        <div className="space-y-6">
          <div>
            <h3 className="text-lg font-bold">{q.industries.title} <span className="text-sm font-medium text-slate-400">(до 3)</span></h3>
            <div className="mt-3 flex flex-wrap gap-2">
              {q.industries.options.map((o: any) => (
                <button key={o.value} onClick={() => setA(s => ({ ...s, industries: tog(s.industries, o.value, 3) }))}
                  className={clsx('chip px-3 py-1.5 text-sm ring-1', a.industries.includes(o.value) ? 'bg-fsp-pink text-white ring-fsp-pink' : 'bg-white text-slate-600 ring-slate-200')}>{o.label}</button>
              ))}
            </div>
          </div>
          <div>
            <h3 className="text-lg font-bold">{q.roles.title}</h3>
            <div className="mt-3 flex flex-wrap gap-2">
              {q.roles.options.map((o: any) => (
                <button key={o.value} onClick={() => setA(s => ({ ...s, roles: tog(s.roles, o.value) }))}
                  className={clsx('chip px-3 py-1.5 text-sm ring-1', a.roles.includes(o.value) ? 'bg-fsp-deep text-white ring-fsp-deep' : 'bg-white text-slate-600 ring-slate-200')}>{o.label}</button>
              ))}
            </div>
          </div>
          <div>
            <h3 className="text-lg font-bold">{q.work_formats.title}</h3>
            <div className="mt-3 flex flex-wrap gap-2">
              {q.work_formats.options.map((o: any) => (
                <button key={o.value} onClick={() => setA(s => ({ ...s, work_formats: tog(s.work_formats, o.value) }))}
                  className={clsx('rounded-xl px-4 py-2 text-sm font-semibold ring-1', a.work_formats.includes(o.value) ? 'bg-fsp-deep text-white ring-fsp-deep' : 'bg-white ring-slate-200')}>{o.label}</button>
              ))}
            </div>
          </div>
        </div>
      )}

      {step === 3 && (
        <div className="space-y-4">
          <h3 className="text-lg font-bold">{q.fsp_participant.title}</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            <ChoiceCard selected={a.fsp_participant} onClick={() => setA(s => ({ ...s, fsp_participant: true }))} title="Да, участвовал(а)"
              hint="После теста привяжите ФСП ID в настройках — результаты подтянутся из реестра и усилят профиль." />
            <ChoiceCard selected={!a.fsp_participant} onClick={() => setA(s => ({ ...s, fsp_participant: false }))} title="Нет"
              hint="Это нормально: без истории ФСП вы участвуете в подборе на общих основаниях." />
          </div>
        </div>
      )}

      <div className="mt-8 flex items-center justify-between gap-3">
        <Button variant="ghost" disabled={step === 0} onClick={() => setStep(s => s - 1)} icon={<ArrowLeft className="h-4 w-4" />}>Назад</Button>
        {step < steps.length - 1
          ? <Button disabled={!steps[step].valid} onClick={() => setStep(s => s + 1)}>Далее <ArrowRight className="h-4 w-4" /></Button>
          : <Button loading={submit.isPending} onClick={() => submit.mutate()} icon={<ShieldCheck className="h-4 w-4" />}>Сохранить ответы</Button>}
      </div>
    </Card>
  )
}

function HowItWorks({ spec, lang }: { spec?: string | null; lang?: string | null }) {
  const { ref, domainName } = useReference()
  const s = ref?.specializations.find(x => x.code === spec)
  const bp = s ? s.blueprints[lang && s.blueprints[lang] ? lang : s.languages[0]] : null
  return (
    <Card title="Как устроен тест">
      <ul className="space-y-3 text-sm text-slate-600">
        <li className="flex gap-3"><Repeat className="mt-0.5 h-4 w-4 shrink-0 text-fsp-pink" /><span><b className="text-fsp-deep">Адаптивный.</b> Следующее задание подбирается под текущую оценку уровня: после верного ответа — сложнее, после ошибки — проще. 12–24 задания.</span></li>
        <li className="flex gap-3"><Fingerprint className="mt-0.5 h-4 w-4 shrink-0 text-fsp-pink" /><span><b className="text-fsp-deep">Уникальный.</b> Каждое задание — ваш личный вариант: свои числа, данные, код. Ответы других кандидатов не помогут.</span></li>
        <li className="flex gap-3"><Timer className="mt-0.5 h-4 w-4 shrink-0 text-fsp-pink" /><span><b className="text-fsp-deep">С таймером по сложности.</b> От 1 до 5 минут: базовое время зависит от формата (выбор, код, расчёт) и увеличивается для трудных заданий. Вернуться к предыдущему нельзя.</span></li>
        <li className="flex gap-3"><Camera className="mt-0.5 h-4 w-4 shrink-0 text-fsp-pink" /><span><b className="text-fsp-deep">С прокторингом.</b> Снимок экрана, печать или копирование задания: первый раз — предупреждение, второй — тест завершается досрочно с пониженной оценкой. Уход со вкладки учитывается.</span></li>
        <li className="flex gap-3"><Clock className="mt-0.5 h-4 w-4 shrink-0 text-fsp-pink" /><span><b className="text-fsp-deep">Честные ограничения.</b> Смена грейда и повтор того же уровня — не чаще раза в месяц. Не прошли — можно принять грейд ниже по этому же тесту (если тест уверенно его показал) или пройти тест уровнем ниже без ожидания; уверенно прошли — тест уровнем выше доступен без ожидания, начинаете его, когда будете готовы.</span></li>
      </ul>
      {bp && (
        <div className="mt-5 border-t border-slate-100 pt-4">
          <p className="label">Состав теста: {s?.name}</p>
          <div className="space-y-2">
            {Object.entries(bp).sort((x, y) => y[1] - x[1]).map(([d, w]) => (
              <div key={d} className="flex items-center gap-3 text-sm">
                <span className="w-44 shrink-0 truncate text-slate-600">{domainName(d)}</span>
                <div className="h-1.5 flex-1 rounded-full bg-slate-100"><div className="h-full rounded-full bg-fsp-lavender" style={{ width: `${w * 100 * 2.5}%` }} /></div>
                <span className="w-9 text-right text-xs text-slate-400">{Math.round(w * 100)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  )
}

export function Testing() {
  const nav = useNavigate()
  const qc = useQueryClient()
  const { push } = useToast()
  const { specName } = useReference()
  const [params, setParams] = useSearchParams()
  const isNew = params.get('new') === '1'
  const rid = Number(params.get('resume') ?? 0) || 0
  const [resurvey, setResurvey] = useState(false)
  const [warnings, setWarnings] = useState<string[]>([])
  const [grade, setGrade] = useState<string | null>(null)
  const [confirm, setConfirm] = useState<string | null>(null)
  const { data: resumes } = useResumes()
  const { data: el, isLoading } = useQuery({ queryKey: ['eligibility', rid], queryFn: () => api(`/testing/eligibility?resume_id=${rid}`), enabled: !isNew })
  useEffect(() => { setGrade(null); setResurvey(false) }, [rid, isNew])
  const start = useMutation({
    mutationFn: (g: string) => api('/testing/sessions', { body: { grade: g, resume_id: rid } }),
    onSuccess: (s: any) => nav(`/candidate/testing/${s.token}`),
    onError: (e: any) => push(e.message, 'error'),
  })
  const recommended = useMemo(() => el?.grades?.find((g: any) => g.recommended && g.allowed)?.grade, [el])
  if (!resumes || (!isNew && (isLoading || !el))) return <PageLoader />
  const current = resumes.find(r => r.id === rid) ?? resumes[0]
  const mainReady = !!resumes[0]?.survey_completed_at
  const canAdd = mainReady && resumes.length < MAX_RESUMES
  const selected = grade ?? recommended ?? el?.grades?.find((g: any) => g.allowed)?.grade
  const showSurvey = !isNew && (!el.ready || resurvey)
  const refresh = () => { qc.invalidateQueries({ queryKey: ['eligibility'] }); qc.invalidateQueries({ queryKey: ['cand-dashboard'] }); qc.invalidateQueries({ queryKey: ['cand-resumes'] }); qc.invalidateQueries({ queryKey: ['cand-profile'] }) }
  const goTo = (id: number) => setParams(id ? { resume: String(id) } : {})
  const taken = resumes.map(r => r.specialization).filter(Boolean) as string[]

  return (
    <div>
      <PageHeader title="Опрос и тестирование"
        subtitle="Категория, которую видит работодатель, определяется не резюме, а этим путём: опрос → выбор грейда → адаптивный тест. У каждого резюме — своя специализация и своя категория."
        actions={!isNew && el.ready && !resurvey && <Button variant="secondary" icon={<RotateCcw className="h-4 w-4" />} onClick={() => setResurvey(true)}>Пройти опрос заново</Button>} />
      {mainReady && <ResumeTabs resumes={resumes} active={isNew ? 'new' : current.id} onSelect={goTo} onNew={() => setParams({ new: '1' })} canAdd={canAdd} />}
      <div className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
        <div className="space-y-6">
          {isNew ? (
            canAdd ? <SurveyWizard key="new" mode="new" taken={taken} onDone={(w, id) => { setWarnings(w); refresh(); goTo(id); push('Резюме добавлено — теперь пройдите тест по новой специализации') }} />
              : <Alert tone="info" icon={<Layers className="h-4 w-4" />}>{mainReady ? `Можно вести до ${MAX_RESUMES} резюме — удалите лишнее в профиле, чтобы добавить новое.` : 'Сначала пройдите опрос по основной специализации.'}</Alert>
          ) : showSurvey ? (
            <SurveyWizard key={`s-${current.id}`} mode={current.main ? 'main' : 'resume'} resumeId={current.id}
              initial={current.main ? undefined : { specialization: current.specialization ?? '', language: current.primary_language, claimed_grade: current.claimed_grade ?? '' }}
              onDone={w => { setWarnings(w); setResurvey(false); refresh() }} />
          ) : (<>
            {warnings.map((w, i) => <Alert key={i} tone="warn">{w}</Alert>)}
            {el.in_progress && (
              <Alert tone="info" title="У вас есть незавершённый тест" icon={<Play className="h-4 w-4" />}>
                <Button size="sm" className="mt-2" onClick={() => nav(`/candidate/testing/${el.in_progress}`)}>Продолжить</Button>
              </Alert>
            )}
            <Card title="Выберите уровень теста" subtitle={<>Резюме: <b className="text-fsp-deep">{resumeLabel(current)}</b> · специализация: <b className="text-fsp-deep">{specName(el.specialization)}</b>{el.current_grade && <> · текущий грейд: <b className="text-fsp-deep">{el.grades.find((g: any) => g.grade === el.current_grade)?.name}</b></>}</>}>
              <div className="grid gap-3 sm:grid-cols-2">
                {el.grades.map((g: any) => (
                  <ChoiceCard key={g.grade} selected={selected === g.grade && g.allowed} disabled={!g.allowed} onClick={() => setGrade(g.grade)}
                    title={<span className="flex items-center gap-2">{!g.allowed && <Lock className="h-4 w-4 text-slate-400" />}{g.name}</span>}
                    hint={g.reason ? <>{g.reason}{g.available_from && <> · доступно с {date(g.available_from)}</>}</> : undefined}
                    badge={g.recommended && g.allowed ? <Badge tone="pink" icon={<Sparkles className="h-3 w-3" />}>рекомендуем</Badge> : undefined} />
                ))}
              </div>
              <div className="mt-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-surface p-4">
                <p className="text-sm text-slate-600">Тест займёт 20–40 минут. Обеспечьте спокойную обстановку — время на задание ограничено.</p>
                <Button size="lg" disabled={!selected || !el.grades.find((g: any) => g.grade === selected)?.allowed}
                  onClick={() => selected && setConfirm(selected)} icon={<Play className="h-5 w-5" />}>Начать тест</Button>
              </div>
            </Card>
          </>)}
        </div>
        <HowItWorks spec={isNew ? null : el.specialization} lang={isNew ? null : el.language} />
      </div>
      <StartTestModal grade={confirm} title={confirm ? el?.grades?.find((g: any) => g.grade === confirm)?.name : undefined}
        loading={start.isPending} onClose={() => setConfirm(null)} onConfirm={() => confirm && start.mutate(confirm)} />
    </div>
  )
}
