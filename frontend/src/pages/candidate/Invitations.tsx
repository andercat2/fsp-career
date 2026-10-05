import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import clsx from 'clsx'
import { EASE } from '@/lib/motion'
import { Building2, CircleCheck, Flag, Mail, MapPin, MessageSquare, Phone, Send, ShieldCheck, Sparkles, Wallet, X } from 'lucide-react'
import { api } from '@/lib/api'
import { useReference } from '@/lib/reference'
import { useToast } from '@/lib/toast'
import { ago, date, salaryRange } from '@/lib/format'
import { Alert, Badge, Button, Card, EmptyState, Field, Modal, PageHeader, PageLoader, Select, Tabs, Textarea } from '@/components/ui'
import { StatusBadge } from '@/components/Domain'

export function CandidateInvitations() {
  const qc = useQueryClient()
  const { push } = useToast()
  const { ref } = useReference()
  const [tab, setTab] = useState<'active' | 'accepted' | 'archive'>('active')
  const [openId, setOpenId] = useState<number | null>(null)
  const [decline, setDecline] = useState<{ reason: string; comment: string } | null>(null)
  const [complain, setComplain] = useState<{ reason: string; comment: string } | null>(null)
  const { data: list, isLoading } = useQuery({ queryKey: ['cand-invitations'], queryFn: () => api<any[]>('/candidate/invitations') })
  const { data: inv } = useQuery({ queryKey: ['cand-invitation', openId], queryFn: () => api(`/candidate/invitations/${openId}`), enabled: !!openId })
  const refresh = () => { qc.invalidateQueries({ queryKey: ['cand-invitations'] }); qc.invalidateQueries({ queryKey: ['cand-invitation', openId] }); qc.invalidateQueries({ queryKey: ['cand-dashboard'] }) }
  const accept = useMutation({ mutationFn: () => api(`/candidate/invitations/${openId}/accept`, { method: 'POST' }), onSuccess: () => { refresh(); push('Приглашение принято — контакты открыты обеим сторонам') }, onError: (e: any) => push(e.message, 'error') })
  const doDecline = useMutation({ mutationFn: () => api(`/candidate/invitations/${openId}/decline`, { body: decline }), onSuccess: () => { refresh(); setDecline(null); push('Вы отклонили приглашение. Работодатель получит причину — это помогает рынку.') }, onError: (e: any) => push(e.message, 'error') })
  const doComplain = useMutation({ mutationFn: () => api(`/candidate/invitations/${openId}/complain`, { body: complain }), onSuccess: (r: any) => { setComplain(null); push(r.detail) }, onError: (e: any) => push(e.message, 'error') })

  if (isLoading || !list) return <PageLoader />
  const groups = {
    active: list.filter(i => ['sent', 'viewed'].includes(i.status)),
    accepted: list.filter(i => i.status === 'accepted'),
    archive: list.filter(i => ['declined', 'withdrawn', 'expired'].includes(i.status)),
  }
  const items = groups[tab]
  const current = inv ?? list.find(i => i.id === openId)

  return (
    <div>
      <PageHeader title="Приглашения" subtitle="Работодатели сами выходят на вас с конкретным предложением и вилкой зарплаты. Контакты раскрываются только после того, как вы примете приглашение." />
      <Tabs value={tab} onChange={setTab} items={[
        { value: 'active', label: 'Новые и открытые', count: groups.active.length },
        { value: 'accepted', label: 'Принятые', count: groups.accepted.length },
        { value: 'archive', label: 'Архив', count: groups.archive.length },
      ]} />
      <div className="mt-5 grid gap-6 lg:grid-cols-[1fr_1.15fr]">
        <div className="space-y-3">
          {!items.length && <EmptyState icon={<Mail className="h-5 w-5" />} title="Здесь пока пусто" text="Как только работодатель найдёт вас в подборке своей категории, приглашение появится здесь." />}
          {items.map((i, idx) => (
            <motion.button key={i.id} onClick={() => setOpenId(i.id)} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: idx * 0.05, ease: EASE }} whileTap={{ scale: 0.99 }}
              className={clsx('card card-hover w-full p-4 text-left', openId === i.id && '!border-fsp-pink/50 shadow-[0_0_0_3px_rgba(255,0,83,.07)]')}>
              <div className="flex items-start gap-3">
                <div className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-surface text-lg font-bold text-fsp-deep">{i.company.name[0]}</div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-2">
                    <p className="truncate font-semibold text-fsp-deep">{i.title}</p>
                    <StatusBadge status={i.status} />
                  </div>
                  <p className="text-sm text-slate-500">{i.company.name} · {ago(i.created_at)}</p>
                  <p className="mt-2 inline-flex items-center gap-1.5 rounded-lg bg-fsp-blush/50 px-2.5 py-1 text-sm font-bold text-fsp-deep">
                    <Wallet className="h-4 w-4 text-fsp-pink" />{salaryRange(i.salary_from, i.salary_to)}</p>
                </div>
              </div>
            </motion.button>
          ))}
        </div>

        <div className="lg:sticky lg:top-24 lg:self-start">
          <AnimatePresence mode="wait">
          {!current ? <EmptyState key="empty" icon={<Sparkles className="h-5 w-5" />} title="Выберите приглашение" text="Откроется полное описание: условия, компания и почему вас пригласили." /> : (
            <motion.div key={current.id} initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -16 }} transition={{ duration: 0.3, ease: EASE }}>
            <Card>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm text-slate-500">{current.company.name}{current.company.industry && ` · ${current.company.industry}`}</p>
                  <h2 className="mt-0.5 text-xl font-bold">{current.title}</h2>
                </div>
                <StatusBadge status={current.status} />
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <div className="rounded-2xl bg-brand-gradient p-4 text-white">
                  <p className="text-xs text-white/60">Вилка, ₽ в месяц</p>
                  <p className="mt-1 text-lg font-extrabold leading-snug">{salaryRange(current.salary_from, current.salary_to)}</p>
                </div>
                <div className="rounded-2xl bg-surface p-4 text-sm">
                  <p className="flex items-center gap-2"><MapPin className="h-4 w-4 text-fsp-pink" />{current.work_format_name ?? 'Формат обсуждается'}{current.vacancy?.city && `, ${current.vacancy.city}`}</p>
                  <p className="mt-1.5 flex items-center gap-2"><Building2 className="h-4 w-4 text-fsp-pink" />Индекс доверия: {Math.round(current.company.trust_score * 100)}%{current.company.domain_verified && <ShieldCheck className="h-4 w-4 text-emerald-500" />}</p>
                  {current.expires_at && ['sent', 'viewed'].includes(current.status) && <p className="mt-1.5 text-xs text-slate-500">Действует до {date(current.expires_at)}</p>}
                </div>
              </div>
              <div className="mt-5">
                <p className="label">Предложение</p>
                <p className="whitespace-pre-line text-sm leading-relaxed text-slate-700">{current.message}</p>
              </div>
              {!!current.why_you?.length && (
                <div className="mt-5 rounded-2xl bg-[#ECEAFB]/60 p-4">
                  <p className="mb-2 flex items-center gap-2 text-sm font-semibold text-[#3c3480]"><Sparkles className="h-4 w-4" /> Почему вас пригласили</p>
                  <ul className="space-y-1">{current.why_you.map((r: any, k: number) => <li key={k} className="flex gap-2 text-sm text-slate-700"><CircleCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />{r.text}</li>)}</ul>
                </div>
              )}
              {current.company.description && <p className="mt-5 text-sm text-slate-500"><b className="text-fsp-deep">О компании:</b> {current.company.description}</p>}

              {current.status === 'accepted' && current.company_contacts && (
                <Alert tone="success" title="Контакты открыты" icon={<CircleCheck className="h-4 w-4" />}>
                  <div className="mt-1 space-y-0.5">
                    <p><MessageSquare className="mr-1 inline h-3.5 w-3.5" />{current.contact_method}</p>
                    {current.company_contacts.name && <p>{current.company_contacts.name}</p>}
                    {current.company_contacts.telegram && <p>Telegram: {current.company_contacts.telegram}</p>}
                    {current.company_contacts.email && <p><Mail className="mr-1 inline h-3.5 w-3.5" />{current.company_contacts.email}</p>}
                    {current.company_contacts.phone && <p><Phone className="mr-1 inline h-3.5 w-3.5" />{current.company_contacts.phone}</p>}
                    <p className="pt-1 text-xs">Работодатель тоже видит ваши контакты и свяжется с вами.</p>
                  </div>
                </Alert>
              )}
              {current.status === 'declined' && <Alert tone="info">Вы отклонили: {current.decline_reason_name}{current.decline_comment && ` — «${current.decline_comment}»`}</Alert>}

              {['sent', 'viewed'].includes(current.status) && (
                <div className="mt-6 flex flex-wrap gap-2 border-t border-slate-100 pt-5">
                  <Button onClick={() => accept.mutate()} loading={accept.isPending} icon={<Send className="h-4 w-4" />}>Принять и открыть контакты</Button>
                  <Button variant="secondary" onClick={() => setDecline({ reason: 'salary', comment: '' })} icon={<X className="h-4 w-4" />}>Отклонить</Button>
                  <Button variant="ghost" onClick={() => setComplain({ reason: 'fake', comment: '' })} icon={<Flag className="h-4 w-4" />}>Пожаловаться</Button>
                </div>
              )}
            </Card>
            </motion.div>
          )}
          </AnimatePresence>
        </div>
      </div>

      <Modal open={!!decline} onClose={() => setDecline(null)} title="Отклонить приглашение"
        footer={<><Button variant="secondary" onClick={() => setDecline(null)}>Отмена</Button><Button onClick={() => doDecline.mutate()} loading={doDecline.isPending}>Отклонить</Button></>}>
        {decline && <div className="space-y-4">
          <p className="text-sm text-slate-500">Причина поможет работодателю сделать более точное предложение. Ваши контакты не раскрываются.</p>
          <Field label="Причина"><Select value={decline.reason} onChange={e => setDecline({ ...decline, reason: e.target.value })}>
            {Object.entries(ref?.decline_reasons ?? {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Select></Field>
          <Field label="Комментарий (необязательно)"><Textarea value={decline.comment} onChange={e => setDecline({ ...decline, comment: e.target.value })} /></Field>
        </div>}
      </Modal>
      <Modal open={!!complain} onClose={() => setComplain(null)} title="Пожаловаться на приглашение"
        footer={<><Button variant="secondary" onClick={() => setComplain(null)}>Отмена</Button><Button variant="danger" onClick={() => doComplain.mutate()} loading={doComplain.isPending}>Отправить жалобу</Button></>}>
        {complain && <div className="space-y-4">
          <Field label="Причина"><Select value={complain.reason} onChange={e => setComplain({ ...complain, reason: e.target.value })}>
            <option value="fake">Похоже на фиктивную вакансию</option><option value="spam">Спам / массовая рассылка</option>
            <option value="salary_mismatch">Условия не соответствуют заявленным</option><option value="rude">Некорректное общение</option><option value="other">Другое</option></Select></Field>
          <Field label="Комментарий"><Textarea value={complain.comment} onChange={e => setComplain({ ...complain, comment: e.target.value })} /></Field>
          <Badge tone="lavender">Жалобы снижают индекс доверия работодателя и запускают проверку</Badge>
        </div>}
      </Modal>
    </div>
  )
}
