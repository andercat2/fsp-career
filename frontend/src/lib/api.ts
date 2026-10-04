// Тонкий клиент REST API: JWT из localStorage, единая обработка ошибок, скачивание файлов.
export const API_BASE = '/api/v1'
const TOKEN_KEY = 'fsp_career_token'

export const tokenStore = {
  get: (): string | null => {
    try { return localStorage.getItem(TOKEN_KEY) } catch { return null }
  },
  set: (t: string) => { try { localStorage.setItem(TOKEN_KEY, t) } catch { /* приватный режим */ } },
  clear: () => { try { localStorage.removeItem(TOKEN_KEY) } catch { /* noop */ } },
}

export class ApiError extends Error {
  status: number
  detail: unknown
  constructor(status: number, message: string, detail: unknown) {
    super(message)
    this.status = status
    this.detail = detail
  }
}

const RU: [RegExp, string][] = [
  [/^Field required$/, 'обязательное поле'],
  [/^String should have at least (\d+) characters?$/, 'не короче $1 символов'],
  [/^String should have at most (\d+) characters?$/, 'не длиннее $1 символов'],
  [/^Input should be greater than (\d+)$/, 'должно быть больше $1'],
  [/^value is not a valid email address.*$/, 'некорректный e-mail'],
  [/^Value error, (.*)$/, '$1'],
  [/^List should have at least 1 item.*$/, 'выберите хотя бы одно значение'],
  [/^Input should be a valid integer.*$/, 'введите целое число'],
]
const FIELD: Record<string, string> = {
  password: 'Пароль', email: 'E-mail', salary_from: 'Зарплата от', salary_to: 'Зарплата до', title: 'Название',
  message: 'Описание предложения', contact_method: 'Способ связи', grades: 'Грейды', text: 'Текст', code: 'Код',
  consent_pd: 'Согласие', description: 'Описание', answer: 'Ответ', name: 'Название',
}

function humanize(detail: unknown): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((d: any) => {
      let msg: string = d?.msg ?? String(d)
      for (const [re, rep] of RU) if (re.test(msg)) { msg = msg.replace(re, rep); break }
      const loc: string[] = (d?.loc ?? []).filter((x: unknown) => typeof x === 'string' && x !== 'body')
      const field = loc.length ? FIELD[loc[loc.length - 1]] ?? loc[loc.length - 1] : ''
      return field ? `${field}: ${msg}` : msg
    }).join('; ')
  }
  return 'Ошибка запроса'
}

type Opts = { method?: string; body?: unknown; form?: FormData; signal?: AbortSignal }

export async function api<T = any>(path: string, opts: Opts = {}): Promise<T> {
  const headers: Record<string, string> = {}
  const token = tokenStore.get()
  if (token) headers.Authorization = `Bearer ${token}`
  let body: BodyInit | undefined
  if (opts.form) body = opts.form
  else if (opts.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(opts.body)
  }
  const res = await fetch(`${API_BASE}${path}`, { method: opts.method ?? (body ? 'POST' : 'GET'), headers, body, signal: opts.signal })
  if (res.status === 401 && token) {
    tokenStore.clear()
    window.dispatchEvent(new Event('fsp:unauthorized'))
  }
  const text = await res.text()
  const data = text ? safeJson(text) : null
  if (!res.ok) {
    const detail = (data as any)?.detail ?? data
    throw new ApiError(res.status, humanize(detail), detail)
  }
  return data as T
}

function safeJson(text: string): unknown {
  try { return JSON.parse(text) } catch { return text }
}

export async function download(path: string, filename: string) {
  const token = tokenStore.get()
  const res = await fetch(`${API_BASE}${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
  if (!res.ok) throw new ApiError(res.status, 'Не удалось скачать файл', null)
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 2000)
}

export function qs(params: Record<string, unknown>): string {
  const s = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === '' || v === false) continue
    if (Array.isArray(v)) { if (v.length) s.set(k, v.join(',')) } else s.set(k, String(v))
  }
  const out = s.toString()
  return out ? `?${out}` : ''
}
