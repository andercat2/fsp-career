"""Бэкенд-домены: SQL, базы данных, HTTP/API, архитектура, безопасность.

SQL-задания параметрические: для каждого кандидата генерируются свои таблицы, запрос выполняется в in-memory SQLite,
и правильный ответ берётся из реального результата запроса.
"""
from __future__ import annotations

import math
import random
import sqlite3

from app.services.testing.bank.core import Rendered, family, mcq, multi, options_from

# =============================== SQL ===============================
S = "sql"
_NAMES = ["Анна", "Борис", "Вера", "Глеб", "Дина", "Егор", "Жанна", "Иван", "Кира", "Лев", "Мария", "Олег", "Полина",
          "Роман", "Софья", "Тимур"]
_DEPTS = ["Backend", "Data", "QA", "Mobile", "DevOps", "Frontend"]


def _gen_db(rng: random.Random, *, with_null_dept: bool = True, with_bonus: bool = False):
    n_d = rng.randint(3, 4)
    depts = [(i + 1, t) for i, t in enumerate(rng.sample(_DEPTS, n_d))]
    n_e = rng.randint(8, 9)
    names = rng.sample(_NAMES, n_e)
    salaries = rng.sample(range(80, 320, 5), n_e)
    emps = []
    for i in range(n_e):
        r = rng.random()
        dept = None if (with_null_dept and r < 0.15) else (9 if r < 0.22 else rng.randint(1, n_d))
        bonus = (rng.choice([None, None, 10, 15, 20, 30, 40]) if with_bonus else None)
        emps.append((i + 1, names[i], dept, salaries[i] * 1000, rng.randint(2015, 2024), bonus))
    if with_null_dept and not any(e[2] is None for e in emps):
        e = emps[-1]
        emps[-1] = (e[0], e[1], None, e[3], e[4], e[5])
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE departments(id INTEGER PRIMARY KEY, title TEXT)")
    con.execute("CREATE TABLE employees(id INTEGER PRIMARY KEY, name TEXT, dept_id INTEGER, salary INTEGER, hired INTEGER, bonus INTEGER)")
    con.executemany("INSERT INTO departments VALUES (?, ?)", depts)
    con.executemany("INSERT INTO employees VALUES (?, ?, ?, ?, ?, ?)", emps)
    return con, depts, emps


def _fmt(v) -> str:
    return "NULL" if v is None else str(v)


def _tables_md(depts, emps, *, bonus: bool = False) -> str:
    cols = "| id | name | dept_id | salary | hired |" + (" bonus |" if bonus else "")
    sep = "|---|---|---|---|---|" + ("---|" if bonus else "")
    rows = "\n".join(f"| {e[0]} | {e[1]} | {_fmt(e[2])} | {e[3]} | {e[4]} |" + (f" {_fmt(e[5])} |" if bonus else "")
                     for e in emps)
    d_rows = "\n".join(f"| {d[0]} | {d[1]} |" for d in depts)
    return f"**employees**\n\n{cols}\n{sep}\n{rows}\n\n**departments**\n\n| id | title |\n|---|---|\n{d_rows}"


def _q(con, sql):
    return con.execute(sql).fetchall()


@family("sql.count_where", S, 1, "numeric", "Фильтрация WHERE", time_limit=120)
def sql_count_where(rng: random.Random, _l):
    con, depts, emps = _gen_db(rng)
    x = rng.choice(sorted(e[3] for e in emps)[2:-2])
    y = rng.randint(2017, 2022)
    op = rng.choice(["AND", "OR"])
    sql = f"SELECT COUNT(*) FROM employees\nWHERE salary > {x} {op} hired >= {y};"
    return Rendered(f"{_tables_md(depts, emps)}\n\nЧто вернёт запрос?", "numeric", _q(con, sql)[0][0], code=sql, code_lang="sql")


@family("sql.order_offset", S, 2, "input", "ORDER BY / LIMIT / OFFSET", time_limit=120)
def sql_order_offset(rng: random.Random, _l):
    con, depts, emps = _gen_db(rng)
    k = rng.randint(1, 3)
    direction = rng.choice(["DESC", "ASC"])
    sql = f"SELECT name FROM employees\nORDER BY salary {direction}\nLIMIT 1 OFFSET {k};"
    return Rendered(f"{_tables_md(depts, emps)}\n\nЧто вернёт запрос? Введите имя.", "input", _q(con, sql)[0][0],
                    code=sql, code_lang="sql", norm="lower")


@family("sql.inner_join", S, 2, "numeric", "INNER JOIN", time_limit=120)
def sql_inner_join(rng: random.Random, _l):
    con, depts, emps = _gen_db(rng)
    sql = "SELECT COUNT(*)\nFROM employees e\nJOIN departments d ON d.id = e.dept_id;"
    return Rendered(f"{_tables_md(depts, emps)}\n\nЧто вернёт запрос?", "numeric", _q(con, sql)[0][0], code=sql, code_lang="sql")


@family("sql.left_join_null", S, 3, "numeric", "LEFT JOIN и поиск «сирот»", time_limit=150)
def sql_left_join_null(rng: random.Random, _l):
    con, depts, emps = _gen_db(rng)
    sql = "SELECT COUNT(*)\nFROM employees e\nLEFT JOIN departments d ON d.id = e.dept_id\nWHERE d.id IS NULL;"
    return Rendered(f"{_tables_md(depts, emps)}\n\nЧто вернёт запрос?", "numeric", _q(con, sql)[0][0], code=sql, code_lang="sql")


@family("sql.group_having", S, 3, "numeric", "GROUP BY / HAVING", time_limit=180)
def sql_group_having(rng: random.Random, _l):
    con, depts, emps = _gen_db(rng)
    k = rng.choice([2, 3])
    sql = f"SELECT dept_id, COUNT(*)\nFROM employees\nGROUP BY dept_id\nHAVING COUNT(*) >= {k};"
    return Rendered(f"{_tables_md(depts, emps)}\n\nСколько строк вернёт запрос?", "numeric", len(_q(con, sql)), code=sql,
                    code_lang="sql", explanation="NULL в GROUP BY образует отдельную группу.")


@family("sql.subquery_avg", S, 3, "numeric", "Подзапросы", time_limit=150)
def sql_subquery_avg(rng: random.Random, _l):
    con, depts, emps = _gen_db(rng)
    sql = "SELECT COUNT(*)\nFROM employees\nWHERE salary > (SELECT AVG(salary) FROM employees);"
    return Rendered(f"{_tables_md(depts, emps)}\n\nЧто вернёт запрос?", "numeric", _q(con, sql)[0][0], code=sql, code_lang="sql")


@family("sql.top_dept", S, 3, "input", "Агрегация с JOIN", time_limit=180)
def sql_top_dept(rng: random.Random, _l):
    con, depts, emps = _gen_db(rng)
    sql = ("SELECT d.title\nFROM employees e\nJOIN departments d ON d.id = e.dept_id\nGROUP BY d.title\n"
           "ORDER BY SUM(e.salary) DESC, d.title\nLIMIT 1;")
    return Rendered(f"{_tables_md(depts, emps)}\n\nЧто вернёт запрос?", "input", _q(con, sql)[0][0], code=sql,
                    code_lang="sql", norm="lower")


@family("sql.null_agg", S, 4, "numeric", "NULL в агрегатах", time_limit=180)
def sql_null_agg(rng: random.Random, _l):
    con, depts, emps = _gen_db(rng, with_bonus=True)
    if all(e[5] is None for e in emps):
        con.execute("UPDATE employees SET bonus = 20 WHERE id = 1")
        emps[0] = (*emps[0][:5], 20)
    variant = rng.randrange(2)
    sql = ("SELECT ROUND(AVG(bonus), 1) FROM employees;" if variant == 0
           else "SELECT COUNT(*) - COUNT(bonus) FROM employees;")
    return Rendered(f"{_tables_md(depts, emps, bonus=True)}\n\nЧто вернёт запрос?", "numeric", _q(con, sql)[0][0],
                    code=sql, code_lang="sql", tolerance=0.05, explanation="Агрегатные функции игнорируют NULL, кроме COUNT(*).")


@family("sql.window_running", S, 4, "numeric", "Оконные функции", time_limit=180)
def sql_window_running(rng: random.Random, _l):
    con, depts, emps = _gen_db(rng)
    who = rng.choice(emps[2:])
    variant = rng.randrange(2)
    if variant == 0:
        sql = "SELECT name,\n       SUM(salary) OVER (ORDER BY id) AS acc\nFROM employees;"
        q = f"Какое значение `acc` будет в строке сотрудника {who[1]}?"
        ans = next(r[1] for r in _q(con, sql) if r[0] == who[1])
    else:
        sql = "SELECT name,\n       RANK() OVER (ORDER BY salary DESC) AS r\nFROM employees;"
        q = f"Какое значение `r` будет в строке сотрудника {who[1]}?"
        ans = next(r[1] for r in _q(con, sql) if r[0] == who[1])
    return Rendered(f"{_tables_md(depts, emps)}\n\n{q}", "numeric", ans, code=sql, code_lang="sql")


@family("sql.not_in_null", S, 5, "numeric", "NOT IN и NULL", time_limit=180)
def sql_not_in_null(rng: random.Random, _l):
    con, depts, emps = _gen_db(rng, with_null_dept=True)
    sql = "SELECT COUNT(*)\nFROM departments\nWHERE id NOT IN (SELECT dept_id FROM employees);"
    return Rendered(f"{_tables_md(depts, emps)}\n\nЧто вернёт запрос?", "numeric", _q(con, sql)[0][0], code=sql,
                    code_lang="sql", explanation="Если подзапрос содержит NULL, `x NOT IN (...)` никогда не даёт TRUE.")


@family("sql.cross_join", S, 1, "numeric", "Декартово произведение", time_limit=90)
def sql_cross_join(rng: random.Random, _l):
    con, depts, emps = _gen_db(rng)
    sql = "SELECT COUNT(*) FROM employees, departments;"
    return Rendered(f"В таблице employees {len(emps)} строк, в departments — {len(depts)}. Что вернёт запрос?",
                    "numeric", _q(con, sql)[0][0], code=sql, code_lang="sql")


mcq("sql.where_having", S, 2, "Чем WHERE отличается от HAVING?", "WHERE фильтрует строки до группировки, HAVING — группы после",
    ["Ничем", "HAVING работает только с JOIN", "WHERE применяется после ORDER BY", "HAVING нельзя использовать с агрегатами"],
    topic="WHERE/HAVING")
mcq("sql.union", S, 2, "Чем UNION отличается от UNION ALL?", "UNION удаляет дубликаты строк, UNION ALL — нет",
    ["UNION ALL удаляет дубликаты", "UNION объединяет столбцы, а не строки", "UNION ALL работает только для двух таблиц",
     "Ничем"], topic="UNION")
mcq("sql.order_exec", S, 3, "В каком логическом порядке выполняются части SELECT-запроса?",
    "FROM → WHERE → GROUP BY → HAVING → SELECT → ORDER BY", ["SELECT → FROM → WHERE → GROUP BY → ORDER BY",
                                                             "FROM → SELECT → WHERE → ORDER BY → GROUP BY",
                                                             "WHERE → FROM → SELECT → HAVING → ORDER BY"],
    topic="Порядок выполнения")
mcq("sql.coalesce", S, 1, "Что вернёт `COALESCE(NULL, NULL, 7, 3)`?", "7", ["NULL", "3", "0", "Ошибку"], topic="COALESCE")

# =============================== Базы данных ===============================
DB = "databases"


@family("db.composite_index", DB, 4, "single", "Составные индексы", time_limit=150)
def db_composite_index(rng: random.Random, _l):
    x, y, z = rng.sample(["user_id", "status", "created_at", "country", "type", "org_id"], 3)
    tbl = rng.choice(["orders", "events", "payments", "tickets"])
    correct = f"`WHERE {y} = ? AND {z} = ?`"
    opts, key = options_from(rng, correct, [f"`WHERE {x} = ?`", f"`WHERE {x} = ? AND {y} = ?`",
                                            f"`WHERE {x} = ? AND {z} = ?`", f"`WHERE {x} = ? AND {y} > ?`"])
    return Rendered(f"На таблице `{tbl}` создан B-tree индекс `({x}, {y}, {z})`. Какое условие НЕ сможет использовать "
                    "этот индекс для поиска?", "single", key, options=opts,
                    explanation="Индекс используется по левому префиксу столбцов.")


mcq("db.acid_i", DB, 2, "За что отвечает буква I в ACID?", "Изоляция параллельных транзакций",
    ["Индексирование", "Идемпотентность", "Целостность (integrity)", "Инкрементальность"], topic="ACID")
mcq("db.isolation", DB, 4, "Какую аномалию исключает уровень Repeatable Read по стандарту SQL, но допускает Read Committed?",
    "Неповторяющееся чтение", ["Грязное чтение", "Потерянное обновление не исключается ни одним уровнем",
                               "Фантомное чтение", "Взаимоблокировку"], topic="Уровни изоляции")
mcq("db.n_plus_1", DB, 3, "Что такое проблема N+1 запросов в ORM?",
    "Загрузка списка одним запросом и связанных сущностей отдельным запросом для каждого элемента",
    ["Ошибка при вставке N+1 строк", "Переполнение пула соединений", "Дублирование первичных ключей",
     "Неэффективная пагинация"], topic="ORM")
mcq("db.btree_range", DB, 2, "Какой тип индекса поддерживает поиск по диапазону (`BETWEEN`, `>`)?", "B-tree",
    ["Hash", "Bitmap только для текста", "Никакой", "GIN только для JSON"], topic="Индексы")
mcq("db.normal3", DB, 3, "Что требует третья нормальная форма (3НФ)?",
    "Отсутствие транзитивных зависимостей неключевых атрибутов от ключа",
    ["Наличие суррогатного ключа", "Хранение всех данных в одной таблице", "Отсутствие NULL",
     "Индекс на каждом столбце"], topic="Нормализация")
mcq("db.deadlock", DB,3, "Как обычно СУБД разрешает взаимоблокировку (deadlock) транзакций?",
    "Обнаруживает цикл ожидания и откатывает одну из транзакций", ["Ждёт бесконечно", "Перезагружается",
                                                                    "Фиксирует обе транзакции",
                                                                    "Переводит базу в режим только чтения"],
    topic="Блокировки")
mcq("db.mvcc", DB, 4, "Как MVCC в PostgreSQL позволяет читателям не блокировать писателей?",
    "Каждая транзакция видит согласованный снимок версий строк", ["Чтение выполняется из реплики",
                                                                   "Писатели ставят эксклюзивную блокировку таблицы",
                                                                   "Данные кэшируются в памяти клиента",
                                                                   "Изменения записываются только при COMMIT в отдельный файл"],
    topic="MVCC")
mcq("db.sharding", DB, 3, "Чем шардирование отличается от репликации?",
    "Шардирование делит данные между узлами, репликация копирует одни и те же данные",
    ["Ничем", "Репликация делит данные по ключу", "Шардирование нужно только для чтения", "Репликация всегда синхронная"],
    topic="Масштабирование БД")
mcq("db.optimistic", DB, 4, "Как реализуется оптимистическая блокировка при обновлении записи?",
    "Через проверку версии: `UPDATE ... SET version = version + 1 WHERE id = ? AND version = ?`",
    ["Через `SELECT ... FOR UPDATE`", "Через блокировку таблицы", "Через уровень изоляции Serializable всегда",
     "Через триггер на удаление"], topic="Конкурентный доступ")
mcq("db.explain", DB, 3, "Для чего используют `EXPLAIN ANALYZE`?", "Чтобы увидеть фактический план выполнения запроса и время шагов",
    ["Чтобы проверить синтаксис", "Чтобы создать индекс автоматически", "Чтобы очистить кэш", "Чтобы откатить транзакцию"],
    topic="Оптимизация запросов")
mcq("db.vacuum", DB, 5, "Зачем в PostgreSQL нужен VACUUM?", "Освобождает место от «мёртвых» версий строк и предотвращает "
    "переполнение счётчика транзакций", ["Пересоздаёт все индексы", "Сжимает WAL", "Удаляет неиспользуемые таблицы",
                                         "Сбрасывает статистику"], topic="PostgreSQL")

# =============================== HTTP и API ===============================
H = "http_api"
_STATUS = [
    ("Ресурс успешно создан запросом POST", "201 Created"),
    ("Удаление прошло успешно, тело ответа не нужно", "204 No Content"),
    ("Запрос без токена к защищённому ресурсу", "401 Unauthorized"),
    ("Токен валиден, но у пользователя нет прав на ресурс", "403 Forbidden"),
    ("Запрошенный заказ не существует", "404 Not Found"),
    ("Попытка создать пользователя с уже занятым email", "409 Conflict"),
    ("Клиент превысил лимит запросов", "429 Too Many Requests"),
    ("Сервис временно перегружен и просит повторить позже", "503 Service Unavailable"),
    ("Ресурс навсегда перемещён на новый URL", "301 Moved Permanently"),
    ("Ресурс не изменился с момента, указанного в If-None-Match", "304 Not Modified"),
]


@family("http.status", H, 1, "single", "Коды ответа HTTP", time_limit=60)
def http_status(rng: random.Random, _l):
    sit, code = rng.choice(_STATUS)
    others = [c for _, c in _STATUS if c != code] + ["200 OK", "400 Bad Request", "500 Internal Server Error"]
    opts, key = options_from(rng, code, rng.sample(others, 5))
    return Rendered(f"Какой код ответа наиболее уместен? Ситуация: **{sit.lower()}**.", "single", key, options=opts)


@family("http.token_bucket", H, 4, "numeric", "Rate limiting: token bucket", time_limit=180)
def http_token_bucket(rng: random.Random, _l):
    cap, rate = rng.choice([3, 4, 5]), rng.choice([1, 2])
    times = sorted(round(rng.uniform(0, 4), 1) for _ in range(rng.randint(9, 12)))
    tokens, last, ok = float(cap), 0.0, 0
    for t in times:
        tokens = min(cap, tokens + (t - last) * rate)
        last = t
        if tokens >= 1:
            tokens -= 1
            ok += 1
    return Rendered(f"Лимитер «token bucket»: ёмкость {cap} токенов, пополнение {rate} токен/с (непрерывно), в момент 0 "
                    f"ведро полное. Запросы приходят в моменты (с): `{', '.join(map(str, times))}`. Каждый запрос "
                    "забирает 1 токен или отклоняется. Сколько запросов будет принято?", "numeric", ok)


multi("http.idempotent", H, 2, "Какие методы HTTP идемпотентны по спецификации?", ["GET", "PUT", "DELETE", "HEAD"],
      ["POST", "PATCH"], topic="Идемпотентность", show=5)
mcq("http.rest_naming", H, 2, "Какой URL лучше соответствует REST-стилю для получения заказов пользователя 42?",
    "`GET /users/42/orders`", ["`GET /getUserOrders?id=42`", "`POST /users/42/orders/get`", "`GET /orders/getByUser/42`",
                               "`PUT /users/42/orders`"], topic="Проектирование REST")
mcq("http.cursor", H, 4, "Почему для больших и часто меняющихся лент предпочитают курсорную пагинацию, а не OFFSET?",
    "OFFSET требует пропустить N строк и даёт дубли/пропуски при вставках; курсор стабилен и быстр",
    ["Курсорная пагинация позволяет перейти сразу на страницу 500", "OFFSET не поддерживается в PostgreSQL",
     "Курсор не требует индексов", "OFFSET работает только с UUID"], topic="Пагинация")
mcq("http.etag", H, 3, "Как работает условный запрос с ETag?",
    "Клиент присылает If-None-Match со старым ETag, сервер отвечает 304, если ресурс не изменился",
    ["ETag шифрует тело ответа", "ETag задаёт время жизни кэша", "Сервер всегда отвечает 200 с пустым телом",
     "ETag используется для аутентификации"], topic="Кэширование HTTP")
mcq("http.http2", H, 4, "Какую проблему HTTP/1.1 решает мультиплексирование в HTTP/2?",
    "Блокировку очереди запросов в одном соединении (head-of-line на уровне HTTP)",
    ["Отсутствие шифрования", "Отсутствие заголовков", "Невозможность передавать JSON", "Ограничение размера cookie"],
    topic="HTTP/2")
mcq("http.idempotency_key", H, 4, "Зачем платёжному API заголовок Idempotency-Key у POST-запроса?",
    "Чтобы повтор запроса после таймаута не создал второй платёж", ["Для аутентификации клиента",
                                                                     "Для шифрования тела", "Для сжатия ответа",
                                                                     "Для выбора версии API"], topic="Идемпотентность")
mcq("http.grpc", H, 3, "Чем gRPC отличается от типичного REST/JSON API?",
    "Строгий контракт в protobuf, бинарная сериализация и HTTP/2 со стримингом",
    ["gRPC работает только в браузере", "gRPC не поддерживает типы", "gRPC использует только XML",
     "gRPC не требует схемы"], topic="gRPC")
mcq("http.safe", H, 1, "Какой метод HTTP считается безопасным (не изменяет состояние сервера)?", "GET",
    ["POST", "DELETE", "PATCH", "PUT"], topic="Методы HTTP")
mcq("http.websocket", H, 2, "Когда WebSocket предпочтительнее обычных HTTP-запросов?",
    "Когда нужна двусторонняя передача событий в реальном времени", ["Для загрузки статических файлов",
                                                                      "Для кэширования ответов",
                                                                      "Для SEO", "Для отправки форм"],
    topic="WebSocket")
mcq("http.versioning", H, 3, "Какое изменение API обратно несовместимо?", "Переименование обязательного поля в ответе",
    ["Добавление нового необязательного поля в ответ", "Добавление нового эндпоинта",
     "Добавление необязательного query-параметра", "Ускорение ответа"], topic="Версионирование API")

# =============================== Архитектура ===============================
A = "architecture"


@family("arch.availability", A, 3, "numeric", "Доступность цепочки сервисов", time_limit=180)
def arch_availability(rng: random.Random, _l):
    a1, a2 = rng.choice([99.9, 99.5, 99.0, 99.95]), rng.choice([99.9, 99.5, 99.0, 98.0])
    parallel = rng.random() < 0.5
    if parallel:
        a = (1 - (1 - a1 / 100) * (1 - a1 / 100)) * a2 / 100 * 100
        q = (f"Запрос проходит через балансировщик к одному из двух независимых экземпляров сервиса A (доступность каждого "
             f"{a1}%, достаточно одного живого), затем в базу B ({a2}%).")
    else:
        a = a1 * a2 / 100
        q = f"Запрос последовательно проходит через сервис A ({a1}%) и сервис B ({a2}%), сбои независимы."
    return Rendered(f"{q} Какова итоговая доступность, %? Ответ округлите до сотых.", "numeric", round(a, 2), tolerance=0.011)


@family("arch.littles_law", A, 4, "numeric", "Закон Литтла и ёмкость", time_limit=150)
def arch_littles_law(rng: random.Random, _l):
    rps = rng.choice([200, 400, 500, 800, 1200])
    lat = rng.choice([50, 100, 150, 250])
    return Rendered(f"Сервис получает {rps} запросов в секунду, среднее время обработки — {lat} мс. Сколько запросов "
                    "в среднем обрабатывается одновременно (в системе)?", "numeric", rps * lat / 1000, tolerance=0.5,
                    explanation="Закон Литтла: L = λ · W.")


@family("arch.cache_latency", A, 2, "numeric", "Эффективность кэша", time_limit=120)
def arch_cache_latency(rng: random.Random, _l):
    hit = rng.choice([0.8, 0.9, 0.95, 0.7])
    tc, td = rng.choice([1, 2, 5]), rng.choice([40, 50, 100, 120])
    return Rendered(f"Доля попаданий в кэш {int(hit * 100)}%. Ответ из кэша — {tc} мс, промах (кэш + БД) — {td} мс. "
                    "Каково среднее время ответа, мс?", "numeric", round(hit * tc + (1 - hit) * td, 2), tolerance=0.05)


mcq("arch.at_least_once", A, 3, "Брокер гарантирует доставку «at-least-once». Что нужно сделать в потребителе?",
    "Сделать обработку идемпотентной (дедупликация по id сообщения)", ["Ничего, дублей не будет",
                                                                        "Отключить подтверждения", "Читать только из одной партиции",
                                                                        "Увеличить таймаут"], topic="Гарантии доставки")
mcq("arch.cap", A, 3, "Что утверждает теорема CAP?", "При сетевом разделении распределённая система вынуждена выбирать "
    "между согласованностью и доступностью", ["Система не может быть быстрой и дешёвой одновременно",
                                              "Любая БД обеспечивает все три свойства", "Кэш всегда согласован",
                                              "Шардирование невозможно без репликации"], topic="CAP")
mcq("arch.circuit_breaker", A, 3, "Зачем нужен паттерн Circuit Breaker?", "Временно прекращать вызовы деградировавшей "
    "зависимости, чтобы не каскадировать отказ", ["Для шифрования трафика", "Для балансировки нагрузки",
                                                 "Для сжатия ответов", "Для миграций схемы"], topic="Отказоустойчивость")
mcq("arch.saga", A, 4, "Как согласовать бизнес-операцию, затрагивающую несколько микросервисов со своими БД?",
    "Сага: цепочка локальных транзакций с компенсирующими действиями", ["Распределённый JOIN",
                                                                         "Одна общая БД на все сервисы — единственный вариант",
                                                                         "Синхронные вызовы без обработки ошибок",
                                                                         "Двухфазный коммит через HTTP всегда"],
    topic="Распределённые транзакции")
mcq("arch.consistent_hashing", A, 4, "Чем полезно консистентное хеширование при добавлении узла в кластер кэшей?",
    "Перераспределяется лишь малая доля ключей, а не почти все", ["Ключи шифруются", "Все ключи остаются на старых узлах",
                                                                   "Кэш становится строго согласованным",
                                                                   "Пропадает необходимость в репликации"],
    topic="Распределённые кэши")
mcq("arch.cqrs", A, 4, "В чём суть CQRS?", "Разделение моделей записи (команд) и чтения (запросов)",
    ["Шифрование всех запросов", "Кэширование только команд", "Использование только NoSQL", "Один эндпоинт на все операции"],
    topic="CQRS")
mcq("arch.stateless", A, 2, "Что нужно для горизонтального масштабирования веб-сервиса за балансировщиком?",
    "Сделать экземпляры stateless: сессии и состояние — во внешнем хранилище", ["Увеличить RAM одного сервера",
                                                                                 "Хранить сессии в памяти процесса",
                                                                                 "Отключить балансировщик", "Использовать sticky-сессии всегда"],
    topic="Масштабирование")
mcq("arch.backpressure", A, 5, "Производитель шлёт события быстрее, чем потребитель успевает обрабатывать. Какой подход "
    "НЕ решает проблему?", "Неограниченно увеличивать очередь в памяти", ["Ограничить скорость производителя (backpressure)",
                                                                          "Масштабировать потребителей",
                                                                          "Буферизовать в персистентном брокере с лимитом",
                                                                          "Отбрасывать низкоприоритетные события"],
    topic="Backpressure")
mcq("arch.outbox", A, 5, "Как надёжно сохранить изменение в БД и опубликовать событие в брокер без распределённой транзакции?",
    "Transactional outbox: событие пишется в таблицу outbox в той же транзакции и публикуется отдельным процессом",
    ["Сначала опубликовать событие, потом записать в БД", "Публиковать событие из триггера БД по HTTP",
     "Использовать только кэш", "Записать событие в лог приложения"], topic="Outbox")

# =============================== Безопасность ===============================
SEC = "security"


@family("sec.entropy", SEC, 3, "numeric", "Стойкость паролей", time_limit=120)
def sec_entropy(rng: random.Random, _l):
    alpha = rng.choice([(26, "строчные латинские буквы"), (36, "строчные буквы и цифры"), (62, "буквы обоих регистров и цифры"),
                        (10, "только цифры")])
    n = rng.choice([6, 8, 10, 12])
    bits = n * math.log2(alpha[0])
    return Rendered(f"Пароль из {n} случайных символов, алфавит — {alpha[1]} ({alpha[0]} символов). Сколько бит энтропии? "
                    "Округлите до целого.", "numeric", round(bits), tolerance=1.0)


mcq("sec.sqli", SEC, 1, "Как надёжно защититься от SQL-инъекций?", "Параметризованные запросы (prepared statements)",
    ["Экранировать кавычки вручную", "Скрывать текст ошибок", "Использовать POST вместо GET", "Минифицировать SQL"],
    topic="SQL-инъекции")
mcq("sec.passwords", SEC, 2, "Как правильно хранить пароли пользователей?", "Медленный хеш с солью: Argon2, bcrypt или scrypt",
    ["SHA-256 без соли", "MD5 с солью", "Шифрование AES с ключом в конфиге", "Base64"], topic="Хранение паролей")
mcq("sec.csrf", SEC, 3, "Что защищает от CSRF при cookie-аутентификации?", "SameSite-cookie и CSRF-токен в форме/заголовке",
    ["HttpOnly", "HTTPS", "Длинный пароль", "CORS с `*`"], topic="CSRF")
mcq("sec.jwt", SEC, 4, "Какая ошибка при работе с JWT наиболее опасна?", "Принимать токен без проверки подписи "
    "или с `alg: none`", ["Хранить в токене id пользователя", "Использовать короткий срок жизни",
                          "Подписывать токен RS256", "Передавать токен в заголовке Authorization"], topic="JWT")
mcq("sec.idor", SEC, 3, "Пользователь меняет `/api/orders/1001` на `/api/orders/1002` и видит чужой заказ. Как называется "
    "уязвимость?", "IDOR — небезопасная прямая ссылка на объект", ["XSS", "CSRF", "SSRF", "Clickjacking"],
    topic="Контроль доступа")
mcq("sec.ssrf", SEC, 5, "Сервис скачивает файл по URL, переданному пользователем. Какой риск главный?",
    "SSRF: запросы к внутренним адресам (например, метаданным облака)", ["XSS", "Переполнение стека", "SQL-инъекция",
                                                                         "Утечка cookie через Referer"], topic="SSRF")
mcq("sec.secrets", SEC, 2, "Где НЕ следует хранить секреты (пароли БД, ключи API)?", "В репозитории с исходным кодом",
    ["В менеджере секретов (Vault и т. п.)", "В переменных окружения CI с маскированием", "В Kubernetes Secret с шифрованием",
     "В зашифрованном хранилище облака"], topic="Управление секретами")
mcq("sec.least_privilege", SEC, 2, "Что означает принцип наименьших привилегий?", "Выдавать только права, необходимые для задачи",
    ["Давать всем права администратора", "Отключать журналирование", "Использовать один общий аккаунт",
     "Запрещать любой доступ"], topic="Принципы безопасности")
mcq("sec.cors_not_auth", SEC, 4, "Почему CORS не является механизмом защиты API от несанкционированного доступа?",
    "CORS ограничивает только браузерные кросс-доменные запросы; curl или сервер его игнорируют",
    ["CORS шифрует запросы", "CORS работает только для GET", "CORS заменяет аутентификацию", "CORS включается только в HTTP/2"],
    topic="CORS")
