import { useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { Camera, EyeOff, Gauge, Zap } from 'lucide-react'
import { api } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { useReference } from '@/lib/reference'
import { Alert, Button, Checkbox, ChoiceCard, Modal } from './ui'

export type TestMode = 'full' | 'express'

const MODES: Record<TestMode, { title: string; hint: string; icon: ReactNode }> = {
  express: { title: 'Экспресс · ≈ 7 минут', icon: <Zap className="h-4 w-4 text-fsp-pink" />,
    hint: '8 заданий с коротким ответом. Покажет вероятный грейд — категорию не присваивает и попытку не тратит.' },
  full: { title: 'Полный · 20–40 минут', icon: <Gauge className="h-4 w-4 text-fsp-pink" />,
    hint: '12–24 задания. Подтверждает грейд и присваивает категорию, которую видят работодатели.' },
}

export function ModePicker({ value, onChange }: { value: TestMode; onChange: (m: TestMode) => void }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {(['full', 'express'] as const).map(m => (
        <ChoiceCard key={m} selected={value === m} onClick={() => onChange(m)} hint={MODES[m].hint}
          title={<span className="flex items-center gap-2">{MODES[m].icon}{MODES[m].title}</span>} />
      ))}
    </div>
  )
}

/** Включён ли вход «без регистрации» (GUEST_MODE на сервере). */
export function useGuestMode() {
  const { data } = useQuery({ queryKey: ['public-stats'], queryFn: () => api('/public/stats') })
  return !!data?.guest_mode
}

const pill = (on: boolean) => clsx('rounded-xl px-3 py-1.5 text-sm font-semibold ring-1 transition',
  on ? 'bg-fsp-deep text-white ring-fsp-deep' : 'bg-white text-slate-600 ring-slate-200 hover:ring-fsp-lavender')

/** «Попробовать как кандидат»: демо-аккаунт в один клик и сразу тест — без e-mail, пароля и опроса. */
export function GuestStartModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { ref } = useReference()
  const { signIn } = useAuth()
  const nav = useNavigate()
  const [spec, setSpec] = useState('backend')
  const [lang, setLang] = useState<string | null>(null)
  const [grade, setGrade] = useState('junior')
  const [mode, setMode] = useState<TestMode>('express')
  const [consent, setConsent] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const s = ref?.specializations.find(x => x.code === spec)
  const language = lang && s?.languages.includes(lang) ? lang : s?.languages[0]
  const directions = Array.from(new Set(ref?.specializations.map(x => x.direction) ?? []))

  const start = async () => {
    setBusy(true); setError(null)
    try {
      const r = await api<{ access_token: string }>('/auth/guest', { body: { specialization: spec, language, claimed_grade: grade, consent_pd: consent } })
      await signIn(r.access_token)
      const sess = await api<{ token: string }>('/testing/sessions', { body: { grade, mode } })
      nav(`/candidate/testing/${sess.token}`)
    } catch (e: any) { setError(e.message) } finally { setBusy(false) }
  }

  return (
    <Modal open={open} onClose={onClose} wide title="Попробовать как кандидат — без регистрации"
      footer={<><Button variant="secondary" onClick={onClose}>Отмена</Button>
        <Button disabled={!consent || !ref} loading={busy} onClick={start} icon={<Zap className="h-4 w-4" />}>Начать тест</Button></>}>
      <div className="space-y-5">
        <p className="text-sm leading-relaxed text-slate-500">Создадим демо-аккаунт кандидата и сразу запустим тест: без e-mail, пароля и опроса.
          Задания — из того же банка и на той же шкале, что и в основном тесте.</p>
        {error && <Alert tone="error">{error}</Alert>}
        <div>
          <p className="label">Специализация</p>
          <div className="space-y-2.5">
            {directions.map(d => (
              <div key={d} className="grid gap-1.5 sm:grid-cols-[9.5rem_1fr] sm:items-start sm:gap-3">
                <span className="text-xs text-slate-400 sm:pt-2">{d}</span>
                <div className="flex flex-wrap gap-2">
                  {ref!.specializations.filter(x => x.direction === d).map(x => (
                    <button key={x.code} type="button" onClick={() => { setSpec(x.code); setLang(null) }} className={pill(spec === x.code)}>{x.name}</button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
        {s && s.languages.length > 1 && (
          <div>
            <p className="label">Язык заданий с кодом</p>
            <div className="flex flex-wrap gap-2">
              {s.languages.map(l => <button key={l} type="button" onClick={() => setLang(l)} className={pill(language === l)}>{ref?.languages[l] ?? l}</button>)}
            </div>
          </div>
        )}
        <div>
          <p className="label">Ваш уровень, по ощущениям</p>
          <div className="flex flex-wrap gap-2">
            {ref?.grades.map(g => <button key={g.code} type="button" onClick={() => setGrade(g.code)} className={pill(grade === g.code)}>{g.name}</button>)}
          </div>
          <p className="mt-1.5 text-xs text-slate-400">Тест адаптивный: начнёт с этого уровня и подстроится под ваши ответы.</p>
        </div>
        <div>
          <p className="label">Формат</p>
          <ModePicker value={mode} onChange={setMode} />
        </div>
        <ul className="space-y-2 rounded-2xl bg-surface p-3.5 text-xs leading-relaxed text-slate-600">
          <li className="flex gap-2"><Camera className="mt-0.5 h-3.5 w-3.5 shrink-0 text-fsp-pink" />Прокторинг как в основном тесте: снимок экрана или копирование задания — предупреждение, повтор завершает тест.</li>
          <li className="flex gap-2"><EyeOff className="mt-0.5 h-3.5 w-3.5 shrink-0 text-fsp-pink" />Демо-аккаунт не виден работодателям и удаляется вместе с ответами через 2 дня.</li>
        </ul>
        <div className="rounded-2xl border border-line p-3.5">
          <Checkbox checked={consent} onChange={setConsent} label={<span className="text-xs leading-relaxed text-slate-600">
            Согласен(на) на обработку ответов теста для оценки уровня (152-ФЗ). Персональные данные не запрашиваются.</span>} />
        </div>
      </div>
    </Modal>
  )
}
