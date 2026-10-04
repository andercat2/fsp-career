"""Алгоритмы и структуры данных. Большинство семейств параметрические: массивы, графы и константы
генерируются заново для каждого кандидата, код показывается на основном языке кандидата."""
from __future__ import annotations

import heapq
import random

from app.services.testing.bank.core import Rendered, family, mcq, options_from, pick_lang

D = "algorithms"


def _arr(xs: list[int], lang: str) -> str:
    inner = ", ".join(map(str, xs))
    return {"python": f"[{inner}]", "javascript": f"[{inner}]", "java": f"{{{inner}}}", "go": f"[]int{{{inner}}}"}[lang]


# ---------------- уровень 1–2: чтение кода ----------------

@family("alg.loop_sum", D, 1, "input", "Цикл с условием", time_limit=90)
def loop_sum(rng: random.Random, lang: str | None) -> Rendered:
    lang = pick_lang(lang)
    a, b = rng.randint(0, 5), rng.randint(12, 22)
    k = rng.choice([2, 3, 4, 5])
    r = rng.randint(0, k - 1)
    ans = sum(i for i in range(a, b) if i % k == r)
    code = {
        "python": f"s = 0\nfor i in range({a}, {b}):\n    if i % {k} == {r}:\n        s += i\nprint(s)",
        "javascript": f"let s = 0;\nfor (let i = {a}; i < {b}; i++) {{\n  if (i % {k} === {r}) s += i;\n}}\nconsole.log(s);",
        "java": f"int s = 0;\nfor (int i = {a}; i < {b}; i++) {{\n    if (i % {k} == {r}) s += i;\n}}\nSystem.out.println(s);",
        "go": f"s := 0\nfor i := {a}; i < {b}; i++ {{\n\tif i%{k} == {r} {{\n\t\ts += i\n\t}}\n}}\nfmt.Println(s)",
    }[lang]
    return Rendered("Что выведет программа?", "input", str(ans), code=code, code_lang=lang,
                    explanation=f"Суммируются числа из [{a}, {b}) с остатком {r} по модулю {k}.")


@family("alg.complexity", D, 2, "single", "Асимптотическая сложность", time_limit=90)
def complexity(rng: random.Random, lang: str | None) -> Rendered:
    lang = pick_lang(lang)
    v = rng.choice(["n", "m", "size", "count"])
    patterns = {
        "O(n²)": {
            "python": f"for i in range({v}):\n    for j in range(i, {v}):\n        total += i * j",
            "javascript": f"for (let i = 0; i < {v}; i++)\n  for (let j = i; j < {v}; j++)\n    total += i * j;",
            "java": f"for (int i = 0; i < {v}; i++)\n    for (int j = i; j < {v}; j++)\n        total += i * j;",
            "go": f"for i := 0; i < {v}; i++ {{\n\tfor j := i; j < {v}; j++ {{\n\t\ttotal += i * j\n\t}}\n}}",
        },
        "O(n log n)": {
            "python": f"for i in range({v}):\n    j = 1\n    while j < {v}:\n        total += j\n        j *= 2",
            "javascript": f"for (let i = 0; i < {v}; i++)\n  for (let j = 1; j < {v}; j *= 2)\n    total += j;",
            "java": f"for (int i = 0; i < {v}; i++)\n    for (int j = 1; j < {v}; j *= 2)\n        total += j;",
            "go": f"for i := 0; i < {v}; i++ {{\n\tfor j := 1; j < {v}; j *= 2 {{\n\t\ttotal += j\n\t}}\n}}",
        },
        "O(log n)": {
            "python": f"i = {v}\nwhile i > 1:\n    total += i\n    i //= 2",
            "javascript": f"for (let i = {v}; i > 1; i = Math.floor(i / 2))\n  total += i;",
            "java": f"for (int i = {v}; i > 1; i /= 2)\n    total += i;",
            "go": f"for i := {v}; i > 1; i /= 2 {{\n\ttotal += i\n}}",
        },
        "O(n)": {
            "python": f"for i in range({v}):\n    total += i\nfor j in range({v}):\n    total -= j",
            "javascript": f"for (let i = 0; i < {v}; i++) total += i;\nfor (let j = 0; j < {v}; j++) total -= j;",
            "java": f"for (int i = 0; i < {v}; i++) total += i;\nfor (int j = 0; j < {v}; j++) total -= j;",
            "go": f"for i := 0; i < {v}; i++ {{\n\ttotal += i\n}}\nfor j := 0; j < {v}; j++ {{\n\ttotal -= j\n}}",
        },
        "O(√n)": {
            "python": f"i = 1\nwhile i * i <= {v}:\n    total += i\n    i += 1",
            "javascript": f"for (let i = 1; i * i <= {v}; i++)\n  total += i;",
            "java": f"for (int i = 1; i * i <= {v}; i++)\n    total += i;",
            "go": f"for i := 1; i*i <= {v}; i++ {{\n\ttotal += i\n}}",
        },
    }
    correct = rng.choice(list(patterns))
    opts, key = options_from(rng, correct, [p for p in [*patterns, "O(n³)", "O(2ⁿ)"] if p != correct])
    return Rendered(f"Какова асимптотическая сложность фрагмента по времени (n = `{v}`)?", "single", key,
                    options=opts, code=patterns[correct][lang], code_lang=lang)


@family("alg.stack_queue", D, 1, "input", "Стек и очередь", time_limit=90)
def stack_queue(rng: random.Random, _lang: str | None) -> Rendered:
    is_stack = rng.random() < 0.5
    ops, cur = [], []
    for _ in range(rng.randint(7, 9)):
        if cur and rng.random() < 0.35:
            ops.append("pop" if is_stack else "dequeue")
            cur.pop() if is_stack else cur.pop(0)
        else:
            x = rng.randint(1, 30)
            ops.append(f"push({x})" if is_stack else f"enqueue({x})")
            cur.append(x)
    if not cur:
        x = rng.randint(1, 30)
        ops.append(f"push({x})" if is_stack else f"enqueue({x})")
        cur.append(x)
    what = "стек (LIFO)" if is_stack else "очередь (FIFO)"
    order = "снизу вверх" if is_stack else "от головы к хвосту"
    return Rendered(
        f"Над пустой структурой «{what}» выполнены операции:\n\n`{', '.join(ops)}`\n\n"
        f"Перечислите оставшиеся элементы {order} через пробел.",
        "input", " ".join(map(str, cur)), placeholder="например: 4 8 15")


@family("alg.prefix_window", D, 2, "numeric", "Скользящее окно", time_limit=120)
def prefix_window(rng: random.Random, _lang: str | None) -> Rendered:
    xs = [rng.randint(-9, 20) for _ in range(rng.randint(8, 10))]
    k = rng.randint(2, 4)
    best = max(sum(xs[i:i + k]) for i in range(len(xs) - k + 1))
    return Rendered(f"Массив: `{xs}`. Найдите максимальную сумму {k} подряд идущих элементов.", "numeric", best,
                    explanation="Скользящее окно: сумма пересчитывается за O(1) при сдвиге.")


@family("alg.hash_chain", D, 2, "numeric", "Хеш-таблица с цепочками", time_limit=150)
def hash_chain(rng: random.Random, _lang: str | None) -> Rendered:
    m = rng.choice([5, 7, 9, 11])
    keys = rng.sample(range(1, 100), 9)
    buckets: dict[int, int] = {}
    for kk in keys:
        buckets[kk % m] = buckets.get(kk % m, 0) + 1
    return Rendered(
        f"В пустую хеш-таблицу из {m} корзин с методом цепочек и хеш-функцией `h(k) = k mod {m}` "
        f"последовательно вставлены ключи: `{', '.join(map(str, keys))}`.\n\nКакова длина самой длинной цепочки?",
        "numeric", max(buckets.values()))


# ---------------- уровень 3: трассировка алгоритмов ----------------

@family("alg.binsearch", D, 3, "numeric", "Бинарный поиск", time_limit=150)
def binsearch(rng: random.Random, lang: str | None) -> Rendered:
    lang = pick_lang(lang)
    n = rng.randint(11, 17)
    a = sorted(rng.sample(range(1, 99), n))
    target = rng.choice(a) if rng.random() < 0.6 else rng.choice([x for x in range(1, 99) if x not in a])
    lo, hi, steps = 0, n - 1, 0
    while lo <= hi:
        steps += 1
        mid = (lo + hi) // 2
        if a[mid] == target:
            break
        if a[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    code = {
        "python": "def search(a, t):\n    lo, hi, steps = 0, len(a) - 1, 0\n    while lo <= hi:\n        steps += 1\n"
                  "        mid = (lo + hi) // 2\n        if a[mid] == t:\n            return steps\n"
                  "        if a[mid] < t:\n            lo = mid + 1\n        else:\n            hi = mid - 1\n    return steps",
        "javascript": "function search(a, t) {\n  let lo = 0, hi = a.length - 1, steps = 0;\n  while (lo <= hi) {\n"
                      "    steps++;\n    const mid = Math.floor((lo + hi) / 2);\n    if (a[mid] === t) return steps;\n"
                      "    if (a[mid] < t) lo = mid + 1; else hi = mid - 1;\n  }\n  return steps;\n}",
        "java": "static int search(int[] a, int t) {\n    int lo = 0, hi = a.length - 1, steps = 0;\n    while (lo <= hi) {\n"
                "        steps++;\n        int mid = (lo + hi) / 2;\n        if (a[mid] == t) return steps;\n"
                "        if (a[mid] < t) lo = mid + 1; else hi = mid - 1;\n    }\n    return steps;\n}",
        "go": "func search(a []int, t int) int {\n\tlo, hi, steps := 0, len(a)-1, 0\n\tfor lo <= hi {\n\t\tsteps++\n"
              "\t\tmid := (lo + hi) / 2\n\t\tif a[mid] == t {\n\t\t\treturn steps\n\t\t}\n\t\tif a[mid] < t {\n"
              "\t\t\tlo = mid + 1\n\t\t} else {\n\t\t\thi = mid - 1\n\t\t}\n\t}\n\treturn steps\n}",
    }[lang]
    return Rendered(f"Что вернёт `search(a, {target})` для массива\n\n`a = {_arr(a, lang)}`?", "numeric", steps,
                    code=code, code_lang=lang)


@family("alg.bubble_pass", D, 3, "input", "Сортировки: трассировка", time_limit=150)
def bubble_pass(rng: random.Random, _lang: str | None) -> Rendered:
    xs = rng.sample(range(1, 60), rng.randint(6, 7))
    algo = rng.choice(["bubble", "insertion", "selection"])
    k = rng.randint(1, 2) if algo == "bubble" else rng.randint(2, 3)
    a = xs[:]
    if algo == "bubble":
        for i in range(k):
            for j in range(len(a) - 1 - i):
                if a[j] > a[j + 1]:
                    a[j], a[j + 1] = a[j + 1], a[j]
        what = f"{k} полн{'ый проход' if k == 1 else 'ых прохода'} пузырьковой сортировки"
    elif algo == "insertion":
        for i in range(1, k + 1):
            cur, j = a[i], i - 1
            while j >= 0 and a[j] > cur:
                a[j + 1] = a[j]
                j -= 1
            a[j + 1] = cur
        what = f"{k} итерации внешнего цикла сортировки вставками (начиная с i = 1)"
    else:
        for i in range(k):
            m = min(range(i, len(a)), key=lambda t: a[t])
            a[i], a[m] = a[m], a[i]
        what = f"{k} итерации сортировки выбором (поиск минимума и обмен)"
    return Rendered(f"Массив `{xs}` сортируется по возрастанию. Каким он будет после того, как выполнены {what}?\n\n"
                    "Введите элементы через пробел.", "input", " ".join(map(str, a)))


@family("alg.recursion", D, 3, "numeric", "Рекурсия", time_limit=150)
def recursion(rng: random.Random, lang: str | None) -> Rendered:
    lang = pick_lang(lang)
    p, q = rng.randint(1, 2), rng.randint(1, 3)
    n = rng.randint(5, 7)
    f = [0, 1]
    for i in range(2, n + 1):
        f.append(p * f[i - 1] + q * f[i - 2])
    pe = "" if p == 1 else f"{p} * "
    qe = "" if q == 1 else f"{q} * "
    code = {
        "python": f"def f(n):\n    if n < 2:\n        return n\n    return {pe}f(n - 1) + {qe}f(n - 2)\n\nprint(f({n}))",
        "javascript": f"function f(n) {{\n  if (n < 2) return n;\n  return {pe}f(n - 1) + {qe}f(n - 2);\n}}\nconsole.log(f({n}));",
        "java": f"static int f(int n) {{\n    if (n < 2) return n;\n    return {pe}f(n - 1) + {qe}f(n - 2);\n}}\n// ...\nSystem.out.println(f({n}));",
        "go": f"func f(n int) int {{\n\tif n < 2 {{\n\t\treturn n\n\t}}\n\treturn {pe}f(n-1) + {qe}f(n-2)\n}}\n// ...\nfmt.Println(f({n}))",
    }[lang]
    return Rendered("Что выведет программа?", "numeric", f[n], code=code, code_lang=lang)


@family("alg.bits", D, 3, "numeric", "Битовые операции", time_limit=120)
def bits(rng: random.Random, lang: str | None) -> Rendered:
    lang = pick_lang(lang)
    x = rng.randint(17, 250)
    variant = rng.randrange(4)
    if variant == 0:
        expr, val = "x & (x - 1)", x & (x - 1)
    elif variant == 1:
        expr, val = "x ^ (x >> 1)", x ^ (x >> 1)
    elif variant == 2:
        m, s = rng.choice([15, 31, 63, 240]), rng.randint(1, 3)
        expr, val = f"(x & {m}) | (x >> {s})", (x & m) | (x >> s)
    else:
        s = rng.randint(1, 3)
        expr, val = f"(x << {s}) & 255", (x << s) & 255
    decl = {"python": f"x = {x}", "javascript": f"const x = {x};", "java": f"int x = {x};", "go": f"x := {x}"}[lang]
    out = {"python": f"print({expr})", "javascript": f"console.log({expr});", "java": f"System.out.println({expr});",
           "go": f"fmt.Println({expr})"}[lang]
    return Rendered("Что выведет программа?", "numeric", val, code=f"{decl}\n{out}", code_lang=lang)


@family("alg.bfs", D, 3, "numeric", "Обход графа в ширину", time_limit=180)
def bfs(rng: random.Random, _lang: str | None) -> Rendered:
    nodes = list("ABCDEFG")
    # гарантируем связность: случайное остовное дерево + несколько дополнительных рёбер
    order = nodes[:]
    rng.shuffle(order)
    edges = set()
    for i in range(1, len(order)):
        u, v = order[i], rng.choice(order[:i])
        edges.add(tuple(sorted((u, v))))
    while len(edges) < 9:
        u, v = rng.sample(nodes, 2)
        edges.add(tuple(sorted((u, v))))
    adj = {n: [] for n in nodes}
    for u, v in edges:
        adj[u].append(v)
        adj[v].append(u)
    dist = {"A": 0}
    q = ["A"]
    while q:
        u = q.pop(0)
        for v in adj[u]:
            if v not in dist:
                dist[v] = dist[u] + 1
                q.append(v)
    target = max((n for n in nodes if n != "A"), key=lambda n: (dist[n], rng.random()))
    el = ", ".join(f"{u}–{v}" for u, v in sorted(edges))
    return Rendered(f"Неориентированный граф задан рёбрами: `{el}`.\n\n"
                    f"Сколько рёбер в кратчайшем пути из **A** в **{target}**?", "numeric", dist[target])


@family("alg.modpow", D, 3, "numeric", "Модульная арифметика", time_limit=150)
def modpow(rng: random.Random, _lang: str | None) -> Rendered:
    base = rng.randint(2, 9)
    exp = rng.randint(20, 60)
    mod = rng.choice([7, 11, 13, 17])
    return Rendered(f"Вычислите `{base}^{exp} mod {mod}`.", "numeric", pow(base, exp, mod),
                    explanation="Быстрое возведение в степень или малая теорема Ферма.")


@family("alg.stairs_dp", D, 3, "numeric", "Динамическое программирование", time_limit=180)
def stairs_dp(rng: random.Random, _lang: str | None) -> Rendered:
    steps = rng.choice([(1, 2), (1, 3), (1, 2, 3), (2, 3)])
    n = rng.randint(7, 11)
    ways = [0] * (n + 1)
    ways[0] = 1
    for i in range(1, n + 1):
        ways[i] = sum(ways[i - s] for s in steps if i - s >= 0)
    return Rendered(f"Сколькими способами можно подняться на {n} ступенек, если за один шаг можно подняться на "
                    f"{' или '.join(map(str, steps))} ступеньки? Порядок шагов важен.", "numeric", ways[n])


# ---------------- уровень 4–5 ----------------

@family("alg.fib_calls", D, 4, "numeric", "Сложность наивной рекурсии", time_limit=180)
def fib_calls(rng: random.Random, lang: str | None) -> Rendered:
    lang = pick_lang(lang)
    n = rng.randint(5, 8)
    calls = [1, 1]
    for i in range(2, n + 1):
        calls.append(1 + calls[i - 1] + calls[i - 2])
    code = {
        "python": "def fib(n):\n    if n < 2:\n        return n\n    return fib(n - 1) + fib(n - 2)",
        "javascript": "function fib(n) {\n  if (n < 2) return n;\n  return fib(n - 1) + fib(n - 2);\n}",
        "java": "static int fib(int n) {\n    if (n < 2) return n;\n    return fib(n - 1) + fib(n - 2);\n}",
        "go": "func fib(n int) int {\n\tif n < 2 {\n\t\treturn n\n\t}\n\treturn fib(n-1) + fib(n-2)\n}",
    }[lang]
    return Rendered(f"Сколько всего раз будет вызвана функция `fib` (включая первый вызов) при вычислении `fib({n})`?",
                    "numeric", calls[n], code=code, code_lang=lang)


@family("alg.heap", D, 4, "input", "Двоичная куча", time_limit=180)
def heap(rng: random.Random, _lang: str | None) -> Rendered:
    xs = rng.sample(range(1, 50), 7)
    h: list[int] = []
    for x in xs:  # heapq реализует классический sift-up — совпадает с учебной вставкой
        heapq.heappush(h, x)
    return Rendered(f"В пустую двоичную min-кучу (хранится в массиве) по очереди вставили: `{', '.join(map(str, xs))}`.\n\n"
                    "Каким будет массив кучи? Введите элементы через пробел.", "input", " ".join(map(str, h)))


@family("alg.dijkstra", D, 5, "numeric", "Кратчайшие пути (Дейкстра)", time_limit=240)
def dijkstra(rng: random.Random, _lang: str | None) -> Rendered:
    nodes = list("ABCDEF")
    edges = {}
    order = nodes[:]
    rng.shuffle(order)
    for i in range(1, len(order)):
        u, v = order[i], rng.choice(order[:i])
        edges[tuple(sorted((u, v)))] = rng.randint(1, 9)
    while len(edges) < 9:
        u, v = rng.sample(nodes, 2)
        edges.setdefault(tuple(sorted((u, v))), rng.randint(1, 9))
    adj = {n: [] for n in nodes}
    for (u, v), w in edges.items():
        adj[u].append((v, w))
        adj[v].append((u, w))
    dist = {n: float("inf") for n in nodes}
    dist["A"] = 0
    pq = [(0, "A")]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        for v, w in adj[u]:
            if d + w < dist[v]:
                dist[v] = d + w
                heapq.heappush(pq, (dist[v], v))
    target = max((n for n in nodes if n != "A"), key=lambda n: (dist[n], rng.random()))
    el = ", ".join(f"{u}–{v}: {w}" for (u, v), w in sorted(edges.items()))
    return Rendered(f"Взвешенный неориентированный граф (ребро: вес): `{el}`.\n\n"
                    f"Найдите длину кратчайшего пути из **A** в **{target}**.", "numeric", dist[target])


@family("alg.two_sum_count", D, 4, "numeric", "Два указателя", time_limit=180)
def two_sum_count(rng: random.Random, lang: str | None) -> Rendered:
    lang = pick_lang(lang)
    a = sorted(rng.sample(range(1, 40), 10))
    t = rng.choice([a[i] + a[j] for i in range(10) for j in range(i + 1, 10)])
    i, j, cnt = 0, len(a) - 1, 0
    while i < j:
        s = a[i] + a[j]
        if s == t:
            cnt += 1
            i += 1
            j -= 1
        elif s < t:
            i += 1
        else:
            j -= 1
    code = {
        "python": f"a = {a}\ni, j, cnt = 0, len(a) - 1, 0\nwhile i < j:\n    s = a[i] + a[j]\n    if s == {t}:\n"
                  "        cnt += 1; i += 1; j -= 1\n    elif s < " + str(t) + ":\n        i += 1\n    else:\n        j -= 1\nprint(cnt)",
        "javascript": f"const a = {a};\nlet i = 0, j = a.length - 1, cnt = 0;\nwhile (i < j) {{\n  const s = a[i] + a[j];\n"
                      f"  if (s === {t}) {{ cnt++; i++; j--; }}\n  else if (s < {t}) i++;\n  else j--;\n}}\nconsole.log(cnt);",
        "java": f"int[] a = {_arr(a, 'java')};\nint i = 0, j = a.length - 1, cnt = 0;\nwhile (i < j) {{\n    int s = a[i] + a[j];\n"
                f"    if (s == {t}) {{ cnt++; i++; j--; }}\n    else if (s < {t}) i++;\n    else j--;\n}}\nSystem.out.println(cnt);",
        "go": f"a := {_arr(a, 'go')}\ni, j, cnt := 0, len(a)-1, 0\nfor i < j {{\n\ts := a[i] + a[j]\n\tif s == {t} {{\n"
              f"\t\tcnt++\n\t\ti++\n\t\tj--\n\t}} else if s < {t} {{\n\t\ti++\n\t}} else {{\n\t\tj--\n\t}}\n}}\nfmt.Println(cnt)",
    }[lang]
    return Rendered("Что выведет программа?", "numeric", cnt, code=code, code_lang=lang)


# ---------------- статичные вопросы (с выборкой дистракторов) ----------------

mcq("alg.ds.lru", D, 3, "Какая комбинация структур данных позволяет реализовать LRU-кэш с операциями get/put за O(1)?",
    "Хеш-таблица + двусвязный список",
    ["Отсортированный массив + бинарный поиск", "Двоичная куча", "Красно-чёрное дерево", "Стек + очередь",
     "Префиксное дерево (trie)"], topic="Проектирование структур данных")
mcq("alg.ds.hash_worst", D, 2, "Какова сложность поиска в хеш-таблице в худшем случае (все ключи в одной корзине)?",
    "O(n)", ["O(1)", "O(log n)", "O(n log n)", "O(√n)"], topic="Хеш-таблицы")
mcq("alg.sort.stable", D, 2, "Какой из алгоритмов сортировки является устойчивым (сохраняет порядок равных элементов)?",
    "Сортировка слиянием", ["Быстрая сортировка (классическая)", "Пирамидальная сортировка", "Сортировка выбором",
                            "Сортировка Шелла"], topic="Свойства сортировок")
mcq("alg.sort.quick_worst", D, 2, "Какова сложность быстрой сортировки в худшем случае?", "O(n²)",
    ["O(n log n)", "O(n)", "O(log n)", "O(n³)"], topic="Свойства сортировок")
mcq("alg.graph.negative", D, 4, "Какой алгоритм корректно находит кратчайшие пути от одной вершины в графе с "
    "отрицательными весами рёбер (без отрицательных циклов)?", "Беллмана — Форда",
    ["Дейкстры", "Обход в ширину", "Прима", "Краскала"], topic="Кратчайшие пути")
mcq("alg.graph.topo", D, 3, "Для какого графа существует топологическая сортировка?",
    "Для ориентированного ациклического графа", ["Для любого связного графа", "Только для деревьев",
                                                 "Для любого ориентированного графа", "Для полного графа"],
    topic="Топологическая сортировка")
mcq("alg.ds.amortized", D, 4, "Какова амортизированная сложность добавления элемента в конец динамического массива "
    "с удвоением ёмкости?", "O(1)", ["O(n)", "O(log n)", "O(n log n)", "Θ(√n)"], topic="Амортизационный анализ")
mcq("alg.ds.union_find", D, 5, "Какова амортизированная сложность операций в системе непересекающихся множеств "
    "(DSU) с эвристиками сжатия путей и объединения по рангу?", "O(α(n)) — обратная функция Аккермана",
    ["O(log n)", "O(1) в худшем случае", "O(log log n)", "O(√n)"], topic="DSU")
mcq("alg.ds.trie", D, 3, "Какая структура данных эффективнее всего для поиска всех слов с заданным префиксом?",
    "Префиксное дерево (trie)", ["Хеш-таблица", "Двоичная куча", "Стек", "Очередь с приоритетом"],
    topic="Префиксные деревья")
mcq("alg.np", D, 5, "Что верно про задачу коммивояжёра в форме распознавания («есть ли маршрут длины ≤ K»)?",
    "Она NP-полна", ["Она решается за полиномиальное время жадным алгоритмом", "Она неразрешима",
                     "Она принадлежит классу P, но не NP", "Она решается динамикой за O(n²)"],
    topic="Классы сложности")
