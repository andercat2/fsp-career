import { useQuery } from '@tanstack/react-query'
import { api } from './api'

export type Skill = { id: string; name: string; group: string; domains: string[]; specs: string[] }
export type Spec = {
  code: string; name: string; direction: string; description: string; languages: string[]; core_skills: string[]
  blueprints: Record<string, Record<string, number>>
}
export type Grade = { code: string; name: string; short: string; experience: string; description: string }
export type Reference = {
  specializations: Spec[]
  grades: Grade[]
  theta_cuts: number[]
  domains: Record<string, string>
  languages: Record<string, string>
  industries: string[]
  work_formats: Record<string, string>
  team_roles: Record<string, string>
  soft_skills: Record<string, string>
  decline_reasons: Record<string, string>
  fsp_disciplines: Record<string, string>
  fsp_levels: Record<string, string>
  skills: Skill[]
}

export function useReference() {
  const q = useQuery({ queryKey: ['reference'], queryFn: () => api<Reference>('/reference'), staleTime: Infinity })
  const ref = q.data
  return {
    ref,
    loading: q.isLoading,
    specName: (c?: string | null) => ref?.specializations.find(s => s.code === c)?.name ?? c ?? '—',
    gradeName: (c?: string | null) => ref?.grades.find(g => g.code === c)?.name ?? c ?? '—',
    skillName: (id: string) => ref?.skills.find(s => s.id === id)?.name ?? id,
    domainName: (d: string) => ref?.domains[d] ?? d,
  }
}
