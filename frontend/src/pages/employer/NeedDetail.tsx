import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { ArrowLeft, Ban, Check, Eye, EyeOff, Fingerprint, Lock, Pencil, RefreshCw, Sparkles, X } from 'lucide-react'
import { api } from '@/lib/api'
import { useToast } from '@/lib/toast'
import { ago, salaryRange } from '@/lib/format'
import { Alert, Badge, Button, ButtonLink, Card, EmptyState, PageHeader, PageLoader, Tabs } from '@/components/ui'
import { CategoryPill, MatchRing, Reasons } from '@/components/Domain'
import { CodeBlock, Markdown } from '@/components/Content'

function Applications({ vid }: { vid: string }) {
  const qc = useQueryClient()
  const { push } = useToast()
  const { data, isLoading } = useQuery({ queryKey: ['emp-apps', vid], queryFn: () => api<any[]>(`/employer/vacancies/${vid}/applications`) })
  const upd = useMutation({ mutationFn: (p: { id: number; status: string }) => api(`/employer/applications/${p.id}`, { method: 'PUT', body: { status: p.status } }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['emp-apps', vid] }); push('Статус отклика обновлён') }, onError: (e: any) => push(e.message, 'error') })
  if (isLoading || !data) return <PageLoader />
  if (!data.length) return <EmptyState title="Откликов пока нет" text="Опубликуйте вакансию — кандидаты без приглашений смогут проявить инициативу сами." />
  return (
    <div className="space-y-3">
      {data.map(a => (
        <Card key={a.id}>
          <div className="flex flex-wrap items-start gap-4">
            {a.match != null ? <MatchRing value={a.match} /> : <div className="grid h-16 w-16 place-items-center rounded-full bg-slate-100 text-center text-[10px] text-slate-500">нет<br />категории</div>}
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <Link to={`/employer/candidates/${a.candidate.id}`} className="text-lg font-bold text-fsp-deep hover:text-fsp-pink">{a.candidate.display_name}</Link>
                <CategoryPill spec={a.candidate.specialization_name} grade={a.candidate.grade_name} />
                <Badge tone={a.status === 'accepted' ? 'green' : a.status === 'rejected' ? 'red' : a.status === 'viewed' ? 'lavender' : 'blue'}>{a.status_name}</Badge>
              </div>
              <p className="text-sm text-slate-500">{a.candidate.headline} · {a.candidate.city} · {ago(a.created_at)}</p>
              {a.cover_letter && <p className="mt-2 rounded-xl bg-surface px-3 py-2 text-sm text-slate-700">{a.cover_letter}</p>}
              {!!a.reasons?.length && <div className="mt-3"><Reasons reasons={a.reasons} limit={4} /></div>}
            </div>
            <div className="flex flex-wrap gap-2">
              {a.status === 'sent' && <Button size="sm" variant="secondary" onClick={() => upd.mutate({ id: a.id, status: 'viewed' })}>Просмотрено</Button>}
              {['sent', 'viewed'].includes(a.status) && <>
                <Button size="sm" onClick={() => upd.mutate({ id: a.id, status: 'accepted' })} icon={<Check className="h-4 w-4" />}>Пригласить на интервью</Button>
                <Button size="sm" variant="danger" onClick={() => upd.mutate({ id: a.id, status: 'rejected' })} icon={<X className="h-4 w-4" />}>Отказать</Button></>}
            </div>
          </div>
        </Card>
      ))}
    </div>
  )
}

function TestPreview({ vid }: { vid: string }) {
  const [seed, setSeed] = useState<number | undefined>(undefined)
  const [show, setShow] = useState(false)
  const { data, isLoading, isFetching } = useQuery({ queryKey: ['test-preview', vid, seed], queryFn: () => api(`/employer/vacancies/${vid}/test-preview${seed ? `?seed=${seed}` : ''}`) })
  if (isLoading || !data) return <PageLoader />
  const fmt = (a: any, it: any) => it.options ? (Array.isArray(a) ? a : [a]).map((id: string) => it.options.find((o: any) => o.id === id)?.text).join('; ') : String(a)
  return (
    <div className="space-y-6">
      <Alert tone="info" icon={<Sparkles className="h-4 w-4" />} title="Как система формирует тест по вакансии">
        <ul className="mt-1 list-disc space-y-0.5 pl-4">{data.how_it_works.map((t: string, i: number) => <li key={i}>{t}</li>)}</ul>
      </Alert>
      <div className="grid gap-6 lg:grid-cols-[1fr_1.4fr]">
        <Card title="Блюпринт теста" subtitle={`Целевой уровень: ${data.grade_name} (θ ≈ ${data.theta_target})`}>
          <div className="space-y-2">
            {data.blueprint.map((b: any) => (
              <div key={b.domain} className="flex items-center gap-3 text-sm">
                <span className="w-44 shrink-0 truncate text-slate-600">{b.name}</span>
                <div className="h-2 flex-1 rounded-full bg-slate-100"><div className="h-full rounded-full bg-fsp-pink" style={{ width: `${Math.min(100, b.weight * 250)}%` }} /></div>
                <span className="w-10 text-right text-xs text-slate-500">{Math.round(b.weight * 100)}%</span>
              </div>
            ))}
          </div>
          {!!data.boosts.length && <div className="mt-4 border-t border-slate-100 pt-3">
            <p className="label">Усиление по навыкам вакансии</p>
            <div className="flex flex-wrap gap-1.5">{data.boosts.slice(0, 12).map((b: any, i: number) => <Badge key={i} tone={b.kind === 'обязательный' ? 'pink' : 'lavender'}>{b.skill} → {b.domain}</Badge>)}</div>
          </div>}
        </Card>
        <Card title="Уникальность вариантов" subtitle={`Одно семейство «${data.uniqueness_demo.topic}» — три кандидата получат разные данные и ответы при одинаковой трудности`}>
          <div className="grid gap-3 md:grid-cols-3">
            {data.uniqueness_demo.variants.map((v: any, i: number) => (
              <div key={i} className="rounded-2xl bg-surface p-3 text-xs">
                <p className="mb-2 flex items-center gap-1.5 font-semibold text-fsp-deep"><Fingerprint className="h-3.5 w-3.5 text-fsp-pink" />Кандидат {i + 1}</p>
                <div className="max-h-56 overflow-y-auto"><Markdown className="!text-xs">{v.prompt}</Markdown>{v.code && <pre className="mt-2 overflow-x-auto rounded-lg bg-[#22093d] p-2 font-mono text-[10px] text-white">{v.code}</pre>}</div>
                <p className="mt-2 rounded-lg bg-white px-2 py-1 font-mono">Ответ: <b>{fmt(v.answer, v)}</b></p>
              </div>
            ))}
          </div>
        </Card>
      </div>
      <Card title="Пример заданий для этой вакансии" subtitle="Подборка по доменам блюпринта на уровне грейда вакансии"
        actions={<><Button size="sm" variant="secondary" onClick={() => setShow(s => !s)} icon={show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}>{show ? 'Скрыть ответы' : 'Показать ответы'}</Button>
          <Button size="sm" variant="soft" loading={isFetching} onClick={() => setSeed(Math.floor(Math.random() * 1e9))} icon={<RefreshCw className="h-4 w-4" />}>Другие варианты</Button></>}>
        <div className="grid gap-4 lg:grid-cols-2">
          {data.items.map((it: any, i: number) => (
            <div key={i} className="rounded-2xl ring-1 ring-slate-100 p-4">
              <div className="mb-2 flex flex-wrap gap-1.5"><Badge tone="lavender">{it.domain_name}</Badge><Badge>уровень {it.level}/5</Badge>{it.parametric && <Badge tone="pink">параметрическое</Badge>}</div>
              <Markdown className="!text-sm">{it.prompt}</Markdown>
              {it.code && <div className="mt-2"><CodeBlock code={it.code} lang={it.code_lang} /></div>}
              {it.options && <ul className="mt-2 space-y-1 text-sm">{it.options.map((o: any) => (
                <li key={o.id} className={clsx('rounded-lg px-2 py-1', show && (Array.isArray(it.answer) ? it.answer.includes(o.id) : it.answer === o.id) ? 'bg-emerald-50 font-semibold text-emerald-800' : 'bg-surface')}>{o.text}</li>))}</ul>}
              {show && !it.options && <p className="mt-2 rounded-lg bg-emerald-50 px-2 py-1 font-mono text-sm text-emerald-800">Ответ: {String(it.answer)}</p>}
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}

export function NeedDetail() {
  const { id } = useParams()
  const nav = useNavigate()
  const qc = useQueryClient()
  const { push } = useToast()
  const [tab, setTab] = useState<'apps' | 'test' | 'selections'>('apps')
  const { data: v, isLoading } = useQuery({ queryKey: ['emp-vacancy', id], queryFn: () => api(`/employer/vacancies/${id}`) })
  const { data: sels } = useQuery({ queryKey: ['emp-selections'], queryFn: () => api<any[]>('/employer/selections') })
  const match = useMutation({ mutationFn: () => api('/employer/selections', { body: { vacancy_id: Number(id) } }), onSuccess: (s: any) => nav(`/employer/selections/${s.id}`), onError: (e: any) => push(e.message, 'error') })
  const publish = useMutation({
    mutationFn: () => api(`/employer/vacancies/${id}`, { method: 'PUT', body: { ...v, is_published: !v.is_published, city: v.city || null } }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['emp-vacancy', id] }); qc.invalidateQueries({ queryKey: ['emp-vacancies'] }); push(v.is_published ? 'Вакансия снята с публикации' : 'Вакансия опубликована') },
    onError: (e: any) => push(e.message, 'error'),
  })
  const close = useMutation({ mutationFn: () => api(`/employer/vacancies/${id}/close`, { method: 'POST' }), onSuccess: () => { qc.invalidateQueries({ queryKey: ['emp-vacancy', id] }); push('Вакансия закрыта') } })
  if (isLoading || !v) return <PageLoader />
  const mine = sels?.filter(s => s.vacancy_id === v.id) ?? []
  return (
    <div>
      <PageHeader back={<Link to="/employer/needs" className="mb-2 inline-flex items-center gap-1.5 text-sm font-semibold text-slate-500 hover:text-fsp-pink"><ArrowLeft className="h-4 w-4" /> Потребности</Link>}
        title={v.title}
        subtitle={<span className="flex flex-wrap items-center gap-2">
          <Badge tone={v.is_published ? 'green' : 'gray'} icon={v.is_published ? <Eye className="h-3 w-3" /> : <Lock className="h-3 w-3" />}>{v.is_published ? 'опубликована' : 'приватная потребность'}</Badge>
          <Badge tone="lavender">{v.specialization_name}</Badge>{v.grade_names.map((g: string) => <Badge key={g}>{g}</Badge>)}
          <span>{salaryRange(v.salary_from, v.salary_to)} · {v.work_format_name}{v.city && `, ${v.city}`}</span></span>}
        actions={<>
          <ButtonLink to={`/employer/needs/${v.id}/edit`} variant="secondary" icon={<Pencil className="h-4 w-4" />}>Изменить</ButtonLink>
          {v.status === 'active' && <Button variant="secondary" loading={publish.isPending} onClick={() => publish.mutate()} icon={v.is_published ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}>{v.is_published ? 'Снять с публикации' : 'Опубликовать'}</Button>}
          {v.status === 'active' && <Button variant="ghost" onClick={() => close.mutate()} icon={<Ban className="h-4 w-4" />}>Закрыть</Button>}
          <Button loading={match.isPending} onClick={() => match.mutate()} icon={<Sparkles className="h-4 w-4" />}>Подобрать кандидатов</Button>
        </>} />
      <Tabs value={tab} onChange={setTab} items={[
        { value: 'apps', label: 'Отклики', count: v.applications_count },
        { value: 'test', label: 'Тест по вакансии' },
        { value: 'selections', label: 'Подборки', count: mine.length },
      ]} />
      <div className="mt-5">
        {tab === 'apps' && <Applications vid={id!} />}
        {tab === 'test' && <TestPreview vid={id!} />}
        {tab === 'selections' && (!mine.length ? <EmptyState icon={<Sparkles className="h-5 w-5" />} title="Подборок по этой потребности ещё нет" action={<Button size="sm" onClick={() => match.mutate()}>Подобрать</Button>} /> :
          <div className="space-y-2">{mine.map(s => (
            <Link key={s.id} to={`/employer/selections/${s.id}`} className="card flex items-center justify-between p-4 hover:ring-fsp-lavender">
              <span className="font-semibold text-fsp-deep">{s.title}</span><span className="text-sm text-slate-500">{s.total} кандидатов · {ago(s.created_at)}</span></Link>))}</div>)}
      </div>
    </div>
  )
}
