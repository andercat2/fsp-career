"""Языковые домены: Python, Java, Go. Параметрические задачи «что выведет код» + статичные вопросы
на понимание семантики языка."""
from __future__ import annotations

import random

from app.services.testing.bank.core import Rendered, family, mcq, multi, options_from

# =============================== Python ===============================
P = "python"


@family("py.slice", P, 1, "input", "Срезы списков", time_limit=90)
def py_slice(rng: random.Random, _l):
    xs = rng.sample(range(1, 30), 8)
    a, b = rng.randint(0, 3), rng.randint(5, 8)
    step = rng.choice([1, 2, 2, 3, -1])
    if step < 0:
        a, b = b - 1, rng.randint(0, 2)
    res = xs[a:b:step]
    return Rendered("Что выведет код? Введите элементы через пробел.", "input", " ".join(map(str, res)),
                    code=f"xs = {xs}\nprint(xs[{a}:{b}:{step}])", code_lang="python")


@family("py.floordiv", P, 2, "input", "Целочисленное деление", time_limit=90)
def py_floordiv(rng: random.Random, _l):
    a = rng.choice([-1, 1]) * rng.randint(7, 40)
    b = rng.choice([-1, 1]) * rng.randint(2, 6)
    if a > 0 and b > 0:
        a = -a
    return Rendered("Что выведет код? Введите два числа через пробел.", "input", f"{a // b} {a % b}",
                    code=f"print({a} // {b}, {a} % {b})", code_lang="python",
                    explanation="В Python // округляет вниз (к −∞), а знак остатка совпадает со знаком делителя.")


@family("py.mutable_default", P, 3, "input", "Изменяемые аргументы по умолчанию", time_limit=120)
def py_mutable_default(rng: random.Random, _l):
    fn = rng.choice(["add", "push", "collect", "remember"])
    vals = rng.sample(range(1, 50), 3)
    return Rendered("Что выведет код? Введите элементы списка через пробел.", "input", " ".join(map(str, vals)),
                    code=f"def {fn}(x, acc=[]):\n    acc.append(x)\n    return acc\n\n{fn}({vals[0]})\n{fn}({vals[1]})\n"
                         f"print({fn}({vals[2]}))", code_lang="python",
                    explanation="Значение по умолчанию вычисляется один раз при определении функции.")


@family("py.late_binding", P, 4, "input", "Замыкания и позднее связывание", time_limit=120)
def py_late_binding(rng: random.Random, _l):
    n, k = rng.randint(3, 5), rng.randint(2, 7)
    fixed = rng.random() < 0.35
    lam = f"lambda i=i: i * {k}" if fixed else f"lambda: i * {k}"
    res = [i * k for i in range(n)] if fixed else [(n - 1) * k] * n
    return Rendered("Что выведет код? Введите элементы через пробел.", "input", " ".join(map(str, res)),
                    code=f"fs = [{lam} for i in range({n})]\nprint([f() for f in fs])", code_lang="python")


@family("py.generator", P, 3, "numeric", "Генераторы", time_limit=120)
def py_generator(rng: random.Random, _l):
    n, m = rng.randint(6, 10), rng.choice([2, 3])
    skip = rng.randint(1, 2)
    seq = [i * i for i in range(n) if i % m == 0]
    return Rendered("Что выведет код?", "numeric", sum(seq[skip:]),
                    code=f"def gen(n):\n    for i in range(n):\n        if i % {m} == 0:\n            yield i * i\n\n"
                         f"g = gen({n})\n" + "next(g)\n" * skip + "print(sum(g))", code_lang="python")


@family("py.finally", P, 3, "input", "try/finally", time_limit=120)
def py_finally(rng: random.Random, _l):
    a, b = rng.sample(range(1, 20), 2)
    variant = rng.randrange(2)
    if variant == 0:
        code = f"def f():\n    try:\n        return {a}\n    finally:\n        return {b}\n\nprint(f())"
        ans = str(b)
    else:
        code = (f"def f():\n    x = {a}\n    try:\n        return x\n    finally:\n        x = {b}\n        print('fin', end=' ')\n\n"
                "print(f())")
        ans = f"fin {a}"
    return Rendered("Что выведет код?", "input", ans, code=code, code_lang="python")


@family("py.decorator", P, 3, "numeric", "Декораторы", time_limit=150)
def py_decorator(rng: random.Random, _l):
    calls = rng.randint(2, 5)
    mult = rng.randint(2, 4)
    return Rendered("Что выведет код?", "numeric", calls * mult,
                    code=f"def counted(fn):\n    def wrapper(*args):\n        wrapper.calls += {mult}\n        return fn(*args)\n"
                         "    wrapper.calls = 0\n    return wrapper\n\n@counted\ndef ping():\n    return 'pong'\n\n"
                         + "ping()\n" * calls + "print(ping.calls)", code_lang="python")


@family("py.dict_ops", P, 2, "input", "Словари", time_limit=120)
def py_dict_ops(rng: random.Random, _l):
    keys = rng.sample(["a", "b", "c", "d", "e"], 3)
    vals = rng.sample(range(1, 10), 3)
    d = dict(zip(keys, vals))
    k_new = rng.choice([k for k in "abcde" if k not in d])
    d2 = dict(d)
    d2.setdefault(keys[0], 100)
    d2.setdefault(k_new, 0)
    d2[k_new] += 5
    total = sum(d2.values())
    return Rendered("Что выведет код? Введите два числа через пробел.", "input", f"{len(d2)} {total}",
                    code=f"d = {d}\nd.setdefault('{keys[0]}', 100)\nd.setdefault('{k_new}', 0)\nd['{k_new}'] += 5\n"
                         "print(len(d), sum(d.values()))", code_lang="python")


@family("py.mro", P, 5, "input", "MRO и множественное наследование", time_limit=150)
def py_mro(rng: random.Random, _l):
    names = rng.sample(["Base", "Left", "Right", "Mixin", "Core", "Alpha", "Beta"], 3)
    a, b, c = names
    code = (f"class {a}:\n    def who(self): return '{a}'\n\nclass {b}({a}):\n    def who(self): return '{b}>' + super().who()\n\n"
            f"class {c}({a}):\n    def who(self): return '{c}>' + super().who()\n\nclass D({b}, {c}):\n    pass\n\nprint(D().who())")
    return Rendered("Что выведет код?", "input", f"{b}>{c}>{a}", code=code, code_lang="python", norm="exact",
                    explanation="super() идёт по MRO класса D: D → B → C → A (C3-линеаризация).")


@family("py.copy", P, 2, "input", "Копирование объектов", time_limit=120)
def py_copy(rng: random.Random, _l):
    x, y = rng.sample(range(1, 30), 2)
    deep = rng.random() < 0.5
    fn = "copy.deepcopy(a)" if deep else "copy.copy(a)"
    ans = f"{x}" if deep else f"{y}"
    return Rendered("Что выведет код?", "input", ans,
                    code=f"import copy\n\na = [[{x}], [0]]\nb = {fn}\nb[0][0] = {y}\nprint(a[0][0])", code_lang="python")


mcq("py.gil", P, 3, "Чему в первую очередь мешает GIL в CPython?",
    "Параллельному выполнению CPU-bound кода в нескольких потоках одного процесса",
    ["Использованию asyncio", "Параллельной работе нескольких процессов", "Ожиданию сетевого ввода-вывода в потоках",
     "Использованию C-расширений вроде NumPy"], topic="GIL")
mcq("py.is_eq", P, 1, "Чем отличается `a is b` от `a == b`?", "`is` сравнивает идентичность объектов, `==` — значения",
    ["Ничем, это синонимы", "`is` работает только для чисел", "`==` сравнивает адреса в памяти",
     "`is` сравнивает типы объектов"], topic="Сравнение объектов")
mcq("py.asyncio_block", P, 4, "Что из перечисленного заблокирует цикл событий asyncio внутри корутины?",
    "`time.sleep(1)`", ["`await asyncio.sleep(1)`", "`await queue.get()`", "`await asyncio.gather(*tasks)`",
                        "`async with session.get(url)`"], topic="asyncio")
mcq("py.immutable", P, 1, "Какой из типов в Python неизменяемый?", "tuple", ["list", "dict", "set", "bytearray"],
    topic="Типы данных")
mcq("py.context", P, 2, "Какие методы должен реализовать объект, чтобы использоваться в `with`?",
    "`__enter__` и `__exit__`", ["`__init__` и `__del__`", "`__iter__` и `__next__`", "`__open__` и `__close__`",
                                 "`__call__`"], topic="Контекстные менеджеры")
mcq("py.slots", P, 4, "Что даёт объявление `__slots__` в классе?",
    "Экономию памяти за счёт отказа от `__dict__` у экземпляров",
    ["Потокобезопасность атрибутов", "Ускорение импорта модуля", "Автоматическую генерацию `__eq__`",
     "Запрет наследования"], topic="Модель данных")
mcq("py.dataclass", P, 2, "Что генерирует декоратор `@dataclass` по умолчанию?", "`__init__`, `__repr__` и `__eq__`",
    ["Только `__init__`", "`__hash__` и `__lt__`", "Сериализацию в JSON", "Валидацию типов в рантайме"],
    topic="dataclasses")
multi("py.iterables", P, 2, "Какие объекты можно перебрать в цикле `for` без дополнительных преобразований?",
      ["Строка", "Словарь", "Множество", "Генератор", "Объект файла"], ["Целое число", "None", "Функция"],
      topic="Итерируемые объекты")

# =============================== Java ===============================
J = "java"


@family("java.integer_cache", J, 4, "input", "Integer cache и сравнение ссылок", time_limit=120)
def java_integer_cache(rng: random.Random, _l):
    n = rng.choice([rng.randint(-128, 127), rng.randint(128, 1000)])
    ans = "true" if -128 <= n <= 127 else "false"
    return Rendered("Что выведет код (стандартные настройки JVM)?", "input", f"{ans} true",
                    code=f"Integer x = {n};\nInteger y = {n};\nSystem.out.println((x == y) + \" \" + x.equals(y));",
                    code_lang="java", explanation="Автоупаковка кэширует Integer в диапазоне [−128; 127].")


@family("java.overflow", J, 3, "numeric", "Переполнение int", time_limit=120)
def java_overflow(rng: random.Random, _l):
    k = rng.randint(1, 20)
    v = (2**31 - 1 + k + 2**31) % 2**32 - 2**31
    return Rendered("Что выведет код?", "numeric", v,
                    code=f"int x = Integer.MAX_VALUE;\nx += {k};\nSystem.out.println(x);", code_lang="java")


@family("java.streams", J, 3, "numeric", "Stream API", time_limit=120)
def java_streams(rng: random.Random, _l):
    a, b = rng.randint(1, 5), rng.randint(12, 25)
    k, m = rng.choice([2, 3, 4]), rng.randint(2, 5)
    ans = sum(x * m for x in range(a, b + 1) if x % k == 0)
    return Rendered("Что выведет код?", "numeric", ans,
                    code=f"int r = IntStream.rangeClosed({a}, {b})\n    .filter(x -> x % {k} == 0)\n    .map(x -> x * {m})\n"
                         "    .sum();\nSystem.out.println(r);", code_lang="java")


@family("java.finally", J, 3, "input", "try/finally", time_limit=120)
def java_finally(rng: random.Random, _l):
    a, b = rng.sample(range(1, 20), 2)
    return Rendered("Что выведет код?", "input", f"F {a}",
                    code=f"static int f() {{\n    int x = {a};\n    try {{\n        return x;\n    }} finally {{\n"
                         f"        x = {b};\n        System.out.print(\"F \");\n    }}\n}}\n// ...\nSystem.out.println(f());",
                    code_lang="java", explanation="Значение для return вычислено до выполнения finally.")


@family("java.polymorphism", J, 2, "input", "Полиморфизм", time_limit=120)
def java_poly(rng: random.Random, _l):
    base, child = rng.sample(["Animal", "Shape", "Vehicle", "Node", "Account"], 2)
    x, y = rng.sample(range(1, 9), 2)
    return Rendered("Что выведет код? Введите два числа через пробел.", "input", f"{y} {x}",
                    code=f"class {base} {{ int v() {{ return {x}; }} static int s() {{ return {x}; }} }}\n"
                         f"class {child} extends {base} {{ int v() {{ return {y}; }} static int s() {{ return {y}; }} }}\n"
                         f"// ...\n{base} o = new {child}();\nSystem.out.println(o.v() + \" \" + {base}.s());",
                    code_lang="java", explanation="Виртуальные методы выбираются по динамическому типу, статические — нет.")


mcq("java.string_eq", J, 1, 'Что выведет `System.out.println(new String("a") == "a");`?', "false",
    ["true", "Ошибка компиляции", "NullPointerException"], topic="Сравнение строк", show=4)
mcq("java.hash_contract", J, 3, "Что обязательно при переопределении `equals` в Java?",
    "Переопределить `hashCode` так, чтобы равные объекты имели равный хеш",
    ["Сделать класс final", "Переопределить `toString`", "Реализовать `Comparable`", "Объявить `equals` synchronized"],
    topic="equals/hashCode")
mcq("java.volatile", J, 4, "Что гарантирует модификатор `volatile` для поля?",
    "Видимость изменений между потоками и запрет переупорядочивания вокруг доступа",
    ["Атомарность операции `x++`", "Взаимное исключение как у synchronized", "Хранение поля в стеке потока",
     "Неизменяемость значения"], topic="Модель памяти Java")
mcq("java.collections", J, 2, "Какая реализация Map хранит ключи в отсортированном порядке?", "TreeMap",
    ["HashMap", "LinkedHashMap", "IdentityHashMap", "WeakHashMap"], topic="Коллекции")
mcq("java.chm", J, 3, "Почему для общего доступа из многих потоков предпочитают ConcurrentHashMap, а не "
    "Collections.synchronizedMap?", "Блокировки мелкой гранулярности и неблокирующее чтение повышают параллелизм",
    ["Она хранит данные в отсортированном виде", "Она допускает null-ключи", "Она быстрее в однопоточном коде всегда",
     "Она не требует hashCode у ключей"], topic="Конкурентные коллекции")
mcq("java.checked", J, 1, "Какое исключение является проверяемым (checked)?", "IOException",
    ["NullPointerException", "IllegalArgumentException", "ArithmeticException", "ClassCastException"],
    topic="Исключения")
mcq("java.gc", J, 4, "Где в JVM размещаются объекты, созданные через `new` (без учёта escape-анализа)?", "В куче (heap)",
    ["В стеке потока", "В Metaspace", "В пуле строк", "В регистрах процессора"], topic="Память JVM")
mcq("java.virtual_threads", J, 5, "В каком сценарии виртуальные потоки (Java 21) дают наибольший выигрыш?",
    "Много одновременных задач, большую часть времени ожидающих ввода-вывода",
    ["Тяжёлые вычисления на всех ядрах", "Код с длительными synchronized-секциями вокруг I/O",
     "Однопоточная обработка в памяти", "Вычисления на GPU"], topic="Виртуальные потоки")

# =============================== Go ===============================
G = "go"


@family("go.defer", G, 2, "input", "defer", time_limit=120)
def go_defer(rng: random.Random, _l):
    xs = rng.sample(range(1, 10), 3)
    lines = "\n".join(f"\tdefer fmt.Print({x}, \" \")" for x in xs)
    return Rendered("Что выведет код? Введите числа через пробел.", "input", " ".join(map(str, reversed(xs))),
                    code=f"func main() {{\n{lines}\n}}", code_lang="go", explanation="defer выполняются в порядке LIFO.")


@family("go.append_alias", G, 4, "input", "Срезы и append", time_limit=150)
def go_append(rng: random.Random, _l):
    n, cap = rng.randint(2, 4), rng.choice([10, 8, 16])
    x, y = rng.sample(range(1, 50), 2)
    small_cap = rng.random() < 0.35
    if small_cap:
        cap = n
        ans = f"{x} {y}"
    else:
        ans = f"{y} {y}"
    return Rendered("Что выведет код? Введите два числа через пробел.", "input", ans,
                    code=f"a := make([]int, {n}, {cap})\nb := append(a, {x})\nc := append(a, {y})\n"
                         f"fmt.Println(b[{n}], c[{n}])", code_lang="go",
                    explanation="Пока ёмкости хватает, append пишет в общий базовый массив.")


@family("go.divmod", G, 1, "input", "Целочисленное деление", time_limit=90)
def go_divmod(rng: random.Random, _l):
    a = -rng.randint(7, 40)
    b = rng.randint(2, 6)
    q = int(a / b)
    return Rendered("Что выведет код? Введите два числа через пробел.", "input", f"{q} {a - q * b}",
                    code=f"fmt.Println({a} / {b}, {a} % {b})", code_lang="go",
                    explanation="В Go деление целых округляет к нулю.")


@family("go.strlen", G, 3, "input", "Строки, байты и руны", time_limit=120)
def go_strlen(rng: random.Random, _l):
    word = rng.choice(["привет", "мир", "код", "сеть", "данные", "go", "дом", "кот"]) + rng.choice(["", "!", "42", "ок"])
    return Rendered("Что выведет код? Введите два числа через пробел.", "input",
                    f"{len(word.encode('utf-8'))} {len(word)}",
                    code=f's := "{word}"\nfmt.Println(len(s), utf8.RuneCountInString(s))', code_lang="go",
                    explanation="len возвращает число байт UTF-8, кириллица занимает 2 байта на символ.")


@family("go.struct_copy", G, 2, "input", "Значения и указатели", time_limit=120)
def go_struct_copy(rng: random.Random, _l):
    a, b, c = rng.sample(range(1, 30), 3)
    return Rendered("Что выведет код? Введите два числа через пробел.", "input", f"{a} {c}",
                    code=f"type P struct{{ X int }}\n\np := P{{X: {a}}}\nq := p\nq.X = {b}\nr := &p\nr2 := r\nr2.X = {c}\n"
                         "fmt.Println(q.X - " + str(b - a) + ", p.X)", code_lang="go")


mcq("go.map_order", G, 2, "Каков порядок обхода map в Go через range?", "Не определён и может меняться от запуска к запуску",
    ["По возрастанию ключей", "В порядке вставки", "По убыванию хешей", "Обратный порядку вставки"], topic="map")
mcq("go.closed_chan", G, 3, "Что произойдёт при чтении из закрытого (и опустевшего) канала?",
    "Вернётся нулевое значение типа и ok == false", ["Паника", "Горутина заблокируется навсегда",
                                                       "Вернётся последнее отправленное значение", "Ошибка компиляции"],
    topic="Каналы")
mcq("go.send_closed", G, 3, "Что произойдёт при отправке в закрытый канал?", "Паника",
    ["Значение будет отброшено", "Горутина заблокируется", "Канал откроется заново", "Вернётся ошибка"], topic="Каналы")
mcq("go.nil_iface", G, 5, "Функция возвращает `error`, внутри — `var e *MyErr = nil; return e`. Чему равно `err != nil` "
    "у вызывающего?", "true — интерфейс хранит тип *MyErr и nil-указатель",
    ["false", "Паника при сравнении", "Ошибка компиляции", "Зависит от GOARCH"], topic="Интерфейсы и nil")
mcq("go.waitgroup", G, 3, "Для чего используется `sync.WaitGroup`?", "Дождаться завершения группы горутин",
    ["Ограничить число одновременно работающих горутин", "Передать данные между горутинами",
     "Защитить переменную от гонки", "Отменить горутины по таймауту"], topic="Синхронизация")
mcq("go.loopvar", G, 4, "Как изменилась семантика переменной цикла `for i := ...` в Go 1.22?",
    "Для каждой итерации создаётся новая переменная", ["Переменная стала неизменяемой",
                                                       "Цикл стал выполняться параллельно",
                                                       "Переменная стала глобальной", "Ничего не изменилось"],
    topic="Переменные цикла")
mcq("go.context", G, 3, "Для чего в Go передают `context.Context` первым аргументом?",
    "Для распространения отмены, дедлайнов и request-scoped значений", ["Для логирования",
                                                                         "Для передачи конфигурации приложения",
                                                                         "Для доступа к глобальному состоянию",
                                                                         "Для управления сборщиком мусора"],
    topic="context")
mcq("go.errors_is", G, 3, "Как проверить, что в цепочке обёрнутых ошибок есть `ErrNotFound`?",
    "`errors.Is(err, ErrNotFound)`", ["`err == ErrNotFound`", "`err.(ErrNotFound)`",
                                      "`strings.Contains(err.Error(), \"not found\")`", "`errors.New(ErrNotFound)`"],
    topic="Ошибки")
mcq("go.select", G, 4, "Что делает `select` без `default`, если ни один канал не готов?",
    "Блокируется до готовности одного из каналов", ["Сразу возвращается", "Паникует",
                                                    "Выбирает первый case", "Завершает горутину"], topic="select")


@family("go.goroutine_count", G, 4, "single", "Гонки данных", time_limit=120)
def go_race(rng: random.Random, _l):
    n = rng.choice([100, 500, 1000])
    opts, key = options_from(rng, f"Любое число от 1 до {n}: инкремент не атомарный — гонка данных",
                             [f"Всегда {n}", "Всегда 0", "Паника: concurrent map writes", f"Всегда {n // 2}"])
    return Rendered("Что можно сказать о выводе программы?", "single", key, options=opts,
                    code=f"var cnt int\nvar wg sync.WaitGroup\nfor i := 0; i < {n}; i++ {{\n\twg.Add(1)\n"
                         "\tgo func() {\n\t\tdefer wg.Done()\n\t\tcnt++\n\t}()\n}\nwg.Wait()\nfmt.Println(cnt)",
                    code_lang="go")
