import { Highlight, type PrismTheme } from 'prism-react-renderer'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

// Тема подсветки в палитре ФСП
const theme: PrismTheme = {
  plain: { color: '#F3EEFF', backgroundColor: '#22093d' },
  styles: [
    { types: ['comment'], style: { color: '#8f86b8', fontStyle: 'italic' } },
    { types: ['keyword', 'builtin', 'tag'], style: { color: '#FF5C8F' } },
    { types: ['string', 'char', 'attr-value'], style: { color: '#9BE7C4' } },
    { types: ['number', 'boolean', 'constant'], style: { color: '#FFC56B' } },
    { types: ['function', 'class-name'], style: { color: '#B9B3FF' } },
    { types: ['operator', 'punctuation'], style: { color: '#d7cfee' } },
    { types: ['property', 'attr-name'], style: { color: '#7FD3FF' } },
  ],
}

const LANG_ALIAS: Record<string, string> = { javascript: 'javascript', jsx: 'jsx', python: 'python', go: 'go', java: 'java',
  sql: 'sql', css: 'css', bash: 'bash', dockerfile: 'docker', ts: 'tsx' }
const LANG_LABEL: Record<string, string> = { javascript: 'JavaScript', jsx: 'React (JSX)', python: 'Python', go: 'Go', java: 'Java',
  sql: 'SQL', css: 'CSS', bash: 'Shell', dockerfile: 'Dockerfile' }

export function CodeBlock({ code, lang }: { code: string; lang?: string | null }) {
  const language = LANG_ALIAS[lang ?? ''] ?? 'clike'
  return (
    <div className="overflow-hidden rounded-2xl ring-1 ring-fsp-deep/20">
      {lang && <div className="flex items-center justify-between bg-[#2c0d4d] px-4 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-white/60">
        <span>{LANG_LABEL[lang] ?? lang}</span>
        <span className="flex gap-1"><i className="h-2 w-2 rounded-full bg-fsp-pink/80" /><i className="h-2 w-2 rounded-full bg-fsp-lavender/80" /><i className="h-2 w-2 rounded-full bg-white/30" /></span>
      </div>}
      <Highlight code={code.trimEnd()} language={language} theme={theme}>
        {({ style, tokens, getLineProps, getTokenProps }) => (
          <pre className="scrollbar-thin overflow-x-auto px-4 py-3 font-mono text-[13px] leading-relaxed" style={style}>
            {tokens.map((line, i) => (
              <div key={i} {...getLineProps({ line })}>
                {line.map((token, key) => <span key={key} {...getTokenProps({ token })} />)}
              </div>
            ))}
          </pre>
        )}
      </Highlight>
    </div>
  )
}

export function Markdown({ children, className }: { children: string; className?: string }) {
  return (
    <div className={`md-body text-[15px] text-fsp-ink ${className ?? ''}`}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={{
        code({ className: cls, children: c, ...props }) {
          const m = /language-(\w+)/.exec(cls || '')
          const text = String(c)
          if (m || text.includes('\n')) return <CodeBlock code={text} lang={m?.[1] ?? null} />
          return <code {...props}>{c}</code>
        },
        pre({ children: c }) { return <div className="my-3">{c}</div> },
        table({ children: c }) { return <div className="scrollbar-thin overflow-x-auto"><table>{c}</table></div> },
      }}>
        {children}
      </ReactMarkdown>
    </div>
  )
}
