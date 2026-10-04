import { useEffect, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes,
  type TextareaHTMLAttributes } from 'react'
import { Link } from 'react-router-dom'
import clsx from 'clsx'
import { Check, LoaderCircle, X } from 'lucide-react'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'soft' | 'dark'
type Size = 'sm' | 'md' | 'lg'

const btnBase = 'inline-flex select-none items-center justify-center gap-2 rounded-xl font-semibold transition ' +
  'disabled:cursor-not-allowed disabled:opacity-50 active:scale-[.98]'
const btnVariant: Record<Variant, string> = {
  primary: 'bg-fsp-pink text-white shadow-sm shadow-fsp-pink/30 hover:bg-[#e6004b]',
  secondary: 'bg-white text-fsp-deep ring-1 ring-[#E4E1EE] hover:ring-fsp-lavender hover:bg-surface',
  ghost: 'text-fsp-deep hover:bg-fsp-deep/5',
  danger: 'bg-white text-red-600 ring-1 ring-red-200 hover:bg-red-50',
  soft: 'bg-fsp-blush/60 text-fsp-deep hover:bg-fsp-blush',
  dark: 'bg-fsp-deep text-white hover:bg-fsp-purple',
}
const btnSize: Record<Size, string> = { sm: 'h-8 px-3 text-xs', md: 'h-10 px-4 text-sm', lg: 'h-12 px-6 text-base' }

type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant; size?: Size; loading?: boolean; icon?: ReactNode
}

export function Button({ variant = 'primary', size = 'md', loading, icon, className, children, disabled, ...rest }: BtnProps) {
  return (
    <button className={clsx(btnBase, btnVariant[variant], btnSize[size], className)} disabled={disabled || loading} {...rest}>
      {loading ? <LoaderCircle className="h-4 w-4 animate-spin" /> : icon}
      {children}
    </button>
  )
}

export function ButtonLink({ to, variant = 'primary', size = 'md', icon, className, children }: {
  to: string; variant?: Variant; size?: Size; icon?: ReactNode; className?: string; children: ReactNode
}) {
  return (
    <Link to={to} className={clsx(btnBase, btnVariant[variant], btnSize[size], className)}>
      {icon}{children}
    </Link>
  )
}

export function Card({ title, subtitle, actions, className, children, pad = true }: {
  title?: ReactNode; subtitle?: ReactNode; actions?: ReactNode; className?: string; children?: ReactNode; pad?: boolean
}) {
  return (
    <section className={clsx('card', className)}>
      {(title || actions) && (
        <header className="flex flex-wrap items-start justify-between gap-3 px-5 pt-5 sm:px-6">
          <div className="min-w-0">
            {title && <h3 className="text-base font-bold text-fsp-deep">{title}</h3>}
            {subtitle && <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p>}
          </div>
          {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={clsx(pad && 'card-pad', (title || actions) && pad && '!pt-4')}>{children}</div>
    </section>
  )
}

type Tone = 'pink' | 'purple' | 'lavender' | 'green' | 'amber' | 'red' | 'gray' | 'blue'
const tones: Record<Tone, string> = {
  pink: 'bg-fsp-blush/70 text-[#b0003a]',
  purple: 'bg-fsp-deep text-white',
  lavender: 'bg-[#ECEAFB] text-[#4b4392]',
  green: 'bg-emerald-50 text-emerald-700',
  amber: 'bg-amber-50 text-amber-700',
  red: 'bg-red-50 text-red-700',
  gray: 'bg-slate-100 text-slate-600',
  blue: 'bg-sky-50 text-sky-700',
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
      {hint && !error && <span className="mt-1 block text-xs text-slate-400">{hint}</span>}
      {error && <span className="mt-1 block text-xs text-red-600">{error}</span>}
    </label>
  )
}

export const Input = ({ className, ...p }: InputHTMLAttributes<HTMLInputElement>) => <input className={clsx('input', className)} {...p} />
export const Textarea = ({ className, ...p }: TextareaHTMLAttributes<HTMLTextAreaElement>) =>
  <textarea className={clsx('input min-h-[96px] leading-relaxed', className)} {...p} />
export const Select = ({ className, children, ...p }: SelectHTMLAttributes<HTMLSelectElement>) =>
  <select className={clsx('input pr-8', className)} {...p}>{children}</select>

export function Toggle({ checked, onChange, label, hint, disabled }: {
  checked: boolean; onChange: (v: boolean) => void; label: ReactNode; hint?: ReactNode; disabled?: boolean
}) {
  return (
    <label className={clsx('flex cursor-pointer items-start justify-between gap-4 py-2', disabled && 'opacity-60')}>
      <span>
        <span className="block text-sm font-medium text-fsp-ink">{label}</span>
        {hint && <span className="mt-0.5 block text-xs text-slate-500">{hint}</span>}
      </span>
      <button type="button" role="switch" aria-checked={checked} disabled={disabled} onClick={() => onChange(!checked)}
        className={clsx('relative mt-0.5 h-6 w-11 shrink-0 rounded-full transition', checked ? 'bg-fsp-pink' : 'bg-slate-300')}>
        <span className={clsx('absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition', checked ? 'left-[22px]' : 'left-0.5')} />
      </button>
    </label>
  )
}

export function Checkbox({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: ReactNode }) {
  return (
    <label className="flex cursor-pointer items-center gap-2 text-sm">
      <span className={clsx('grid h-5 w-5 place-items-center rounded-md ring-1 transition',
        checked ? 'bg-fsp-pink text-white ring-fsp-pink' : 'bg-white ring-slate-300')}>
        {checked && <Check className="h-3.5 w-3.5" />}
      </span>
      <input type="checkbox" className="sr-only" checked={checked} onChange={e => onChange(e.target.checked)} />
      {label}
    </label>
  )
}

export function Spinner({ className }: { className?: string }) {
  return <LoaderCircle className={clsx('h-5 w-5 animate-spin text-fsp-pink', className)} />
}

export function PageLoader() {
  return <div className="grid min-h-[40vh] place-items-center"><Spinner className="h-8 w-8" /></div>
}

export function EmptyState({ icon, title, text, action }: { icon?: ReactNode; title: string; text?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-white/60 px-6 py-12 text-center">
      {icon && <div className="mb-3 grid h-12 w-12 place-items-center rounded-2xl bg-fsp-blush/60 text-fsp-pink">{icon}</div>}
      <p className="font-semibold text-fsp-deep">{title}</p>
      {text && <p className="mt-1 max-w-md text-sm text-slate-500">{text}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function Tabs<T extends string>({ value, onChange, items }: {
  value: T; onChange: (v: T) => void; items: { value: T; label: ReactNode; count?: number }[]
}) {
  return (
    <div className="scrollbar-thin -mx-1 flex gap-1 overflow-x-auto px-1">
      {items.map(it => (
        <button key={it.value} onClick={() => onChange(it.value)}
          className={clsx('flex shrink-0 items-center gap-2 rounded-xl px-3.5 py-2 text-sm font-semibold transition',
            value === it.value ? 'bg-fsp-deep text-white' : 'text-slate-600 hover:bg-white')}>
          {it.label}
          {it.count != null && (
            <span className={clsx('rounded-full px-1.5 text-[11px]', value === it.value ? 'bg-white/20' : 'bg-slate-200')}>{it.count}</span>
          )}
        </button>
      ))}
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
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-fsp-deep/40 p-0 backdrop-blur-[2px] sm:items-center sm:p-6"
         onMouseDown={e => e.target === e.currentTarget && onClose()} role="dialog" aria-modal="true">
      <div className={clsx('flex max-h-[92vh] w-full flex-col rounded-t-3xl bg-white shadow-pop sm:rounded-3xl', wide ? 'sm:max-w-3xl' : 'sm:max-w-lg')}>
        <div className="flex items-center justify-between gap-4 border-b border-slate-100 px-6 py-4">
          <h3 className="text-lg font-bold">{title}</h3>
          <button onClick={onClose} className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600" aria-label="Закрыть">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="scrollbar-thin overflow-y-auto px-6 py-5">{children}</div>
        {footer && <div className="flex flex-wrap justify-end gap-2 border-t border-slate-100 px-6 py-4">{footer}</div>}
      </div>
    </div>
  )
}

export function Stat({ label, value, hint, icon, accent }: { label: ReactNode; value: ReactNode; hint?: ReactNode; icon?: ReactNode; accent?: boolean }) {
  return (
    <div className={clsx('card card-pad flex items-start gap-4', accent && 'bg-brand-gradient text-white ring-0')}>
      {icon && <div className={clsx('grid h-11 w-11 shrink-0 place-items-center rounded-2xl', accent ? 'bg-white/15' : 'bg-fsp-blush/60 text-fsp-pink')}>{icon}</div>}
      <div className="min-w-0">
        <p className={clsx('text-xs font-semibold uppercase tracking-wide', accent ? 'text-white/70' : 'text-slate-500')}>{label}</p>
        <p className={clsx('mt-1 text-2xl font-bold', accent ? 'text-white' : 'text-fsp-deep')}>{value}</p>
        {hint && <p className={clsx('mt-0.5 text-xs', accent ? 'text-white/70' : 'text-slate-500')}>{hint}</p>}
      </div>
    </div>
  )
}

export function Progress({ value, className, tone = 'pink' }: { value: number; className?: string; tone?: 'pink' | 'lavender' | 'green' | 'deep' }) {
  const color = { pink: 'bg-fsp-pink', lavender: 'bg-fsp-lavender', green: 'bg-emerald-500', deep: 'bg-fsp-deep' }[tone]
  return (
    <div className={clsx('h-2 w-full overflow-hidden rounded-full bg-slate-100', className)}>
      <div className={clsx('h-full rounded-full transition-all', color)} style={{ width: `${Math.max(2, Math.min(100, value * 100))}%` }} />
    </div>
  )
}

export function PageHeader({ title, subtitle, actions, back }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode; back?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {back}
        <h1 className="text-2xl font-bold tracking-tight sm:text-[28px]">{title}</h1>
        {subtitle && <p className="mt-1 max-w-3xl text-sm text-slate-500">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

export function ChoiceCard({ selected, onClick, title, hint, disabled, badge, children }: {
  selected: boolean; onClick: () => void; title: ReactNode; hint?: ReactNode; disabled?: boolean; badge?: ReactNode; children?: ReactNode
}) {
  return (
    <button type="button" onClick={onClick} disabled={disabled}
      className={clsx('relative w-full rounded-2xl p-4 text-left ring-1 transition',
        selected ? 'bg-fsp-blush/40 ring-2 ring-fsp-pink' : 'bg-white ring-[#E4E1EE] hover:ring-fsp-lavender',
        disabled && 'cursor-not-allowed opacity-50')}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-semibold text-fsp-deep">{title}</p>
          {hint && <p className="mt-1 text-xs leading-relaxed text-slate-500">{hint}</p>}
        </div>
        <span className={clsx('grid h-5 w-5 shrink-0 place-items-center rounded-full ring-1',
          selected ? 'bg-fsp-pink text-white ring-fsp-pink' : 'ring-slate-300')}>
          {selected && <Check className="h-3 w-3" />}
        </span>
      </div>
      {badge && <div className="mt-2">{badge}</div>}
      {children}
    </button>
  )
}

export function KV({ k, v }: { k: ReactNode; v: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1.5 text-sm">
      <span className="text-slate-500">{k}</span>
      <span className="text-right font-medium text-fsp-ink">{v}</span>
    </div>
  )
}

export function Alert({ tone = 'info', title, children, icon }: { tone?: 'info' | 'warn' | 'error' | 'success'; title?: ReactNode; children?: ReactNode; icon?: ReactNode }) {
  const cls = {
    info: 'bg-[#ECEAFB] text-[#3c3480]', warn: 'bg-amber-50 text-amber-800', error: 'bg-red-50 text-red-700',
    success: 'bg-emerald-50 text-emerald-800',
  }[tone]
  return (
    <div className={clsx('flex gap-3 rounded-2xl px-4 py-3 text-sm', cls)}>
      {icon && <div className="mt-0.5 shrink-0">{icon}</div>}
      <div>{title && <p className="font-semibold">{title}</p>}{children && <div className={clsx(title && 'mt-0.5')}>{children}</div>}</div>
    </div>
  )
}
