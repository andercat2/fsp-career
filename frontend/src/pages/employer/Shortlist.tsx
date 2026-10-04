import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Star } from 'lucide-react'
import { api } from '@/lib/api'
import { EmptyState, PageHeader, PageLoader } from '@/components/ui'
import { InviteModal, type InviteTarget } from '@/components/InviteModal'
import { CandidateRow, useShortlistToggle } from './Selection'

export function Shortlist() {
  const { data, isLoading } = useQuery({ queryKey: ['shortlist'], queryFn: () => api<any[]>('/employer/shortlist') })
  const toggle = useShortlistToggle()
  const [invite, setInvite] = useState<InviteTarget | null>(null)
  if (isLoading || !data) return <PageLoader />
  return (
    <div>
      <PageHeader title="Избранное" subtitle="Кандидаты, которых вы отметили в подборках и банке — чтобы вернуться к ним позже." />
      {!data.length ? <EmptyState icon={<Star className="h-5 w-5" />} title="Пока пусто" text="Нажмите ☆ в карточке кандидата, чтобы сохранить его сюда." /> : (
        <div className="space-y-3">
          {data.map(it => (
            <CandidateRow key={it.id} c={{ ...it.candidate, shortlisted: true }} onShortlist={on => toggle.mutate({ id: it.candidate.id, on })}
              onInvite={() => setInvite({ id: it.candidate.id, display_name: it.candidate.display_name, grade_name: it.candidate.grade_name, specialization_name: it.candidate.specialization_name })} />
          ))}
        </div>
      )}
      <InviteModal target={invite} onClose={() => setInvite(null)} />
    </div>
  )
}
