import { useMemo, useRef, useState } from 'react'
import { Plus, Search, X } from 'lucide-react'
import clsx from 'clsx'
import { useReference } from '@/lib/reference'

/** Выбор навыков из онтологии платформы: поиск по названию и синонимам, группировка, «чипы». */
export function SkillPicker({ value, onChange, placeholder = 'Добавить навык…', verified = [], tone = 'pink', max }: {
  value: string[]; onChange: (v: string[]) => void; placeholder?: string; verified?: string[]; tone?: 'pink' | 'lavender'; max?: number
}) {
  const { ref } = useReference()
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  const options = useMemo(() => {
    const ql = q.trim().toLowerCase()
    return (ref?.skills ?? []).filter(s => !value.includes(s.id) && (!ql || s.name.toLowerCase().includes(ql) || s.id.includes(ql))).slice(0, 40)
  }, [ref, q, value])
  const add = (id: string) => {
    if (max && value.length >= max) return
    onChange([...value, id]); setQ('')
  }
  const name = (id: string) => ref?.skills.find(s => s.id === id)?.name ?? id
  return (
    <div ref={box} className="relative" onBlur={e => { if (!box.current?.contains(e.relatedTarget as Node)) setOpen(false) }}>
      <div className="input flex min-h-[44px] flex-wrap items-center gap-1.5 py-1.5" onClick={() => setOpen(true)}>
        {value.map(id => (
          <span key={id} className={clsx('chip', tone === 'pink' ? 'bg-fsp-blush/70 text-[#9e0035]' : 'bg-[#ECEAFB] text-[#4b4392]')}>
            {verified.includes(id) && <span title="Подтверждён тестом">✓</span>}{name(id)}
            <button type="button" onClick={e => { e.stopPropagation(); onChange(value.filter(x => x !== id)) }} aria-label={`Убрать ${name(id)}`}>
              <X className="h-3 w-3" />
            </button>
          </span>
        ))}
        <div className="flex min-w-[140px] flex-1 items-center gap-1.5">
          <Search className="h-3.5 w-3.5 text-slate-400" />
          <input value={q} onChange={e => { setQ(e.target.value); setOpen(true) }} onFocus={() => setOpen(true)}
                 onKeyDown={e => { if (e.key === 'Enter' && options[0]) { e.preventDefault(); add(options[0].id) } }}
                 placeholder={value.length ? '' : placeholder} className="w-full border-0 bg-transparent p-0 text-sm outline-none focus:ring-0" />
        </div>
      </div>
      {open && options.length > 0 && (
        <div className="absolute z-30 mt-1 max-h-64 w-full overflow-y-auto rounded-2xl bg-white p-1.5 shadow-pop ring-1 ring-slate-100">
          {options.map(s => (
            <button key={s.id} type="button" onMouseDown={e => e.preventDefault()} onClick={() => add(s.id)}
              className="flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2 text-left text-sm hover:bg-surface">
              <span className="flex items-center gap-2"><Plus className="h-3.5 w-3.5 text-fsp-pink" />{s.name}</span>
              <span className="text-[11px] text-slate-400">{s.group}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
