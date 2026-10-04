import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { PageLoader } from '@/components/ui'
import { PublicHeader } from './Landing'

export function Methodology() {
  const { data, isLoading } = useQuery({ queryKey: ['methodology'], queryFn: () => api('/public/methodology') })
  return (
    <div className="min-h-screen bg-white">
      <section className="bg-hero pb-12"><PublicHeader /><div className="mx-auto max-w-6xl px-4 pt-6 text-white sm:px-6"><h1 className="text-4xl font-extrabold text-white">Методика и валидация</h1></div></section>
      <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">{isLoading ? <PageLoader /> : <pre className="text-xs">{JSON.stringify(data?.bank, null, 2)}</pre>}</div>
    </div>
  )
}
