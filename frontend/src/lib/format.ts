export const rub = (n?: number | null) =>
  n == null ? '—' : `${new Intl.NumberFormat('ru-RU').format(Math.round(n))} ₽`

export const salaryRange = (from?: number | null, to?: number | null) => {
  if (from && to) return `${new Intl.NumberFormat('ru-RU').format(from)} – ${new Intl.NumberFormat('ru-RU').format(to)} ₽`
  if (from) return `от ${rub(from)}`
  if (to) return `до ${rub(to)}`
  return 'не указана'
}

export const date = (s?: string | null) =>
  s ? new Date(s.endsWith('Z') || s.includes('+') ? s : `${s}Z`).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' }) : '—'

export const dateTime = (s?: string | null) =>
  s ? new Date(s.endsWith('Z') || s.includes('+') ? s : `${s}Z`).toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—'

export function ago(s?: string | null): string {
  if (!s) return '—'
  const d = new Date(s.endsWith('Z') || s.includes('+') ? s : `${s}Z`).getTime()
  const diff = (Date.now() - d) / 1000
  if (diff < 60) return 'только что'
  if (diff < 3600) return `${Math.round(diff / 60)} мин назад`
  if (diff < 86400) return `${Math.round(diff / 3600)} ч назад`
  if (diff < 86400 * 30) return `${Math.round(diff / 86400)} дн назад`
  return date(s)
}

export function plural(n: number, one: string, few: string, many: string) {
  const m10 = n % 10, m100 = n % 100
  if (m10 === 1 && m100 !== 11) return one
  if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return few
  return many
}

export const pct = (x?: number | null, digits = 0) => (x == null ? '—' : `${(x * 100).toFixed(digits)}%`)

export const years = (y?: number | null) => {
  if (y == null) return '—'
  const r = Math.round(y * 10) / 10
  const whole = Math.floor(r)
  return `${String(r).replace('.', ',')} ${plural(whole, 'год', 'года', 'лет')}`
}

export const WORK_FORMATS: Record<string, string> = { office: 'Офис', hybrid: 'Гибрид', remote: 'Удалённо' }
