import { useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip,
  XAxis, YAxis, ZAxis,
} from 'recharts'
import clsx from 'clsx'
import { motion } from 'framer-motion'
import { Blobs, EASE, Reveal } from '@/lib/motion'
import { Fingerprint, Gauge, Repeat, Scale, ShieldCheck, Sigma, Target, Timer } from 'lucide-react'
import { api } from '@/lib/api'
import { PageLoader, Select } from '@/components/ui'
import { PublicHeader } from './Landing'

// Категориальная палитра графиков (бренд ФСП), проверена validate_palette.js: CVD ΔE ≥ 13, 4-й слот — с табличной подписью
const C = { s1: '#FF0053', s2: '#8A83D1', s3: '#8E24AA', s4: '#E8A33D', grid: '#EEEAF5', axis: '#94a3b8' }
const tooltipStyle = { borderRadius: 12, border: 'none', boxShadow: '0 10px 30px -10px rgba(49,15,83,.3)', fontSize: 12 }
const pct = (x?: number | null, d = 0) => (x == null ? '—' : `${(x * 100).toFixed(d)}%`)

function Section({ id, kicker, title, lead, children }: { id: string; kicker: string; title: string; lead?: ReactNode; children: ReactNode }) {
  return (
    <section id={id} className="scroll-mt-32 border-t border-line py-16">
      <Reveal>
        <p className="eyebrow">{kicker}</p>
        <h2 className="mt-2 text-3xl font-extrabold tracking-tight">{title}</h2>
        {lead && <p className="mt-3 max-w-3xl leading-relaxed text-slate-500">{lead}</p>}
      </Reveal>
      <Reveal delay={0.08} className="mt-8">{children}</Reveal>
    </section>
  )
}

function Kpi({ label, value, hint, accent }: { label: string; value: ReactNode; hint?: ReactNode; accent?: boolean }) {
  return (
    <div className={clsx('rounded-2xl p-5', accent ? 'bg-brand-gradient text-white' : 'bg-surface')}>
      <p className={clsx('text-xs font-semibold uppercase tracking-wide', accent ? 'text-white/70' : 'text-slate-500')}>{label}</p>
      <p className={clsx('mt-1 text-3xl font-extrabold', accent ? 'text-white' : 'text-fsp-deep')}>{value}</p>
      {hint && <p className={clsx('mt-1 text-xs', accent ? 'text-white/70' : 'text-slate-500')}>{hint}</p>}
    </div>
  )
}

function ChartCard({ title, note, children, table }: { title: string; note?: ReactNode; children: ReactNode; table?: ReactNode }) {
  const [asTable, setAsTable] = useState(false)
  return (
    <div className="card p-5">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div><p className="font-bold text-fsp-deep">{title}</p>{note && <p className="mt-0.5 text-xs text-slate-500">{note}</p>}</div>
        {table && <button onClick={() => setAsTable(v => !v)} className="shrink-0 rounded-lg px-2 py-1 text-xs font-semibold text-fsp-lavender hover:bg-surface">{asTable ? 'График' : 'Таблица'}</button>}
      </div>
      {asTable && table ? table : children}
    </div>
  )
}

function Table({ head, rows }: { head: ReactNode[]; rows: ReactNode[][] }) {
  return (
    <div className="scrollbar-thin overflow-x-auto">
      <table className="w-full min-w-[480px] text-sm">
        <thead><tr className="text-left text-xs uppercase tracking-wide text-slate-400">{head.map((h, i) => <th key={i} className="pb-2 pr-3 font-semibold">{h}</th>)}</tr></thead>
        <tbody className="divide-y divide-slate-100">{rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j} className="py-2 pr-3">{c}</td>)}</tr>)}</tbody>
      </table>
    </div>
  )
}

const SPEC_NAMES: Record<string, string> = { backend: 'Backend', frontend: 'Frontend', fullstack: 'Fullstack', ml: 'Data Science / ML',
  data_analyst: 'Аналитик данных', devops: 'DevOps / SRE', qa: 'QA' }
const METHOD: Record<string, string> = { keyword: 'Поиск по ключевым словам', filters: 'Фильтры по самоописанию', ours: 'ФСП Карьера',
  ours_nlp: 'ФСП Карьера (потребность текстом)', ours_self_declared_category: 'Абляция: категория из самоописания',
  ours_no_fsp: 'Абляция: без ФСП', ours_no_verification: 'Абляция: без проверки навыков' }

export function Methodology() {
  const { data, isLoading } = useQuery({ queryKey: ['methodology'], queryFn: () => api('/public/methodology') })
  const [spec, setSpec] = useState('backend')
  if (isLoading || !data) return <div className="min-h-screen bg-white"><PublicHeader solid /><section className="bg-hero h-72" /><div className="mx-auto max-w-6xl px-4 py-10"><PageLoader /></div></div>
  const cat = data.cat_validation
  const mv = data.matching_validation
  const nlp = data.nlp_validation
  const bank = data.bank
  const bankRows = Object.entries(bank.domains as Record<string, any>).map(([k, v]) => ({ name: v.name, key: k, parametric: v.parametric, static: v.families - v.parametric }))
    .sort((a, b) => (b.parametric + b.static) - (a.parametric + a.static))
  const leakRows = cat ? ['0', '5', '25', '100'].map(k => ({
    k: k === '0' ? 'честно' : `K=${k}`, fixed: cat.leak_attack.inflation_rate.fixed_form[k], static: cat.leak_attack.inflation_rate.static_bank[k],
    ours: cat.leak_attack.inflation_rate.ours[k], undetected: cat.leak_attack.undetected_inflation_rate.ours[k],
  })) : []
  const driftRows = cat ? Object.entries(cat.drift_detection.checkpoints as Record<string, any>).map(([n, v]) => ({ n: Number(n), tpr: v['3.0'].tpr, fpr: v['3.0'].fpr })) : []
  const infoRows = cat ? cat.information.theta.map((t: number, i: number) => ({ theta: t, info: cat.information.info[spec][i], se: +(1 / Math.sqrt(cat.information.info[spec][i])).toFixed(3) })) : []
  const methods = mv ? ['keyword', 'filters', 'ours_self_declared_category', 'ours_no_fsp', 'ours_no_verification', 'ours_nlp', 'ours'] : []

  return (
    <div className="min-h-screen bg-white">
      <PublicHeader />
      <section className="bg-hero noise relative overflow-hidden pb-20 pt-32">
        <Blobs className="opacity-50" />
        <div className="relative mx-auto max-w-6xl px-4 text-white sm:px-6">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-fsp-blush">Методика и валидация</p>
          <motion.h1 initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, ease: EASE }}
            className="mt-3 max-w-3xl text-4xl font-extrabold leading-tight tracking-tightest text-white sm:text-[52px]">Как мы проверяем, что тесту и выдаче <span className="text-gradient">можно доверять</span></motion.h1>
          <p className="mt-4 max-w-3xl text-white/75">Эталонной разметки на хакатоне нет, поэтому мы построили собственную процедуру: синтетическую популяцию
            с известной «истиной» (истинный уровень, реальные навыки, честное или завышенное резюме) и прогоняем через неё и тестирование, и подбор,
            и атаки на утечку заданий. Все эксперименты воспроизводимы командой <code className="rounded bg-white/10 px-1.5 py-0.5 text-white">python -m validation.run_all</code>.</p>
          {cat && mv && (
            <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Kpi accent label="Грейд по тесту верен" value={pct(cat.grades.grade_exact_accuracy)} hint={`самооценка в резюме — ${pct(cat.grades.self_declared_exact_accuracy)}`} />
              <Kpi accent label="Завышение грейда" value={pct(cat.grades.overgrading_rate_test, 1)} hint={`в самоописании — ${pct(cat.grades.overgrading_rate_self_declared)}`} />
              <Kpi accent label="P@10 подбора" value={mv.summary.ours.p10.toFixed(2)} hint={`фильтры — ${mv.summary.filters.p10.toFixed(2)}, ключевые слова — ${mv.summary.keyword.p10.toFixed(2)}`} />
              <Kpi accent label="Утечка: незаметное завышение" value={pct(cat.leak_attack.undetected_inflation_rate.ours['25'])} hint={`фиксированный тест — ${pct(cat.leak_attack.inflation_rate.fixed_form['25'])}`} />
            </div>
          )}
        </div>
      </section>

      <nav className="sticky top-16 z-30 border-b border-line bg-white/85 backdrop-blur-xl">
        <div className="scrollbar-thin mx-auto flex max-w-6xl gap-1 overflow-x-auto px-4 py-2 text-sm font-semibold sm:px-6">
          {[['mechanics', 'Механика теста'], ['bank', 'Банк заданий'], ['cat', 'Точность и стабильность'], ['leaks', 'Устойчивость к утечкам'],
            ['matching', 'Подбор'], ['nlp', 'NLP'], ['limits', 'Ограничения']].map(([id, l]) => (
            <a key={id} href={`#${id}`} className="shrink-0 rounded-lg px-3 py-1.5 text-slate-600 hover:bg-surface hover:text-fsp-deep">{l}</a>))}
        </div>
      </nav>

      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <Section id="mechanics" kicker="01 · Механика" title="Адаптивный тест на модели IRT + уникальные варианты"
          lead="Единый набор заданий быстро утекает, а генерация уникальных заданий нейросетью не гарантирует равной сложности. Мы разделяем «трудность» и «конкретику»: трудность принадлежит семейству заданий и калибруется, конкретика (числа, данные, код, ответ) генерируется для каждого кандидата.">
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {[
              { icon: <Fingerprint />, t: 'Семейства заданий', d: 'Шаблон с известной трудностью. Вариант порождается seed’ом сессии: свои таблицы для SQL-запроса, свой массив, свой код на языке кандидата. Ответ вычисляется генератором — SQL-задачи реально выполняются в SQLite.' },
              { icon: <Sigma />, t: 'Модель 3PL', d: 'P(верно | θ) = c + (1 − c) / (1 + e^(−a(θ − b))). a — дискриминативность, b — трудность, c — угадывание. Уровень θ оценивается байесовски (EAP) с одинаковым prior для всех — результаты разных наборов заданий сопоставимы.' },
              { icon: <Repeat />, t: 'Адаптивный выбор', d: 'Следующее задание — домен с наибольшим отставанием от блюпринта специализации и максимум информации Фишера при текущей θ̂, случайно среди 4 лучших (контроль экспозиции).' },
              { icon: <Timer />, t: 'Остановка и решение', d: `${cat?.config.min_items ?? 12}–${cat?.config.max_items ?? 24} заданий; стоп при SE ≤ ${cat?.config.se_stop ?? 0.28} или уверенном решении по обеим границам грейда. Грейд подтверждён, если P(θ ≥ нижней границы) ≥ 0.6.` },
              { icon: <ShieldCheck />, t: 'Три детектора нечестности', d: 'Ответ «чужого варианта» (списанный ответ не подходит к своему варианту); дрейф решаемости задания относительно модели (утечка статичных заданий); person-fit lz и слишком быстрые верные ответы на трудные задания.' },
              { icon: <Scale />, t: 'Правила смены грейда', d: 'Грейд не понижается принудительно. Не прошли — грейд ниже можно принять по тому же тесту (если тест уверенно его показал) или пройти тест уровнем ниже; уверенно прошли — тест уровнем выше доступен без ожидания, когда кандидат готов. Смена грейда и повтор уровня — не чаще раза в месяц, при пересдаче — другие задания.' },
            ].map(c => (
              <div key={c.t} className="rounded-2xl bg-surface p-5">
                <div className="grid h-10 w-10 place-items-center rounded-xl bg-fsp-deep text-white [&>svg]:h-5 [&>svg]:w-5">{c.icon}</div>
                <p className="mt-3 font-bold text-fsp-deep">{c.t}</p>
                <p className="mt-1.5 text-sm leading-relaxed text-slate-600">{c.d}</p>
              </div>
            ))}
          </div>
        </Section>

        <Section id="bank" kicker="02 · Банк заданий" title={`${bank.total_families} семейств, ${bank.parametric} параметрических`}
          lead="27 тестовых доменов покрывают 7 специализаций. Блюпринт специализации задаёт доли доменов; основной язык кандидата определяет язык кода в заданиях.">
          <ChartCard title="Состав банка по доменам" note="Число семейств; параметрические порождают уникальный вариант для каждого кандидата"
            table={<Table head={['Домен', 'Параметрических', 'Статичных']} rows={bankRows.map(r => [r.name, r.parametric, r.static])} />}>
            <div style={{ height: Math.max(420, bankRows.length * 22) }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={bankRows} layout="vertical" margin={{ left: 8, right: 16 }} barCategoryGap={4}>
                  <CartesianGrid horizontal={false} stroke={C.grid} />
                  <XAxis type="number" tick={{ fontSize: 11, fill: C.axis }} axisLine={false} tickLine={false} />
                  <YAxis type="category" dataKey="name" width={190} tick={{ fontSize: 11, fill: '#475569' }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={tooltipStyle} cursor={{ fill: '#F6F4FA' }} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="parametric" name="Параметрические" stackId="a" fill={C.s1} stroke="#fff" strokeWidth={2} />
                  <Bar dataKey="static" name="Статичные" stackId="a" fill={C.s2} stroke="#fff" strokeWidth={2} radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </ChartCard>
        </Section>

        {cat && (
          <Section id="cat" kicker="03 · Точность и стабильность" title="Тест даёт сопоставимый и воспроизводимый грейд"
            lead={`${cat.config.population} синтетических кандидатов, 35% завышают заявленный грейд. Ответы порождаются моделью из истинных доменных способностей (с разбросом между доменами), тест видит только ответы.`}>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Kpi label="Корреляция θ̂ и θ" value={cat.recovery.pearson_r.toFixed(2)} hint={`RMSE ${cat.recovery.rmse}, смещение ${cat.recovery.bias}`} />
              <Kpi label="Решение по грейду" value={pct(cat.recovery.decision.accuracy)} hint={`ложно подтверждено ${pct(cat.recovery.decision.false_confirm_rate)}, ложно отказано ${pct(cat.recovery.decision.false_reject_rate)}`} />
              <Kpi label="Повторный тест: тот же грейд" value={pct(cat.grades.retest.grade_agreement)} hint={`взвешенная κ ${cat.grades.retest.weighted_kappa}, r(θ̂₁,θ̂₂) ${cat.grades.retest.theta_test_retest_r}`} />
              <Kpi label="Длина теста" value={cat.recovery.test_length.mean.toFixed(1)} hint={`заданий; ≈ ${Math.round(cat.recovery.est_duration_min)} мин`} />
            </div>
            <div className="mt-6 grid gap-6 lg:grid-cols-2">
              <ChartCard title="Оценка уровня против истинного" note="Каждая точка — кандидат; диагональ — идеальная оценка">
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <ScatterChart margin={{ left: -10, right: 10, top: 10 }}>
                      <CartesianGrid stroke={C.grid} />
                      <XAxis type="number" dataKey="t" name="истинный θ" domain={[-3, 3]} tick={{ fontSize: 11, fill: C.axis }} label={{ value: 'истинный θ', position: 'insideBottom', offset: -2, fontSize: 11, fill: C.axis }} />
                      <YAxis type="number" dataKey="h" name="оценка θ̂" domain={[-3, 3]} tick={{ fontSize: 11, fill: C.axis }} />
                      <ZAxis range={[24, 24]} />
                      <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => v.toFixed(2)} />
                      <ReferenceLine segment={[{ x: -3, y: -3 }, { x: 3, y: 3 }]} stroke="#cbd5e1" strokeDasharray="4 4" />
                      <Scatter data={cat.recovery.scatter_sample.map(([t, h]: number[]) => ({ t, h }))} fill={C.s1} fillOpacity={0.45} />
                    </ScatterChart>
                  </ResponsiveContainer>
                </div>
              </ChartCard>
              <ChartCard title="Истинный грейд → присвоенный" note="Строки — истина, столбцы — результат политики аттестации (с пересдачей уровнем ниже/выше)">
                <Table head={['Истина \\ Присвоен', ...cat.grades.confusion_true_vs_assigned.cols]} rows={cat.grades.confusion_true_vs_assigned.matrix.map((row: number[], i: number) => {
                  const total = row.reduce((a, b) => a + b, 0)
                  return [<b key="r" className="text-fsp-deep">{cat.grades.confusion_true_vs_assigned.rows[i]}</b>, ...row.map((v, j) => (
                    <span key={j} className="inline-block min-w-[44px] rounded-md px-1.5 py-0.5 text-center" style={{ background: `rgba(255,0,83,${(v / total) * 0.85})`, color: v / total > 0.45 ? '#fff' : '#1C1D22' }}>{v}</span>))]
                })} />
                <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
                  <div className="rounded-xl bg-surface p-3"><p className="text-xs text-slate-500">Точно / ±1 ступень</p><p className="font-bold text-fsp-deep">{pct(cat.grades.grade_exact_accuracy)} / {pct(cat.grades.grade_within_one)}</p></div>
                  <div className="rounded-xl bg-surface p-3"><p className="text-xs text-slate-500">Без категории</p><p className="font-bold text-fsp-deep">{pct(cat.grades.no_category_rate, 1)}</p></div>
                </div>
              </ChartCard>
            </div>
            <div className="mt-6 grid gap-6 lg:grid-cols-[1.3fr_1fr]">
              <ChartCard title="Информационная функция теста" note="Сколько информации даёт банк на каждом уровне θ при составе по блюпринту (20 заданий); SE ≈ 1/√I"
                table={<Table head={['θ', 'Информация', 'SE']} rows={infoRows.filter((_: any, i: number) => i % 3 === 0).map((r: any) => [r.theta, r.info, r.se])} />}>
                <div className="mb-2 max-w-[240px]"><Select value={spec} onChange={e => setSpec(e.target.value)}>
                  {Object.keys(cat.information.info).map(s => <option key={s} value={s}>{SPEC_NAMES[s] ?? s}</option>)}</Select></div>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={infoRows} margin={{ left: -10, right: 10, top: 10 }}>
                      <CartesianGrid stroke={C.grid} vertical={false} />
                      <XAxis dataKey="theta" type="number" domain={[-3, 3]} tick={{ fontSize: 11, fill: C.axis }} />
                      <YAxis tick={{ fontSize: 11, fill: C.axis }} />
                      <Tooltip contentStyle={tooltipStyle} />
                      {(cat.config.theta_cuts as number[]).map(c => <ReferenceLine key={c} x={c} stroke="#cbd5e1" strokeDasharray="3 3" />)}
                      <Line type="monotone" dataKey="info" name="Информация" stroke={C.s1} strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
                <p className="mt-1 text-xs text-slate-500">Пунктир — границы грейдов (Стажёр | Junior | Middle | Senior): тест точнее всего там, где принимается решение.</p>
              </ChartCard>
              <div className="space-y-4">
                <div className="card p-5">
                  <p className="font-bold text-fsp-deep">Дискриминативность заданий</p>
                  <p className="mt-1 text-sm text-slate-600">Калибровочное исследование: каждое семейство решают 300 кандидатов без адаптивности. Индекс D — разница доли верных у верхних и нижних 27%.</p>
                  <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
                    <div className="rounded-xl bg-surface p-3"><p className="text-xs text-slate-500">Медиана D</p><p className="text-xl font-bold text-fsp-deep">{cat.discrimination.median_D}</p></div>
                    <div className="rounded-xl bg-surface p-3"><p className="text-xs text-slate-500">Заданий с D ≥ 0.3</p><p className="text-xl font-bold text-fsp-deep">{pct(cat.discrimination.share_D_ge_0_3)}</p></div>
                    <div className="rounded-xl bg-surface p-3"><p className="text-xs text-slate-500">Параметрические / статичные</p><p className="text-xl font-bold text-fsp-deep">{cat.discrimination.median_D_parametric} / {cat.discrimination.median_D_static}</p></div>
                    <div className="rounded-xl bg-surface p-3"><p className="text-xs text-slate-500">Медиана r_pb</p><p className="text-xl font-bold text-fsp-deep">{cat.discrimination.median_rpb}</p></div>
                  </div>
                </div>
                <div className="card p-5">
                  <p className="font-bold text-fsp-deep">Устойчивость к ошибкам калибровки</p>
                  <p className="mt-1 text-sm text-slate-600">Истинные параметры заданий отличаются от экспертных (b ± 0.4). Точность грейда: {pct(cat.misspecification.grade_accuracy.prior_params)} против {pct(cat.misspecification.grade_accuracy.oracle_true_params)} у «оракула» с истинными параметрами. Онлайн-калибровка по рабочим сессиям снижает ошибку трудности {cat.misspecification.b_rmse_prior} → {cat.misspecification.b_rmse_after_calibration}.</p>
                </div>
                <div className="card p-5">
                  <p className="font-bold text-fsp-deep">Сопоставимость между языками</p>
                  <p className="mt-1 text-sm text-slate-600">Смещение оценки для Backend по языку кода: {Object.entries(cat.recovery.bias_by_language_backend as Record<string, any>).map(([k, v]) => `${k} ${v.bias > 0 ? '+' : ''}${v.bias}`).join(', ')} — систематического сдвига нет.</p>
                </div>
              </div>
            </div>
          </Section>
        )}

        {cat && (
          <Section id="leaks" kicker="04 · Утечки" title="Слитые ответы почти не помогают — и выдают себя"
            lead={cat.leak_attack.attack_model}>
            <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
              <ChartCard title="Доля нечестных кандидатов, получивших завышенный грейд" note="K — сколько предыдущих кандидатов «слили» свои задания"
                table={<Table head={['', 'Фиксированный тест', 'Адаптивный без вариантов', 'ФСП Карьера', 'ФСП Карьера: незаметно']}
                  rows={leakRows.map(r => [r.k, pct(r.fixed), pct(r.static), pct(r.ours), pct(r.undetected)])} />}>
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={leakRows} margin={{ left: -10, right: 10, top: 10 }} barGap={2} barCategoryGap="22%">
                      <CartesianGrid stroke={C.grid} vertical={false} />
                      <XAxis dataKey="k" tick={{ fontSize: 12, fill: '#475569' }} axisLine={false} tickLine={false} />
                      <YAxis tickFormatter={v => `${Math.round(v * 100)}%`} tick={{ fontSize: 11, fill: C.axis }} axisLine={false} tickLine={false} domain={[0, 1]} />
                      <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => pct(v)} cursor={{ fill: '#F6F4FA' }} />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                      <Bar dataKey="fixed" name="Фиксированный тест" fill={C.s4} radius={[4, 4, 0, 0]} />
                      <Bar dataKey="static" name="Адаптивный без вариантов" fill={C.s2} radius={[4, 4, 0, 0]} />
                      <Bar dataKey="ours" name="ФСП Карьера" fill={C.s3} radius={[4, 4, 0, 0]} />
                      <Bar dataKey="undetected" name="ФСП Карьера: незаметно" fill={C.s1} radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </ChartCard>
              <div className="space-y-4">
                <div className="card p-5">
                  <p className="font-bold text-fsp-deep">Детектор «чужого варианта»</p>
                  <p className="mt-1 text-sm text-slate-600">Списанный ответ не подходит к своему варианту — и совпадает с ключом чужого. Помечено нечестных сессий: <b className="text-fsp-deep">{pct(cat.leak_attack.detection_rate.ours['25'])}</b> (K=25); ложные пометки у честных: <b className="text-fsp-deep">{pct(cat.leak_attack.honest_flag_rate.ours, 1)}</b>. Помеченный результат не меняет грейд до перепроверки.</p>
                </div>
                <div className="card p-5">
                  <p className="font-bold text-fsp-deep">Пересечение заданий</p>
                  <p className="mt-1 text-sm text-slate-600">У двух кандидатов одного уровня и специализации в идентичной форме совпадает лишь <b className="text-fsp-deep">{pct(cat.overlap.mean_identical_question_overlap)}</b> вопросов (семейств — {pct(cat.overlap.mean_family_overlap)}). Используется {pct(cat.exposure.used_share)} банка, максимальная доля показов одного семейства — {pct(cat.exposure.max_exposure_rate)}.</p>
                </div>
              </div>
            </div>
            <div className="mt-6">
              <ChartCard title="Автоматическое обнаружение утечки статичных заданий" note={`${cat.drift_detection.specialization}: утекли ${cat.drift_detection.leaked_static_families} самых популярных статичных семейств, их знают ${pct(cat.drift_detection.cheater_share)} кандидатов. Порог z > 3.`}
                table={<Table head={['Прохождений', 'Найдено утекших (TPR)', 'Ложные срабатывания (FPR)']} rows={driftRows.map(r => [r.n, pct(r.tpr), pct(r.fpr, 1)])} />}>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={driftRows} margin={{ left: -10, right: 16, top: 10 }}>
                      <CartesianGrid stroke={C.grid} vertical={false} />
                      <XAxis dataKey="n" tick={{ fontSize: 11, fill: C.axis }} label={{ value: 'прохождений теста', position: 'insideBottomRight', offset: -2, fontSize: 11, fill: C.axis }} />
                      <YAxis tickFormatter={v => `${Math.round(v * 100)}%`} domain={[0, 1]} tick={{ fontSize: 11, fill: C.axis }} />
                      <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => pct(v, 1)} />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                      <Line dataKey="tpr" name="Найдено утекших" stroke={C.s1} strokeWidth={2} dot={{ r: 4 }} />
                      <Line dataKey="fpr" name="Ложные срабатывания" stroke={C.s2} strokeWidth={2} dot={{ r: 4 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </ChartCard>
            </div>
          </Section>
        )}

        {mv && (
          <Section id="matching" kicker="05 · Подбор" title="Доля релевантных кандидатов в топе выдачи"
            lead={`${mv.setup.candidates} кандидатов (35% завышают резюме), ${mv.setup.needs} потребностей. Релевантность пары (0–3) задаётся латентной истиной — ${mv.setup.relevance}. Системы видят только наблюдаемые данные.`}>
            <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
              <ChartCard title="P@10 — доля релевантных в первой десятке" note="Среднее по потребностям; планка — 95% доверительный интервал"
                table={<Table head={['Система', 'P@10', 'nDCG@10', 'MRR', 'Нерелевантных', '«Завысивших»']} rows={methods.map(m => [METHOD[m], mv.summary[m].p10, mv.summary[m].ndcg10, mv.summary[m].mrr, pct(mv.summary[m].irrelevant_in_top10), pct(mv.summary[m].inflated_in_top10)])} />}>
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={methods.map(m => ({ name: METHOD[m], p10: mv.summary[m].p10, ours: m === 'ours' }))} layout="vertical" margin={{ left: 8, right: 24 }}>
                      <CartesianGrid horizontal={false} stroke={C.grid} />
                      <XAxis type="number" domain={[0, 1]} tick={{ fontSize: 11, fill: C.axis }} axisLine={false} tickLine={false} />
                      <YAxis type="category" dataKey="name" width={230} tick={{ fontSize: 11, fill: '#475569' }} axisLine={false} tickLine={false} />
                      <Tooltip contentStyle={tooltipStyle} cursor={{ fill: '#F6F4FA' }} />
                      <Bar dataKey="p10" name="P@10" radius={[0, 4, 4, 0]} label={{ position: 'right', fontSize: 11, fill: '#334155' }}
                        shape={(props: any) => <rect x={props.x} y={props.y + 2} width={props.width} height={Math.max(0, props.height - 4)} rx={4} fill={props.payload.ours ? C.s1 : C.s2} />} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </ChartCard>
              <div className="space-y-4">
                <Kpi label="ФСП Карьера: P@10 / nDCG@10 / MRR" value={`${mv.summary.ours.p10.toFixed(2)} / ${mv.summary.ours.ndcg10.toFixed(2)} / ${mv.summary.ours.mrr.toFixed(2)}`} hint={`фильтры по самоописанию: ${mv.summary.filters.p10.toFixed(2)} / ${mv.summary.filters.ndcg10.toFixed(2)} / ${mv.summary.filters.mrr.toFixed(2)}`} />
                <Kpi label="«Завысившие» кандидаты в топ-10" value={pct(mv.summary.ours.inflated_in_top10, 1)} hint={`фильтры по самоописанию — ${pct(mv.summary.filters.inflated_in_top10, 1)}: категория по тесту отсекает тех, кто приписал себе грейд`} />
                <Kpi label="С учётом уровня владения навыками" value={`${mv.summary_with_proficiency.ours.p10.toFixed(2)}`} hint={`P@10; фильтры — ${mv.summary_with_proficiency.filters.p10.toFixed(2)}, ключевые слова — ${mv.summary_with_proficiency.keyword.p10.toFixed(2)}`} />
                <div className="rounded-2xl bg-surface p-4 text-sm text-slate-600">
                  Сквозной сценарий «потребность текстом → NLP → подбор» даёт {mv.summary.ours_nlp.p10.toFixed(2)} P@10. Ранжирование пула до {mv.setup.candidates} кандидатов — {Math.round(mv.latency_ms.mean)} мс.
                  Вклад ФСП и проверки навыков в P@10 на этом наборе — в пределах погрешности; основной выигрыш даёт категоризация по тесту
                  (+{((mv.summary.ours.p10 - mv.summary.ours_self_declared_category.p10) * 100).toFixed(0)} п.п. к категории из самоописания).
                </div>
              </div>
            </div>
            {mv.example && (
              <div className="mt-6">
                <ChartCard title="Пример: топ-5 по одной потребности" note={`${SPEC_NAMES[mv.example.need.specialization]}, грейды ${mv.example.need.grades.join('/')}; метка релевантности 0–3, ⚠ — кандидат завысил грейд в резюме`}>
                  <div className="grid gap-4 md:grid-cols-3">
                    {(['keyword', 'filters', 'ours'] as const).map(m => (
                      <div key={m} className={clsx('rounded-2xl p-4', m === 'ours' ? 'bg-fsp-blush/40 ring-1 ring-fsp-pink/30' : 'bg-surface')}>
                        <p className="mb-2 text-sm font-bold text-fsp-deep">{METHOD[m]}</p>
                        <ol className="space-y-1.5 text-sm">
                          {mv.example.top5[m].map((c: any, i: number) => (
                            <li key={i} className="flex items-center justify-between gap-2">
                              <span>{i + 1}. {SPEC_NAMES[c.spec]}, истинно {c.true_grade}{c.inflated && <span title="Завысил грейд в резюме" className="ml-1">⚠</span>}</span>
                              <span className={clsx('rounded-md px-1.5 text-xs font-bold', c.label >= 2 ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700')}>{c.label}</span>
                            </li>))}
                        </ol>
                      </div>
                    ))}
                  </div>
                </ChartCard>
              </div>
            )}
          </Section>
        )}

        {nlp && (
          <Section id="nlp" kicker="06 · NLP" title="Разбор вакансий и резюме"
            lead="Вакансия → специализация (TF-IDF + логистическая регрессия в гибриде с правилами по онтологии навыков), грейды, обязательные и желательные навыки, вилка, формат, город. Резюме (PDF) → ФИО (NER-модель Natasha), контакты, стаж, навыки, роли.">
            <div className="grid gap-6 lg:grid-cols-2">
              <div className="card p-5">
                <p className="font-bold text-fsp-deep">Вакансии · {nlp.vacancies.n} размеченных текстов разных стилей</p>
                <Table head={['Поле', 'Качество']} rows={[
                  ['Специализация (гибрид / только модель / только правила)', `${pct(nlp.vacancies.specialization_accuracy.hybrid)} / ${pct(nlp.vacancies.specialization_accuracy.model_only)} / ${pct(nlp.vacancies.specialization_accuracy.rules_only)}`],
                  ['Грейды (точное совпадение)', pct(nlp.vacancies.grades_exact)],
                  ['Навыки: precision / recall / F1', `${nlp.vacancies.skills.precision} / ${nlp.vacancies.skills.recall} / ${nlp.vacancies.skills.f1}`],
                  ['«Будет плюсом» распознано', pct(nlp.vacancies.nice_to_have_detected)],
                  ['Вилка зарплаты', pct(nlp.vacancies.salary_exact)], ['Формат работы', pct(nlp.vacancies.work_format)], ['Город', pct(nlp.vacancies.city)],
                ]} />
              </div>
              <div className="card p-5">
                <p className="font-bold text-fsp-deep">Резюме · {nlp.resumes.n} PDF ({nlp.resumes.pipeline})</p>
                <Table head={['Поле', 'Точность']} rows={[
                  ['ФИО', pct(nlp.resumes.field_accuracy.name)], ['E-mail / телефон / Telegram', `${pct(nlp.resumes.field_accuracy.email)} / ${pct(nlp.resumes.field_accuracy.phone)} / ${pct(nlp.resumes.field_accuracy.telegram)}`],
                  ['Город', pct(nlp.resumes.field_accuracy.city)], ['Стаж ± 0,5 года', `${pct(nlp.resumes.field_accuracy.years_within_0_5)} (MAE ${nlp.resumes.experience_mae_years} г.)`],
                  ['Навыки, F1', nlp.resumes.skills_f1],
                ]} />
              </div>
            </div>
          </Section>
        )}

        <Section id="limits" kicker="07 · Честно об ограничениях" title="Что подтверждено, а что — следующий шаг">
          <div className="grid gap-4 md:grid-cols-3">
            {[
              { icon: <Target />, t: 'Синтетическая истина', d: 'Проверены свойства процедур при известной истине. Следующий шаг — пилот: 50–100 участников ФСП с экспертной оценкой уровня, сравнение с грейдом теста (κ, точность по грейдам).' },
              { icon: <Gauge />, t: 'Калибровка на реальных ответах', d: 'Стартовые параметры заданий экспертные. Механизм пилотных заданий и онлайн-калибровки трудности реализован (/admin/items/calibrate) — после ~40 ответов задание переводится в рабочий банк.' },
              { icon: <ShieldCheck />, t: 'Прокторинг по запросу', d: 'Помеченные детекторами сессии направляются на повторный тест под наблюдением. Интеграция с прокторингом и ФСП-площадками — в плане развития.' },
            ].map(c => (
              <div key={c.t} className="rounded-2xl bg-surface p-5">
                <div className="grid h-10 w-10 place-items-center rounded-xl bg-fsp-blush text-fsp-pink [&>svg]:h-5 [&>svg]:w-5">{c.icon}</div>
                <p className="mt-3 font-bold text-fsp-deep">{c.t}</p>
                <p className="mt-1.5 text-sm leading-relaxed text-slate-600">{c.d}</p>
              </div>
            ))}
          </div>
        </Section>
      </div>
      <footer className="bg-fsp-deep">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-6 px-4 py-10 text-sm text-white/60 sm:px-6">
          <img src="/brand/fsp-logo-white.png" alt="ФСП" className="h-9 w-auto" />
          <span>Отчёты: backend/validation/reports · сгенерировано {cat?.generated_at ?? '—'}</span>
        </div>
      </footer>
    </div>
  )
}
