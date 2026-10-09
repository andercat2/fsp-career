import { useRef, type CSSProperties, type KeyboardEvent } from 'react'
import { Highlight } from 'prism-react-renderer'
import clsx from 'clsx'
import { CheckCircle2, Clock, EyeOff, TriangleAlert, XCircle } from 'lucide-react'
import { codeTheme, LANG_LABEL } from './Content'
import { Badge } from './ui'

const LINE = 21  // высота строки, px (одинаковая у подсветки и поля ввода)
const PAD = 12
const FONT: CSSProperties = {
  fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace',
  fontSize: 13, lineHeight: `${LINE}px`, letterSpacing: 0, tabSize: 4,
}

/** Редактор кода без зависимостей: поле ввода поверх подсветки Prism, номера строк, Tab и автоотступ.
 *  onPaste сообщает размер вставки — это сигнал для работодателя (решения, вставленные целиком). */
export function CodeEditor({ value, onChange, language, onPaste, readOnly, minLines = 12, maxLines = 26, label }: {
  value: string; onChange: (v: string) => void; language: string; onPaste?: (chars: number) => void
  readOnly?: boolean; minLines?: number; maxLines?: number; label?: string
}) {
  const ta = useRef<HTMLTextAreaElement>(null)
  const pre = useRef<HTMLPreElement>(null)
  const gutter = useRef<HTMLDivElement>(null)
  const count = value.split('\n').length
  const height = Math.min(Math.max(count + 1, minLines), maxLines) * LINE + PAD * 2
  const indent = language === 'python' ? '    ' : '  '

  const sync = () => {
    if (!ta.current) return
    if (pre.current) { pre.current.scrollTop = ta.current.scrollTop; pre.current.scrollLeft = ta.current.scrollLeft }
    if (gutter.current) gutter.current.scrollTop = ta.current.scrollTop
  }
  const replace = (from: number, to: number, text: string, caret: number) => {
    onChange(value.slice(0, from) + text + value.slice(to))
    requestAnimationFrame(() => { if (ta.current) { ta.current.selectionStart = ta.current.selectionEnd = caret } })
  }
  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (readOnly) return
    const { selectionStart: s, selectionEnd: en } = e.currentTarget
    if (e.key === 'Tab') {
      e.preventDefault()
      const lineStart = value.lastIndexOf('\n', s - 1) + 1
      if (e.shiftKey) {  // снять отступ у текущей строки
        const lead = value.slice(lineStart).match(/^ {1,4}/)?.[0] ?? ''
        if (lead) replace(lineStart, lineStart + lead.length, '', Math.max(lineStart, s - lead.length))
        return
      }
      replace(s, en, indent, s + indent.length)
    } else if (e.key === 'Enter') {
      e.preventDefault()
      const lineStart = value.lastIndexOf('\n', s - 1) + 1
      const current = value.slice(lineStart, s)
      const lead = current.match(/^\s*/)?.[0] ?? ''
      const extra = /[:{[(]\s*$/.test(current) ? indent : ''
      const text = '\n' + lead + extra
      replace(s, en, text, s + text.length)
    }
  }

  return (
    <div className="overflow-hidden rounded-2xl ring-1 ring-fsp-deep/25" style={{ background: '#22093d' }}>
      <div className="flex items-center justify-between bg-[#2c0d4d] px-4 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-white/60">
        <span>{label ?? LANG_LABEL[language] ?? language}</span>
        <span className="normal-case tracking-normal text-white/60">{readOnly ? 'только чтение' : 'Tab — отступ · Shift+Tab — убрать'}</span>
      </div>
      <div className="relative flex" style={{ height }}>
        <div ref={gutter} aria-hidden className="select-none overflow-hidden text-right text-white/50"
          style={{ ...FONT, padding: `${PAD}px 10px ${PAD}px 12px`, minWidth: 44 }}>
          {Array.from({ length: Math.max(count, minLines) }, (_, i) => <div key={i}>{i + 1}</div>)}
        </div>
        <div className="relative min-w-0 flex-1">
          <Highlight code={value + '\n'} language={language === 'javascript' ? 'javascript' : 'python'} theme={codeTheme}>
            {({ tokens, getLineProps, getTokenProps }) => (
              <pre ref={pre} aria-hidden className="pointer-events-none absolute inset-0 m-0 overflow-hidden whitespace-pre"
                style={{ ...FONT, padding: PAD, background: 'transparent' }}>
                {tokens.map((line, i) => (
                  <div key={i} {...getLineProps({ line })}>{line.map((token, k) => <span key={k} {...getTokenProps({ token })} />)}</div>
                ))}
              </pre>
            )}
          </Highlight>
          <textarea ref={ta} value={value} readOnly={readOnly} onChange={e => onChange(e.target.value)} onKeyDown={onKeyDown} onScroll={sync}
            onPaste={e => onPaste?.(e.clipboardData.getData('text').length)}
            spellCheck={false} autoCapitalize="off" autoComplete="off" autoCorrect="off" wrap="off" aria-label="Редактор кода"
            className="scrollbar-thin absolute inset-0 h-full w-full resize-none overflow-auto whitespace-pre bg-transparent outline-none selection:bg-fsp-pink/35"
            style={{ ...FONT, padding: PAD, color: 'transparent', caretColor: '#fff', WebkitTextFillColor: 'transparent' }} />
        </div>
      </div>
    </div>
  )
}

const fmt = (v: unknown) => {
  const s = JSON.stringify(v)
  return s === undefined ? 'null' : s.length > 160 ? s.slice(0, 160) + '…' : s
}
const STATUS: Record<string, [string, 'green' | 'red' | 'amber' | 'gray']> = {
  ok: ['выполнено', 'green'], compile_error: ['ошибка в коде', 'red'], timeout: ['превышено время', 'amber'], error: ['ошибка выполнения', 'red'],
}

/** Результаты прогона тестов: кандидат видит открытые тесты полностью, а скрытые — только «пройден / нет». */
export function TestResults({ res, title }: { res: any; title?: string }) {
  if (!res) return null
  const st = STATUS[res.status] ?? [res.status, 'gray']
  return (
    <div className="rounded-2xl border border-line bg-white p-4">
      <div className="flex flex-wrap items-center gap-2">
        <p className="font-semibold text-fsp-deep">{title ?? (res.which === 'visible' ? 'Запуск на примерах' : 'Проверка на всех тестах')}</p>
        <Badge tone={st[1]}>{st[0]}</Badge>
        {res.status === 'ok' && <Badge tone={res.passed === res.total ? 'green' : 'amber'}>пройдено {res.passed} из {res.total}</Badge>}
        {res.hidden_total > 0 && <Badge tone="lavender" icon={<EyeOff className="h-3 w-3" />}>скрытых: {res.hidden_passed} из {res.hidden_total}</Badge>}
        {res.duration_ms != null && <span className="inline-flex items-center gap-1 text-xs text-slate-400"><Clock className="h-3 w-3" />{res.duration_ms} мс</span>}
      </div>
      {res.error && <pre className="mt-3 whitespace-pre-wrap rounded-xl bg-red-50 p-3 font-mono text-xs text-red-800">{res.error}</pre>}
      {!!res.tests?.length && (
        <ul className="mt-3 space-y-2">
          {res.tests.map((x: any) => (
            <li key={x.index} className={clsx('rounded-xl px-3 py-2 text-xs', x.passed ? 'bg-emerald-50/70' : 'bg-red-50/70')}>
              <p className="flex items-center gap-1.5 font-semibold text-fsp-deep">
                {x.passed ? <CheckCircle2 className="h-4 w-4 text-emerald-500" /> : <XCircle className="h-4 w-4 text-red-500" />}
                {x.hidden ? `Скрытый тест ${x.index + 1}` : (x.name || `Тест ${x.index + 1}`)}{x.ms != null && <span className="font-normal text-slate-400">· {x.ms} мс</span>}
              </p>
              {'args' in x && (
                <div className="mt-1 grid gap-0.5 font-mono text-[11.5px] text-slate-600">
                  <span>аргументы: {fmt(x.args)}</span>
                  <span>ожидалось: {fmt(x.expected)}</span>
                  {!x.passed && !x.error && <span className="text-red-700">получено: {fmt(x.actual)}</span>}
                </div>
              )}
              {x.error && <p className="mt-1 flex items-start gap-1 font-mono text-[11.5px] text-red-700"><TriangleAlert className="mt-0.5 h-3 w-3 shrink-0" />{x.error}</p>}
              {x.stdout && <pre className="mt-1 whitespace-pre-wrap rounded-lg bg-white/70 p-2 font-mono text-[11px] text-slate-500">{x.stdout}</pre>}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
