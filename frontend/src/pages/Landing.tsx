import { useEffect, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { AnimatePresence, motion, useMotionValueEvent, useScroll, useTransform } from 'framer-motion'
import clsx from 'clsx'
import {
  ArrowRight, ArrowUpRight, BadgeCheck, Building2, ChartBar, CircleCheck, Eye, Fingerprint, Lock, LockOpen, Mail, Medal, Repeat,
  Search, ShieldCheck, Sparkles, Trophy, UserRound, Wallet, Zap,
} from 'lucide-react'
import { api } from '@/lib/api'
import { homeFor, useAuth } from '@/lib/auth'
import { Blobs, CountUp, EASE, Reveal } from '@/lib/motion'
import { ButtonLink } from '@/components/ui'
import { Logo } from '@/components/Layout'
import { GuestStartModal } from '@/components/GuestStart'

export function PublicHeader({ solid = false }: { solid?: boolean }) {
  const { user } = useAuth()
  const { scrollY } = useScroll()
  const [scrolled, setScrolled] = useState(false)
  useMotionValueEvent(scrollY, 'change', v => setScrolled(v > 12))
  return (
    <header className={clsx('fixed inset-x-0 top-0 z-40 transition-all duration-300',
      scrolled || solid ? 'border-b border-white/10 bg-[#1d0834]/70 backdrop-blur-xl' : 'bg-transparent')}>
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
        <Logo dark />
        <nav className="flex items-center gap-1 sm:gap-2">
          <Link to="/methodology" className="hidden rounded-xl px-3 py-2 text-sm font-medium text-white/70 transition hover:text-white sm:block">Методика</Link>
          <a href="/docs" className="hidden rounded-xl px-3 py-2 text-sm font-medium text-white/70 transition hover:text-white md:block">API</a>
          {user ? (
            <ButtonLink to={homeFor(user.role)} size="sm">Личный кабинет</ButtonLink>
          ) : (<>
            <Link to="/login" className="rounded-xl px-3 py-2 text-sm font-medium text-white/80 transition hover:text-white">Войти</Link>
            <ButtonLink to="/register" size="sm">Начать</ButtonLink>
          </>)}
        </nav>
      </div>
    </header>
  )
}

const WORDS = ['Работодатель', 'находит']

function HeroTitle() {
  return (
    <h1 className="mt-6 text-[44px] font-extrabold leading-[1.02] tracking-tightest text-white sm:text-6xl lg:text-[72px]">
      {WORDS.map((w, i) => (
        <motion.span key={w} className="mr-[0.25em] inline-block" initial={{ opacity: 0, y: 28, filter: 'blur(8px)' }}
          animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }} transition={{ duration: 0.8, ease: EASE, delay: 0.15 + i * 0.12 }}>{w}</motion.span>
      ))}
      <br />
      <motion.span className="inline-block bg-gradient-to-r from-[#ff3d7f] via-[#ff7aa8] to-[#b8b2ff] bg-[length:200%_auto] bg-clip-text text-transparent animate-gradient-x"
        initial={{ opacity: 0, y: 28, filter: 'blur(8px)' }} animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }} transition={{ duration: 0.9, ease: EASE, delay: 0.42 }}>
        вас сам
      </motion.span>
    </h1>
  )
}

function FloatCard({ children, className, delay = 0, float = 'animate-float' }: { children: ReactNode; className?: string; delay?: number; float?: string }) {
  return (
    <motion.div initial={{ opacity: 0, y: 40, scale: 0.96 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ duration: 0.9, ease: EASE, delay }}
      className={className}>
      <div className={float} style={{ animationDelay: `${-delay * 3}s` }}>{children}</div>
    </motion.div>
  )
}

function HeroVisual() {
  const { scrollY } = useScroll()
  const y1 = useTransform(scrollY, [0, 600], [0, -60])
  const y2 = useTransform(scrollY, [0, 600], [0, -110])
  return (
    <div className="relative mx-auto h-[460px] w-full max-w-[460px] lg:mx-0">
      <motion.div style={{ y: y1 }} className="absolute left-0 top-4 w-[330px]">
        <FloatCard delay={0.5}>
          <div className="rounded-3xl border border-white/15 bg-white/[0.08] p-5 shadow-2xl backdrop-blur-2xl">
            <div className="flex items-center justify-between">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-white/10 px-3 py-1 text-xs font-semibold text-white ring-1 ring-white/15">
                <ShieldCheck className="h-3.5 w-3.5 text-fsp-blush" /> Backend · Middle
              </span>
              <span className="text-xs font-semibold text-emerald-300">выше 78%</span>
            </div>
            <p className="mt-4 text-sm font-semibold text-white">Кандидат C-7F3A2B</p>
            <div className="mt-3 space-y-2.5">
              {[['SQL', 86], ['Python', 81], ['HTTP и API', 72], ['Архитектура', 64]].map(([d, v], i) => (
                <div key={d as string}>
                  <div className="flex justify-between text-[11px] text-white/70"><span>{d}</span><b className="text-white">{v}%</b></div>
                  <div className="mt-1 h-1.5 rounded-full bg-white/10">
                    <motion.div className="h-full rounded-full bg-gradient-to-r from-fsp-pink to-[#ff7aa8]" initial={{ width: 0 }}
                      animate={{ width: `${v}%` }} transition={{ duration: 1.2, ease: EASE, delay: 0.9 + i * 0.1 }} />
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-4 flex flex-wrap gap-1.5">
              <span className="chip bg-fsp-pink/20 text-[#ffc2d6]"><Trophy className="h-3 w-3" /> Призёр ФСП ×2</span>
              <span className="chip bg-white/10 text-white/80">✓ PostgreSQL</span>
              <span className="chip bg-white/10 text-white/80">✓ FastAPI</span>
            </div>
          </div>
        </FloatCard>
      </motion.div>
      <motion.div style={{ y: y2 }} className="absolute bottom-6 right-0 w-[300px]">
        <FloatCard delay={0.75} float="animate-float-slow">
          <div className="rounded-3xl border border-white/60 bg-white p-4 shadow-pop">
            <div className="flex items-center gap-3">
              <div className="relative grid h-10 w-10 place-items-center rounded-2xl bg-gradient-to-br from-fsp-pink to-[#ff5c95] text-white">
                <Mail className="h-5 w-5" />
                <span className="absolute -right-0.5 -top-0.5 h-3 w-3 animate-pulse-ring rounded-full bg-fsp-pink" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-bold text-fsp-deep">Приглашение · ТехноПульс</p>
                <p className="text-xs text-slate-500">Python-разработчик · гибрид</p>
              </div>
            </div>
            <div className="mt-3 flex items-center justify-between rounded-2xl bg-surface px-3 py-2.5">
              <span className="text-xs text-slate-500">Вилка</span>
              <span className="text-sm font-bold text-fsp-deep">250–320 тыс ₽</span>
            </div>
            <div className="mt-2.5 grid grid-cols-2 gap-2">
              <span className="rounded-xl bg-fsp-deep py-2 text-center text-xs font-semibold text-white">Принять</span>
              <span className="rounded-xl border border-line py-2 text-center text-xs font-semibold text-slate-500">Отклонить</span>
            </div>
          </div>
        </FloatCard>
      </motion.div>
      <FloatCard delay={1} className="absolute bottom-0 left-4" float="animate-float-slow">
        <div className="flex items-center gap-2.5 rounded-2xl border border-white/15 bg-white/10 px-3.5 py-2.5 text-white backdrop-blur-xl">
          <div className="relative h-9 w-9">
            <svg viewBox="0 0 36 36" className="h-9 w-9 -rotate-90"><circle cx="18" cy="18" r="15" stroke="rgba(255,255,255,.15)" strokeWidth="4" fill="none" />
              <motion.circle cx="18" cy="18" r="15" stroke="#FF0053" strokeWidth="4" fill="none" strokeLinecap="round" strokeDasharray={94.2}
                initial={{ strokeDashoffset: 94.2 }} animate={{ strokeDashoffset: 94.2 * 0.08 }} transition={{ duration: 1.6, ease: EASE, delay: 1.2 }} /></svg>
          </div>
          <div><p className="text-[11px] text-white/60">совпадение</p><p className="text-sm font-bold">92%</p></div>
        </div>
      </FloatCard>
    </div>
  )
}

const TECH = ['Python', 'Go', 'Java', 'TypeScript', 'React', 'PostgreSQL', 'Kubernetes', 'Docker', 'Kafka', 'PyTorch', 'SQL', 'Linux',
  'FastAPI', 'Spring', 'ClickHouse', 'Terraform', 'pytest', 'A/B-тесты', 'Алгоритмы', 'Redis']

function Marquee() {
  return (
    <div className="mask-fade-x overflow-hidden border-y border-line bg-white py-5">
      <div className="flex w-max animate-marquee gap-10 pr-10">
        {[...TECH, ...TECH].map((t, i) => (
          <span key={i} className="flex items-center gap-10 text-sm font-semibold text-slate-400">{t}<span className="h-1 w-1 rounded-full bg-fsp-pink/50" /></span>
        ))}
      </div>
    </div>
  )
}

const VARIANTS = [
  { who: 'Кандидат A', arr: '[3, 8, 1, 6]', ans: '4' },
  { who: 'Кандидат B', arr: '[5, 2, 7, 4]', ans: '12' },
  { who: 'Кандидат C', arr: '[9, 4, 2, 1]', ans: '10' },
]

function VariantDemo() {
  const [i, setI] = useState(0)
  useEffect(() => { const t = setInterval(() => setI(x => (x + 1) % VARIANTS.length), 2600); return () => clearInterval(t) }, [])
  const v = VARIANTS[i]
  return (
    <div className="rounded-2xl bg-[#1d0b33] p-4 font-mono text-[13px] text-white/90 shadow-lift">
      <div className="mb-3 flex items-center justify-between font-sans text-xs">
        <AnimatePresence mode="wait">
          <motion.span key={v.who} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} className="font-semibold text-fsp-blush">{v.who}</motion.span>
        </AnimatePresence>
        <span className="text-white/40">семейство alg.loop_sum · b = −1.6</span>
      </div>
      <p><span className="text-[#ff7aa8]">xs</span> = <AnimatePresence mode="wait"><motion.span key={v.arr} className="inline-block text-[#FFC56B]"
        initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}>{v.arr}</motion.span></AnimatePresence></p>
      <p><span className="text-[#ff7aa8]">print</span>(<span className="text-[#B9B3FF]">sum</span>(x <span className="text-[#ff7aa8]">for</span> x <span className="text-[#ff7aa8]">in</span> xs <span className="text-[#ff7aa8]">if</span> x % 2))</p>
      <div className="mt-3 flex items-center justify-between rounded-xl bg-white/5 px-3 py-2 font-sans text-xs">
        <span className="text-white/50">правильный ответ</span>
        <AnimatePresence mode="wait"><motion.b key={v.ans} initial={{ opacity: 0, scale: 0.6 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.6 }}
          className="text-base text-emerald-300">{v.ans}</motion.b></AnimatePresence>
      </div>
    </div>
  )
}

function UnlockDemo() {
  const [open, setOpen] = useState(false)
  useEffect(() => { const t = setInterval(() => setOpen(x => !x), 2800); return () => clearInterval(t) }, [])
  return (
    <div className="flex items-center gap-4 rounded-2xl border border-line bg-white p-4">
      <motion.div animate={{ backgroundColor: open ? '#ECFDF5' : '#FFF0F5', color: open ? '#059669' : '#FF0053' }} className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl">
        <AnimatePresence mode="wait">
          <motion.span key={String(open)} initial={{ scale: 0.4, rotate: -30, opacity: 0 }} animate={{ scale: 1, rotate: 0, opacity: 1 }} exit={{ scale: 0.4, opacity: 0 }}>
            {open ? <LockOpen className="h-5 w-5" /> : <Lock className="h-5 w-5" />}
          </motion.span>
        </AnimatePresence>
      </motion.div>
      <div className="min-w-0 text-sm">
        <AnimatePresence mode="wait">
          <motion.div key={String(open)} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}>
            <p className="font-semibold text-fsp-deep">{open ? 'Иван Петров' : 'Кандидат C-BDE88C'}</p>
            <p className="truncate text-xs text-slate-500">{open ? '@ivan_petrov_dev · +7 917 000-12-34' : 'контакты откроются после согласия'}</p>
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  )
}

function MatchDemo() {
  const rows = [['C-7F3A2B', 'Backend · Middle', 92], ['C-09FD97', 'Backend · Middle', 87], ['C-B13D3F', 'Fullstack · Middle', 78]] as const
  return (
    <div className="space-y-2">
      {rows.map(([id, cat, v], i) => (
        <motion.div key={id} initial={{ opacity: 0, x: 24 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }}
          transition={{ duration: 0.5, ease: EASE, delay: 0.15 + i * 0.12 }}
          className="flex items-center gap-3 rounded-2xl border border-line bg-white px-3 py-2.5">
          <div className="relative h-9 w-9 shrink-0">
            <svg viewBox="0 0 36 36" className="h-9 w-9 -rotate-90"><circle cx="18" cy="18" r="15" stroke="#F1EFF6" strokeWidth="4" fill="none" />
              <motion.circle cx="18" cy="18" r="15" stroke={v > 80 ? '#FF0053' : '#8A83D1'} strokeWidth="4" fill="none" strokeLinecap="round" strokeDasharray={94.2}
                initial={{ strokeDashoffset: 94.2 }} whileInView={{ strokeDashoffset: 94.2 * (1 - v / 100) }} viewport={{ once: true }}
                transition={{ duration: 1.2, ease: EASE, delay: 0.3 + i * 0.12 }} /></svg>
            <span className="absolute inset-0 grid place-items-center text-[10px] font-bold text-fsp-deep">{v}</span>
          </div>
          <div className="min-w-0 flex-1"><p className="text-sm font-semibold text-fsp-deep">{id}</p><p className="text-xs text-slate-400">{cat}</p></div>
          <span className="rounded-lg bg-[#FFF0F5] px-2 py-1 text-[11px] font-semibold text-fsp-pink">Пригласить</span>
        </motion.div>
      ))}
    </div>
  )
}

function Bento({ className, title, text, children, dark }: { className?: string; title: string; text: string; children?: ReactNode; dark?: boolean }) {
  return (
    <Reveal className={className}>
      <div className={clsx('group relative h-full overflow-hidden rounded-[28px] p-6 transition duration-500 hover:-translate-y-1 sm:p-7',
        dark ? 'bg-brand-gradient text-white shadow-lift' : 'border border-line bg-white shadow-soft hover:shadow-lift')}>
        {dark && <div className="pointer-events-none absolute -right-16 -top-16 h-56 w-56 rounded-full bg-fsp-pink/30 blur-3xl transition duration-700 group-hover:scale-125" />}
        <div className="relative">
          <p className={clsx('text-lg font-bold tracking-tight', dark ? 'text-white' : 'text-fsp-deep')}>{title}</p>
          <p className={clsx('mt-2 max-w-md text-sm leading-relaxed', dark ? 'text-white/70' : 'text-slate-500')}>{text}</p>
          {children && <div className="mt-6">{children}</div>}
        </div>
      </div>
    </Reveal>
  )
}

export function Landing() {
  const { user } = useAuth()
  const [guest, setGuest] = useState(false)
  const { data: stats } = useQuery({ queryKey: ['public-stats'], queryFn: () => api('/public/stats') })
  const canTry = !!stats?.guest_mode && !user
  const { data: meth } = useQuery({ queryKey: ['methodology'], queryFn: () => api('/public/methodology') })
  const cat = meth?.cat_validation
  const mv = meth?.matching_validation
  const steps = {
    candidate: [
      { icon: <UserRound />, t: 'Профиль за 2 минуты', d: 'Загрузите PDF-резюме — поля распознаются автоматически.' },
      { icon: <ChartBar />, t: 'Опрос и адаптивный тест', d: 'Тест подстраивается под ваш уровень, задания уникальны.' },
      { icon: <BadgeCheck />, t: 'Категория, а не резюме', d: 'Грейд подтверждает тест, ФСП ID добавляет достижения.' },
      { icon: <Mail />, t: 'Предложения приходят сами', d: 'С вилкой зарплаты. Контакты — только с вашего согласия.' },
    ],
    employer: [
      { icon: <Sparkles />, t: 'Опишите потребность', d: 'Текстом — NLP определит специализацию, грейд и навыки.' },
      { icon: <Search />, t: 'Получите подборку', d: 'Категории с аналитикой рынка и кандидаты с объяснением.' },
      { icon: <Wallet />, t: 'Пригласите человека', d: 'Вилка обязательна. Видна вероятность отклика до отправки.' },
      { icon: <CircleCheck />, t: 'Контакт после согласия', d: 'Принял приглашение — контакты открыты. Отказ — с причиной.' },
    ],
  }
  return (
    <div className="min-h-screen bg-white">
      <PublicHeader />
      <section className="bg-hero noise relative overflow-hidden pb-24 pt-28 sm:pt-32">
        <Blobs className="opacity-70" />
        <div className="bg-grid absolute inset-0 opacity-[0.15] [mask-image:radial-gradient(ellipse_at_top,black,transparent_70%)]" />
        <div className="relative mx-auto grid max-w-6xl items-center gap-14 px-4 sm:px-6 lg:grid-cols-[1.15fr_.85fr]">
          <div className="text-white">
            <motion.span initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, ease: EASE }}
              className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3.5 py-1.5 text-xs font-semibold text-white/85 backdrop-blur">
              <span className="relative flex h-2 w-2"><span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-fsp-pink opacity-70" /><span className="relative inline-flex h-2 w-2 rounded-full bg-fsp-pink" /></span>
              Платформа Федерации спортивного программирования
            </motion.span>
            <HeroTitle />
            <motion.p initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, ease: EASE, delay: 0.6 }}
              className="mt-6 max-w-xl text-base leading-relaxed text-white/70 sm:text-lg">
              Подбор ИТ-специалистов с обратной механикой: уровень подтверждает адаптивный тест и достижения ФСП,
              а работодатель сам приходит к конкретному человеку — с предложением и вилкой зарплаты.
            </motion.p>
            <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, ease: EASE, delay: 0.75 }} className="mt-9 flex flex-wrap gap-3">
              <ButtonLink to="/register?role=candidate" size="lg" icon={<UserRound className="h-5 w-5" />} className="group">
                Я кандидат <ArrowRight className="h-4 w-4 transition group-hover:translate-x-1" />
              </ButtonLink>
              <Link to="/register?role=employer" className="group inline-flex h-12 items-center gap-2 rounded-xl border border-white/20 bg-white/5 px-6 text-[15px] font-semibold text-white backdrop-blur transition hover:bg-white/10">
                <Building2 className="h-5 w-5" /> Я работодатель <ArrowUpRight className="h-4 w-4 transition group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
              </Link>
            </motion.div>
            {canTry && (
              <motion.button type="button" onClick={() => setGuest(true)} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.8, delay: 0.9 }}
                className="group mt-4 inline-flex items-center gap-2 text-sm font-semibold text-white/75 transition hover:text-white">
                <Zap className="h-4 w-4 text-[#ff7aa8]" />Без регистрации: экспресс-тест за 7 минут
                <ArrowRight className="h-4 w-4 transition group-hover:translate-x-1" />
              </motion.button>
            )}
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 1, delay: 1 }}
              className="mt-12 grid max-w-xl grid-cols-2 gap-6 sm:grid-cols-4">
              {[[stats?.categorized, 'с подтверждённой категорией'], [stats?.with_fsp, 'с ФСП ID'], [stats?.item_families, 'семейств заданий'],
                [stats?.vacancies, 'открытых вакансий']].map(([v, l]) => (
                <div key={l as string}>
                  <p className="text-[28px] font-extrabold tabular-nums text-white">{typeof v === 'number' ? <CountUp value={v} /> : '—'}</p>
                  <p className="mt-1 text-xs leading-snug text-white/50">{l}</p>
                </div>
              ))}
            </motion.div>
          </div>
          <HeroVisual />
        </div>
      </section>

      <Marquee />

      <section className="mx-auto max-w-6xl px-4 py-24 sm:px-6">
        <Reveal><p className="eyebrow">Как это работает</p><h2 className="mt-3 max-w-2xl text-4xl font-extrabold tracking-tight">Инициатива — на стороне работодателя</h2>
          <p className="mt-3 max-w-2xl text-slate-500">Кандидату не нужно рассылать отклики вслепую: достаточно один раз подтвердить уровень.</p></Reveal>
        <div className="mt-12 grid gap-6 lg:grid-cols-2">
          {(['candidate', 'employer'] as const).map((side, si) => (
            <Reveal key={side} delay={si * 0.1}>
              <div className="rounded-[28px] border border-line bg-surface/50 p-7 sm:p-8">
                <p className="text-sm font-bold text-fsp-pink">{side === 'candidate' ? 'Кандидату' : 'Работодателю'}</p>
                <ol className="relative mt-6 space-y-7">
                  <motion.span className="absolute left-[21px] top-3 w-px origin-top bg-gradient-to-b from-fsp-pink/50 via-fsp-lavender/40 to-transparent"
                    initial={{ scaleY: 0 }} whileInView={{ scaleY: 1 }} viewport={{ once: true }} transition={{ duration: 1.2, ease: EASE }} style={{ height: 'calc(100% - 24px)' }} />
                  {steps[side].map((s, i) => (
                    <motion.li key={i} className="relative flex gap-4" initial={{ opacity: 0, y: 12 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}
                      transition={{ duration: 0.5, ease: EASE, delay: 0.1 + i * 0.1 }}>
                      <div className="relative grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-white text-fsp-pink shadow-card ring-1 ring-line [&>svg]:h-5 [&>svg]:w-5">{s.icon}</div>
                      <div className="pt-0.5"><p className="font-bold text-fsp-deep">{s.t}</p><p className="mt-1 text-sm leading-relaxed text-slate-500">{s.d}</p></div>
                    </motion.li>
                  ))}
                </ol>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      <section className="bg-surface/60">
        <div className="mx-auto max-w-6xl px-4 py-24 sm:px-6">
          <Reveal><p className="eyebrow">Почему это работает</p><h2 className="mt-3 max-w-2xl text-4xl font-extrabold tracking-tight">Доверие к уровню — по построению</h2></Reveal>
          <div className="mt-12 grid gap-5 md:grid-cols-6">
            <Bento className="md:col-span-4" dark title="Тест, который бесполезно сливать"
              text="Каждое задание — семейство с откалиброванной трудностью. У каждого кандидата свои числа, данные и код, поэтому чужой ответ не подходит, а попытка его ввести выдаёт списывание.">
              <VariantDemo />
            </Bento>
            <Bento className="md:col-span-2" title="Подборка за секунды" text="Категории по тесту, ранжирование с объяснением «почему этот кандидат».">
              <MatchDemo />
            </Bento>
            <Bento className="md:col-span-2" title="Контакты — с согласия" text="До принятия приглашения работодатель видит анонимный код и подтверждённые данные.">
              <UnlockDemo />
            </Bento>
            <Bento className="md:col-span-2" title="Вилка — сразу" text="Зарплата обязательна в вакансии и в каждом приглашении.">
              <div className="flex items-end gap-2">
                {[38, 54, 72, 61, 88, 66, 47].map((h, i) => (
                  <motion.span key={i} className={clsx('w-full rounded-t-lg', i === 4 ? 'bg-gradient-to-t from-fsp-pink to-[#ff7aa8]' : 'bg-[#EDEAF7]')}
                    initial={{ height: 0 }} whileInView={{ height: h }} viewport={{ once: true }} transition={{ duration: 0.8, ease: EASE, delay: i * 0.06 }} />
                ))}
              </div>
              <p className="mt-2 text-xs text-slate-400">медиана ожиданий категории vs ваша вилка</p>
            </Bento>
            <Bento className="md:col-span-2" title="ФСП — бонус, не барьер" text="Достижения подтягиваются по ФСП ID и усиливают профиль. Без них — участие на общих основаниях.">
              <div className="flex items-center gap-3">
                {[['1', 'from-[#ffd56b] to-[#f5a524]'], ['2', 'from-[#e2e8f0] to-[#94a3b8]'], ['3', 'from-[#f3b38a] to-[#c46a3b]']].map(([n, g], i) => (
                  <motion.span key={n} className={`relative grid h-12 w-12 place-items-center rounded-2xl bg-gradient-to-br ${g} text-white shadow-card`}
                    initial={{ y: 16, opacity: 0 }} whileInView={{ y: 0, opacity: 1 }} viewport={{ once: true }} transition={{ type: 'spring', delay: 0.1 + i * 0.1 }}>
                    <Medal className="h-5 w-5" /><span className="absolute -bottom-1 -right-1 grid h-5 w-5 place-items-center rounded-full bg-white text-[10px] font-bold text-fsp-deep ring-1 ring-line">{n}</span>
                  </motion.span>
                ))}
              </div>
            </Bento>
          </div>
        </div>
      </section>

      {cat && mv && (
        <section className="mx-auto max-w-6xl px-4 py-24 sm:px-6">
          <div className="flex flex-wrap items-end justify-between gap-6">
            <Reveal><p className="eyebrow">Проверено валидацией</p><h2 className="mt-3 max-w-2xl text-4xl font-extrabold tracking-tight">Цифры, а не обещания</h2></Reveal>
            <Reveal delay={0.1}><ButtonLink to="/methodology" variant="secondary" icon={<Eye className="h-4 w-4" />}>Вся методика</ButtonLink></Reveal>
          </div>
          <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {[
              { v: cat.grades.overgrading_rate_test * 100, d: 1, s: '%', t: 'кандидатов с завышенным грейдом', h: `в резюме — ${Math.round(cat.grades.overgrading_rate_self_declared * 100)}%`, icon: <ShieldCheck /> },
              { v: mv.summary.ours.p10, d: 2, s: '', t: 'P@10 — доля релевантных в топ-10', h: `поиск по ключевым словам — ${mv.summary.keyword.p10.toFixed(2)}`, icon: <Search /> },
              { v: cat.grades.retest.weighted_kappa, d: 2, s: '', t: 'согласованность повторного теста (κ)', h: `r(θ̂₁, θ̂₂) = ${cat.grades.retest.theta_test_retest_r}`, icon: <Repeat /> },
              { v: cat.leak_attack.detection_rate.ours['25'] * 100, d: 0, s: '%', t: 'списывающих сессий помечено', h: `ложных пометок — ${(cat.leak_attack.honest_flag_rate.ours * 100).toFixed(1)}%`, icon: <Fingerprint /> },
            ].map((k, i) => (
              <Reveal key={k.t} delay={i * 0.08}>
                <div className="group h-full rounded-[24px] border border-line bg-white p-6 shadow-soft transition duration-300 hover:-translate-y-1 hover:shadow-lift">
                  <div className="grid h-10 w-10 place-items-center rounded-xl bg-[#FFF0F5] text-fsp-pink transition group-hover:scale-110 [&>svg]:h-5 [&>svg]:w-5">{k.icon}</div>
                  <p className="mt-5 text-4xl font-extrabold tracking-tight text-fsp-deep"><CountUp value={k.v} decimals={k.d} suffix={k.s} /></p>
                  <p className="mt-2 text-sm font-medium text-slate-600">{k.t}</p>
                  <p className="mt-1 text-xs text-slate-400">{k.h}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </section>
      )}

      <section className="mx-auto max-w-6xl px-4 pb-24 sm:px-6">
        <Reveal>
          <div className="relative overflow-hidden rounded-[32px] bg-[linear-gradient(120deg,#2a0c48,#520978,#8a1a7a,#2a0c48)] bg-[length:300%_300%] p-8 text-white animate-gradient-x sm:p-12">
            <Blobs className="opacity-50" />
            <div className="relative flex flex-col items-start justify-between gap-8 sm:flex-row sm:items-center">
              <div>
                <p className="text-3xl font-extrabold tracking-tight">Готовы показать свой уровень?</p>
                <p className="mt-2 max-w-lg text-white/70">Регистрация, опрос и тест — около 30 минут. Дальше предложения приходят сами.</p>
              </div>
              <div className="flex flex-wrap gap-3">
                {canTry && (
                  <button type="button" onClick={() => setGuest(true)}
                    className="inline-flex h-12 items-center gap-2 rounded-xl border border-white/20 bg-white/5 px-6 text-[15px] font-semibold text-white backdrop-blur transition hover:bg-white/10">
                    <Zap className="h-5 w-5" />Экспресс-тест без регистрации</button>
                )}
                <ButtonLink to="/register" size="lg" className="group">Начать <ArrowRight className="h-4 w-4 transition group-hover:translate-x-1" /></ButtonLink>
              </div>
            </div>
          </div>
        </Reveal>
      </section>

      <GuestStartModal open={guest} onClose={() => setGuest(false)} />
      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-6 px-4 py-10 text-sm text-slate-500 sm:flex-row sm:items-center sm:px-6">
          <img src="/brand/fsp-logo-black.png" alt="Федерация спортивного программирования России" className="h-8 w-auto opacity-80" />
          <div className="flex flex-wrap gap-6">
            <Link to="/methodology" className="transition hover:text-fsp-deep">Методика</Link>
            <a href="/docs" className="transition hover:text-fsp-deep">API</a>
            <span>ЛЦТ 2026 · спецтрек ФСП</span>
          </div>
        </div>
      </footer>
    </div>
  )
}
