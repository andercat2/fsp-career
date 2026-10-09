import { useEffect, useId, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes,
  type TextareaHTMLAttributes } from 'react'
import { Link } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import clsx from 'clsx'
import { Check, ChevronDown, LoaderCircle, X } from 'lucide-react'
import { CountUp, EASE, SPRING } from '@/lib/motion'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'soft' | 'dark'
type Size = 'sm' | 'md' | 'lg'

const btnBase = 'relative inline-flex select-none items-center justify-center gap-2 overflow-hidden rounded-xl font-semibold ' +
  'transition-[background,box-shadow,color,border-color] duration-200 disabled:cursor-not-allowed disabled:opacity-50'
const btnVariant: Record<Variant, string> = {
  primary: 'bg-gradient-to-b from-[#ea0f57] to-fsp-pink text-white shadow-[0_1px_0_rgba(255,255,255,.25)_inset,0_6px_16px_-8px_rgba(255,0,83,.7)] hover:shadow-glow',
  secondary: 'border border-line bg-white text-fsp-deep shadow-soft hover:border-[#D9D4E7] hover:bg-[#FCFBFE]',
  ghost: 'text-slate-600 hover:bg-fsp-deep/[0.05] hover:text-fsp-deep',
  danger: 'border border-red-100 bg-white text-red-600 hover:bg-red-50',
  soft: 'bg-[#FFF0F5] text-[#c4004a] hover:bg-[#FFE3EC]',
  dark: 'bg-fsp-deep text-white shadow-[0_8px_20px_-10px_rgba(49,15,83,.8)] hover:bg-[#3d1466]',
}
const btnSize: Record<Size, string> = { sm: 'h-8 px-3 text-xs', md: 'h-10 px-4 text-sm', lg: 'h-12 px-6 text-[15px]' }

type BtnProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'onAnimationStart' | 'onDrag' | 'onDragEnd' | 'onDragStart'> & {
  variant?: Variant; size?: Size; loading?: boolean; icon?: ReactNode
}

export function Button({ variant = 'primary', size = 'md', loading, icon, className, children, disabled, ...rest }: BtnProps) {
  return (
    <motion.button whileTap={disabled || loading ? undefined : { scale: 0.97 }} transition={SPRING}
      className={clsx(btnBase, btnVariant[variant], btnSize[size], className)} disabled={disabled || loading} {...(rest as any)}>
      {loading ? <LoaderCircle className="h-4 w-4 animate-spin" /> : icon}
      {children}
    </motion.button>
  )
}

const MotionLink = motion.create(Link)

export function ButtonLink({ to, variant = 'primary', size = 'md', icon, className, children }: {
  to: string; variant?: Variant; size?: Size; icon?: ReactNode; className?: string; children: ReactNode
}) {
  return (
    <MotionLink to={to} whileTap={{ scale: 0.97 }} transition={SPRING} className={clsx(btnBase, btnVariant[variant], btnSize[size], className)}>
      {icon}{children}
    </MotionLink>
  )
}

export function Card({ title, subtitle, actions, className, children, pad = true, hover = false }: {
  title?: ReactNode; subtitle?: ReactNode; actions?: ReactNode; className?: string; children?: ReactNode; pad?: boolean; hover?: boolean
}) {
  return (
    <motion.section initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, ease: EASE }}
      className={clsx('card', hover && 'card-hover', className)}>
      {(title || actions) && (
        <header className="flex flex-wrap items-start justify-between gap-3 px-5 pt-5 sm:px-6">
          <div className="min-w-0">
            {title && <h3 className="text-[15px] font-bold text-fsp-deep">{title}</h3>}
            {subtitle && <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p>}
          </div>
          {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={clsx(pad && 'card-pad', (title || actions) && pad && '!pt-4')}>{children}</div>
    </motion.section>
  )
}

type Tone = 'pink' | 'purple' | 'lavender' | 'green' | 'amber' | 'red' | 'gray' | 'blue'
const tones: Record<Tone, string> = {
  pink: 'bg-[#FFF0F5] text-[#c4004a] ring-1 ring-inset ring-[#FFD6E4]',
  purple: 'bg-fsp-deep text-white',
  lavender: 'bg-[#F2F1FC] text-[#4b4392] ring-1 ring-inset ring-[#E3E1F7]',
  green: 'bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-100',
  amber: 'bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-100',
  red: 'bg-red-50 text-red-700 ring-1 ring-inset ring-red-100',
  gray: 'bg-slate-50 text-slate-600 ring-1 ring-inset ring-slate-200/70',
  blue: 'bg-sky-50 text-sky-700 ring-1 ring-inset ring-sky-100',
}

export function Badge({ tone = 'gray', children, className, icon }: { tone?: Tone; children: ReactNode; className?: string; icon?: ReactNode }) {
  return <span className={clsx('chip', tones[tone], className)}>{icon}{children}</span>
}

export function Field({ label, hint, error, children, className, required }: {
  label?: ReactNode; hint?: ReactNode; error?: ReactNode; children: ReactNode; className?: string; required?: boolean
}) {
  return (
    <label className={clsx('block', className)}>
      {label && <span className="label">{label}{required && <span className="text-fsp-pink"> *</span>}</span>}
      {children}
      {hint && !error && <span className="mt-1.5 block text-xs text-slate-400">{hint}</span>}
      {error && <span className="mt-1.5 block text-xs text-red-600">{error}</span>}
    </label>
  )
}

export const Input = ({ className, ...p }: InputHTMLAttributes<HTMLInputElement>) => <input className={clsx('input', className)} {...p} />
export const Textarea = ({ className, ...p }: TextareaHTMLAttributes<HTMLTextAreaElement>) =>
  <textarea className={clsx('input min-h-[96px] leading-relaxed', className)} {...p} />
export const Select = ({ className, children, ...p }: SelectHTMLAttributes<HTMLSelectElement>) => (
  <div className={clsx('relative', className)}>
    <select className="input appearance-none pr-9" {...p}>{children}</select>
    <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
  </div>
)

export function Toggle({ checked, onChange, label, hint, disabled }: {
  checked: boolean; onChange: (v: boolean) => void; label: ReactNode; hint?: ReactNode; disabled?: boolean
}) {
  return (
    <label className={clsx('flex cursor-pointer items-start justify-between gap-4 py-2.5', disabled && 'opacity-60')}>
      <span>
        <span className="block text-sm font-medium text-fsp-ink">{label}</span>
        {hint && <span className="mt-0.5 block text-xs leading-relaxed text-slate-500">{hint}</span>}
      </span>
      <button type="button" role="switch" aria-checked={checked} disabled={disabled} onClick={() => onChange(!checked)}
        className={clsx('relative mt-0.5 flex h-6 w-11 shrink-0 items-center rounded-full p-0.5 transition-colors duration-300',
          checked ? 'bg-fsp-pink' : 'bg-slate-200')}>
        <motion.span layout transition={SPRING} className={clsx('h-5 w-5 rounded-full bg-white shadow-md', checked && 'ml-auto')} />
      </button>
    </label>
  )
}

export function Checkbox({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: ReactNode }) {
  return (
    <label className="flex cursor-pointer items-center gap-2.5 text-sm">
      <span className={clsx('grid h-5 w-5 shrink-0 place-items-center rounded-md border transition-colors duration-200',
        checked ? 'border-fsp-pink bg-fsp-pink text-white' : 'border-[#D6D1E4] bg-white')}>
        <AnimatePresence>{checked && (
          <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }} transition={SPRING}><Check className="h-3.5 w-3.5" strokeWidth={3} /></motion.span>
        )}</AnimatePresence>
      </span>
      <input type="checkbox" className="sr-only" checked={checked} onChange={e => onChange(e.target.checked)} />
      {label}
    </label>
  )
}

export function Spinner({ className }: { className?: string }) {
  return <LoaderCircle className={clsx('h-5 w-5 animate-spin text-fsp-pink', className)} />
}

export function Skeleton({ className }: { className?: string }) {
  return (
    <div className={clsx('relative overflow-hidden rounded-xl bg-[#F1EFF6]', className)}>
      <div className="absolute inset-0 -translate-x-full animate-shimmer bg-gradient-to-r from-transparent via-white/70 to-transparent" />
    </div>
  )
}

/** Скелетон страницы вместо спиннера: интерфейс «проявляется», а не мигает. */
export function PageLoader() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Загрузка">
      <div className="space-y-2.5"><Skeleton className="h-8 w-72" /><Skeleton className="h-4 w-[28rem] max-w-full" /></div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{[0, 1, 2, 3].map(i => <Skeleton key={i} className="h-24 rounded-[20px]" />)}</div>
      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]"><Skeleton className="h-64 rounded-[20px]" /><Skeleton className="h-64 rounded-[20px]" /></div>
    </div>
  )
}

export function EmptyState({ icon, title, text, action }: { icon?: ReactNode; title: string; text?: ReactNode; action?: ReactNode }) {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, ease: EASE }}
      className="flex flex-col items-center justify-center rounded-[20px] border border-dashed border-[#E2DEEE] bg-white/60 px-6 py-14 text-center">
      {icon && <div className="mb-4 grid h-12 w-12 animate-float place-items-center rounded-2xl bg-gradient-to-br from-[#FFF0F5] to-[#F2F1FC] text-fsp-pink ring-1 ring-line">{icon}</div>}
      <p className="font-semibold text-fsp-deep">{title}</p>
      {text && <p className="mt-1.5 max-w-md text-sm leading-relaxed text-slate-500">{text}</p>}
      {action && <div className="mt-5">{action}</div>}
    </motion.div>
  )
}

export function Tabs<T extends string>({ value, onChange, items }: {
  value: T; onChange: (v: T) => void; items: { value: T; label: ReactNode; count?: number }[]
}) {
  const id = useId()
  return (
    <div className="scrollbar-thin -mx-1 overflow-x-auto px-1">
      <div className="inline-flex gap-1 rounded-2xl border border-line bg-white p-1 shadow-soft">
        {items.map(it => {
          const active = value === it.value
          return (
            <button key={it.value} onClick={() => onChange(it.value)}
              className={clsx('relative flex shrink-0 items-center gap-2 rounded-xl px-3.5 py-2 text-sm font-semibold transition-colors',
                active ? 'text-white' : 'text-slate-500 hover:text-fsp-deep')}>
              {active && <motion.span layoutId={`tab-${id}`} transition={SPRING} className="absolute inset-0 rounded-xl bg-fsp-deep" />}
              <span className="relative">{it.label}</span>
              {it.count != null && (
                <span className={clsx('relative rounded-full px-1.5 text-[11px] tabular-nums', active ? 'bg-white/20' : 'bg-slate-100')}>{it.count}</span>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}

export function Modal({ open, onClose, title, children, footer, wide }: {
  open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; footer?: ReactNode; wide?: boolean
}) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.removeEventListener('keydown', onKey); document.body.style.overflow = prev }
  }, [open, onClose])
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-50 flex items-end justify-center p-0 sm:items-center sm:p-6" role="dialog" aria-modal="true"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
          <div className="absolute inset-0 bg-[#1b0a2e]/40 backdrop-blur-[3px]" onMouseDown={onClose} />
          <motion.div initial={{ opacity: 0, y: 24, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 16, scale: 0.98 }}
            transition={{ duration: 0.32, ease: EASE }}
            className={clsx('relative flex max-h-[92vh] w-full flex-col rounded-t-[28px] bg-white shadow-pop sm:rounded-[28px]', wide ? 'sm:max-w-3xl' : 'sm:max-w-lg')}>
            <div className="flex items-center justify-between gap-4 px-6 pb-2 pt-5">
              <h3 className="text-lg font-bold">{title}</h3>
              <button onClick={onClose} className="grid h-9 w-9 place-items-center rounded-xl text-slate-400 transition hover:bg-slate-100 hover:text-slate-700" aria-label="Закрыть">
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="scrollbar-thin overflow-y-auto px-6 py-4">{children}</div>
            {footer && <div className="flex flex-wrap justify-end gap-2 border-t border-line px-6 py-4">{footer}</div>}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

/** Число в карточке плавно досчитывается, если значение похоже на число («40%», «23.8 ч», 307). */
function AnimatedValue({ value }: { value: ReactNode }) {
  if (typeof value === 'number') return <CountUp value={value} decimals={Number.isInteger(value) ? 0 : 1} />
  if (typeof value === 'string') {
    const m = /^(\d+(?:[.,]\d+)?)(\s?\S*)$/.exec(value.trim())
    if (m) {
      const num = Number(m[1].replace(',', '.'))
      const decimals = m[1].includes('.') || m[1].includes(',') ? 1 : 0
      return <CountUp value={num} decimals={decimals} suffix={m[2]} />
    }
  }
  return <>{value}</>
}

export function Stat({ label, value, hint, icon, accent }: { label: ReactNode; value: ReactNode; hint?: ReactNode; icon?: ReactNode; accent?: boolean }) {
  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, ease: EASE }}
      className={clsx('group relative overflow-hidden rounded-[20px] p-5 transition duration-300',
        accent ? 'bg-brand-gradient text-white shadow-lift' : 'card card-hover')}>
      {accent && <div className="pointer-events-none absolute -right-10 -top-10 h-32 w-32 rounded-full bg-fsp-pink/40 blur-2xl transition duration-500 group-hover:scale-125" />}
      <div className="relative flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className={clsx('text-xs font-semibold', accent ? 'text-white/70' : 'text-slate-500')}>{label}</p>
          <p className={clsx('mt-2 text-[28px] font-bold leading-none tracking-tight tabular-nums', accent ? 'text-white' : 'text-fsp-deep')}><AnimatedValue value={value} /></p>
          {hint && <p className={clsx('mt-2 text-xs', accent ? 'text-white/65' : 'text-slate-400')}>{hint}</p>}
        </div>
        {icon && <div className={clsx('grid h-10 w-10 shrink-0 place-items-center rounded-xl transition duration-300 group-hover:scale-110',
          accent ? 'bg-white/15 text-white' : 'bg-[#FFF0F5] text-fsp-pink')}>{icon}</div>}
      </div>
    </motion.div>
  )
}

export function Progress({ value, className, tone = 'pink' }: { value: number; className?: string; tone?: 'pink' | 'lavender' | 'green' | 'deep' }) {
  const color = { pink: 'bg-gradient-to-r from-fsp-pink to-[#ff4d8a]', lavender: 'bg-fsp-lavender', green: 'bg-emerald-500', deep: 'bg-fsp-deep' }[tone]
  return (
    <div className={clsx('h-2 w-full overflow-hidden rounded-full bg-[#F1EFF6]', className)}>
      <motion.div className={clsx('h-full rounded-full', color)} initial={{ width: 0 }}
        animate={{ width: `${Math.max(2, Math.min(100, value * 100))}%` }} transition={{ duration: 0.8, ease: EASE }} />
    </div>
  )
}

export function PageHeader({ title, subtitle, actions, back }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode; back?: ReactNode }) {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, ease: EASE }}
      className="mb-7 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {back}
        <h1 className="text-[26px] font-bold tracking-tight sm:text-[30px]">{title}</h1>
        {subtitle && <div className="mt-1.5 max-w-3xl text-sm leading-relaxed text-slate-500">{subtitle}</div>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </motion.div>
  )
}

export function ChoiceCard({ selected, onClick, title, hint, disabled, badge, children }: {
  selected: boolean; onClick: () => void; title: ReactNode; hint?: ReactNode; disabled?: boolean; badge?: ReactNode; children?: ReactNode
}) {
  return (
    <motion.button type="button" onClick={onClick} disabled={disabled} whileTap={disabled ? undefined : { scale: 0.985 }} transition={SPRING}
      className={clsx('relative w-full rounded-2xl border p-4 text-left transition duration-200',
        selected ? 'border-fsp-pink bg-[#FFF5F8] shadow-[0_0_0_3px_rgba(255,0,83,.08)]' : 'border-line bg-white hover:border-[#D9D4E7] hover:shadow-card',
        disabled && 'cursor-not-allowed opacity-50')}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-semibold text-fsp-deep">{title}</p>
          {hint && <p className="mt-1 text-xs leading-relaxed text-slate-500">{hint}</p>}
        </div>
        <span className={clsx('grid h-5 w-5 shrink-0 place-items-center rounded-full border transition-colors',
          selected ? 'border-fsp-pink bg-fsp-pink text-white' : 'border-[#D6D1E4]')}>
          <AnimatePresence>{selected && (
            <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }} transition={SPRING}><Check className="h-3 w-3" strokeWidth={3} /></motion.span>
          )}</AnimatePresence>
        </span>
      </div>
      {badge && <div className="mt-2">{badge}</div>}
      {children}
    </motion.button>
  )
}

export function KV({ k, v }: { k: ReactNode; v: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-2 text-sm">
      <span className="text-slate-500">{k}</span>
      <span className="text-right font-medium text-fsp-ink">{v}</span>
    </div>
  )
}

export function Alert({ tone = 'info', title, children, icon }: { tone?: 'info' | 'warn' | 'error' | 'success'; title?: ReactNode; children?: ReactNode; icon?: ReactNode }) {
  const cls = {
    info: 'bg-[#F4F3FD] text-[#3c3480] border-[#E6E4F8]', warn: 'bg-amber-50/80 text-amber-900 border-amber-100',
    error: 'bg-red-50/80 text-red-700 border-red-100', success: 'bg-emerald-50/80 text-emerald-800 border-emerald-100',
  }[tone]
  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, ease: EASE }}
      className={clsx('flex gap-3 rounded-2xl border px-4 py-3 text-sm', cls)}>
      {icon && <div className="mt-0.5 shrink-0">{icon}</div>}
      <div className="min-w-0">{title && <p className="font-semibold">{title}</p>}{children && <div className={clsx(title && 'mt-0.5', 'leading-relaxed')}>{children}</div>}</div>
    </motion.div>
  )
}

export function Avatar({ name, className }: { name?: string | null; className?: string }) {
  const initials = (name ?? '?').split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0]?.toUpperCase()).join('') || '?'
  return (
    <span className={clsx('grid shrink-0 place-items-center rounded-xl bg-gradient-to-br from-fsp-pink to-fsp-lavender text-xs font-bold text-white', className ?? 'h-9 w-9')}>
      {initials}
    </span>
  )
}
