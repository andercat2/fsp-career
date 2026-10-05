import { Suspense, useEffect, useRef, useState, type ReactNode } from 'react'
import { Link, NavLink, Navigate, useLocation, useNavigate, useOutlet } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import clsx from 'clsx'
import {
  Award, Bell, BellOff, Briefcase, Building2, ClipboardCheck, Database, FileText, FlaskConical, LayoutDashboard, ListChecks,
  LogOut, Mail, Menu, Search, Send, Settings, Sparkles, Star, UserRound, X,
} from 'lucide-react'
import { api } from '@/lib/api'
import { homeFor, useAuth } from '@/lib/auth'
import { ago } from '@/lib/format'
import { EASE, SPRING } from '@/lib/motion'
import { Avatar, PageLoader } from './ui'

type NavItem = { to: string; label: string; icon: ReactNode; end?: boolean; badge?: number }

function useNav(role?: string): NavItem[] {
  const isCand = role === 'candidate'
  const { data: dash } = useQuery({ queryKey: ['cand-dashboard'], queryFn: () => api('/candidate/dashboard'), enabled: isCand, staleTime: 30_000 })
  const ic = 'h-[18px] w-[18px]'
  if (role === 'candidate') return [
    { to: '/candidate', label: 'Главная', icon: <LayoutDashboard className={ic} />, end: true },
    { to: '/candidate/profile', label: 'Профиль и резюме', icon: <UserRound className={ic} /> },
    { to: '/candidate/testing', label: 'Опрос и тест', icon: <ClipboardCheck className={ic} /> },
    { to: '/candidate/grade', label: 'Категория и грейд', icon: <Award className={ic} /> },
    { to: '/candidate/invitations', label: 'Приглашения', icon: <Mail className={ic} />, badge: dash?.stats?.invitations_new },
    { to: '/candidate/vacancies', label: 'Вакансии', icon: <Briefcase className={ic} /> },
    { to: '/candidate/applications', label: 'Мои отклики', icon: <Send className={ic} /> },
    { to: '/candidate/tasks', label: 'Задания', icon: <ListChecks className={ic} />, badge: dash?.stats?.tasks_open },
    { to: '/candidate/settings', label: 'Настройки и ФСП ID', icon: <Settings className={ic} /> },
  ]
  if (role === 'employer') return [
    { to: '/employer', label: 'Главная', icon: <LayoutDashboard className={ic} />, end: true },
    { to: '/employer/needs', label: 'Потребности', icon: <FileText className={ic} /> },
    { to: '/employer/selections', label: 'Подборки', icon: <Sparkles className={ic} /> },
    { to: '/employer/search', label: 'Банк кандидатов', icon: <Search className={ic} /> },
    { to: '/employer/invitations', label: 'Приглашения', icon: <Send className={ic} /> },
    { to: '/employer/shortlist', label: 'Избранное', icon: <Star className={ic} /> },
    { to: '/employer/tasks', label: 'Задания', icon: <ListChecks className={ic} /> },
    { to: '/employer/company', label: 'Компания', icon: <Building2 className={ic} /> },
  ]
  return [
    { to: '/admin', label: 'Банк заданий', icon: <Database className={ic} />, end: true },
    { to: '/methodology', label: 'Методика', icon: <FlaskConical className={ic} /> },
  ]
}

export function Logo({ dark = false, compact = false }: { dark?: boolean; compact?: boolean }) {
  return (
    <Link to="/" className="group flex items-center gap-2.5">
      <motion.img whileHover={{ rotate: 72 }} transition={{ type: 'spring', stiffness: 200, damping: 12 }}
        src={dark ? '/brand/fsp-star-white.png' : '/brand/fsp-star-pink.png'} alt="" className="h-8 w-8" />
      {!compact && (
        <span className={clsx('leading-tight', dark ? 'text-white' : 'text-fsp-deep')}>
          <span className="block text-[15px] font-extrabold tracking-tight">ФСП Карьера</span>
          <span className={clsx('block text-[10px] font-semibold uppercase tracking-[0.16em]', dark ? 'text-white/55' : 'text-slate-400')}>доказанный уровень</span>
        </span>
      )}
    </Link>
  )
}

function Sidebar({ items, onNavigate, layoutKey }: { items: NavItem[]; onNavigate?: () => void; layoutKey: string }) {
  return (
    <nav className="space-y-0.5">
      {items.map(it => (
        <NavLink key={it.to} to={it.to} end={it.end} onClick={onNavigate}
          className={({ isActive }) => clsx('group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors duration-200',
            isActive ? 'font-semibold text-fsp-deep' : 'font-medium text-slate-500 hover:bg-slate-50 hover:text-fsp-deep')}>
          {({ isActive }) => (<>
            {isActive && <motion.span layoutId={`nav-${layoutKey}`} transition={SPRING} className="absolute inset-0 rounded-xl bg-[#F5F3FB]" />}
            {isActive && <motion.span layoutId={`nav-bar-${layoutKey}`} transition={SPRING} className="absolute -left-4 top-2 bottom-2 w-1 rounded-r-full bg-fsp-pink" />}
            <span className={clsx('relative transition-colors', isActive ? 'text-fsp-pink' : 'text-slate-400 group-hover:text-fsp-deep')}>{it.icon}</span>
            <span className="relative flex-1">{it.label}</span>
            {!!it.badge && (
              <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} transition={SPRING}
                className="relative grid h-5 min-w-5 place-items-center rounded-full bg-fsp-pink px-1.5 text-[11px] font-bold text-white">{it.badge}</motion.span>
            )}
          </>)}
        </NavLink>
      ))}
    </nav>
  )
}

function NotificationsBell() {
  const [open, setOpen] = useState(false)
  const qc = useQueryClient()
  const nav = useNavigate()
  const ref = useRef<HTMLDivElement>(null)
  const { data } = useQuery({ queryKey: ['notifications'], queryFn: () => api('/notifications'), refetchInterval: 30_000 })
  const read = useMutation({ mutationFn: () => api('/notifications/read', { method: 'POST' }), onSuccess: () => qc.invalidateQueries({ queryKey: ['notifications'] }) })
  useEffect(() => {
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])
  return (
    <div className="relative" ref={ref}>
      <motion.button whileTap={{ scale: 0.92 }} onClick={() => { setOpen(o => !o); if (!open && data?.unread) read.mutate() }}
        className="relative grid h-10 w-10 place-items-center rounded-xl text-slate-500 transition hover:bg-white hover:text-fsp-deep hover:shadow-soft" aria-label="Уведомления">
        <Bell className="h-[19px] w-[19px]" />
        {!!data?.unread && (<>
          <span className="absolute right-2 top-2 h-2.5 w-2.5 animate-pulse-ring rounded-full bg-fsp-pink" />
          <span className="absolute right-2 top-2 h-2.5 w-2.5 rounded-full bg-fsp-pink ring-2 ring-[#FAFAFC]" />
        </>)}
      </motion.button>
      <AnimatePresence>
        {open && (
          <motion.div initial={{ opacity: 0, y: -6, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -6, scale: 0.98 }}
            transition={{ duration: 0.2, ease: EASE }}
            className="absolute right-0 z-40 mt-2 w-[min(92vw,380px)] origin-top-right rounded-2xl border border-line bg-white p-2 shadow-pop">
            <p className="px-3 pb-1 pt-2 text-xs font-semibold text-slate-400">Уведомления</p>
            {!data?.items?.length && <div className="flex flex-col items-center gap-2 px-3 py-8 text-sm text-slate-400"><BellOff className="h-5 w-5" />Пока ничего нового</div>}
            <div className="max-h-96 overflow-y-auto">
              {data?.items?.map((n: any, i: number) => (
                <motion.button key={n.id} initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.03 }}
                  onClick={() => { setOpen(false); if (n.link) nav(n.link) }}
                  className="flex w-full gap-3 rounded-xl px-3 py-2.5 text-left transition hover:bg-surface">
                  <span className={clsx('mt-1.5 h-2 w-2 shrink-0 rounded-full', n.is_read ? 'bg-slate-200' : 'bg-fsp-pink')} />
                  <span className="min-w-0">
                    <span className={clsx('block text-sm', n.is_read ? 'text-slate-600' : 'font-semibold text-fsp-deep')}>{n.title}</span>
                    {n.body && <span className="mt-0.5 line-clamp-2 block text-xs text-slate-500">{n.body}</span>}
                    <span className="mt-1 block text-[11px] text-slate-400">{ago(n.created_at)}</span>
                  </span>
                </motion.button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export function AppShell({ role }: { role: 'candidate' | 'employer' | 'admin' }) {
  const { user, loading, signOut } = useAuth()
  const items = useNav(user?.role)
  const [drawer, setDrawer] = useState(false)
  const loc = useLocation()
  const outlet = useOutlet()
  useEffect(() => { setDrawer(false); window.scrollTo({ top: 0 }) }, [loc.pathname])
  if (loading) return <div className="p-10"><PageLoader /></div>
  if (!user) return <Navigate to={`/login?next=${encodeURIComponent(loc.pathname)}`} replace />
  if (user.role !== role) return <Navigate to={homeFor(user.role)} replace />
  const who = user.role === 'employer' ? user.company?.name : user.candidate?.full_name || user.email
  const roleName = role === 'employer' ? 'Работодатель' : role === 'admin' ? 'Администратор' : 'Кандидат'
  const current = [...items].sort((a, b) => b.to.length - a.to.length).find(i => loc.pathname === i.to || loc.pathname.startsWith(i.to + '/'))
  const side = (key: string) => (
    <div className="flex h-full flex-col px-4 py-5">
      <div className="px-2"><Logo /></div>
      <p className="mb-2 mt-8 px-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">{roleName}</p>
      <Sidebar items={items} onNavigate={() => setDrawer(false)} layoutKey={key} />
      <div className="mt-auto">
        <div className="flex items-center gap-3 rounded-2xl border border-line bg-surface/60 p-3">
          <Avatar name={who} />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-fsp-deep">{who}</p>
            <p className="truncate text-xs text-slate-400">{user.email}</p>
          </div>
          <motion.button whileTap={{ scale: 0.9 }} onClick={signOut} title="Выйти"
            className="grid h-8 w-8 place-items-center rounded-lg text-slate-400 transition hover:bg-white hover:text-fsp-pink"><LogOut className="h-4 w-4" /></motion.button>
        </div>
      </div>
    </div>
  )
  return (
    <div className="bg-app min-h-screen lg:pl-[264px]">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[264px] border-r border-line bg-white/80 backdrop-blur-xl lg:block">{side('desktop')}</aside>
      <AnimatePresence>
        {drawer && (
          <motion.div className="fixed inset-0 z-50 lg:hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <div className="absolute inset-0 bg-[#1b0a2e]/40 backdrop-blur-[2px]" onClick={() => setDrawer(false)} />
            <motion.aside initial={{ x: -320 }} animate={{ x: 0 }} exit={{ x: -320 }} transition={{ duration: 0.32, ease: EASE }}
              className="absolute inset-y-0 left-0 w-[84%] max-w-[300px] bg-white shadow-pop">
              <button onClick={() => setDrawer(false)} className="absolute right-3 top-5 grid h-9 w-9 place-items-center rounded-lg text-slate-400 hover:bg-slate-100" aria-label="Закрыть меню"><X className="h-5 w-5" /></button>
              {side('mobile')}
            </motion.aside>
          </motion.div>
        )}
      </AnimatePresence>
      <header className="sticky top-0 z-20 flex h-16 items-center justify-between gap-3 border-b border-line/70 bg-[#FAFAFC]/75 px-4 backdrop-blur-xl sm:px-6 lg:px-10">
        <div className="flex items-center gap-2 lg:hidden">
          <button onClick={() => setDrawer(true)} className="grid h-10 w-10 place-items-center rounded-xl text-slate-600 hover:bg-white" aria-label="Меню"><Menu className="h-5 w-5" /></button>
          <Logo compact />
        </div>
        <AnimatePresence mode="wait">
          <motion.div key={current?.to ?? 'x'} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }} transition={{ duration: 0.2 }}
            className="hidden items-center gap-2 text-sm lg:flex">
            <span className="text-slate-400">{roleName}</span><span className="text-slate-300">/</span>
            <span className="font-semibold text-fsp-deep">{current?.label ?? ''}</span>
          </motion.div>
        </AnimatePresence>
        <div className="flex items-center gap-1.5">
          <NotificationsBell />
          <div className="hidden sm:block"><Avatar name={who} className="h-9 w-9" /></div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-[1240px] px-4 py-7 sm:px-6 lg:px-10 lg:py-9">
        <motion.div key={loc.pathname} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.38, ease: EASE }}>
          <Suspense fallback={<PageLoader />}>{outlet}</Suspense>
        </motion.div>
      </main>
    </div>
  )
}
