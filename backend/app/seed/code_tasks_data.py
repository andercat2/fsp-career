"""Демо-задачи с кодом: работодатель задаёт функцию, шаблон, открытые и скрытые тесты и эталон.

Эталоны проверяются в автотестах (tests/test_code_tasks_data.py): каждый проходит все свои тесты в песочнице.
"""

PHONES_REF = '''def normalize_phones(phones):
    seen, result = set(), []
    for raw in phones:
        digits = "".join(ch for ch in raw if ch.isdigit())
        if len(digits) == 10:
            digits = "7" + digits
        if len(digits) != 11 or digits[0] not in "78":
            continue
        number = "+7" + digits[1:]
        if number not in seen:
            seen.add(number)
            result.append(number)
    return result
'''

RATE_REF = '''from collections import deque


def allowed_requests(timestamps, limit, window):
    accepted = deque()
    out = []
    for t in timestamps:
        while accepted and accepted[0] <= t - window:
            accepted.popleft()
        ok = len(accepted) < limit
        if ok:
            accepted.append(t)
        out.append(ok)
    return out
'''

PLURAL_REF = '''function plural(n, one, few, many) {
  const a = Math.abs(n) % 100;
  const b = a % 10;
  if (a > 10 && a < 20) return many;
  if (b > 1 && b < 5) return few;
  if (b === 1) return one;
  return many;
}
'''

TOP_WORDS_REF = '''import re
from collections import Counter


def top_words(text, k):
    words = re.findall(r"[a-zа-яё0-9]+", text.lower())
    counts = Counter(words)
    return [[w, c] for w, c in sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:k]]
'''

CODE_TASKS = [
    {"company": "technopulse", "specialization": "backend", "grades": [], "kind": "code", "code_language": "python",
     "title": "Нормализация телефонных номеров", "entrypoint": "normalize_phones", "time_estimate_min": 20,
     "description": "Из формы заказа приходят телефоны в любом виде: `8 (900) 123-45-67`, `+7 900 1234567`, `9001234567`.\n\n"
                    "Напишите функцию `normalize_phones(phones)`, которая приводит российские номера к виду `+7XXXXXXXXXX`, "
                    "отбрасывает некорректные и убирает дубли, сохраняя порядок первого появления.",
     "starter_code": "def normalize_phones(phones):\n    # phones: список строк\n    # верните список номеров вида +7XXXXXXXXXX без дублей\n    pass\n",
     "reference_solution": PHONES_REF,
     "tests": [
         {"name": "разные форматы", "args": [["8 (900) 123-45-67", "+7 901 000 00 01"]], "expected": ["+79001234567", "+79010000001"]},
         {"name": "дубли и мусор", "args": [["89001234567", "+7 900 123 45 67", "123"]], "expected": ["+79001234567"]},
         {"args": [["9001234567"]], "expected": ["+79001234567"], "hidden": True},
         {"args": [[]], "expected": [], "hidden": True},
         {"args": [["+1 202 555 0100", "7 (999) 000-11-22"]], "expected": ["+79990001122"], "hidden": True},
         {"args": [["8-800-555-35-35", "88005553535", "8 800 555 35 36"]], "expected": ["+78005553535", "+78005553536"], "hidden": True},
     ]},
    {"company": "fintechlab", "specialization": "backend", "grades": ["middle", "senior"], "kind": "code", "code_language": "python",
     "title": "Ограничение частоты запросов к кредитному бюро", "entrypoint": "allowed_requests", "time_estimate_min": 25,
     "description": "Бюро принимает не больше `limit` запросов за любые `window` секунд. Время запросов `timestamps` идёт по "
                    "возрастанию.\n\nНапишите `allowed_requests(timestamps, limit, window)`: для каждого запроса верните "
                    "`True`, если его можно отправить (отклонённые запросы лимит не расходуют), иначе `False`.",
     "starter_code": "def allowed_requests(timestamps, limit, window):\n    pass\n",
     "reference_solution": RATE_REF,
     "tests": [
         {"name": "простое окно", "args": [[0, 1, 2, 3], 2, 10], "expected": [True, True, False, False]},
         {"name": "окно сдвигается", "args": [[0, 5, 10, 11], 2, 10], "expected": [True, True, True, False]},
         {"args": [[], 3, 5], "expected": [], "hidden": True},
         {"args": [[1, 1, 1, 2], 3, 1], "expected": [True, True, True, True], "hidden": True},
         {"args": [[0, 3, 6, 9, 12, 15], 2, 7], "expected": [True, True, False, True, True, False], "hidden": True},
     ]},
    {"company": "pixel", "specialization": "frontend", "grades": [], "kind": "code", "code_language": "javascript",
     "title": "Склонение слова после числа", "entrypoint": "plural", "time_estimate_min": 15,
     "description": "В интерфейсе нужно писать «1 задача», «3 задачи», «11 задач».\n\nНапишите функцию "
                    "`plural(n, one, few, many)`, которая возвращает правильную форму слова для числа `n`.",
     "starter_code": "function plural(n, one, few, many) {\n  // верните one, few или many\n}\n",
     "reference_solution": PLURAL_REF,
     "tests": [
         {"name": "1, 3, 5", "args": [1, "задача", "задачи", "задач"], "expected": "задача"},
         {"args": [3, "задача", "задачи", "задач"], "expected": "задачи"},
         {"args": [11, "задача", "задачи", "задач"], "expected": "задач", "hidden": True},
         {"args": [21, "задача", "задачи", "задач"], "expected": "задача", "hidden": True},
         {"args": [112, "задача", "задачи", "задач"], "expected": "задач", "hidden": True},
         {"args": [0, "задача", "задачи", "задач"], "expected": "задач", "hidden": True},
     ]},
    {"company": "medtech", "specialization": "data_analyst", "grades": [], "kind": "code", "code_language": "python",
     "title": "Частые слова в отзывах пациентов", "entrypoint": "top_words", "time_estimate_min": 15,
     "description": "Напишите `top_words(text, k)`: `k` самых частых слов текста без учёта регистра и знаков препинания — "
                    "список пар `[слово, количество]`, по убыванию частоты, при равенстве — по алфавиту.",
     "starter_code": "def top_words(text, k):\n    pass\n",
     "reference_solution": TOP_WORDS_REF,
     "tests": [
         {"name": "простой текст", "args": ["Врач хороший, врач внимательный", 1], "expected": [["врач", 2]]},
         {"args": ["а б а в б а", 2], "expected": [["а", 3], ["б", 2]]},
         {"args": ["", 3], "expected": [], "hidden": True},
         {"args": ["Да! да? ДА. нет", 5], "expected": [["да", 3], ["нет", 1]], "hidden": True},
     ]},
]

# Решения синтетических кандидатов: верное, частично верное и «переименованная копия» первого — для антиплагиата
PHONES_GOOD = '''import re


def normalize_phones(phones):
    result = []
    for raw in phones:
        digits = re.sub(r"\\D", "", raw)
        if len(digits) == 10:
            digits = "7" + digits
        if len(digits) == 11 and digits[0] in "78":
            phone = "+7" + digits[1:]
            if phone not in result:
                result.append(phone)
    return result
'''
PHONES_PARTIAL = '''def normalize_phones(phones):
    out = []
    for p in phones:
        d = "".join(c for c in p if c.isdigit())
        if len(d) == 11:
            out.append("+7" + d[1:])
    return out
'''
PHONES_COPY = '''import re


def normalize_phones(items):
    res = []
    for item in items:
        nums = re.sub(r"\\D", "", item)
        if len(nums) == 10:
            nums = "7" + nums
        if len(nums) == 11 and nums[0] in "78":
            p = "+7" + nums[1:]
            if p not in res:
                res.append(p)
    return res
'''
