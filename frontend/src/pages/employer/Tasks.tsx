import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { ClipboardPaste, Code2, Copy, EyeOff, FlaskConical, ListChecks, Plus, Star, Trash2 } from 'lucide-react'
import { api } from '@/lib/api'
import { useReference } from '@/lib/reference'
import { useToast } from '@/lib/toast'
import { ago } from '@/lib/format'
import { Alert, Badge, Button, Card, Checkbox, EmptyState, Field, Input, Modal, PageHeader, PageLoader, Select, Tabs, Textarea } from '@/components/ui'
import { CodeBlock } from '@/components/Content'
import { CodeEditor, TestResults } from '@/components/CodeEditor'

type TestRow = { name: string; args: string; expected: string; hidden: boolean }
const EXAMPLE: Record<string, { entrypoint: string; starter: string; reference: string; tests: TestRow[] }> = {
  python: {
    entrypoint: 'solve',
    starter: 'def solve(nums):\n    # верните сумму чётных чисел списка\n    pass\n',
    reference: 'def solve(nums):\n    return sum(x for x in nums if x % 2 == 0)\n',
    tests: [{ name: 'пример', args: '[[1, 2, 3, 4]]', expected: '6', hidden: false }, { name: 'пустой список', args: '[[]]', expected: '0', hidden: false },
      { name: '', args: '[[-2, 5, 7]]', expected: '-2', hidden: true }, { name: '', args: '[[10, 11, 12]]', expected: '22', hidden: true }],
  },
  javascript: {
    entrypoint: 'solve',
    starter: 'function solve(nums) {\n  // верните сумму чётных чисел массива\n}\n',
    reference: 'function solve(nums) {\n  return nums.filter(x => x % 2 === 0).reduce((a, b) => a + b, 0);\n}\n',
    tests: [{ name: 'пример', args: '[[1, 2, 3, 4]]', expected: '6', hidden: false }, { name: 'пустой массив', args: '[[]]', expected: '0', hidden: false },
      { name: '', args: '[[-2, 5, 7]]', expected: '-2', hidden: true }, { name: '', args: '[[10, 11, 12]]', expected: '22', hidden: true }],
  },
}
const KIND: Record<string, string> = { approach: 'предложить подход', solve: 'решить', code: 'код' }

function parseTests(rows: TestRow[]): { tests?: any[]; error?: string } {
  const tests = []
  for (const [i, r] of rows.entries()) {
    try {
      const args = JSON.parse(r.args)
      if (!Array.isArray(args)) return { error: `Тест ${i + 1}: аргументы — JSON-массив, например [[1, 2, 3]]` }
      tests.push({ name: r.name || null, args, expected: JSON.parse(r.expected), hidden: r.hidden })
    } catch { return { error: `Тест ${i + 1}: некорректный JSON` } }
  }
  if (!tests.some(t => !t.hidden) || !tests.some(t => t.hidden)) return { error: 'Нужен хотя бы один открытый и один скрытый тест' }
  return { tests }
}

function Review({ ta }: { ta: any }) {
  const qc = useQueryClient()
  const { push } = useToast()
  const [score, setScore] = useState(ta.score ?? 0)
  const [feedback, setFeedback] = useState(ta.feedback ?? '')
  const save = useMutation({ mutationFn: () => api(`/employer/submissions/${ta.id}/review`, { body: { score, feedback } }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['emp-subs'] }); push('Оценка сохранена — профиль кандидата обновлён') }, onError: (e: any) => push(e.message, 'error') })
  const code = ta.task.kind === 'code'
  const sig = ta.signals
  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-bold text-fsp-deep">{ta.task.title}</p>
          <p className="text-sm text-slate-500"><Link to={`/employer/candidates/${ta.candidate.id}`} className="link">{ta.candidate.public_id}</Link> · {ta.candidate.specialization_name} · {ta.candidate.grade_name} · {ago(ta.submitted_at)}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {code && ta.results && <Badge tone={ta.results.passed === ta.results.total ? 'green' : 'amber'}>тесты: {ta.results.passed} из {ta.results.total}</Badge>}
          {!code && ta.auto_score != null && <Badge tone="lavender">автооценка по рубрике: {Math.round(ta.auto_score * 100)}%</Badge>}
        </div>
      </div>
      {code ? (
        <div className="mt-3 space-y-3">
          {ta.plagiarism && (
            <Alert tone="warn" icon={<Copy className="h-4 w-4" />} title="Антиплагиат: решение похоже на другое">
              {ta.plagiarism.similarity != null && <>Сходство по структуре кода {Math.round(ta.plagiarism.similarity * 100)}% с решением кандидата {ta.plagiarism.candidate_public_id}. </>}
              {ta.plagiarism.reference_similarity != null && <>Совпадение с вашим эталоном: {Math.round(ta.plagiarism.reference_similarity * 100)}%. </>}
              Переименование переменных и форматирование не скрывают копию; одинаковые решения также бывают сгенерированы одной подсказкой LLM.
            </Alert>
          )}
          {sig && (
            <p className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
              <span className="inline-flex items-center gap-1"><ClipboardPaste className="h-3.5 w-3.5" />вставок из буфера: {sig.pastes}{sig.pasted_chars ? ` (${sig.pasted_chars} симв., ${Math.round(sig.paste_share * 100)}% решения)` : ''}</span>
              <span>уходов со вкладки: {sig.away_count}</span>
              <span>запусков: {sig.runs}</span>
              {sig.elapsed_ms > 0 && <span>время работы: {Math.round(sig.elapsed_ms / 60000)} мин</span>}
            </p>
          )}
          <CodeBlock code={ta.code ?? ''} lang={ta.task.code_language} />
          <TestResults res={ta.results} title="Автопроверка на всех тестах (скрытые видны только вам)" />
        </div>
      ) : <p className="mt-3 whitespace-pre-line rounded-2xl bg-surface p-4 text-sm text-slate-700">{ta.answer}</p>}
      <div className="mt-4 flex flex-wrap items-end gap-3">
        <div>
          <p className="label">Оценка</p>
          <div className="flex gap-1">{[1, 2, 3, 4, 5].map(n => (
            <button key={n} onClick={() => setScore(n)} aria-label={`${n}`}><Star className={clsx('h-7 w-7', n <= score ? 'fill-amber-400 text-amber-400' : 'text-slate-300')} /></button>))}</div>
        </div>
        <Input className="min-w-[240px] flex-1" placeholder="Комментарий кандидату" value={feedback} onChange={e => setFeedback(e.target.value)} />
        <Button disabled={!score} loading={save.isPending} onClick={() => save.mutate()}>{ta.status === 'reviewed' ? 'Обновить' : 'Оценить'}</Button>
      </div>
    </Card>
  )
}

const EMPTY = { title: '', description: '', specialization: 'backend', kind: 'approach', expected_answer: '', time_estimate_min: 30,
  code_language: 'python', entrypoint: 'solve', starter_code: '', reference_solution: '', compare: 'exact', time_limit_ms: 2000 }

function TaskModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient()
  const { push } = useToast()
  const { ref } = useReference()
  const [f, setF] = useState<any>(EMPTY)
  const [rows, setRows] = useState<TestRow[]>([])
  const [check, setCheck] = useState<any>(null)
  const code = f.kind === 'code'
  const setKind = (kind: string) => {
    if (kind === 'code' && !rows.length) applyExample(f.code_language)
    setF((s: any) => ({ ...s, kind }))
  }
  const applyExample = (lang: string) => {
    const ex = EXAMPLE[lang]
    setF((s: any) => ({ ...s, code_language: lang, entrypoint: ex.entrypoint, starter_code: ex.starter, reference_solution: ex.reference }))
    setRows(ex.tests)
    setCheck(null)
  }
  const body = () => {
    if (!code) return { ...f, expected_answer: f.expected_answer || null, code_language: null, entrypoint: null, tests: [] }
    const parsed = parseTests(rows)
    if (parsed.error) throw new Error(parsed.error)
    return { ...f, expected_answer: null, tests: parsed.tests, reference_solution: f.reference_solution || null, starter_code: f.starter_code || null }
  }
  const verify = useMutation({
    mutationFn: () => { const b = body(); return api('/employer/tasks/check-code', { body: { code_language: b.code_language, entrypoint: b.entrypoint, tests: b.tests, time_limit_ms: b.time_limit_ms, compare: b.compare, reference_solution: b.reference_solution } }) },
    onSuccess: (r: any) => setCheck(r), onError: (e: any) => push(e.message, 'error'),
  })
  const create = useMutation({ mutationFn: () => api('/employer/tasks', { body: body() }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['emp-tasks'] }); onClose(); setF(EMPTY); setRows([]); setCheck(null); push('Задание создано — система будет предлагать его кандидатам категории') },
    onError: (e: any) => push(e.message, 'error') })
  const updRow = (i: number, patch: Partial<TestRow>) => { setRows(r => r.map((x, j) => j === i ? { ...x, ...patch } : x)); setCheck(null) }
  return (
    <Modal open={open} onClose={onClose} title="Новое задание" wide
      footer={<><Button variant="secondary" onClick={onClose}>Отмена</Button><Button loading={create.isPending} disabled={f.title.length < 3 || f.description.length < 10} onClick={() => create.mutate()}>Создать</Button></>}>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Название" required className="sm:col-span-2"><Input value={f.title} onChange={e => setF({ ...f, title: e.target.value })} /></Field>
        <Field label="Специализация"><Select value={f.specialization} onChange={e => setF({ ...f, specialization: e.target.value })}>
          {ref?.specializations.map(s => <option key={s.code} value={s.code}>{s.name}</option>)}</Select></Field>
        <Field label="Тип"><Select value={f.kind} onChange={e => setKind(e.target.value)}>
          <option value="approach">Предложить подход</option><option value="solve">Решить (текстом)</option><option value="code">Задача с кодом — автопроверка тестами</option></Select></Field>
        <Field label={code ? 'Условие (поддерживается Markdown)' : 'Условие'} required className="sm:col-span-2"><Textarea rows={4} value={f.description} onChange={e => setF({ ...f, description: e.target.value })} /></Field>
        {!code && <Field label="Эталон / рубрика (для предварительной автооценки)" className="sm:col-span-2"><Textarea rows={3} value={f.expected_answer} onChange={e => setF({ ...f, expected_answer: e.target.value })} /></Field>}
        <Field label="Оценка времени, мин"><Input type="number" value={f.time_estimate_min} onChange={e => setF({ ...f, time_estimate_min: Number(e.target.value) })} /></Field>
        {code && <>
          <Field label="Язык"><Select value={f.code_language} onChange={e => applyExample(e.target.value)}><option value="python">Python</option><option value="javascript">JavaScript</option></Select></Field>
          <Field label="Имя функции" hint="Кандидат пишет эту функцию"><Input className="font-mono" value={f.entrypoint} onChange={e => setF({ ...f, entrypoint: e.target.value })} /></Field>
          <Field label="Сравнение результата"><Select value={f.compare} onChange={e => setF({ ...f, compare: e.target.value })}><option value="exact">Точное (числа — с допуском 1e-6)</option><option value="unordered">Порядок элементов не важен</option></Select></Field>
          <Field label="Лимит времени на прогон, мс"><Input type="number" min={500} max={10000} step={500} value={f.time_limit_ms} onChange={e => setF({ ...f, time_limit_ms: Number(e.target.value) })} /></Field>
          <div className="sm:col-span-2"><p className="label">Шаблон для кандидата</p><CodeEditor value={f.starter_code} onChange={v => setF({ ...f, starter_code: v })} language={f.code_language} minLines={5} maxLines={12} /></div>
          <div className="sm:col-span-2"><p className="label">Эталонное решение — проверяет тесты, кандидату не показывается</p><CodeEditor value={f.reference_solution} onChange={v => { setF({ ...f, reference_solution: v }); setCheck(null) }} language={f.code_language} minLines={5} maxLines={12} /></div>
          <div className="sm:col-span-2">
            <div className="mb-2 flex items-center justify-between"><p className="label !mb-0">Тесты: аргументы и ожидаемый результат в JSON</p>
              <Button size="sm" variant="soft" icon={<Plus className="h-3.5 w-3.5" />} onClick={() => setRows(r => [...r, { name: '', args: '[]', expected: 'null', hidden: true }])}>Тест</Button></div>
            <div className="space-y-2">
              {rows.map((r, i) => (
                <div key={i} className="grid items-center gap-2 rounded-xl bg-surface p-2 sm:grid-cols-[1fr_1.4fr_1fr_auto_auto]">
                  <Input placeholder="название" value={r.name} onChange={e => updRow(i, { name: e.target.value })} />
                  <Input className="font-mono" placeholder="[аргументы]" value={r.args} onChange={e => updRow(i, { args: e.target.value })} />
                  <Input className="font-mono" placeholder="ожидается" value={r.expected} onChange={e => updRow(i, { expected: e.target.value })} />
                  <Checkbox checked={r.hidden} onChange={v => updRow(i, { hidden: v })} label={<span className="inline-flex items-center gap-1 text-xs"><EyeOff className="h-3 w-3" />скрытый</span>} />
                  <Button size="sm" variant="ghost" aria-label="Удалить тест" onClick={() => setRows(x => x.filter((_, j) => j !== i))}><Trash2 className="h-3.5 w-3.5" /></Button>
                </div>
              ))}
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <Button size="sm" variant="secondary" loading={verify.isPending} disabled={!f.reference_solution} onClick={() => verify.mutate()} icon={<FlaskConical className="h-4 w-4" />}>Проверить тесты эталоном</Button>
              <span className="text-xs text-slate-500">Открытые тесты — примеры для кандидата; скрытые проверяются при отправке, кандидат видит только «пройден / нет».</span>
            </div>
            {check && <div className="mt-3"><TestResults res={check} title="Эталон на всех тестах" /></div>}
          </div>
        </>}
      </div>
      <div className="mt-4"><Alert tone="info">{code ? 'Код кандидата исполняется в изолированной песочнице (без сети, с лимитами времени и памяти). Автооценка — доля пройденных тестов; итоговую оценку 1–5 ставите вы.' : 'Решения оцениваются по шкале 1–5. Оценка влияет на компонент «активность» в силе профиля кандидата.'}</Alert></div>
    </Modal>
  )
}

export function EmployerTasks() {
  const [tab, setTab] = useState<'submitted' | 'reviewed' | 'tasks'>('submitted')
  const [open, setOpen] = useState(false)
  const { data: tasks } = useQuery({ queryKey: ['emp-tasks'], queryFn: () => api<any[]>('/employer/tasks') })
  const { data: subs, isLoading } = useQuery({ queryKey: ['emp-subs', tab], queryFn: () => api<any[]>(`/employer/tasks/submissions?status=${tab}`), enabled: tab !== 'tasks' })
  return (
    <div>
      <PageHeader title="Регулярные задания" subtitle="Короткие задачи от вашей команды: текстом или с кодом — тогда решение автоматически проверяется тестами в песочнице. Раз в неделю система предлагает задания кандидатам подходящей категории."
        actions={<Button onClick={() => setOpen(true)} icon={<Plus className="h-4 w-4" />}>Новое задание</Button>} />
      <Tabs value={tab} onChange={setTab} items={[{ value: 'submitted', label: 'На проверке' }, { value: 'reviewed', label: 'Проверенные' }, { value: 'tasks', label: 'Мои задания', count: tasks?.length }]} />
      <div className="mt-5 space-y-3">
        {tab === 'tasks' ? (
          !tasks?.length ? <EmptyState icon={<ListChecks className="h-5 w-5" />} title="Заданий пока нет" /> : tasks.map(t => (
            <Card key={t.id}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div><p className="font-bold text-fsp-deep">{t.title}</p><p className="text-sm text-slate-500">{t.specialization_name} · {KIND[t.kind]}{t.kind === 'code' && ` · ${t.code_language === 'python' ? 'Python' : 'JavaScript'} · тестов ${t.tests.length} (скрытых ${t.hidden_count})`} · ~{t.time_estimate_min} мин</p></div>
                <div className="flex flex-wrap gap-2 text-xs">{t.kind === 'code' && <Badge tone="pink" icon={<Code2 className="h-3 w-3" />}>автопроверка</Badge>}<Badge tone="amber">предложено {t.counts.offered}</Badge><Badge tone="blue">ответов {t.counts.submitted}</Badge><Badge tone="green">проверено {t.counts.reviewed}</Badge></div>
              </div>
              <p className="mt-2 line-clamp-3 whitespace-pre-line text-sm text-slate-600">{t.description}</p>
            </Card>
          ))
        ) : isLoading ? <PageLoader /> : !subs?.length ? <EmptyState icon={<ListChecks className="h-5 w-5" />} title={tab === 'submitted' ? 'Новых решений нет' : 'Проверенных решений нет'} /> : subs.map(ta => <Review key={ta.id} ta={ta} />)}
      </div>
      <TaskModal open={open} onClose={() => setOpen(false)} />
    </div>
  )
}
