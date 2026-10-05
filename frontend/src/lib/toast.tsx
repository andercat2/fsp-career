import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
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
    setTimeout(() => remove(id), kind === 'error' ? 7000 : 4200)
  }, [])
  return (
    <ToastCtx.Provider value={{ push }}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 bottom-5 z-[100] flex flex-col items-center gap-2 px-4 sm:items-end sm:pr-6" role="status" aria-live="polite">
        <AnimatePresence initial={false}>
          {items.map(t => {
            const Icon = t.kind === 'success' ? CircleCheck : t.kind === 'error' ? CircleAlert : Info
            return (
              <motion.div key={t.id} layout initial={{ opacity: 0, y: 24, scale: 0.96 }} animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, x: 40, scale: 0.96 }} transition={{ type: 'spring', stiffness: 420, damping: 34 }}
                className={clsx('pointer-events-auto flex w-full max-w-sm items-start gap-3 overflow-hidden rounded-2xl px-4 py-3.5 text-sm shadow-pop',
                  t.kind === 'error' ? 'border border-red-100 bg-white text-red-700' : 'bg-[#1d0b33]/95 text-white backdrop-blur-xl')}>
                <Icon className={clsx('mt-0.5 h-4 w-4 shrink-0', t.kind === 'success' && 'text-emerald-300', t.kind === 'info' && 'text-fsp-lavender')} />
                <span className="flex-1 leading-relaxed">{t.text}</span>
                <button onClick={() => remove(t.id)} className="opacity-50 transition hover:opacity-100" aria-label="Закрыть"><X className="h-4 w-4" /></button>
              </motion.div>
            )
          })}
        </AnimatePresence>
      </div>
    </ToastCtx.Provider>
  )
}

export const useToast = () => useContext(ToastCtx)
