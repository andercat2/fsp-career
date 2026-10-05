import { useEffect, useState } from 'react'
import { Camera, Clock, Repeat, Timer } from 'lucide-react'
import { Button, Checkbox, Modal } from './ui'

/** Тест начинается только после подтверждения готовности: правила, время, прокторинг и ограничения частоты. */
export function StartTestModal({ grade, title, onClose, onConfirm, loading }: {
  grade: string | null; title?: string; onClose: () => void; onConfirm: () => void; loading?: boolean
}) {
  const [ready, setReady] = useState(false)
  useEffect(() => { if (grade) setReady(false) }, [grade])
  const rules = [
    { icon: <Timer className="h-4 w-4" />, text: '12–24 задания, обычно 20–40 минут. Время на задание зависит от его сложности, вернуться к заданию нельзя.' },
    { icon: <Camera className="h-4 w-4" />, text: 'Прокторинг: снимок экрана, печать или копирование задания — первый раз предупреждение, второй — тест завершится досрочно с пониженной оценкой.' },
    { icon: <Repeat className="h-4 w-4" />, text: 'Попытка засчитывается: повторить этот уровень можно через месяц. Грейд не понижается — текущая категория сохранится при любом результате.' },
    { icon: <Clock className="h-4 w-4" />, text: 'Нужны спокойная обстановка и стабильный интернет; незавершённый тест закрывается через 3 часа.' },
  ]
  return (
    <Modal open={!!grade} onClose={onClose} title={`Готовы к тесту${title ? ` на ${title}` : ''}?`}
      footer={<><Button variant="secondary" onClick={onClose}>Позже</Button>
        <Button disabled={!ready} loading={loading} onClick={onConfirm}>Начать тест</Button></>}>
      <ul className="space-y-3 text-sm leading-relaxed text-slate-600">
        {rules.map((r, i) => (
          <li key={i} className="flex gap-3"><span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-fsp-blush/60 text-fsp-pink">{r.icon}</span><span>{r.text}</span></li>
        ))}
      </ul>
      <div className="mt-5 rounded-2xl bg-surface p-3">
        <Checkbox checked={ready} onChange={setReady} label="Я готов(а) начать тест сейчас" />
      </div>
    </Modal>
  )
}
