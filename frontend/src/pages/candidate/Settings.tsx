import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Download, LinkIcon, RefreshCw, Trash2, Unlink } from 'lucide-react'
import { api } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { useToast } from '@/lib/toast'
import { date, dateTime } from '@/lib/format'
import { Alert, Badge, Button, Card, Modal, PageHeader, PageLoader, Toggle } from '@/components/ui'
import { FspAchievements } from '@/components/Domain'

const PRIVACY: [string, string, string][] = [
  ['visible_in_search', 'Участвовать в подборках и банке кандидатов', 'Если выключить, работодатели не найдут ваш профиль'],
  ['show_name', 'Показывать имя до принятия приглашения', 'По умолчанию работодатель видит анонимный код — это снижает предвзятость'],
  ['show_salary', 'Показывать ожидания по доходу', 'Помогает работодателю сразу предложить подходящую вилку'],
  ['show_companies', 'Показывать названия прошлых работодателей', ''],
  ['show_fsp', 'Показывать достижения ФСП', 'Детали соревнований и места'],
  ['hide_invites_below_salary', 'Не принимать приглашения с вилкой ниже моих ожиданий', 'Работодатель получит отказ при отправке, не узнав ваших точных ожиданий'],
  ['show_unconfirmed', 'Показываться работодателям, пока грейд не подтверждён', 'Со статусом «не подтверждён» и ниже кандидатов с подтверждённым грейдом — так вы не выпадаете из поиска'],
]

export function CandidateSettings() {
  const qc = useQueryClient()
  const { push } = useToast()
  const { signOut } = useAuth()
  const [params, setParams] = useSearchParams()
  const [confirmDelete, setConfirmDelete] = useState(false)
  const { data: p, isLoading } = useQuery({ queryKey: ['cand-profile'], queryFn: () => api('/candidate/profile') })
  const { data: consents } = useQuery({ queryKey: ['consents'], queryFn: () => api<any[]>('/candidate/consents') })
  useEffect(() => {
    if (params.get('fsp') === 'linked') { push('ФСП ID привязан, достижения загружены из реестра'); qc.invalidateQueries(); setParams({}, { replace: true }) }
    const err = params.get('fsp_error')
    if (err) { push(err, 'error'); setParams({}, { replace: true }) }
  }, [params, push, qc, setParams])
  const refresh = () => { qc.invalidateQueries({ queryKey: ['cand-profile'] }); qc.invalidateQueries({ queryKey: ['cand-dashboard'] }); qc.invalidateQueries({ queryKey: ['consents'] }) }
  const privacy = useMutation({ mutationFn: (pv: any) => api('/candidate/privacy', { method: 'PUT', body: pv }), onSuccess: () => { refresh(); push('Настройки приватности сохранены') } })
  const consent = useMutation({ mutationFn: (b: any) => api('/candidate/consents', { body: b }), onSuccess: () => { refresh(); push('Согласие обновлено') }, onError: (e: any) => push(e.message, 'error') })
  const link = useMutation({ mutationFn: () => api<{ authorize_url: string }>('/fsp/link'), onSuccess: r => { window.location.href = r.authorize_url }, onError: (e: any) => push(e.message, 'error') })
  const sync = useMutation({ mutationFn: () => api('/fsp/sync', { method: 'POST' }), onSuccess: () => { refresh(); push('Данные ФСП обновлены') }, onError: (e: any) => push(e.message, 'error') })
  const unlink = useMutation({ mutationFn: () => api('/fsp/link', { method: 'DELETE' }), onSuccess: () => { refresh(); push('ФСП ID отвязан') } })
  const exportData = async () => {
    const data = await api('/candidate/export')
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
    const a = document.createElement('a'); a.href = url; a.download = 'fsp-career-my-data.json'; a.click(); URL.revokeObjectURL(url)
  }
  const del = useMutation({ mutationFn: () => api('/candidate/account', { method: 'DELETE' }), onSuccess: () => { signOut(); window.location.href = '/' } })
  if (isLoading || !p) return <PageLoader />
  const pv = p.privacy

  return (
    <div className="space-y-6">
      <PageHeader title="Настройки" subtitle="Что видит работодатель, согласия на обработку данных и связь с ФСП ID." />
      <div className="grid gap-6 xl:grid-cols-2">
        <Card title="ФСП ID" subtitle="Привязка через OpenID Connect (совместимо с Keycloak). Мы получаем только идентификатор участника и результаты соревнований.">
          {p.fsp_id ? (<>
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-surface p-4">
              <div>
                <p className="text-sm text-slate-500">Привязан {date(p.fsp_linked_at)} · обновлён {dateTime(p.fsp_synced_at)}</p>
                <p className="font-mono text-sm font-semibold text-fsp-deep">{p.fsp_id}</p>
              </div>
              <div className="flex gap-2">
                <Button size="sm" variant="secondary" loading={sync.isPending} onClick={() => sync.mutate()} icon={<RefreshCw className="h-4 w-4" />}>Обновить</Button>
                <Button size="sm" variant="ghost" onClick={() => unlink.mutate()} icon={<Unlink className="h-4 w-4" />}>Отвязать</Button>
              </div>
            </div>
            <FspAchievements fsp={p.fsp} />
          </>) : (
            <div className="space-y-4">
              <p className="text-sm text-slate-600">Результаты соревнований ФСП — объективное подтверждение практических навыков. После привязки они автоматически появятся в профиле и усилят его в подборках.</p>
              <Alert tone="info">Нет истории ФСП? Ничего страшного — профиль участвует в подборе на общих основаниях, достижения дают только бонус.</Alert>
              <Button variant="dark" loading={link.isPending} onClick={() => link.mutate()} icon={<img src="/brand/fsp-star-white.png" alt="" className="h-5 w-5" />}>Привязать ФСП ID</Button>
            </div>
          )}
        </Card>

        <Card title="Приватность" subtitle="Контакты раскрываются только после принятия приглашения или вашего отклика — это правило не отключается.">
          <div className="divide-y divide-slate-100">
            {PRIVACY.map(([k, label, hint]) => (
              <Toggle key={k} checked={!!pv[k]} label={label} hint={hint} onChange={v => privacy.mutate({ ...pv, [k]: v })} />
            ))}
          </div>
        </Card>

        <Card title="Согласия (152-ФЗ)" subtitle="Каждое изменение фиксируется в журнале с датой и устройством.">
          <Toggle checked={p.consent_pd} label="Обработка персональных данных" hint="Без него невозможны подбор и приглашения"
            onChange={v => consent.mutate({ kind: 'pd_processing', granted: v })} />
          <Toggle checked={p.consent_publish} label="Публикация профиля для работодателей" hint="Категория, подтверждённые навыки и обезличенные данные профиля"
            onChange={v => consent.mutate({ kind: 'profile_publication', granted: v })} />
          <div className="mt-4 max-h-48 space-y-1.5 overflow-y-auto rounded-2xl bg-surface p-3">
            {consents?.map((c, i) => (
              <p key={i} className="flex justify-between gap-3 text-xs text-slate-600">
                <span>{c.kind === 'pd_processing' ? 'Обработка ПДн' : 'Публикация профиля'} — <Badge tone={c.granted ? 'green' : 'red'}>{c.granted ? 'дано' : 'отозвано'}</Badge></span>
                <span>{dateTime(c.created_at)}</span>
              </p>
            ))}
          </div>
        </Card>

        <Card title="Мои данные">
          <p className="text-sm text-slate-600">Вы можете выгрузить все данные, которые хранит платформа, или удалить аккаунт вместе с персональными данными.</p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => exportData().catch(e => push(e.message, 'error'))} icon={<Download className="h-4 w-4" />}>Выгрузить данные (JSON)</Button>
            <Button variant="danger" onClick={() => setConfirmDelete(true)} icon={<Trash2 className="h-4 w-4" />}>Удалить аккаунт</Button>
          </div>
          <p className="mt-4 flex items-center gap-1.5 text-xs text-slate-400"><LinkIcon className="h-3 w-3" /> Код профиля: {p.public_id}</p>
        </Card>
      </div>
      <Modal open={confirmDelete} onClose={() => setConfirmDelete(false)} title="Удалить аккаунт?"
        footer={<><Button variant="secondary" onClick={() => setConfirmDelete(false)}>Отмена</Button><Button variant="danger" loading={del.isPending} onClick={() => del.mutate()}>Удалить навсегда</Button></>}>
        <p className="text-sm text-slate-600">Профиль, результаты тестов, приглашения и отклики будут удалены без возможности восстановления.</p>
      </Modal>
    </div>
  )
}
