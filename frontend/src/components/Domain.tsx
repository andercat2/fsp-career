import clsx from 'clsx'
import { CircleAlert, CircleCheck, CircleMinus, Info, Trophy, Medal, ExternalLink, ShieldCheck } from 'lucide-react'
import type { ReactNode } from 'react'
import { Badge } from './ui'
import { date } from '@/lib/format'

export type DomainScore = { n: number; correct: number; score: number; theta?: number; name?: string }

export function DomainBars({ domains, names, compact }: { domains: Record<string, DomainScore>; names?: Record<string, string>; compact?: boolean }) {
  const rows = Object.entries(domains ?? {}).sort((a, b) => b[1].score - a[1].score)
  if (!rows.length) return <p className="muted">Нет данных тестирования</p>
  return (
    <div className={clsx('space-y-2.5', compact && 'space-y-2')}>
      {rows.map(([d, v]) => {
        const s = Math.round(v.score * 100)
        return (
          <div key={d}>
            <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
              <span className="truncate font-medium text-fsp-ink">{v.name ?? names?.[d] ?? d}</span>
              <span className="shrink-0 text-xs text-slate-500"><b className="text-fsp-deep">{s}%</b> · {v.correct}/{v.n}</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-slate-100">
              <div className={clsx('h-full rounded-full', s >= 70 ? 'bg-fsp-pink' : s >= 50 ? 'bg-fsp-lavender' : 'bg-slate-300')}
                   style={{ width: `${Math.max(3, s)}%` }} />
            </div>
          </div>
        )
      })}
    </div>
  )
}

export function MatchRing({ value, size = 64, label = 'совпадение' }: { value: number; size?: number; label?: string }) {
  const r = (size - 8) / 2
  const c = 2 * Math.PI * r
  const v = Math.max(0, Math.min(100, value))
  const color = v >= 70 ? '#FF0053' : v >= 50 ? '#8A83D1' : '#94a3b8'
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }} title={`${label}: ${v}%`}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} stroke="#F1EEF7" strokeWidth={7} fill="none" />
        <circle cx={size / 2} cy={size / 2} r={r} stroke={color} strokeWidth={7} fill="none" strokeLinecap="round"
                strokeDasharray={c} strokeDashoffset={c * (1 - v / 100)} />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">
        <span className="text-sm font-bold leading-none text-fsp-deep">{v}%</span>
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
          <li key={i} className="flex gap-2 text-sm leading-snug">
            <Icon className={clsx('mt-0.5 h-4 w-4 shrink-0', r.kind === 'plus' ? 'text-emerald-500' : r.kind === 'minus' ? 'text-amber-500' : 'text-slate-400')} />
            <span className={clsx(r.kind === 'minus' ? 'text-amber-800' : 'text-slate-700')}>{r.text}</span>
          </li>
        )
      })}
    </ul>
  )
}

const COMP_LABEL: Record<string, string> = { skills: 'Навыки', strength: 'Сила профиля', category: 'Категория', conditions: 'Условия', text: 'Текст' }
const COMP_WEIGHT: Record<string, number> = { skills: 0.3, strength: 0.25, category: 0.2, conditions: 0.15, text: 0.1 }

export function Components({ components }: { components: Record<string, number> }) {
  return (
    <div className="grid grid-cols-5 gap-2">
      {Object.entries(COMP_LABEL).map(([k, label]) => {
        const v = components?.[k] ?? 0
        return (
          <div key={k} title={`${label}: ${Math.round(v * 100)}% (вес ${COMP_WEIGHT[k] * 100}%)`}>
            <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
              <div className="h-full rounded-full bg-fsp-lavender" style={{ width: `${Math.max(3, v * 100)}%` }} />
            </div>
            <p className="mt-1 truncate text-[10px] font-medium uppercase tracking-wide text-slate-400">{label}</p>
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

export function StatusBadge({ status, label }: { status: string; label?: string }) {
  return <Badge tone={INV_TONE[status] ?? 'gray'}>{label ?? STATUS_RU[status] ?? status}</Badge>
}

export function CategoryPill({ spec, grade, className }: { spec?: string | null; grade?: string | null; className?: string }) {
  if (!grade) return <Badge tone="gray" className={className}>Категория не присвоена</Badge>
  return (
    <span className={clsx('inline-flex items-center gap-1.5 rounded-full bg-fsp-deep px-3 py-1 text-xs font-semibold text-white', className)}>
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
      <div className="mb-3 flex flex-wrap gap-2">
        {fsp.headline && <Badge tone="pink" icon={<Trophy className="h-3.5 w-3.5" />}>{fsp.headline}</Badge>}
        {fsp.sport_rank && <Badge tone="purple">{fsp.sport_rank}</Badge>}
        {fsp.rating && <Badge tone="lavender">Рейтинг ФСП: {fsp.rating.points}</Badge>}
      </div>
      <ol className="relative space-y-3 border-l-2 border-fsp-blush pl-5">
        {fsp.achievements.map((a, i) => (
          <li key={i} className="relative">
            <span className={clsx('absolute -left-[29px] top-0.5 grid h-6 w-6 place-items-center rounded-full ring-4 ring-white',
              a.place && a.place <= 3 ? 'bg-fsp-pink text-white' : 'bg-fsp-blush text-fsp-pink')}>
              {a.place && a.place <= 3 ? <Medal className="h-3.5 w-3.5" /> : <CircleMinus className="h-3.5 w-3.5" />}
            </span>
            <p className="text-sm font-semibold text-fsp-deep">{a.event}</p>
            <p className="text-xs text-slate-500">
              {date(a.date)} · {a.level_name} · {a.discipline_name} · <b className="text-fsp-ink">{a.place_label}</b>
              {a.team && <> · команда «{a.team}»{a.role ? `, ${a.role}` : ''}</>}
            </p>
            {a.result_url && <a href={a.result_url} target="_blank" rel="noreferrer" className="mt-0.5 inline-flex items-center gap-1 text-xs text-fsp-lavender hover:underline">
              протокол <ExternalLink className="h-3 w-3" /></a>}
          </li>
        ))}
      </ol>
    </div>
  )
}
