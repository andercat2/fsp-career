import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { ArrowLeft, ArrowRight, Clock, Fingerprint, Lock, Play, Repeat, RotateCcw, ShieldCheck, Sparkles, Timer } from 'lucide-react'
import { api } from '@/lib/api'
import { useReference } from '@/lib/reference'
import { useToast } from '@/lib/toast'
import { date } from '@/lib/format'
import { Alert, Badge, Button, Card, ChoiceCard, PageHeader, PageLoader, Progress } from '@/components/ui'

type Survey = {
  industries: string[]; specialization: string; language: string | null; experience: string; roles: string[]
  work_formats: string[]; claimed_grade: string; fsp_participant: boolean
}

function SurveyWizard({ onDone, initial }: { onDone: (warnings: string[]) => void; initial?: Partial<Survey> }) {
  const { data: survey } = useQuery({ queryKey: ['survey'], queryFn: () => api('/testing/survey') })
  const { push } = useToast()
  const [step, setStep] = useState(0)
  const [a, setA] = useState<Survey>({
    industries: [], specialization: '', language: null, experience: '', roles: [], work_formats: [], claimed_grade: '',
    fsp_participant: false, ...initial,
  })
  const submit = useMutation({
    mutationFn: () => api('/testing/survey', { body: a }),
    onSuccess: (r: any) => onDone(r.warnings),
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
          <h3 className="text-lg font-bold">{q.specialization.title}</h3>
          {groups.map(g => (
            <div key={g}>
              <p className="label">{g}</p>
              <div className="grid gap-3 sm:grid-cols-2">
                {q.specialization.options.filter((o: any) => o.group === g).map((o: any) => (
                  <ChoiceCard key={o.value} selected={a.specialization === o.value} title={o.label} hint={o.hint}
                    onClick={() => setA(s => ({ ...s, specialization: o.value, language: q.language.options_by[o.value][0].value }))} />
                ))}
              </div>
            </div>
          ))}
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
        <li className="flex gap-3"><Timer className="mt-0.5 h-4 w-4 shrink-0 text-fsp-pink" /><span><b className="text-fsp-deep">С таймером.</b> На каждое задание 1–4 минуты. Вернуться к предыдущему нельзя.</span></li>
        <li className="flex gap-3"><Clock className="mt-0.5 h-4 w-4 shrink-0 text-fsp-pink" /><span><b className="text-fsp-deep">Честные ограничения.</b> Смена грейда — не чаще раза в 90 дней, повтор того же уровня — через 30 дней. Не прошли — можно сразу уровнем ниже; уверенно прошли — сразу уровнем выше.</span></li>
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
  const [resurvey, setResurvey] = useState(false)
  const [warnings, setWarnings] = useState<string[]>([])
  const [grade, setGrade] = useState<string | null>(null)
  const { data: el, isLoading } = useQuery({ queryKey: ['eligibility'], queryFn: () => api('/testing/eligibility') })
  const start = useMutation({
    mutationFn: (g: string) => api('/testing/sessions', { body: { grade: g } }),
    onSuccess: (s: any) => nav(`/candidate/testing/${s.token}`),
    onError: (e: any) => push(e.message, 'error'),
  })
  const recommended = useMemo(() => el?.grades?.find((g: any) => g.recommended && g.allowed)?.grade, [el])
  if (isLoading || !el) return <PageLoader />
  const selected = grade ?? recommended ?? el.grades?.find((g: any) => g.allowed)?.grade
  const showSurvey = !el.ready || resurvey

  return (
    <div>
      <PageHeader title="Опрос и тестирование"
        subtitle="Категория, которую видит работодатель, определяется не резюме, а этим путём: опрос → выбор грейда → адаптивный тест."
        actions={el.ready && !resurvey && <Button variant="secondary" icon={<RotateCcw className="h-4 w-4" />} onClick={() => setResurvey(true)}>Пройти опрос заново</Button>} />
      <div className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
        <div className="space-y-6">
          {showSurvey ? (
            <SurveyWizard onDone={w => { setWarnings(w); setResurvey(false); qc.invalidateQueries({ queryKey: ['eligibility'] }); qc.invalidateQueries({ queryKey: ['cand-dashboard'] }) }} />
          ) : (<>
            {warnings.map((w, i) => <Alert key={i} tone="warn">{w}</Alert>)}
            {el.in_progress && (
              <Alert tone="info" title="У вас есть незавершённый тест" icon={<Play className="h-4 w-4" />}>
                <Button size="sm" className="mt-2" onClick={() => nav(`/candidate/testing/${el.in_progress}`)}>Продолжить</Button>
              </Alert>
            )}
            <Card title="Выберите уровень теста" subtitle={<>Специализация: <b className="text-fsp-deep">{specName(el.specialization)}</b>{el.current_grade && <> · текущий грейд: <b className="text-fsp-deep">{el.grades.find((g: any) => g.grade === el.current_grade)?.name}</b></>}</>}>
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
                  loading={start.isPending} onClick={() => selected && start.mutate(selected)} icon={<Play className="h-5 w-5" />}>Начать тест</Button>
              </div>
            </Card>
          </>)}
        </div>
        <HowItWorks spec={el.specialization} lang={el.language} />
      </div>
    </div>
  )
}
