import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { Gauge, Send, Wallet } from 'lucide-react'
import { api, qs } from '@/lib/api'
import { useToast } from '@/lib/toast'
import { WORK_FORMATS } from '@/lib/format'
import { Alert, Button, Field, Input, Modal, Select, Textarea } from './ui'

export type InviteTarget = {
  id: number; display_name: string; grade_name?: string; specialization_name?: string; reasons?: { kind: string; text: string }[]
}

export function InviteModal({ target, onClose, vacancyId, defaults }: {
  target: InviteTarget | null; onClose: () => void; vacancyId?: number | null
  defaults?: { salary_from?: number | null; salary_to?: number | null; title?: string; work_format?: string | null }
}) {
  const qc = useQueryClient()
  const { push } = useToast()
  const { data: vacancies } = useQuery({ queryKey: ['emp-vacancies'], queryFn: () => api<any[]>('/employer/vacancies'), enabled: !!target })
  const { data: company } = useQuery({ queryKey: ['emp-company'], queryFn: () => api('/employer/company'), enabled: !!target })
  const [f, setF] = useState({ vacancy_id: '', title: '', message: '', salary_from: '', salary_to: '', work_format: '', contact_method: '' })

  useEffect(() => {
    if (!target) return
    const v = vacancies?.find(x => x.id === vacancyId)
    const plus = (target.reasons ?? []).filter(r => r.kind === 'plus').slice(0, 2).map(r => r.text.charAt(0).toLowerCase() + r.text.slice(1))
    setF({
      vacancy_id: vacancyId ? String(vacancyId) : '',
      title: defaults?.title ?? v?.title ?? '',
      message: `Здравствуйте! Мы нашли ваш профиль в категории «${target.specialization_name ?? ''} · ${target.grade_name ?? ''}».` +
        (plus.length ? ` Нас впечатлило: ${plus.join('; ')}.` : '') + ' Будем рады обсудить задачи команды и ответить на вопросы.',
      salary_from: String(defaults?.salary_from ?? v?.salary_from ?? ''),
      salary_to: String(defaults?.salary_to ?? v?.salary_to ?? ''),
      work_format: defaults?.work_format ?? v?.work_format ?? '',
      contact_method: company?.contact_telegram ? `Telegram: ${company.contact_telegram}` : company?.contact_email ? `E-mail: ${company.contact_email}` : '',
    })
  }, [target, vacancyId, vacancies, company, defaults])

  const salaryTo = Number(f.salary_to) || 0
  const { data: lh } = useQuery({
    queryKey: ['likelihood', target?.id, salaryTo, f.work_format],
    queryFn: () => api(`/employer/likelihood/${target!.id}${qs({ salary_to: salaryTo, work_format: f.work_format })}`),
    enabled: !!target && salaryTo > 0,
  })
  const send = useMutation({
    mutationFn: () => api('/employer/invitations', { body: {
      candidate_id: target!.id, vacancy_id: f.vacancy_id ? Number(f.vacancy_id) : null, title: f.title, message: f.message,
      salary_from: Number(f.salary_from), salary_to: Number(f.salary_to), work_format: f.work_format || null, contact_method: f.contact_method,
    } }),
    onSuccess: () => {
      push('Приглашение отправлено. Статус можно отслеживать в разделе «Приглашения».')
      qc.invalidateQueries({ queryKey: ['selection'] }); qc.invalidateQueries({ queryKey: ['emp-candidate'] })
      qc.invalidateQueries({ queryKey: ['emp-invitations'] }); qc.invalidateQueries({ queryKey: ['emp-search'] })
      onClose()
    },
    onError: (e: any) => push(e.message, 'error'),
  })
  const pickVacancy = (id: string) => {
    const v = vacancies?.find(x => String(x.id) === id)
    setF(s => ({ ...s, vacancy_id: id, ...(v ? { title: v.title, salary_from: String(v.salary_from), salary_to: String(v.salary_to), work_format: v.work_format } : {}) }))
  }
  const valid = useMemo(() => f.title.length >= 3 && f.message.length >= 10 && Number(f.salary_from) > 0 && Number(f.salary_to) >= Number(f.salary_from) && f.contact_method.length >= 3, [f])

  return (
    <Modal open={!!target} onClose={onClose} title={`Приглашение: ${target?.display_name ?? ''}`} wide
      footer={<><Button variant="secondary" onClick={onClose}>Отмена</Button>
        <Button disabled={!valid} loading={send.isPending} onClick={() => send.mutate()} icon={<Send className="h-4 w-4" />}>Отправить приглашение</Button></>}>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Вакансия (необязательно)" className="sm:col-span-2" hint="Приглашение можно отправить и без привязки к опубликованной вакансии">
          <Select value={f.vacancy_id} onChange={e => pickVacancy(e.target.value)}>
            <option value="">Без привязки к вакансии</option>
            {vacancies?.filter(v => v.status === 'active').map(v => <option key={v.id} value={v.id}>{v.title}{!v.is_published ? ' (приватная потребность)' : ''}</option>)}
          </Select>
        </Field>
        <Field label="Позиция" required className="sm:col-span-2"><Input value={f.title} onChange={e => setF({ ...f, title: e.target.value })} placeholder="Python-разработчик в команду платежей" /></Field>
        <Field label="Зарплата от, ₽" required><Input type="number" step={5000} value={f.salary_from} onChange={e => setF({ ...f, salary_from: e.target.value })} /></Field>
        <Field label="Зарплата до, ₽" required><Input type="number" step={5000} value={f.salary_to} onChange={e => setF({ ...f, salary_to: e.target.value })} /></Field>
        <Field label="Формат работы"><Select value={f.work_format} onChange={e => setF({ ...f, work_format: e.target.value })}>
          <option value="">Обсуждается</option>{Object.entries(WORK_FORMATS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Select></Field>
        <Field label="Способ связи" required><Input value={f.contact_method} onChange={e => setF({ ...f, contact_method: e.target.value })} placeholder="Telegram: @hr_company" /></Field>
        <Field label="Описание предложения" required className="sm:col-span-2"><Textarea rows={5} value={f.message} onChange={e => setF({ ...f, message: e.target.value })} /></Field>
      </div>
      {lh && (
        <div className={clsx('mt-4 flex items-start gap-3 rounded-2xl p-4', lh.label === 'высокая' ? 'bg-emerald-50' : lh.label === 'средняя' ? 'bg-amber-50' : 'bg-red-50')}>
          <Gauge className="mt-0.5 h-5 w-5 shrink-0 text-fsp-deep" />
          <div className="text-sm">
            <p className="font-semibold text-fsp-deep">Вероятность отклика: {lh.label} ({Math.round(lh.p * 100)}%)</p>
            <p className="mt-0.5 text-slate-600">
              {lh.salary_fits === true && 'Вилка соответствует ожиданиям кандидата. '}
              {lh.salary_fits === false && 'Вилка ниже ожиданий кандидата — вероятен отказ по зарплате. '}
              Оценка учитывает условия, формат и активность кандидата.</p>
          </div>
        </div>
      )}
      <Alert tone="info" icon={<Wallet className="h-4 w-4" />}>Кандидат увидит вилку, компанию и описание до начала общения. Ваши контакты и его контакты откроются обеим сторонам после принятия.</Alert>
    </Modal>
  )
}
