import { ButtonLink } from '@/components/ui'

export function NotFound() {
  return (
    <div className="bg-hero grid min-h-screen place-items-center px-4 text-center text-white">
      <div>
        <img src="/brand/fsp-star-white.png" alt="" className="mx-auto h-16 w-16 opacity-80" />
        <p className="mt-6 text-6xl font-extrabold">404</p>
        <p className="mt-2 text-white/70">Такой страницы нет — возможно, она переехала.</p>
        <ButtonLink to="/" className="mt-6">На главную</ButtonLink>
      </div>
    </div>
  )
}
