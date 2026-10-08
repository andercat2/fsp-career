import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Building2, KeyRound, Mail, ShieldCheck, UserRound, Zap } from 'lucide-react'
import clsx from 'clsx'
import { Blobs, EASE } from '@/lib/motion'
import { api } from '@/lib/api'
import { homeFor, useAuth } from '@/lib/auth'
import { useToast } from '@/lib/toast'
import { Alert, Button, Checkbox, Field, Input, PageLoader } from '@/components/ui'
import { Logo } from '@/components/Layout'
import { GuestStartModal, useGuestMode } from '@/components/GuestStart'

const FEATURES = [
  { icon: <ShieldCheck className="h-4 w-4" />, t: 'Категория подтверждается адаптивным тестом' },
  { icon: <Mail className="h-4 w-4" />, t: 'Приглашения сразу с вилкой зарплаты' },
  { icon: <KeyRound className="h-4 w-4" />, t: 'Контакты — только после вашего согласия' },
]

function AuthLayout({ title, subtitle, children }: { title: string; subtitle?: ReactNode; children: ReactNode }) {
  return (
    <div className="grid min-h-screen bg-white lg:grid-cols-[1fr_1.05fr]">
      <aside className="bg-hero noise relative hidden flex-col justify-between overflow-hidden p-10 text-white lg:flex">
        <Blobs className="opacity-60" />
        <div className="relative"><Logo dark /></div>
        <div className="relative">
          <motion.p initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, ease: EASE }}
            className="text-[40px] font-extrabold leading-[1.05] tracking-tightest">Категория по тесту,<br /><span className="text-gradient">а не по ключевым словам</span></motion.p>
          <div className="mt-8 space-y-3">
            {FEATURES.map((f, i) => (
              <motion.div key={f.t} initial={{ opacity: 0, x: -16 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.6, ease: EASE, delay: 0.3 + i * 0.12 }}
                className="flex w-fit items-center gap-3 rounded-2xl border border-white/10 bg-white/[0.06] px-4 py-3 text-sm text-white/85 backdrop-blur-xl">
                <span className="grid h-8 w-8 place-items-center rounded-xl bg-fsp-pink/25 text-[#ffc2d6]">{f.icon}</span>{f.t}
              </motion.div>
            ))}
          </div>
        </div>
        <img src="/brand/fsp-logo-white.png" alt="ФСП" className="relative h-8 w-auto self-start opacity-70" />
      </aside>
      <main className="relative flex flex-col justify-center px-4 py-10 sm:px-10">
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.55, ease: EASE }} className="mx-auto w-full max-w-md">
          <div className="mb-10 lg:hidden"><Logo /></div>
          <h1 className="text-[30px] font-extrabold tracking-tight">{title}</h1>
          {subtitle && <p className="mt-2 text-sm text-slate-500">{subtitle}</p>}
          <div className="mt-8">{children}</div>
        </motion.div>
      </main>
    </div>
  )
}

const DEMO = [
  { email: 'candidate@demo.ru', label: 'Кандидат с категорией', icon: <UserRound className="h-4 w-4" /> },
  { email: 'newbie@demo.ru', label: 'Новый кандидат (без теста)', icon: <UserRound className="h-4 w-4" /> },
  { email: 'employer@demo.ru', label: 'Работодатель «ТехноПульс»', icon: <Building2 className="h-4 w-4" /> },
  { email: 'admin@demo.ru', label: 'Администратор', icon: <KeyRound className="h-4 w-4" /> },
]

async function startFspLogin(push: (t: string, k?: 'error') => void) {
  try {
    const r = await api<{ authorize_url: string }>('/fsp/login')
    window.location.href = r.authorize_url
  } catch (e: any) { push(e.message, 'error') }
}

export function Login() {
  const { signIn } = useAuth()
  const nav = useNavigate()
  const [params] = useSearchParams()
  const { push } = useToast()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(params.get('fsp_error'))
  const [guest, setGuest] = useState(false)
  const guestMode = useGuestMode()

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true); setError(null)
    try {
      const r = await api<{ access_token: string }>('/auth/login', { body: { email, password } })
      const me = await signIn(r.access_token)
      nav(params.get('next') || homeFor(me.role), { replace: true })
    } catch (err: any) {
      if (err.status === 403 && /не подтвержд/i.test(err.message)) nav(`/verify?email=${encodeURIComponent(email)}`)
      setError(err.message)
    } finally { setBusy(false) }
  }

  return (
    <AuthLayout title="Вход" subtitle={<>Нет аккаунта? <Link to="/register" className="link">Зарегистрироваться</Link></>}>
      <form onSubmit={submit} className="space-y-4">
        {error && <Alert tone="error">{error}</Alert>}
        <Field label="E-mail"><Input type="email" autoComplete="email" required value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" /></Field>
        <Field label="Пароль"><Input type="password" autoComplete="current-password" required value={password} onChange={e => setPassword(e.target.value)} /></Field>
        <Button type="submit" loading={busy} className="w-full" size="lg">Войти</Button>
      </form>
      <div className="my-6 flex items-center gap-3 text-xs text-slate-400"><span className="h-px flex-1 bg-slate-200" />или<span className="h-px flex-1 bg-slate-200" /></div>
      <Button variant="dark" size="lg" className="w-full" onClick={() => startFspLogin(push)}
              icon={<img src="/brand/fsp-star-white.png" alt="" className="h-5 w-5" />}>Войти через ФСП ID</Button>
      <div className="mt-8 rounded-[20px] border border-line bg-surface/60 p-4">
        <p className="px-1 text-xs font-semibold text-slate-500">Демо-аккаунты · пароль demo12345</p>
        <div className="mt-2.5 grid gap-1.5">
          {DEMO.map((d, i) => (
            <motion.button key={d.email} type="button" onClick={() => { setEmail(d.email); setPassword('demo12345') }}
              initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 + i * 0.05 }} whileTap={{ scale: 0.98 }}
              className={clsx('group flex items-center justify-between gap-3 rounded-xl border bg-white px-3 py-2.5 text-left text-sm transition',
                email === d.email ? 'border-fsp-pink/50 shadow-[0_0_0_3px_rgba(255,0,83,.07)]' : 'border-line hover:border-[#D9D4E7]')}>
              <span className="flex items-center gap-2.5 font-medium text-fsp-deep"><span className="text-slate-400 transition group-hover:text-fsp-pink">{d.icon}</span>{d.label}</span>
              <span className="text-xs text-slate-400">{d.email}</span>
            </motion.button>
          ))}
        </div>
      </div>
      {guestMode && (
        <div className="mt-3 flex items-center justify-between gap-3 rounded-[20px] border border-dashed border-[#FFC2D6] bg-[#FFF7FA] p-4">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-fsp-deep">Без регистрации</p>
            <p className="mt-0.5 text-xs leading-relaxed text-slate-500">Демо-кандидат в один клик и сразу тест: экспресс за ≈ 7 минут или полный</p>
          </div>
          <Button size="sm" onClick={() => setGuest(true)} icon={<Zap className="h-4 w-4" />}>Попробовать</Button>
        </div>
      )}
      <GuestStartModal open={guest} onClose={() => setGuest(false)} />
    </AuthLayout>
  )
}

export function Register() {
  const nav = useNavigate()
  const [params] = useSearchParams()
  const [role, setRole] = useState<'candidate' | 'employer'>(params.get('role') === 'employer' ? 'employer' : 'candidate')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [company, setCompany] = useState('')
  const [consent, setConsent] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!consent) { setError('Нужно согласие на обработку персональных данных'); return }
    setBusy(true); setError(null)
    try {
      const r = await api<{ dev_code?: string }>('/auth/register', { body: { email, password, role, consent_pd: consent, company_name: role === 'employer' ? company : null } })
      nav(`/verify?email=${encodeURIComponent(email)}${r.dev_code ? `&dev=${r.dev_code}` : ''}`)
    } catch (err: any) { setError(err.message) } finally { setBusy(false) }
  }

  return (
    <AuthLayout title="Регистрация" subtitle={<>Уже есть аккаунт? <Link to="/login" className="link">Войти</Link></>}>
      <div className="mb-6 grid grid-cols-2 gap-1 rounded-2xl border border-line bg-surface/70 p-1">
        {(['candidate', 'employer'] as const).map(r => (
          <button key={r} type="button" onClick={() => setRole(r)}
            className={clsx('relative flex items-center justify-center gap-2 rounded-xl py-2.5 text-sm font-semibold transition-colors',
              role === r ? 'text-fsp-deep' : 'text-slate-500 hover:text-fsp-deep')}>
            {role === r && <motion.span layoutId="role-pill" transition={{ type: 'spring', stiffness: 400, damping: 32 }} className="absolute inset-0 rounded-xl bg-white shadow-card" />}
            <span className="relative flex items-center gap-2">{r === 'candidate' ? <UserRound className="h-4 w-4" /> : <Building2 className="h-4 w-4" />}
              {r === 'candidate' ? 'Я кандидат' : 'Я работодатель'}</span>
          </button>
        ))}
      </div>
      <form onSubmit={submit} className="space-y-4">
        {error && <Alert tone="error">{error}</Alert>}
        {role === 'employer' && <Field label="Компания" required><Input required value={company} onChange={e => setCompany(e.target.value)} placeholder="ООО «Пример»" /></Field>}
        <Field label="E-mail" required hint="Пришлём код подтверждения"><Input type="email" required autoComplete="email" value={email} onChange={e => setEmail(e.target.value)} /></Field>
        <Field label="Пароль" required hint="Не короче 8 символов"><Input type="password" required minLength={8} autoComplete="new-password" value={password} onChange={e => setPassword(e.target.value)} /></Field>
        <div className="rounded-2xl border border-line bg-surface/60 p-3.5">
          <Checkbox checked={consent} onChange={setConsent} label={<span className="text-xs leading-relaxed text-slate-600">
            Даю согласие на обработку персональных данных в соответствии с Федеральным законом № 152-ФЗ
            для целей подбора персонала. Согласие можно отозвать в настройках.</span>} />
        </div>
        <Button type="submit" loading={busy} className="w-full" size="lg">Создать аккаунт</Button>
      </form>
    </AuthLayout>
  )
}

export function Verify() {
  const [params] = useSearchParams()
  const email = params.get('email') ?? ''
  const [code, setCode] = useState(params.get('dev') ?? '')
  const [dev, setDev] = useState(params.get('dev'))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { signIn } = useAuth()
  const { push } = useToast()
  const nav = useNavigate()

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true); setError(null)
    try {
      const r = await api<{ access_token: string }>('/auth/verify-email', { body: { email, code } })
      const me = await signIn(r.access_token)
      push('E-mail подтверждён. Добро пожаловать!')
      nav(homeFor(me.role), { replace: true })
    } catch (err: any) { setError(err.message) } finally { setBusy(false) }
  }
  const resend = async () => {
    try {
      const r = await api<{ dev_code?: string; detail: string }>('/auth/resend-code', { body: { email } })
      if (r.dev_code) { setDev(r.dev_code); setCode(r.dev_code) }
      push(r.detail)
    } catch (err: any) { push(err.message, 'error') }
  }
  return (
    <AuthLayout title="Подтвердите e-mail" subtitle={<>Мы отправили 6-значный код на <b className="text-fsp-deep">{email}</b></>}>
      <form onSubmit={submit} className="space-y-4">
        {error && <Alert tone="error">{error}</Alert>}
        {dev && <Alert tone="info" icon={<Mail className="h-4 w-4" />} title="Демо-режим">
          Письмо также доступно в Mailpit (http://localhost:8025). Код для проверки: <b>{dev}</b></Alert>}
        <Field label="Код подтверждения">
          <Input inputMode="numeric" maxLength={6} value={code} onChange={e => setCode(e.target.value.replace(/\D/g, ''))}
                 className="text-center text-2xl font-bold tracking-[0.5em]" placeholder="••••••" />
        </Field>
        <Button type="submit" loading={busy} disabled={code.length !== 6} className="w-full" size="lg" icon={<ShieldCheck className="h-5 w-5" />}>Подтвердить</Button>
        <button type="button" onClick={resend} className="w-full text-center text-sm text-slate-500 hover:text-fsp-pink">Отправить код ещё раз</button>
      </form>
    </AuthLayout>
  )
}

export function FspAuth() {
  const { signIn } = useAuth()
  const nav = useNavigate()
  const loc = useLocation()
  useEffect(() => {
    const token = new URLSearchParams(loc.hash.replace(/^#/, '')).get('token')
    if (!token) { nav('/login?fsp_error=Не удалось войти через ФСП ID', { replace: true }); return }
    window.history.replaceState(null, '', '/auth/fsp')
    signIn(token).then(me => nav(homeFor(me.role), { replace: true })).catch(() => nav('/login', { replace: true }))
  }, [loc.hash, nav, signIn])
  return <PageLoader />
}
