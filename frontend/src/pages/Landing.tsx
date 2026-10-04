import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowRight, BadgeCheck, Building2, ChartBar, CircleCheck, Eye, Fingerprint, Lock, Mail, Repeat, Search, ShieldCheck,
  Sparkles, Trophy, UserRound, Wallet,
} from 'lucide-react'
import { api } from '@/lib/api'
import { homeFor, useAuth } from '@/lib/auth'
import { ButtonLink } from '@/components/ui'
import { Logo } from '@/components/Layout'

export function PublicHeader() {
  const { user } = useAuth()
  return (
    <header className="relative z-10 mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-5 sm:px-6">
      <Logo dark />
      <nav className="flex items-center gap-2 sm:gap-3">
        <Link to="/methodology" className="hidden rounded-xl px-3 py-2 text-sm font-semibold text-white/80 hover:text-white sm:block">Методика</Link>
        {user ? (
          <ButtonLink to={homeFor(user.role)} size="sm">Личный кабинет</ButtonLink>
        ) : (<>
          <Link to="/login" className="rounded-xl px-3 py-2 text-sm font-semibold text-white/80 hover:text-white">Войти</Link>
          <ButtonLink to="/register" size="sm">Регистрация</ButtonLink>
        </>)}
      </nav>
    </header>
  )
}

function HeroVisual() {
  return (
    <div className="relative mx-auto w-full max-w-md lg:mx-0">
      <div className="absolute -inset-6 rounded-[2.5rem] bg-fsp-pink/20 blur-3xl" />
      <div className="relative space-y-3">
        <div className="rounded-3xl bg-white p-5 shadow-pop">
          <div className="flex items-center justify-between">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-fsp-deep px-3 py-1 text-xs font-semibold text-white">
              <ShieldCheck className="h-3.5 w-3.5 text-fsp-blush" /> Backend · Middle
            </span>
            <span className="text-xs font-semibold text-emerald-600">выше 78% рынка</span>
          </div>
          <p className="mt-3 text-sm font-semibold text-fsp-deep">Кандидат C-7F3A2B</p>
          <div className="mt-3 space-y-2">
            {[['SQL', 86], ['Python', 81], ['HTTP и API', 72], ['Архитектура', 64]].map(([d, v]) => (
              <div key={d as string}>
                <div className="flex justify-between text-xs"><span>{d}</span><b className="text-fsp-deep">{v}%</b></div>
                <div className="mt-1 h-1.5 rounded-full bg-slate-100"><div className="h-full rounded-full bg-fsp-pink" style={{ width: `${v}%` }} /></div>
              </div>
            ))}
          </div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            <span className="chip bg-fsp-blush/70 text-[#9e0035]"><Trophy className="h-3 w-3" /> Призёр ФСП ×2</span>
            <span className="chip bg-[#ECEAFB] text-[#4b4392]">✓ PostgreSQL</span>
            <span className="chip bg-[#ECEAFB] text-[#4b4392]">✓ FastAPI</span>
          </div>
        </div>
        <div className="ml-10 rounded-3xl bg-white/95 p-4 shadow-pop">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-2xl bg-fsp-pink text-white"><Mail className="h-5 w-5" /></div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-fsp-deep">Приглашение от «ТехноПульс»</p>
              <p className="text-xs text-slate-500">Python-разработчик · гибрид, Казань</p>
            </div>
          </div>
          <div className="mt-3 flex items-center justify-between rounded-2xl bg-surface px-3 py-2">
            <span className="text-xs text-slate-500">Вилка</span>
            <span className="text-sm font-bold text-fsp-deep">250 000 – 320 000 ₽</span>
          </div>
        </div>
      </div>
    </div>
  )
}

export function Landing() {
  const { data: stats } = useQuery({ queryKey: ['public-stats'], queryFn: () => api('/public/stats') })
  const steps = {
    candidate: [
      { icon: <UserRound />, t: 'Профиль за 2 минуты', d: 'Загрузите PDF-резюме — поля распознаются автоматически. Или заполните форму.' },
      { icon: <ChartBar />, t: 'Опрос и адаптивный тест', d: 'Выберите специализацию и грейд. Тест подстраивается под ваш уровень, задания уникальны.' },
      { icon: <BadgeCheck />, t: 'Категория, а не резюме', d: 'Грейд подтверждается тестом. Достижения ФСП подтягиваются по ФСП ID и усиливают профиль.' },
      { icon: <Mail />, t: 'Предложения приходят сами', d: 'Работодатели приглашают вас с вилкой зарплаты. Контакты открываются только с вашего согласия.' },
    ],
    employer: [
      { icon: <Sparkles />, t: 'Опишите потребность', d: 'Вставьте текст вакансии: NLP определит специализацию, грейд, обязательные и желательные навыки.' },
      { icon: <Search />, t: 'Получите подборку', d: 'Рекомендованные категории с аналитикой рынка и ранжированные кандидаты с объяснением.' },
      { icon: <Wallet />, t: 'Пригласите конкретного человека', d: 'Предложение с обязательной вилкой. Видно вероятность отклика ещё до отправки.' },
      { icon: <CircleCheck />, t: 'Контакт после согласия', d: 'Кандидат принимает приглашение — открываются контакты. Отказы приходят с причиной.' },
    ],
  }
  return (
    <div className="min-h-screen bg-white">
      <section className="bg-hero relative overflow-hidden pb-20">
        <PublicHeader />
        <div className="mx-auto grid max-w-6xl items-center gap-14 px-4 pt-8 sm:px-6 lg:grid-cols-[1.1fr_.9fr] lg:pt-16">
          <div className="text-white">
            <span className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-semibold text-white/90 ring-1 ring-white/15">
              <img src="/brand/fsp-star-white.png" alt="" className="h-4 w-4" /> Платформа Федерации спортивного программирования
            </span>
            <h1 className="mt-5 text-4xl font-extrabold leading-[1.08] tracking-tight text-white sm:text-5xl lg:text-[56px]">
              Работодатель находит <span className="text-fsp-pink">вас сам</span>
            </h1>
            <p className="mt-5 max-w-xl text-base leading-relaxed text-white/80 sm:text-lg">
              Подбор ИТ-специалистов с обратной механикой. Категория кандидата определяется адаптивным тестом
              и подтверждёнными достижениями ФСП, а не ключевыми словами в резюме. Работодатель выбирает категорию
              и приходит к конкретному человеку с предложением и вилкой зарплаты.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <ButtonLink to="/register?role=candidate" size="lg" icon={<UserRound className="h-5 w-5" />}>Я кандидат</ButtonLink>
              <ButtonLink to="/register?role=employer" size="lg" variant="secondary" icon={<Building2 className="h-5 w-5" />}>Я работодатель</ButtonLink>
            </div>
            <div className="mt-10 grid max-w-xl grid-cols-2 gap-4 sm:grid-cols-4">
              {[
                [stats?.categorized ?? '—', 'кандидатов с категорией'],
                [stats?.with_fsp ?? '—', 'с привязанным ФСП ID'],
                [stats?.item_families ?? '—', 'семейств заданий'],
                [stats?.vacancies ?? '—', 'открытых вакансий'],
              ].map(([v, l]) => (
                <div key={l as string}><p className="text-2xl font-extrabold text-white">{v}</p><p className="text-xs leading-snug text-white/60">{l}</p></div>
              ))}
            </div>
          </div>
          <HeroVisual />
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
        <h2 className="text-3xl font-extrabold tracking-tight">Как это работает</h2>
        <p className="mt-2 max-w-2xl text-slate-500">Инициатива на стороне работодателя: кандидату не нужно рассылать отклики вслепую — достаточно один раз подтвердить уровень.</p>
        <div className="mt-10 grid gap-8 lg:grid-cols-2">
          {(['candidate', 'employer'] as const).map(side => (
            <div key={side} className="rounded-3xl bg-surface p-6 sm:p-8">
              <p className="text-sm font-bold uppercase tracking-wider text-fsp-pink">{side === 'candidate' ? 'Кандидату' : 'Работодателю'}</p>
              <ol className="mt-5 space-y-5">
                {steps[side].map((s, i) => (
                  <li key={i} className="flex gap-4">
                    <div className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-white text-fsp-pink shadow-card [&>svg]:h-5 [&>svg]:w-5">{s.icon}</div>
                    <div><p className="font-bold text-fsp-deep">{i + 1}. {s.t}</p><p className="mt-1 text-sm leading-relaxed text-slate-600">{s.d}</p></div>
                  </li>
                ))}
              </ol>
            </div>
          ))}
        </div>
      </section>

      <section className="bg-surface">
        <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h2 className="text-3xl font-extrabold tracking-tight">Почему результату теста можно доверять</h2>
              <p className="mt-2 max-w-2xl text-slate-500">Единый набор заданий быстро утекает, а генерация «на лету» не гарантирует равной сложности. Мы совмещаем лучшее из двух подходов.</p>
            </div>
            <ButtonLink to="/methodology" variant="secondary" icon={<ChartBar className="h-4 w-4" />}>Методика и валидация</ButtonLink>
          </div>
          <div className="mt-10 grid gap-5 md:grid-cols-3">
            {[
              { icon: <Fingerprint />, t: 'Уникальный вариант для каждого', d: 'Задание — это семейство с откалиброванной трудностью. Для каждого кандидата генерируются свои данные, код и ответ: «слитый» ответ бесполезен.' },
              { icon: <Repeat />, t: 'Адаптивность по модели IRT', d: 'Следующее задание выбирается под текущую оценку уровня. Результаты разных кандидатов лежат на одной шкале и сопоставимы.' },
              { icon: <Eye />, t: 'Мониторинг утечек', d: 'Если задание вдруг стало решаться лучше, чем предсказывает модель, оно автоматически выводится из ротации. Аномальные паттерны ответов помечаются.' },
            ].map(c => (
              <div key={c.t} className="card card-pad">
                <div className="grid h-11 w-11 place-items-center rounded-2xl bg-fsp-deep text-white [&>svg]:h-5 [&>svg]:w-5">{c.icon}</div>
                <p className="mt-4 font-bold text-fsp-deep">{c.t}</p>
                <p className="mt-2 text-sm leading-relaxed text-slate-600">{c.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
        <div className="grid gap-5 md:grid-cols-3">
          {[
            { icon: <Wallet />, t: 'Зарплата видна сразу', d: 'Вилка обязательна в вакансии и в каждом приглашении — кандидат знает условия до начала общения.' },
            { icon: <Lock />, t: 'Контакты — только с согласия', d: 'До принятия приглашения работодатель видит анонимный код и подтверждённые данные, но не контакты.' },
            { icon: <Trophy />, t: 'ФСП — бонус, а не барьер', d: 'Достижения в соревнованиях усиливают профиль. Кандидаты без истории ФСП участвуют в подборе наравне.' },
          ].map(c => (
            <div key={c.t} className="flex gap-4">
              <div className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-fsp-blush text-fsp-pink [&>svg]:h-5 [&>svg]:w-5">{c.icon}</div>
              <div><p className="font-bold text-fsp-deep">{c.t}</p><p className="mt-1 text-sm leading-relaxed text-slate-600">{c.d}</p></div>
            </div>
          ))}
        </div>
        <div className="bg-brand-gradient mt-16 flex flex-col items-start justify-between gap-6 rounded-[2rem] p-8 text-white sm:flex-row sm:items-center sm:p-10">
          <div>
            <p className="text-2xl font-extrabold">Готовы показать свой уровень?</p>
            <p className="mt-1 text-white/70">Регистрация, опрос и тест — около 30 минут. Дальше предложения приходят сами.</p>
          </div>
          <ButtonLink to="/register" size="lg" icon={<ArrowRight className="h-5 w-5" />}>Начать</ButtonLink>
        </div>
      </section>

      <footer className="bg-fsp-deep">
        <div className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-6 px-4 py-10 text-sm text-white/60 sm:flex-row sm:items-center sm:px-6">
          <img src="/brand/fsp-logo-white.png" alt="Федерация спортивного программирования России" className="h-9 w-auto" />
          <div className="flex flex-wrap gap-5">
            <Link to="/methodology" className="hover:text-white">Методика</Link>
            <a href="/docs" className="hover:text-white">API (Swagger)</a>
            <span>ЛЦТ 2026 · специальный трек ФСП</span>
          </div>
        </div>
      </footer>
    </div>
  )
}
