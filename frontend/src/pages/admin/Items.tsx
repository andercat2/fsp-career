import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { Database, FlaskConical, ShieldAlert, Sigma } from 'lucide-react'
import { api } from '@/lib/api'
import { useReference } from '@/lib/reference'
import { useToast } from '@/lib/toast'
import { Badge, Button, Card, Input, PageHeader, PageLoader, Select, Stat } from '@/components/ui'

export function AdminItems() {
  const qc = useQueryClient()
  const { push } = useToast()
  const { domainName } = useReference()
  const [q, setQ] = useState('')
  const [status, setStatus] = useState('')
  const { data, isLoading } = useQuery({ queryKey: ['admin-items'], queryFn: () => api<any[]>('/admin/items') })
  const calibrate = useMutation({ mutationFn: () => api<any[]>('/admin/items/calibrate', { method: 'POST' }),
    onSuccess: (r) => { qc.invalidateQueries({ queryKey: ['admin-items'] }); push(`Пилотных заданий обработано: ${r.length}, переведено в банк: ${r.filter(x => x.promoted).length}`) } })
  const rows = useMemo(() => (data ?? []).filter(r => (!q || r.family_id.includes(q) || (r.domain ?? '').includes(q)) && (!status || r.status === status)), [data, q, status])
  if (isLoading || !data) return <PageLoader />
  const exposed = data.filter(r => r.exposures > 0)
  const maxExp = Math.max(1, ...data.map(r => r.exposures))
  return (
    <div className="space-y-6">
      <PageHeader title="Банк заданий" subtitle="Онлайн-статистика семейств: экспозиция, наблюдаемая и ожидаемая по модели решаемость, z-статистика дрейфа. При z > 3 (≥30 показов) семейство автоматически выводится из ротации как вероятно скомпрометированное."
        actions={<Button variant="secondary" loading={calibrate.isPending} onClick={() => calibrate.mutate()} icon={<FlaskConical className="h-4 w-4" />}>Откалибровать пилотные</Button>} />
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <Stat label="Семейств в банке" value={data.length} icon={<Database className="h-5 w-5" />} />
        <Stat label="Использовались" value={exposed.length} hint={`${Math.round(exposed.length / data.length * 100)}% банка`} icon={<Sigma className="h-5 w-5" />} />
        <Stat label="Помечены (дрейф)" value={data.filter(r => r.status === 'flagged').length} icon={<ShieldAlert className="h-5 w-5" />} />
        <Stat label="Пилотные" value={data.filter(r => r.status === 'pretest').length} icon={<FlaskConical className="h-5 w-5" />} />
      </div>
      <Card>
        <div className="mb-4 flex flex-wrap gap-3">
          <Input className="max-w-xs" placeholder="Фильтр по id или домену" value={q} onChange={e => setQ(e.target.value)} />
          <Select className="max-w-[200px]" value={status} onChange={e => setStatus(e.target.value)}>
            <option value="">Все статусы</option><option value="active">active</option><option value="flagged">flagged</option><option value="pretest">pretest</option><option value="retired">retired</option></Select>
        </div>
        <div className="scrollbar-thin overflow-x-auto">
          <table className="w-full min-w-[820px] text-sm">
            <thead><tr className="text-left text-xs uppercase tracking-wide text-slate-400">
              <th className="pb-2">Семейство</th><th className="pb-2">Домен</th><th className="pb-2">Статус</th><th className="pb-2">a / b / c</th>
              <th className="pb-2">Показов</th><th className="pb-2">Верно (набл. / ожид.)</th><th className="pb-2">z дрейфа</th></tr></thead>
            <tbody className="divide-y divide-slate-100">
              {rows.slice(0, 400).map(r => (
                <tr key={r.family_id}>
                  <td className="py-2 font-mono text-xs">{r.family_id}</td>
                  <td>{domainName(r.domain)}</td>
                  <td><Badge tone={r.status === 'active' ? 'green' : r.status === 'flagged' ? 'red' : r.status === 'pretest' ? 'amber' : 'gray'}>{r.status}</Badge></td>
                  <td className="font-mono text-xs">{r.a.toFixed(2)} / {r.b.toFixed(2)} / {r.c.toFixed(2)}</td>
                  <td><div className="flex items-center gap-2"><div className="h-1.5 w-16 rounded-full bg-slate-100"><div className="h-full rounded-full bg-fsp-lavender" style={{ width: `${r.exposures / maxExp * 100}%` }} /></div>{r.exposures}</div></td>
                  <td>{r.correct} / {r.expected}</td>
                  <td className={clsx('font-semibold', r.drift_z > 3 ? 'text-red-600' : r.drift_z > 2 ? 'text-amber-600' : 'text-slate-500')}>{r.drift_z.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
