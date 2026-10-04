import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Save, ShieldCheck } from 'lucide-react'
import { api } from '@/lib/api'
import { useReference } from '@/lib/reference'
import { useToast } from '@/lib/toast'
import { Alert, Badge, Button, Card, Field, Input, PageHeader, PageLoader, Select, Textarea } from '@/components/ui'

const FIELDS = ['name', 'description', 'industry', 'website', 'city', 'size', 'contact_name', 'contact_email', 'contact_phone', 'contact_telegram', 'ats_webhook_url'] as const

export function CompanyPage() {
  const qc = useQueryClient()
  const { push } = useToast()
  const { ref } = useReference()
  const { data, isLoading } = useQuery({ queryKey: ['emp-company'], queryFn: () => api('/employer/company') })
  const [f, setF] = useState<Record<string, string>>({})
  useEffect(() => { if (data) setF(Object.fromEntries(FIELDS.map(k => [k, data[k] ?? '']))) }, [data])
  const save = useMutation({
    mutationFn: () => api('/employer/company', { method: 'PUT', body: Object.fromEntries(Object.entries(f).map(([k, v]) => [k, v === '' && k !== 'name' ? null : v])) }),
    onSuccess: (r) => { qc.setQueryData(['emp-company'], r); push('Профиль компании сохранён') }, onError: (e: any) => push(e.message, 'error'),
  })
  if (isLoading || !data) return <PageLoader />
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value })
  return (
    <div>
      <PageHeader title="Профиль компании" subtitle="Эти данные кандидат видит в приглашении. Контакты компании открываются ему после принятия приглашения."
        actions={<Button onClick={() => save.mutate()} loading={save.isPending} icon={<Save className="h-4 w-4" />}>Сохранить</Button>} />
      <div className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
        <Card title="О компании">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Название" required className="sm:col-span-2"><Input value={f.name} onChange={set('name')} /></Field>
            <Field label="Отрасль"><Select value={f.industry} onChange={set('industry')}><option value="">—</option>{ref?.industries.map(i => <option key={i} value={i}>{i}</option>)}</Select></Field>
            <Field label="Размер"><Input value={f.size} onChange={set('size')} placeholder="50–200 сотрудников" /></Field>
            <Field label="Сайт"><Input value={f.website} onChange={set('website')} placeholder="company.ru" /></Field>
            <Field label="Город"><Input value={f.city} onChange={set('city')} /></Field>
            <Field label="Описание" className="sm:col-span-2"><Textarea rows={5} value={f.description} onChange={set('description')} /></Field>
          </div>
        </Card>
        <div className="space-y-6">
          <Card title="Контакты для кандидатов">
            <div className="space-y-3">
              <Field label="Контактное лицо"><Input value={f.contact_name} onChange={set('contact_name')} /></Field>
              <Field label="E-mail"><Input value={f.contact_email} onChange={set('contact_email')} /></Field>
              <Field label="Telegram"><Input value={f.contact_telegram} onChange={set('contact_telegram')} /></Field>
              <Field label="Телефон"><Input value={f.contact_phone} onChange={set('contact_phone')} /></Field>
            </div>
          </Card>
          <Card title="Доверие и интеграции">
            <div className="mb-3 flex flex-wrap gap-2">
              <Badge tone={data.domain_verified ? 'green' : 'gray'} icon={<ShieldCheck className="h-3 w-3" />}>{data.domain_verified ? 'домен e-mail совпадает с сайтом' : 'домен не подтверждён'}</Badge>
              <Badge tone="lavender">индекс доверия {Math.round(data.trust_score * 100)}%</Badge>
            </div>
            <Field label="Webhook ATS (необязательно)" hint="При принятии приглашения отправим POST с данными кандидата в вашу ATS"><Input value={f.ats_webhook_url} onChange={set('ats_webhook_url')} placeholder="https://ats.company.ru/hooks/fsp" /></Field>
            <div className="mt-3"><Alert tone="info">Индекс доверия растёт при совпадении домена e-mail с сайтом компании и снижается при жалобах кандидатов на фиктивные вакансии.</Alert></div>
          </Card>
        </div>
      </div>
    </div>
  )
}
