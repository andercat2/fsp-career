import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'
import { CircleAlert, CircleCheck, Info, X } from 'lucide-react'
import clsx from 'clsx'

type Kind = 'success' | 'error' | 'info'
type Toast = { id: number; kind: Kind; text: string }
type Ctx = { push: (text: string, kind?: Kind) => void }

const ToastCtx = createContext<Ctx>({ push: () => undefined })
let seq = 0

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([])
  const remove = (id: number) => setItems(xs => xs.filter(x => x.id !== id))
  const push = useCallback((text: string, kind: Kind = 'success') => {
    const id = ++seq
    setItems(xs => [...xs.slice(-3), { id, kind, text }])
    setTimeout(() => remove(id), kind === 'error' ? 7000 : 4000)
  }, [])
  return (
    <ToastCtx.Provider value={{ push }}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 bottom-4 z-[100] flex flex-col items-center gap-2 px-4 sm:items-end sm:pr-6"
           role="status" aria-live="polite">
        {items.map(t => {
          const Icon = t.kind === 'success' ? CircleCheck : t.kind === 'error' ? CircleAlert : Info
          return (
            <div key={t.id} className={clsx(
              'pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-2xl px-4 py-3 text-sm shadow-pop ring-1',
              t.kind === 'error' ? 'bg-white text-red-700 ring-red-200' : 'bg-fsp-deep text-white ring-white/10')}>
              <Icon className={clsx('mt-0.5 h-4 w-4 shrink-0', t.kind === 'success' && 'text-emerald-300')} />
              <span className="flex-1">{t.text}</span>
              <button onClick={() => remove(t.id)} className="opacity-60 hover:opacity-100" aria-label="Закрыть">
                <X className="h-4 w-4" />
              </button>
            </div>
          )
        })}
      </div>
    </ToastCtx.Provider>
  )
}

export const useToast = () => useContext(ToastCtx)
