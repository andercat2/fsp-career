import clsx from 'clsx'
import { motion } from 'framer-motion'
import { CircleAlert, CircleCheck, CircleDot, ExternalLink, Info, Medal, ShieldCheck, ShieldQuestionMark, Trophy } from 'lucide-react'
import type { ReactNode } from 'react'
import { Badge } from './ui'
import { date } from '@/lib/format'
import { CountUp, EASE } from '@/lib/motion'
import { useReference } from '@/lib/reference'

export type DomainScore = { n: number; correct: number; score: number; theta?: number; name?: string }

export function DomainBars({ domains, names, compact }: { domains: Record<string, DomainScore>; names?: Record<string, string>; compact?: boolean }) {
  const { domainName } = useReference()
  const rows = Object.entries(domains ?? {}).sort((a, b) => b[1].score - a[1].score)
  if (!rows.length) return <p className="muted">Нет данных тестирования</p>
  return (
    <div className={clsx('space-y-3', compact && 'space-y-2')}>
      {rows.map(([d, v], i) => {
        const s = Math.round(v.score * 100)
        return (
          <div key={d}>
            <div className="mb-1.5 flex items-baseline justify-between gap-3 text-sm">
              <span className="truncate text-slate-700">{v.name ?? names?.[d] ?? domainName(d)}</span>
              <span className="shrink-0 text-xs tabular-nums text-slate-400"><b className="font-semibold text-fsp-deep">{s}%</b> · {v.correct}/{v.n}</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-[#F1EFF6]">
              <motion.div className={clsx('h-full rounded-full', s >= 70 ? 'bg-gradient-to-r from-fsp-pink to-[#ff4d8a]' : s >= 50 ? 'bg-fsp-lavender' : 'bg-slate-300')}
                initial={{ width: 0 }} animate={{ width: `${Math.max(3, s)}%` }} transition={{ duration: 0.9, ease: EASE, delay: 0.05 * i }} />
            </div>
          </div>
        )
      })}
    </div>
  )
}

export function MatchRing({ value, size = 64, label = 'совпадение' }: { value: number; size?: number; label?: string }) {
  const stroke = Math.max(5, size / 11)
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const v = Math.max(0, Math.min(100, value))
  const color = v >= 70 ? 'url(#ring-hot)' : v >= 50 ? '#8A83D1' : '#CBD5E1'
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }} title={`${label}: ${v}%`}>
      <svg width={size} height={size} className="-rotate-90">
        <defs>
          <linearGradient id="ring-hot" x1="0" x2="1" y1="0" y2="1"><stop offset="0%" stopColor="#FF0053" /><stop offset="100%" stopColor="#ff5c95" /></linearGradient>
        </defs>
        <circle cx={size / 2} cy={size / 2} r={r} stroke="#F1EFF6" strokeWidth={stroke} fill="none" />
        <motion.circle cx={size / 2} cy={size / 2} r={r} stroke={color} strokeWidth={stroke} fill="none" strokeLinecap="round"
          strokeDasharray={c} initial={{ strokeDashoffset: c }} animate={{ strokeDashoffset: c * (1 - v / 100) }}
          transition={{ duration: 1.1, ease: EASE }} />
      </svg>
      <div className="absolute inset-0 grid place-items-center">
        <span className="text-[13px] font-bold tabular-nums text-fsp-deep" style={{ fontSize: Math.max(12, size / 4.6) }}><CountUp value={v} suffix="%" duration={1.1} /></span>
      </div>
    </div>
  )
}

export type Reason = { kind: 'plus' | 'minus' | 'info'; text: string }

export function Reasons({ reasons, limit }: { reasons: Reason[]; limit?: number }) {
  const items = limit ? reasons.slice(0, limit) : reasons
  return (
    <ul className="space-y-1.5">
      {items.map((r, i) => {
        const Icon = r.kind === 'plus' ? CircleCheck : r.kind === 'minus' ? CircleAlert : Info
        return (
          <motion.li key={r.text} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.3, delay: i * 0.04 }}
            className="flex gap-2 text-sm leading-snug">
            <Icon className={clsx('mt-0.5 h-4 w-4 shrink-0', r.kind === 'plus' ? 'text-emerald-500' : r.kind === 'minus' ? 'text-amber-500' : 'text-slate-300')} />
            <span className={clsx(r.kind === 'minus' ? 'text-amber-800' : 'text-slate-600')}>{r.text}</span>
          </motion.li>
        )
      })}
    </ul>
  )
}

const COMP_LABEL: Record<string, string> = { skills: 'Навыки', strength: 'Сила', category: 'Категория', conditions: 'Условия', text: 'Текст' }
const COMP_WEIGHT: Record<string, number> = { skills: 0.3, strength: 0.25, category: 0.2, conditions: 0.15, text: 0.1 }

export function Components({ components }: { components: Record<string, number> }) {
  return (
    <div className="grid grid-cols-5 gap-2.5">
      {Object.entries(COMP_LABEL).map(([k, label], i) => {
        const v = components?.[k] ?? 0
        return (
          <div key={k} title={`${label}: ${Math.round(v * 100)}% (вес ${COMP_WEIGHT[k] * 100}%)`}>
            <div className="h-1 overflow-hidden rounded-full bg-[#F1EFF6]">
              <motion.div className="h-full rounded-full bg-fsp-lavender" initial={{ width: 0 }} animate={{ width: `${Math.max(3, v * 100)}%` }}
                transition={{ duration: 0.8, ease: EASE, delay: 0.1 + i * 0.05 }} />
            </div>
            <p className="mt-1 truncate text-[10px] font-medium text-slate-400">{label}</p>
          </div>
        )
      })}
    </div>
  )
}

const INV_TONE: Record<string, 'pink' | 'lavender' | 'green' | 'amber' | 'red' | 'gray' | 'blue'> = {
  sent: 'blue', viewed: 'lavender', accepted: 'green', declined: 'red', withdrawn: 'gray', expired: 'gray',
  rejected: 'red', submitted: 'blue', reviewed: 'green', offered: 'amber', skipped: 'gray',
}
const STATUS_RU: Record<string, string> = {
  sent: 'Отправлено', viewed: 'Просмотрено', accepted: 'Принято', declined: 'Отклонено', withdrawn: 'Отозвано',
  expired: 'Истекло', rejected: 'Отказ', submitted: 'На проверке', reviewed: 'Проверено', offered: 'Новое', skipped: 'Пропущено',
}

/** Статусы приглашения глазами каждой стороны: «viewed» — приглашение открыл кандидат (не просмотр резюме). */
const STATUS_SIDE: Record<'candidate' | 'employer', Record<string, string>> = {
  candidate: { sent: 'Новое', viewed: 'Открыто вами' },
  employer: { sent: 'Отправлено', viewed: 'Прочитано кандидатом' },
}

export function StatusBadge({ status, label, side }: { status: string; label?: string; side?: 'candidate' | 'employer' }) {
  return (
    <Badge tone={INV_TONE[status] ?? 'gray'}>
      <span className={clsx('h-1.5 w-1.5 rounded-full', { blue: 'bg-sky-500', lavender: 'bg-fsp-lavender', green: 'bg-emerald-500', red: 'bg-red-500',
        gray: 'bg-slate-400', amber: 'bg-amber-500', pink: 'bg-fsp-pink' }[INV_TONE[status] ?? 'gray'])} />
      {label ?? (side && STATUS_SIDE[side][status]) ?? STATUS_RU[status] ?? status}
    </Badge>
  )
}

/** Категория резюме. status = unconfirmed — тест не подтвердил заявленный грейд (claimed): кандидат в выдаче со
 *  статусом и ниже подтверждённых. */
export function CategoryPill({ spec, grade, status, claimed, className }: {
  spec?: string | null; grade?: string | null; status?: string | null; claimed?: string | null; className?: string
}) {
  if (status === 'unconfirmed' && claimed) return (
    <span title="Тест не подтвердил заявленный грейд: кандидат в выдаче, но ниже подтверждённых"
      className={clsx('inline-flex items-center gap-1.5 whitespace-nowrap rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-900 ring-1 ring-amber-300', className)}>
      <ShieldQuestionMark className="h-3.5 w-3.5 text-amber-600" />{spec} · {claimed} — не подтверждён
    </span>
  )
  if (!grade) return <Badge tone="gray" className={className}>Категория не присвоена</Badge>
  return (
    <span className={clsx('inline-flex items-center gap-1.5 whitespace-nowrap rounded-full bg-fsp-deep px-3 py-1 text-xs font-semibold text-white', className)}>
      <ShieldCheck className="h-3.5 w-3.5 text-fsp-blush" />{spec} · {grade}
    </span>
  )
}

export type FspAchievement = {
  event: string; discipline_name: string; level_name: string; date: string; place: number | null; participants: number | null
  place_label: string; team?: string; role?: string; result_url?: string
}
export type FspSummary = {
  linked: boolean; hidden?: boolean; score: number; achievements: FspAchievement[]; headline: string | null
  sport_rank?: string | null; rating?: { points: number; season: string } | null; region?: string | null
}

export function FspAchievements({ fsp, empty }: { fsp?: FspSummary | null; empty?: ReactNode }) {
  if (!fsp?.linked) return <>{empty ?? <p className="muted">ФСП ID не привязан. Это не влияет на попадание в подборки — достижения лишь добавляют бонус к силе профиля.</p>}</>
  if (fsp.hidden) return <p className="muted">Кандидат скрыл детали достижений ФСП.</p>
  if (!fsp.achievements.length) return <p className="muted">ФСП ID привязан, в реестре пока нет результатов соревнований. Профиль участвует в подборе на общих основаниях.</p>
  return (
    <div>
      <div className="mb-4 flex flex-wrap gap-2">
        {fsp.headline && <Badge tone="pink" icon={<Trophy className="h-3.5 w-3.5" />}>{fsp.headline}</Badge>}
        {fsp.sport_rank && <Badge tone="purple">{fsp.sport_rank}</Badge>}
        {fsp.rating && <Badge tone="lavender">Рейтинг ФСП: {fsp.rating.points}</Badge>}
      </div>
      <ol className="relative space-y-4 pl-9">
        <motion.span className="absolute left-[11px] top-1 w-0.5 rounded-full bg-gradient-to-b from-fsp-pink/60 to-fsp-lavender/20"
          initial={{ height: 0 }} animate={{ height: 'calc(100% - 8px)' }} transition={{ duration: 0.9, ease: EASE }} />
        {fsp.achievements.map((a, i) => (
          <motion.li key={i} className="relative" initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.4, delay: 0.1 + i * 0.07, ease: EASE }}>
            <span className={clsx('absolute -left-9 top-0.5 grid h-6 w-6 place-items-center rounded-full ring-4 ring-white',
              a.place && a.place <= 3 ? 'bg-gradient-to-br from-fsp-pink to-[#ff5c95] text-white shadow-glow' : 'bg-[#FFF0F5] text-fsp-pink')}>
              {a.place && a.place <= 3 ? <Medal className="h-3.5 w-3.5" /> : <CircleDot className="h-3.5 w-3.5" />}
            </span>
            <p className="text-sm font-semibold text-fsp-deep">{a.event}</p>
            <p className="mt-0.5 text-xs leading-relaxed text-slate-500">
              {date(a.date)} · {a.level_name} · {a.discipline_name} · <b className="font-semibold text-fsp-ink">{a.place_label}</b>
              {a.team && <> · «{a.team}»{a.role ? `, ${a.role}` : ''}</>}
            </p>
            {a.result_url && <a href={a.result_url} target="_blank" rel="noreferrer" className="mt-0.5 inline-flex items-center gap-1 text-xs text-fsp-lavender hover:underline">
              протокол <ExternalLink className="h-3 w-3" /></a>}
          </motion.li>
        ))}
      </ol>
    </div>
  )
}
