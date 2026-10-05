// Общие анимации интерфейса: единые кривые, длительности и примитивы (появление, каскад, счётчики).
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { animate, motion, useInView, type Variants } from 'framer-motion'

export const EASE = [0.22, 1, 0.36, 1] as const
export const SPRING = { type: 'spring', stiffness: 380, damping: 32, mass: 0.8 } as const

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: EASE } },
}

export const container = (gap = 0.055, delay = 0): Variants => ({
  hidden: {},
  show: { transition: { staggerChildren: gap, delayChildren: delay } },
})

/** Каскадное появление дочерних <Item>. */
export function Stagger({ children, className, gap, delay, as = 'div' }: {
  children: ReactNode; className?: string; gap?: number; delay?: number; as?: 'div' | 'ul' | 'ol' | 'section'
}) {
  const Comp = motion[as]
  return <Comp className={className} variants={container(gap, delay)} initial="hidden" animate="show">{children}</Comp>
}

export function Item({ children, className, as = 'div' }: { children: ReactNode; className?: string; as?: 'div' | 'li' }) {
  const Comp = motion[as]
  return <Comp className={className} variants={fadeUp}>{children}</Comp>
}

/** Появление при прокрутке в область видимости (один раз). */
export function Reveal({ children, className, delay = 0, y = 24 }: { children: ReactNode; className?: string; delay?: number; y?: number }) {
  return (
    <motion.div className={className} initial={{ opacity: 0, y }} whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-80px' }} transition={{ duration: 0.7, ease: EASE, delay }}>
      {children}
    </motion.div>
  )
}

/** Анимированное число: плавно «досчитывает» до значения, когда попадает в зону видимости. */
export function CountUp({ value, decimals = 0, suffix = '', prefix = '', duration = 1.1, className }: {
  value: number; decimals?: number; suffix?: string; prefix?: string; duration?: number; className?: string
}) {
  const ref = useRef<HTMLSpanElement>(null)
  const inView = useInView(ref, { once: true, margin: '-40px' })
  const [shown, setShown] = useState(0)
  useEffect(() => {
    if (!inView || Number.isNaN(value)) return
    const controls = animate(0, value, { duration, ease: EASE, onUpdate: v => setShown(v) })
    return () => controls.stop()
  }, [inView, value, duration])
  const text = new Intl.NumberFormat('ru-RU', { minimumFractionDigits: decimals, maximumFractionDigits: decimals }).format(shown)
  return <span ref={ref} className={className}>{prefix}{text}{suffix}</span>
}

/** Переход между страницами кабинета. */
export function PageTransition({ children, id }: { children: ReactNode; id: string }) {
  return (
    <motion.div key={id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, ease: EASE }}>
      {children}
    </motion.div>
  )
}

/** Декоративные «живые» пятна фона (CSS-анимация, без нагрузки на JS). */
export function Blobs({ className = '' }: { className?: string }) {
  return (
    <div className={`pointer-events-none absolute inset-0 overflow-hidden ${className}`} aria-hidden>
      <div className="absolute -left-24 top-10 h-72 w-72 animate-blob rounded-full bg-fsp-pink/30 blur-3xl" />
      <div className="absolute right-0 top-40 h-80 w-80 animate-blob rounded-full bg-fsp-lavender/40 blur-3xl [animation-delay:-6s]" />
      <div className="absolute bottom-0 left-1/3 h-72 w-72 animate-blob rounded-full bg-[#b21fd6]/25 blur-3xl [animation-delay:-12s]" />
    </div>
  )
}
