"""Фронтенд-домены: JavaScript, TypeScript, React, HTML/CSS, браузер."""
from __future__ import annotations

import random

from app.services.testing.bank.core import Rendered, family, mcq, multi, options_from

# =============================== JavaScript ===============================
JS = "javascript"


def _simulate_event_loop(stmts: list[tuple]) -> list[str]:
    out: list[str] = []
    micro: list[tuple] = []
    macro: list[tuple] = []

    def run(st: tuple):
        kind = st[0]
        if kind == "sync":
            out.append(st[1])
        elif kind == "timeout":
            macro.append(st)
        elif kind == "micro":
            micro.append(st)

    def exec_cb(st: tuple):
        out.append(st[1])
        if len(st) > 2 and st[2]:
            run(st[2])

    for st in stmts:
        run(st)
    while micro or macro:
        while micro:
            exec_cb(micro.pop(0))
        if macro:
            exec_cb(macro.pop(0))
    return out


@family("js.event_loop", JS, 4, "input", "Event loop: микро- и макрозадачи", time_limit=180)
def js_event_loop(rng: random.Random, _l):
    labels = [str(i) for i in rng.sample(range(1, 10), 6)]
    stmts: list[tuple] = []
    kinds = ["sync", "sync", "timeout", "micro", rng.choice(["timeout_nested", "micro_nested"]), rng.choice(["sync", "micro"])]
    rng.shuffle(kinds)
    lines = []
    li = iter(labels)
    for k in kinds:
        lab = next(li)
        if k == "sync":
            stmts.append(("sync", lab))
            lines.append(f"console.log('{lab}');")
        elif k == "timeout":
            stmts.append(("timeout", lab))
            lines.append(f"setTimeout(() => console.log('{lab}'), 0);")
        elif k == "micro":
            stmts.append(("micro", lab))
            lines.append(f"Promise.resolve().then(() => console.log('{lab}'));")
        elif k == "timeout_nested":
            inner = str(rng.choice([x for x in range(10, 20)]))
            stmts.append(("timeout", lab, ("micro", inner)))
            lines.append(f"setTimeout(() => {{\n  console.log('{lab}');\n  Promise.resolve().then(() => console.log('{inner}'));\n}}, 0);")
        else:
            inner = str(rng.choice([x for x in range(10, 20)]))
            stmts.append(("micro", lab, ("timeout", inner)))
            lines.append(f"Promise.resolve().then(() => {{\n  console.log('{lab}');\n  setTimeout(() => console.log('{inner}'), 0);\n}});")
    out = _simulate_event_loop(stmts)
    return Rendered("В каком порядке будут выведены значения? Введите их через пробел.", "input", " ".join(out),
                    code="\n".join(lines), code_lang="javascript",
                    explanation="Сначала синхронный код, затем все микрозадачи, затем по одной макрозадаче с "
                                "опустошением очереди микрозадач после каждой.")


@family("js.async_await", JS, 3, "input", "async/await", time_limit=150)
def js_async_await(rng: random.Random, _l):
    a, b, c, d = (str(x) for x in rng.sample(range(1, 10), 4))
    return Rendered("В каком порядке будут выведены значения? Введите их через пробел.", "input", f"{c} {a} {d} {b}",
                    code=f"async function f() {{\n  console.log('{a}');\n  await null;\n  console.log('{b}');\n}}\n"
                         f"console.log('{c}');\nf();\nconsole.log('{d}');", code_lang="javascript")


_COERCION_STATIC = [
    ("[1, 2] + [3]", "1,23"), ("null + 1", "1"), ("undefined + 1", "NaN"), ("[] == false", "true"),
    ("null == 0", "false"), ("null >= 0", "true"), ("NaN === NaN", "false"), ('"b" + "a" + +"a" + "a"', "baNaNa"),
    ("0.1 + 0.2 === 0.3", "false"), ('typeof ("5" * 1)', "number"),
]


@family("js.coercion", JS, 2, "input", "Приведение типов", time_limit=90)
def js_coercion(rng: random.Random, _l):
    a, b, c = rng.randint(2, 9), rng.randint(2, 9), rng.randint(2, 9)
    dyn = [(f'"{a}" + {b}', f"{a}{b}"), (f'"{a}" - {b}', str(a - b)), (f"{a} + {b} + \"{c}\"", f"{a + b}{c}"),
           (f'"{a}" + {b} + {c}', f"{a}{b}{c}"), (f'"{a}" * "{b}"', str(a * b)), (f"true + {a}", str(a + 1))]
    expr, ans = rng.choice(dyn + rng.sample(_COERCION_STATIC, 3))
    return Rendered("Что выведет код?", "input", ans, code=f"console.log({expr});", code_lang="javascript", norm="exact")


@family("js.var_let", JS, 3, "input", "var/let и замыкания в цикле", time_limit=120)
def js_var_let(rng: random.Random, _l):
    n = rng.randint(3, 5)
    kw = rng.choice(["var", "let"])
    ans = " ".join([str(n)] * n) if kw == "var" else " ".join(map(str, range(n)))
    return Rendered("Что выведет код? Введите значения через пробел.", "input", ans,
                    code=f"for ({kw} i = 0; i < {n}; i++) {{\n  setTimeout(() => console.log(i), 0);\n}}",
                    code_lang="javascript")


@family("js.array_chain", JS, 2, "numeric", "Методы массивов", time_limit=120)
def js_array_chain(rng: random.Random, _l):
    xs = rng.sample(range(1, 15), 6)
    k, m, s = rng.randint(2, 4), rng.choice([2, 3, 4]), rng.randint(0, 10)
    ans = s + sum(x * k for x in xs if (x * k) % m == 0)
    return Rendered("Что выведет код?", "numeric", ans,
                    code=f"const r = {xs}\n  .map(x => x * {k})\n  .filter(x => x % {m} === 0)\n  .reduce((a, b) => a + b, {s});\n"
                         "console.log(r);", code_lang="javascript")


@family("js.sort_default", JS, 2, "input", "Сортировка по умолчанию", time_limit=90)
def js_sort_default(rng: random.Random, _l):
    xs = rng.sample([1, 2, 5, 9, 10, 15, 21, 100, 25, 3, 40, 300], 5)
    res = sorted(xs, key=str)
    return Rendered("Что выведет код? Введите элементы через пробел.", "input", " ".join(map(str, res)),
                    code=f"console.log({xs}.sort());", code_lang="javascript",
                    explanation="Без компаратора sort сравнивает элементы как строки.")


@family("js.typeof", JS, 1, "input", "typeof", time_limit=60)
def js_typeof(rng: random.Random, _l):
    expr, ans = rng.choice([("null", "object"), ("[]", "object"), ("NaN", "number"), ("() => {}", "function"),
                            ("undefined", "undefined"), ("Symbol('x')", "symbol"), ("10n", "bigint"),
                            ("class A {}", "function"), ("new Date()", "object"), ('"" + 1', "string")])
    return Rendered("Что выведет код?", "input", ans, code=f"console.log(typeof ({expr}));", code_lang="javascript",
                    norm="lower")


@family("js.closure_counter", JS, 2, "input", "Замыкания", time_limit=120)
def js_closure_counter(rng: random.Random, _l):
    s1, s2, step = rng.randint(0, 10), rng.randint(0, 10), rng.randint(2, 5)
    return Rendered("Что выведет код? Введите два числа через пробел.", "input", f"{s1 + 3 * step} {s2 + 2 * step}",
                    code=f"function makeCounter(start) {{\n  let c = start;\n  return () => (c += {step});\n}}\n"
                         f"const a = makeCounter({s1});\nconst b = makeCounter({s2});\na(); a(); b();\n"
                         "console.log(a(), b());", code_lang="javascript")


@family("js.spread_shallow", JS, 3, "input", "Поверхностное копирование", time_limit=120)
def js_spread_shallow(rng: random.Random, _l):
    n, m, p, q = rng.sample(range(1, 50), 4)
    return Rendered("Что выведет код? Введите два числа через пробел.", "input", f"{n} {q}",
                    code=f"const a = {{ x: {n}, inner: {{ y: {m} }} }};\nconst b = {{ ...a }};\nb.x = {p};\nb.inner.y = {q};\n"
                         "console.log(a.x, a.inner.y);", code_lang="javascript")


@family("js.defaults", JS, 3, "input", "Деструктуризация и значения по умолчанию", time_limit=120)
def js_defaults(rng: random.Random, _l):
    a, b = rng.sample(range(1, 20), 2)
    pass_null = rng.random() < 0.5
    src = "{ a: undefined, b: null }" if pass_null else "{ a: undefined }"
    ans = f"{a} null" if pass_null else f"{a} {b}"
    return Rendered("Что выведет код?", "input", ans,
                    code=f"const {{ a = {a}, b = {b} }} = {src};\nconsole.log(a, b);", code_lang="javascript",
                    explanation="Значение по умолчанию применяется только для undefined, но не для null.")


mcq("js.arrow_this", JS, 4, "Чем стрелочная функция отличается от обычной в части `this`?",
    "Она не имеет своего `this` и берёт его из лексического окружения",
    ["Её `this` всегда указывает на window", "Её `this` можно изменить через bind", "Её `this` — всегда undefined",
     "Её `this` указывает на саму функцию"], topic="this")
mcq("js.tdz", JS, 3, "Что произойдёт при обращении к переменной, объявленной через `let`, до строки объявления?",
    "ReferenceError (временная мёртвая зона)", ["Вернётся undefined", "Вернётся null", "TypeError",
                                                 "Переменная будет создана глобально"], topic="Hoisting")
mcq("js.allsettled", JS, 3, "Какой метод дождётся завершения всех промисов, даже если часть из них отклонена?",
    "Promise.allSettled", ["Promise.all", "Promise.race", "Promise.any", "Promise.resolve"], topic="Промисы")
mcq("js.prototype", JS, 4, "Где ищется свойство, которого нет у самого объекта?", "По цепочке прототипов через [[Prototype]]",
    ["В глобальном объекте", "В замыкании конструктора", "В свойстве prototype самого объекта", "Нигде — сразу undefined"],
    topic="Прототипы")
mcq("js.weakmap", JS, 5, "Чем WeakMap принципиально отличается от Map?",
    "Ключи — только объекты, удерживаемые слабо: запись не мешает сборке мусора", ["WeakMap работает быстрее",
                                                                                 "WeakMap можно итерировать",
                                                                                 "WeakMap допускает примитивные ключи",
                                                                                 "WeakMap синхронизирован между вкладками"],
    topic="WeakMap")
mcq("js.debounce", JS, 3, "Поиск по мере ввода шлёт запрос на каждый символ. Что поможет отправлять запрос, только когда "
    "пользователь перестал печатать на 300 мс?", "debounce", ["throttle", "requestAnimationFrame", "Promise.race",
                                                               "setInterval"], topic="Оптимизация событий")
mcq("js.optional_chaining", JS, 1, "Что вернёт выражение `user?.address?.city`, если `user.address` равно undefined?",
    "undefined", ["TypeError", "null", "Пустую строку", "false"], topic="Optional chaining")
mcq("js.modules", JS, 2, "Чем отличаются ES-модули от CommonJS?", "ES-модули импортируются статически (import/export) "
    "и анализируются до выполнения", ["CommonJS работает только в браузере", "ES-модули не поддерживают экспорт по умолчанию",
                                       "CommonJS поддерживает top-level await", "Ничем, это одно и то же"],
    topic="Модули")

# =============================== TypeScript ===============================
TS = "typescript"
mcq("ts.partial", TS, 1, "Что делает утилитарный тип `Partial<T>`?", "Делает все свойства T необязательными",
    ["Делает все свойства readonly", "Удаляет из T необязательные свойства", "Выбирает часть свойств по ключам",
     "Делает T совместимым с any"], topic="Утилитарные типы")
mcq("ts.unknown", TS, 3, "Чем `unknown` безопаснее `any`?", "С `unknown` нельзя работать без сужения типа",
    ["`unknown` запрещает присваивание", "`unknown` проверяется в рантайме", "`unknown` нельзя вернуть из функции",
     "Ничем, это синоним"], topic="unknown/any")
mcq("ts.never", TS, 4, "Для чего используют тип `never` в проверке исчерпывающего switch?",
    "Чтобы компилятор сообщил об ошибке, если какой-то вариант объединения не обработан",
    ["Чтобы ускорить выполнение switch", "Чтобы запретить default", "Чтобы switch возвращал undefined",
     "Чтобы сделать перечисление неизменяемым"], topic="never")
mcq("ts.structural", TS, 2, "Какая типизация используется в TypeScript?", "Структурная: совместимость по форме объекта",
    ["Номинальная: совместимость по имени типа", "Динамическая", "Утиная только в рантайме", "Зависимые типы"],
    topic="Система типов")
mcq("ts.as_const", TS, 4, "Что делает `as const` для литерала массива `['a', 'b']`?",
    "Выводит readonly-кортеж литеральных типов readonly ['a', 'b']", ["Замораживает массив в рантайме",
                                                                      "Делает тип string[]", "Запрещает экспорт",
                                                                      "Превращает массив в enum"], topic="as const")
mcq("ts.infer", TS, 5, "Что вернёт тип `type R<T> = T extends Promise<infer U> ? U : T;` для `R<Promise<number[]>>`?",
    "number[]", ["Promise<number[]>", "number", "unknown", "never"], topic="Условные типы")
mcq("ts.omit", TS, 2, "Какой тип получится из `Omit<{ id: number; name: string; age: number }, 'age'>`?",
    "{ id: number; name: string }", ["{ age: number }", "{ id: number }", "{ name: string; age: number }", "never"],
    topic="Утилитарные типы")
mcq("ts.narrowing", TS, 3, "Как сузить тип `x: string | number[]` до массива внутри if?", "`Array.isArray(x)`",
    ["`typeof x === 'array'`", "`x instanceof Object`", "`x as number[]`", "`'length' in x`"], topic="Сужение типов")

# =============================== React ===============================
R = "react"


@family("react.batching", R, 3, "numeric", "Обновление состояния и батчинг", time_limit=150)
def react_batching(rng: random.Random, _l):
    s, x = rng.randint(0, 10), rng.randint(2, 5)
    ops = [rng.choice(["replace", "fn"]) for _ in range(rng.randint(3, 4))]
    state = s
    lines = []
    for op in ops:
        if op == "replace":
            state = s + x
            lines.append(f"    setCount(count + {x});")
        else:
            state += 1
            lines.append("    setCount(c => c + 1);")
    code = (f"function Counter() {{\n  const [count, setCount] = useState({s});\n  const onClick = () => {{\n"
            + "\n".join(lines) + "\n  };\n  return <button onClick={onClick}>{count}</button>;\n}")
    return Rendered("Какое значение отобразит кнопка после одного клика?", "numeric", state, code=code, code_lang="jsx",
                    explanation="`count` в замыкании — значение текущего рендера; функциональное обновление "
                                "получает актуальное значение из очереди.")


mcq("react.keys", R, 1, "Зачем элементам списка в React нужен проп `key`?",
    "Чтобы React сопоставлял элементы между рендерами и корректно их переиспользовал",
    ["Для стилизации элементов", "Для доступа к элементу из DOM", "Чтобы задать порядок сортировки",
     "Это обязательный атрибут HTML"], topic="Ключи")
mcq("react.effect_empty", R, 2, "Когда выполнится `useEffect(fn, [])`?", "Один раз после первого монтирования",
    ["После каждого рендера", "Перед каждым рендером", "Никогда", "При каждом изменении пропсов"], topic="useEffect")
mcq("react.ref", R, 2, "Что произойдёт при изменении `ref.current`?", "Значение изменится без повторного рендера",
    ["Компонент перерисуется", "React выбросит ошибку", "Перерисуются все дочерние компоненты",
     "Сработает useEffect без зависимостей"], topic="useRef")
mcq("react.memo", R, 3, "Чем отличаются useMemo и useCallback?", "useMemo мемоизирует результат вычисления, "
    "useCallback — саму функцию", ["Ничем", "useCallback кэширует запросы к API", "useMemo работает только в классах",
                                   "useCallback запускается асинхронно"], topic="Мемоизация")
mcq("react.hooks_rules", R, 1, "Какое правило хуков верно?", "Вызывать хуки только на верхнем уровне компонента, "
    "не в условиях и циклах", ["Хуки можно вызывать в любых функциях", "Хуки вызываются только в useEffect",
                               "Хуки нельзя вызывать в кастомных хуках", "Хуки вызываются только в классах"],
    topic="Правила хуков")
mcq("react.key_remount", R, 4, "Что произойдёт, если у компонента сменить проп `key`?",
    "React размонтирует старый экземпляр и смонтирует новый с чистым состоянием",
    ["Компонент просто перерисуется с сохранением состояния", "Ничего", "React выбросит предупреждение",
     "Обновятся только пропсы"], topic="Реконсиляция")
mcq("react.context", R, 4, "Какие компоненты перерисуются при изменении value у Context.Provider?",
    "Все компоненты, вызывающие useContext этого контекста", ["Только сам провайдер",
                                                               "Только прямые дети провайдера",
                                                               "Никакие, нужно вызвать forceUpdate",
                                                               "Все компоненты приложения"], topic="Context")
mcq("react.strict", R, 4, "Почему в режиме разработки с StrictMode эффект выполняется дважды при монтировании?",
    "React намеренно монтирует, размонтирует и снова монтирует компонент, чтобы выявить эффекты без очистки",
    ["Это ошибка конфигурации сборщика", "Из-за двух корневых элементов", "Так работает production-сборка",
     "Из-за включённого батчинга"], topic="StrictMode")
mcq("react.layout_effect", R, 5, "Когда нужен useLayoutEffect вместо useEffect?",
    "Когда нужно измерить DOM и синхронно изменить его до отрисовки браузером",
    ["Для запросов к API", "Для подписки на события окна", "Для ленивой загрузки модулей",
     "Для работы с серверными компонентами"], topic="useLayoutEffect")
mcq("react.controlled", R, 2, "Что такое контролируемый input?", "Его значение хранится в состоянии React и задаётся через value",
    ["Input с атрибутом required", "Input, к которому привязан ref", "Input внутри формы", "Input без onChange"],
    topic="Формы")
mcq("react.rerender_child", R, 3, "Родитель перерисовался, пропсы дочернего компонента не изменились. Что произойдёт "
    "с дочерним компонентом без React.memo?", "Он тоже перерисуется", ["Он не перерисуется",
                                                                       "Он размонтируется",
                                                                       "React выбросит ошибку",
                                                                       "Перерисуется только при наличии key"],
    topic="Рендеринг")

# =============================== HTML и CSS ===============================
W = "web_layout"


def _specificity(parts: list[str]) -> tuple[int, int, int]:
    a = sum(p.startswith("#") for p in parts)
    b = sum(p.startswith((".", "[", ":")) and not p.startswith("::") for p in parts)
    c = sum(p[0].isalpha() or p.startswith("::") for p in parts)
    return a, b, c


@family("css.specificity", W, 3, "single", "Специфичность селекторов", time_limit=150)
def css_specificity(rng: random.Random, _l):
    pool_id = ["#main", "#nav", "#app", "#menu"]
    pool_cls = [".btn", ".active", ".card", ".item", "[type=\"text\"]", ":hover", ".title"]
    pool_el = ["div", "a", "ul", "li", "span", "nav"]
    sels: dict[tuple, str] = {}
    while len(sels) < 4:
        els = rng.sample(pool_el, rng.randint(1, 3))
        mods = rng.sample(pool_id, rng.choice([0, 0, 1])) + rng.sample(pool_cls, rng.randint(0, 3))
        rng.shuffle(mods)
        pseudo_el = ["::before"] if rng.random() < 0.2 else []
        # модификаторы распределяем по составным селекторам: "ul.card li#nav:hover"
        sel = " ".join(e + "".join(mods[i::len(els)]) for i, e in enumerate(els)) + "".join(pseudo_el)
        sp = _specificity(els + mods + pseudo_el)
        if sp not in sels:
            sels[sp] = sel
    best = max(sels)
    opts, key = options_from(rng, sels[best], [v for k, v in sels.items() if k != best], fmt=lambda s: f"`{s}`")
    return Rendered("У какого селектора наибольшая специфичность?", "single", key, options=opts,
                    explanation=f"Специфичность считается тройкой (id, классы/атрибуты/псевдоклассы, элементы): {best}.")


@family("css.box_model", W, 2, "numeric", "Блочная модель", time_limit=120)
def css_box_model(rng: random.Random, _l):
    w, p, b, m = rng.choice([200, 240, 300, 320]), rng.choice([10, 12, 16, 20]), rng.choice([1, 2, 4]), rng.choice([8, 10, 20])
    sizing = rng.choice(["content-box", "border-box"])
    ans = w + 2 * p + 2 * b if sizing == "content-box" else w
    return Rendered("Какова ширина элемента по внешнему краю рамки (offsetWidth, без margin), px?", "numeric", ans,
                    code=f".box {{\n  box-sizing: {sizing};\n  width: {w}px;\n  padding: 0 {p}px;\n  border: {b}px solid;\n"
                         f"  margin: {m}px;\n}}", code_lang="css")


@family("css.margin_collapse", W, 3, "numeric", "Схлопывание отступов", time_limit=120)
def css_margin_collapse(rng: random.Random, _l):
    x, y = rng.choice([10, 16, 20, 24, 30]), rng.choice([12, 15, 25, 32, 40])
    variant = rng.choice(["block", "flex", "negative"])
    if variant == "block":
        parent, ans, mt = "display: block;", max(x, y), y
    elif variant == "flex":
        parent, ans, mt = "display: flex;\n  flex-direction: column;", x + y, y
    else:
        mt = -min(y, x - 2)
        parent, ans = "display: block;", x + mt
    return Rendered("Каким будет расстояние по вертикали между блоками .a и .b, px?", "numeric", ans,
                    code=f".parent {{\n  {parent}\n}}\n.a {{ margin-bottom: {x}px; }}\n.b {{ margin-top: {mt}px; }}",
                    code_lang="css")


@family("css.flex_grow", W, 4, "numeric", "Flexbox: распределение пространства", time_limit=180)
def css_flex_grow(rng: random.Random, _l):
    g = [rng.randint(1, 3) for _ in range(3)]
    basis = [rng.choice([50, 80, 100, 120]) for _ in range(3)]
    free = sum(g) * rng.randint(20, 60)
    w = sum(basis) + free
    k = rng.randrange(3)
    ans = basis[k] + free * g[k] // sum(g)
    items = "\n".join(f".i{i + 1} {{ flex: {g[i]} 1 {basis[i]}px; }}" for i in range(3))
    return Rendered(f"Контейнер шириной {w}px без отступов и рамок. Какой будет ширина `.i{k + 1}`, px?", "numeric", ans,
                    code=f".row {{ display: flex; width: {w}px; }}\n{items}", code_lang="css")


@family("css.grid_fr", W, 3, "numeric", "CSS Grid: единица fr", time_limit=150)
def css_grid_fr(rng: random.Random, _l):
    fixed, gap = rng.choice([100, 120, 200]), rng.choice([10, 16, 20])
    frs = [1, rng.choice([2, 3])]
    unit = rng.randint(60, 140)
    w = fixed + 2 * gap + unit * sum(frs)
    return Rendered(f"Ширина контейнера {w}px. Какова ширина последней колонки, px?", "numeric", unit * frs[1],
                    code=f".grid {{\n  display: grid;\n  width: {w}px;\n  grid-template-columns: {fixed}px 1fr {frs[1]}fr;\n"
                         f"  column-gap: {gap}px;\n}}", code_lang="css")


@family("css.rem_em", W, 2, "numeric", "Единицы rem и em", time_limit=120)
def css_rem_em(rng: random.Random, _l):
    root = rng.choice([10, 16, 20])
    pa = rng.choice([1.5, 2])
    ce = rng.choice([1.5, 2, 0.5])
    pad = rng.choice([1, 2, 3])
    if rng.random() < 0.5:
        q, ans = "font-size", root * pa * ce
    else:
        q, ans = "padding", root * pad
    return Rendered(f"Чему равно вычисленное значение `{q}` у `.child`, px?", "numeric", ans,
                    code=f"html {{ font-size: {root}px; }}\n.parent {{ font-size: {pa}rem; }}\n"
                         f".child {{ font-size: {ce}em; padding: {pad}rem; }}", code_lang="css")


mcq("html.semantic_nav", W, 1, "Какой тег семантически подходит для блока основной навигации сайта?", "<nav>",
    ["<div class=\"nav\">", "<menu>", "<section>", "<aside>"], topic="Семантическая вёрстка")
mcq("css.visibility", W, 1, "Чем `visibility: hidden` отличается от `display: none`?",
    "Элемент скрыт, но продолжает занимать место в потоке", ["Ничем", "Элемент удаляется из DOM",
                                                            "Элемент становится прозрачным для кликов только на мобильных",
                                                            "Элемент скрывается вместе с соседями"], topic="Отображение")
mcq("css.absolute", W, 2, "Относительно чего позиционируется элемент с `position: absolute`?",
    "Относительно ближайшего предка с position, отличным от static", ["Всегда относительно окна", "Относительно родителя",
                                                                       "Относительно body", "Относительно своего места в потоке"],
    topic="Позиционирование")
mcq("css.stacking", W, 4, "Почему элемент с `z-index: 9999` может оказаться под элементом с `z-index: 1`?",
    "Он находится внутри другого контекста наложения с меньшим приоритетом", ["z-index не работает с числами больше 1000",
                                                                              "z-index работает только для flex-элементов",
                                                                              "Браузер ограничивает z-index значением 100",
                                                                              "Из-за box-sizing"], topic="Контекст наложения")
mcq("html.label", W, 2, "Как правильно связать подпись с полем ввода для доступности?",
    "`<label for=\"email\">` и `<input id=\"email\">`", ["Поставить подпись в placeholder", "Использовать <span> перед input",
                                                         "Добавить title к input", "Указать name совпадающим с текстом"],
    topic="Доступность")
mcq("html.alt", W, 1, "Что указывать в атрибуте `alt` декоративного изображения?", "Пустое значение `alt=\"\"`",
    ["Имя файла", "Слово «картинка»", "Атрибут не нужен вообще", "Описание стиля оформления"], topic="Доступность")

# =============================== Браузер ===============================
B = "browser"


@family("web.same_origin", B, 2, "multi", "Same-origin policy", time_limit=150)
def web_same_origin(rng: random.Random, _l):
    host = rng.choice(["app.example.com", "shop.site.ru", "lk.fsp.dev"])
    base = f"https://{host}/profile"
    cands = [
        (f"https://{host}/api/v1/users?id=5", True), (f"https://{host}:443/docs", True),
        (f"http://{host}/profile", False), (f"https://{host}:8443/profile", False),
        (f"https://api.{host.split('.', 1)[1]}/profile", False), (f"https://{host}/a/b/c#hash", True),
        (f"https://{host}.evil.io/profile", False),
    ]
    shown = rng.sample(cands, 5)
    if not any(ok for _, ok in shown):
        shown[0] = cands[0]
    opts = [{"id": f"c{i}" if ok else f"w{i}", "text": f"`{u}`"} for i, (u, ok) in enumerate(shown)]
    return Rendered(f"Какие URL имеют тот же origin, что и `{base}`?\n\n_Выберите все верные варианты._", "multi",
                    [o["id"] for o in opts if o["id"].startswith("c")], options=opts,
                    explanation="Origin = схема + хост + порт. Путь и фрагмент не важны, 443 — порт https по умолчанию.")


@family("web.event_phases", B, 3, "input", "Всплытие и перехват событий", time_limit=180)
def web_event_phases(rng: random.Random, _l):
    els = ["outer", "middle", "inner"]
    listeners = [(el, phase) for el in els[:2] for phase in rng.sample(["capture", "bubble"], rng.randint(1, 2))]
    listeners.append(("inner", "bubble"))
    rng.shuffle(listeners)
    ids = {}
    lines = []
    for i, (el, phase) in enumerate(listeners, start=1):
        ids[(el, phase)] = i
        cap = ", true" if phase == "capture" else ""
        lines.append(f"{el}.addEventListener('click', () => log({i}){cap});")
    order = [ids[(e, "capture")] for e in els[:2] if (e, "capture") in ids]
    order.append(ids[("inner", "bubble")])
    order += [ids[(e, "bubble")] for e in reversed(els[:2]) if (e, "bubble") in ids]
    return Rendered("Элементы вложены: `#outer > #middle > #inner`. Пользователь кликает по `#inner`. "
                    "В каком порядке будут вызваны log? Введите числа через пробел.", "input", " ".join(map(str, order)),
                    code="\n".join(lines), code_lang="javascript")


mcq("web.cors_preflight", B, 3, "Когда браузер отправляет preflight-запрос OPTIONS?",
    "При кросс-доменном запросе с «непростым» методом или заголовками (например, PUT или Content-Type: application/json)",
    ["Перед каждым GET-запросом", "Только для запросов на тот же домен", "Только при использовании HTTP/2",
     "При загрузке изображений"], topic="CORS")
mcq("web.httponly", B, 2, "От чего защищает флаг `HttpOnly` у cookie?", "Cookie недоступна из JavaScript, что снижает ущерб от XSS",
    ["Cookie передаётся только по HTTPS", "Cookie не отправляется на другие домены", "Cookie шифруется",
     "Cookie не сохраняется на диск"], topic="Cookies")
mcq("web.storage", B, 1, "Чем sessionStorage отличается от localStorage?", "Данные живут только в рамках вкладки и сессии",
    ["sessionStorage хранит данные на сервере", "sessionStorage доступен всем доменам", "localStorage очищается при закрытии вкладки",
     "Ничем"], topic="Хранилища")
mcq("web.reflow", B, 3, "Изменение какого свойства обычно НЕ вызывает пересчёт раскладки (layout)?", "transform",
    ["width", "top у position: absolute", "font-size", "padding"], topic="Рендеринг")
mcq("web.defer", B, 3, "Чем `<script defer>` отличается от `<script async>`?",
    "defer выполняется после разбора HTML в порядке подключения, async — сразу по загрузке в любом порядке",
    ["Ничем", "async блокирует разбор HTML до загрузки", "defer работает только для inline-скриптов",
     "defer выполняется до разбора HTML"], topic="Загрузка скриптов")
mcq("web.no_store", B, 4, "Чем `Cache-Control: no-cache` отличается от `no-store`?",
    "no-cache позволяет хранить ответ, но требует ревалидации; no-store запрещает хранение",
    ["Это синонимы", "no-store разрешает кэш на 1 час", "no-cache запрещает любое кэширование", "no-store действует только на прокси"],
    topic="HTTP-кэширование")
mcq("web.lcp", B, 4, "Что измеряет метрика LCP (Largest Contentful Paint)?",
    "Время отрисовки самого крупного видимого элемента контента", ["Задержку первого ввода",
                                                                     "Смещение макета", "Время до первого байта",
                                                                     "Общий вес страницы"], topic="Web Vitals")
mcq("web.sw", B, 5, "Что позволяет Service Worker?", "Перехватывать сетевые запросы страницы и отвечать из кэша, в т. ч. офлайн",
    ["Выполнять код в основном потоке быстрее", "Обходить CORS", "Читать cookies HttpOnly", "Менять DOM напрямую"],
    topic="Service Worker")
multi("web.xss_sinks", B, 3, "Какие способы вывода пользовательских данных в DOM опасны с точки зрения XSS?",
      ["`element.innerHTML = data`", "`document.write(data)`", "`dangerouslySetInnerHTML={{__html: data}}`"],
      ["`element.textContent = data`", "`<div>{data}</div>` в React", "`input.value = data`"], topic="XSS")
