import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Link, NavLink, Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import {
  Award, Bell, Briefcase, Building2, ClipboardCheck, Database, FileText, FlaskConical, LayoutDashboard, ListChecks, LogOut,
  Mail, Menu, Search, Send, Settings, Sparkles, Star, UserRound, X,
} from 'lucide-react'
import { api } from '@/lib/api'
import { homeFor, useAuth } from '@/lib/auth'
import { ago } from '@/lib/format'
import { PageLoader } from './ui'

type NavItem = { to: string; label: string; icon: ReactNode; end?: boolean; badge?: number }

function useNav(role?: string): NavItem[] {
  const isCand = role === 'candidate'
  const { data: dash } = useQuery({ queryKey: ['cand-dashboard'], queryFn: () => api('/candidate/dashboard'), enabled: isCand, staleTime: 30_000 })
  const ic = 'h-[18px] w-[18px]'
  if (role === 'candidate') return [
    { to: '/candidate', label: 'Главная', icon: <LayoutDashboard className={ic} />, end: true },
    { to: '/candidate/profile', label: 'Профиль и резюме', icon: <UserRound className={ic} /> },
    { to: '/candidate/testing', label: 'Опрос и тестирование', icon: <ClipboardCheck className={ic} /> },
    { to: '/candidate/grade', label: 'Категория и грейд', icon: <Award className={ic} /> },
    { to: '/candidate/invitations', label: 'Приглашения', icon: <Mail className={ic} />, badge: dash?.stats?.invitations_new },
    { to: '/candidate/vacancies', label: 'Вакансии', icon: <Briefcase className={ic} /> },
    { to: '/candidate/applications', label: 'Мои отклики', icon: <Send className={ic} /> },
    { to: '/candidate/tasks', label: 'Задания', icon: <ListChecks className={ic} />, badge: dash?.stats?.tasks_open },
    { to: '/candidate/settings', label: 'Настройки и ФСП ID', icon: <Settings className={ic} /> },
  ]
  if (role === 'employer') return [
    { to: '/employer', label: 'Главная', icon: <LayoutDashboard className={ic} />, end: true },
    { to: '/employer/needs', label: 'Потребности и вакансии', icon: <FileText className={ic} /> },
    { to: '/employer/selections', label: 'Подборки', icon: <Sparkles className={ic} /> },
    { to: '/employer/search', label: 'Банк кандидатов', icon: <Search className={ic} /> },
    { to: '/employer/invitations', label: 'Приглашения', icon: <Send className={ic} /> },
    { to: '/employer/shortlist', label: 'Избранное', icon: <Star className={ic} /> },
    { to: '/employer/tasks', label: 'Задания', icon: <ListChecks className={ic} /> },
    { to: '/employer/company', label: 'Компания', icon: <Building2 className={ic} /> },
  ]
  return [
    { to: '/admin', label: 'Банк заданий', icon: <Database className={ic} />, end: true },
    { to: '/methodology', label: 'Методика и валидация', icon: <FlaskConical className={ic} /> },
  ]
}

export function Logo({ dark = false, compact = false }: { dark?: boolean; compact?: boolean }) {
  return (
    <Link to="/" className="flex items-center gap-2.5">
      <img src={dark ? '/brand/fsp-star-white.png' : '/brand/fsp-star-pink.png'} alt="" className="h-8 w-8" />
      {!compact && (
        <span className={clsx('leading-tight', dark ? 'text-white' : 'text-fsp-deep')}>
          <span className="block text-[15px] font-extrabold tracking-tight">ФСП Карьера</span>
          <span className={clsx('block text-[10px] font-medium uppercase tracking-[0.14em]', dark ? 'text-white/60' : 'text-slate-400')}>ИТ-таланты с доказанным уровнем</span>
        </span>
      )}
    </Link>
  )
}

function Sidebar({ items, onNavigate }: { items: NavItem[]; onNavigate?: () => void }) {
  return (
    <nav className="space-y-1">
      {items.map(it => (
        <NavLink key={it.to} to={it.to} end={it.end} onClick={onNavigate}
          className={({ isActive }) => clsx('group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition',
            isActive ? 'bg-white text-fsp-deep shadow-sm' : 'text-white/75 hover:bg-white/10 hover:text-white')}>
          {({ isActive }) => (<>
            <span className={clsx(isActive ? 'text-fsp-pink' : 'text-white/60 group-hover:text-white')}>{it.icon}</span>
            <span className="flex-1">{it.label}</span>
            {!!it.badge && <span className="rounded-full bg-fsp-pink px-2 py-0.5 text-[11px] font-bold text-white">{it.badge}</span>}
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
      <button onClick={() => { setOpen(o => !o); if (!open && data?.unread) read.mutate() }}
        className="relative grid h-10 w-10 place-items-center rounded-xl text-fsp-deep hover:bg-white" aria-label="Уведомления">
        <Bell className="h-5 w-5" />
        {!!data?.unread && <span className="absolute right-1.5 top-1.5 grid h-4 min-w-4 place-items-center rounded-full bg-fsp-pink px-1 text-[10px] font-bold text-white">{data.unread}</span>}
      </button>
      {open && (
        <div className="absolute right-0 z-40 mt-2 w-[min(92vw,380px)] rounded-2xl bg-white p-2 shadow-pop ring-1 ring-slate-100">
          <p className="px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Уведомления</p>
          {!data?.items?.length && <p className="px-3 py-6 text-center text-sm text-slate-400">Пока ничего нового</p>}
          <div className="max-h-96 overflow-y-auto">
            {data?.items?.map((n: any) => (
              <button key={n.id} onClick={() => { setOpen(false); if (n.link) nav(n.link) }}
                className="block w-full rounded-xl px-3 py-2.5 text-left hover:bg-surface">
                <p className={clsx('text-sm', n.is_read ? 'text-slate-600' : 'font-semibold text-fsp-deep')}>{n.title}</p>
                {n.body && <p className="mt-0.5 line-clamp-2 text-xs text-slate-500">{n.body}</p>}
                <p className="mt-1 text-[11px] text-slate-400">{ago(n.created_at)}</p>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export function AppShell({ role }: { role: 'candidate' | 'employer' | 'admin' }) {
  const { user, loading, signOut } = useAuth()
  const items = useNav(user?.role)
  const [drawer, setDrawer] = useState(false)
  const loc = useLocation()
  useEffect(() => { setDrawer(false); window.scrollTo(0, 0) }, [loc.pathname])
  if (loading) return <PageLoader />
  if (!user) return <Navigate to={`/login?next=${encodeURIComponent(loc.pathname)}`} replace />
  if (user.role !== role) return <Navigate to={homeFor(user.role)} replace />
  const who = user.role === 'employer' ? user.company?.name : user.candidate?.full_name || user.email
  const side = (
    <div className="flex h-full flex-col gap-6 p-4">
      <div className="px-1 pt-1"><Logo dark /></div>
      <Sidebar items={items} onNavigate={() => setDrawer(false)} />
      <div className="mt-auto rounded-2xl bg-white/10 p-3 text-white">
        <p className="text-[11px] uppercase tracking-wider text-white/50">{role === 'employer' ? 'Работодатель' : role === 'admin' ? 'Администратор' : 'Кандидат'}</p>
        <p className="mt-0.5 truncate text-sm font-semibold">{who}</p>
        <button onClick={signOut} className="mt-2 inline-flex items-center gap-1.5 text-xs text-white/70 hover:text-white">
          <LogOut className="h-3.5 w-3.5" /> Выйти
        </button>
      </div>
    </div>
  )
  return (
    <div className="min-h-screen lg:pl-72">
      <aside className="bg-brand-gradient fixed inset-y-0 left-0 z-30 hidden w-72 lg:block">{side}</aside>
      {drawer && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-fsp-deep/50" onClick={() => setDrawer(false)} />
          <aside className="bg-brand-gradient absolute inset-y-0 left-0 w-[84%] max-w-xs shadow-pop">
            <button onClick={() => setDrawer(false)} className="absolute right-3 top-4 text-white/70" aria-label="Закрыть меню"><X className="h-5 w-5" /></button>
            {side}
          </aside>
        </div>
      )}
      <header className="sticky top-0 z-20 flex h-16 items-center justify-between gap-3 border-b border-black/[0.04] bg-surface/85 px-4 backdrop-blur sm:px-6 lg:px-10">
        <div className="flex items-center gap-2 lg:hidden">
          <button onClick={() => setDrawer(true)} className="grid h-10 w-10 place-items-center rounded-xl hover:bg-white" aria-label="Меню"><Menu className="h-5 w-5" /></button>
          <Logo compact />
        </div>
        <div className="hidden text-sm text-slate-500 lg:block">{who}</div>
        <div className="flex items-center gap-1">
          <NotificationsBell />
        </div>
      </header>
      <main className="mx-auto w-full max-w-[1280px] px-4 py-6 sm:px-6 lg:px-10 lg:py-8">
        <Outlet />
      </main>
    </div>
  )
}
