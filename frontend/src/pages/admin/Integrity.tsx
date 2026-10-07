import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Camera, ChevronDown, ChevronUp, EyeOff, ShieldAlert, ShieldQuestion } from 'lucide-react'
import { api } from '@/lib/api'
import { dateTime } from '@/lib/format'
import { Badge, Card, EmptyState, PageHeader, PageLoader, Select, Stat } from '@/components/ui'

const FLAG_RU: Record<string, string> = {
  aberrant_pattern: 'несогласованный паттерн ответов', too_fast_on_hard_items: 'слишком быстрые ответы на трудные задания',
  foreign_variant_answers: 'ответы «чужого варианта»',
}
const KIND_RU: Record<string, string> = { screenshot: 'снимок экрана', print: 'печать', copy: 'копирование', focus_loss: 'уход со вкладки' }

export function AdminIntegrity() {
  const [kind, setKind] = useState('')
  const [open, setOpen] = useState<string | null>(null)
  const { data, isLoading } = useQuery({ queryKey: ['admin-integrity'], queryFn: () => api<any>('/admin/integrity') })
  const rows = useMemo(() => (data?.sessions ?? []).filter((s: any) =>
    !kind || (kind === 'violation' && s.violation) || (kind === 'warning' && s.strikes === 1 && !s.violation)
    || (kind === 'review' && s.review_required) || (kind === 'flags' && s.flags.length) || (kind === 'away' && s.away_count && !s.strikes)), [data, kind])
  if (isLoading || !data) return <PageLoader />
  return (
    <div className="space-y-6">
      <PageHeader title="Честность тестирования" subtitle="Сессии с событиями прокторинга (снимок экрана, печать, копирование, уход со вкладки) и флагами детекторов: ответы «чужого варианта», несогласованный паттерн, слишком быстрые ответы. Сохраняются только события — экран не записывается." />
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <Stat label="Досрочно завершены" value={data.summary.violations} hint="повторное нарушение, оценка снижена" icon={<ShieldAlert className="h-5 w-5" />} />
        <Stat label="Предупреждения" value={data.summary.warnings} hint="одно нарушение" icon={<Camera className="h-5 w-5" />} />
        <Stat label="На перепроверку" value={data.summary.review} hint="ответы чужого варианта" icon={<ShieldQuestion className="h-5 w-5" />} />
        <Stat label="Флаги детекторов" value={data.summary.flagged} icon={<EyeOff className="h-5 w-5" />} />
      </div>
      <Card>
        <Select className="mb-4 max-w-xs" value={kind} onChange={e => setKind(e.target.value)}>
          <option value="">Все сессии ({data.total})</option><option value="violation">Досрочно завершены</option>
          <option value="warning">Предупреждение</option><option value="review">На перепроверку</option>
          <option value="flags">Флаги детекторов</option><option value="away">Только уход со вкладки</option>
        </Select>
        {!rows.length ? <EmptyState icon={<ShieldAlert className="h-5 w-5" />} title="Нет сессий" text="Нарушений по выбранному фильтру нет." /> : (
          <div className="divide-y divide-line">
            {rows.map((s: any) => (
              <div key={s.token} className="py-3">
                <button className="flex w-full flex-wrap items-center gap-2 text-left" onClick={() => setOpen(open === s.token ? null : s.token)}>
                  <span className="font-semibold text-fsp-deep">{s.candidate}</span>
                  <span className="text-sm text-slate-500">{s.specialization_name} · {s.target_grade_name} · {dateTime(s.started_at)}</span>
                  {s.violation && <Badge tone="red">завершён: {KIND_RU[s.violation] ?? s.violation}</Badge>}
                  {!s.violation && s.strikes > 0 && <Badge tone="amber">предупреждение</Badge>}
                  {s.review_required && <Badge tone="amber">перепроверка</Badge>}
                  {s.flags.map((f: string) => <Badge key={f} tone="lavender">{FLAG_RU[f] ?? f}</Badge>)}
                  {s.away_count > 0 && <Badge tone="gray">уходов со вкладки: {s.away_count} ({s.away_sec} с)</Badge>}
                  <span className="ml-auto text-slate-400">{open === s.token ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}</span>
                </button>
                {open === s.token && (
                  <div className="mt-3 rounded-2xl bg-surface p-3 text-xs text-slate-600">
                    <p className="mb-2">Решение: <b>{s.decision ?? s.status}</b>{s.assigned_grade && <> · присвоен {s.assigned_grade}</>}{s.penalty ? <> · штраф −{s.penalty}</> : null}</p>
                    {!s.events.length ? <p>Событий прокторинга нет — сессия помечена детекторами ответов.</p> : (
                      <ul className="space-y-1">{s.events.map((e: any, i: number) => (
                        <li key={i}>{dateTime(e.at)} · задание {e.seq ?? '—'} · {KIND_RU[e.kind] ?? e.kind}{e.method && ` (${e.method})`}{e.away_ms && ` · ${Math.round(e.away_ms / 1000)} с`}{e.duplicate && ' · повтор того же действия'}</li>
                      ))}</ul>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}
