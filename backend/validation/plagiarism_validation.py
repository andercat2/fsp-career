"""Валидация антиплагиата задач с кодом: отделяет ли порог сходства копии от независимых решений.

Корпус — четыре демо-задачи (app/seed/code_tasks_data.py). Для каждой есть эталон и независимые решения другого
стиля (в том числе частично верные), а также «замаскированные копии»: переименованные переменные, другие
комментарии и форматирование — так копию прячут на практике; одна копия дополнительно разбавлена неиспользуемым
кодом. Каждое решение сначала прогоняется в песочнице на тестах задачи — корпус проверен на корректность.
Метрики: доля обнаруженных копий и доля ложных срабатываний на парах независимых решений при пороге THRESHOLD.

Запуск: python -m validation.plagiarism_validation (входит в python -m validation.run_all).
"""
from __future__ import annotations

import time
from itertools import combinations
from types import SimpleNamespace

from app.seed.code_tasks_data import CODE_TASKS, PHONES_COPY, PHONES_GOOD, PHONES_PARTIAL
from app.services.sandbox import antiplagiarism as ap
from app.services.sandbox.antiplagiarism import THRESHOLD, similarity
from app.services.sandbox.runner import available_languages
from app.services.sandbox.tasks import evaluate
from validation.common import r3, save_report

# --- независимые решения (другой подход или стиль)
PHONES_ALT = '''import re

PATTERN = re.compile(r"^(?:\\+7|8|7)?(\\d{10})$")


def normalize_phones(phones):
    seen = []
    for raw in phones:
        compact = re.sub(r"[\\s()\\-]", "", raw)
        m = PATTERN.match(compact)
        if not m:
            continue
        phone = "+7" + m.group(1)
        if phone not in seen:
            seen.append(phone)
    return seen
'''
PHONES_FUNC = '''def normalize_phones(phones):
    def canon(s):
        d = [ch for ch in s if ch.isdigit()]
        if len(d) == 10:
            d.insert(0, "7")
        return "+7" + "".join(d[1:]) if len(d) == 11 and d[0] in ("7", "8") else None
    return list(dict.fromkeys(p for p in map(canon, phones) if p))
'''
RATE_LIST = '''def allowed_requests(timestamps, limit, window):
    accepted = []
    result = []
    for t in timestamps:
        recent = [a for a in accepted if a > t - window]
        if len(recent) < limit:
            recent.append(t)
            result.append(True)
        else:
            result.append(False)
        accepted = recent
    return result
'''
RATE_BISECT = '''from bisect import bisect_right


def allowed_requests(timestamps, limit, window):
    ok_times, answer = [], []
    for ts in timestamps:
        start = bisect_right(ok_times, ts - window)
        allowed = len(ok_times) - start < limit
        if allowed:
            ok_times.append(ts)
        answer.append(allowed)
    return answer
'''
PLURAL_SWITCH = '''function plural(n, one, few, many) {
  n = Math.abs(n);
  if ([11, 12, 13, 14].includes(n % 100)) return many;
  switch (n % 10) {
    case 1: return one;
    case 2: case 3: case 4: return few;
    default: return many;
  }
}
'''
PLURAL_ARROW = '''const plural = (n, one, few, many) => {
  const forms = [one, few, many];
  const k = Math.abs(n);
  const idx = k % 10 === 1 && k % 100 !== 11 ? 0
    : k % 10 >= 2 && k % 10 <= 4 && (k % 100 < 10 || k % 100 >= 20) ? 1 : 2;
  return forms[idx];
};
'''
WORDS_LOOP = '''def top_words(text, k):
    counts = {}
    word = ""
    for ch in text.lower() + " ":
        if ch.isalnum():
            word += ch
        elif word:
            counts[word] = counts.get(word, 0) + 1
            word = ""
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [[w, n] for w, n in ranked[:k]]
'''
WORDS_SPLIT = '''import collections
import re


def top_words(text, k):
    tokens = re.split(r"[^\\w]+", text.lower())
    freq = collections.Counter(t for t in tokens if t)
    best = sorted(freq, key=lambda w: (-freq[w], w))[:k]
    return [[w, freq[w]] for w in best]
'''

# --- замаскированные копии эталонов: переименование, комментарии, форматирование
PHONES_REF_COPY = '''def normalize_phones(numbers):
    used, out = set(), []
    for s in numbers:
        ds = "".join(c for c in s if c.isdigit())
        if len(ds) == 10:
            ds = "7" + ds
        if len(ds) != 11 or ds[0] not in "78":
            continue  # не российский номер
        n = "+7" + ds[1:]
        if n not in used:
            used.add(n)
            out.append(n)
    return out
'''
RATE_REF_COPY = '''from collections import deque


def allowed_requests(timestamps, limit, window):
    # очередь принятых запросов
    q = deque()
    res = []
    for ts in timestamps:
        while q and q[0] <= ts - window:  # выкидываем устаревшие
            q.popleft()
        can = len(q) < limit
        if can:
            q.append(ts)
        res.append(can)
    return res
'''
RATE_REF_PADDED = '''from collections import deque

DEBUG = False


def _log(*args):
    if DEBUG:
        print(*args)


def allowed_requests(timestamps, limit, window):
    window_queue = deque()
    decisions = []
    for moment in timestamps:
        _log("request", moment)
        while window_queue and window_queue[0] <= moment - window:
            window_queue.popleft()
        accepted = len(window_queue) < limit
        if accepted:
            window_queue.append(moment)
        decisions.append(accepted)
    _log("done", len(decisions))
    return decisions
'''
PLURAL_REF_COPY = '''function plural(num, f1, f2, f5) {
  // остаток по модулю 100 и 10
  const x = Math.abs(num) % 100;
  const y = x % 10;
  if (x > 10 && x < 20) { return f5; }
  if (y > 1 && y < 5) { return f2; }
  if (y === 1) { return f1; }
  return f5;
}
'''
WORDS_REF_COPY = '''import re
from collections import Counter


def top_words(text, k):
    # все слова в нижнем регистре
    tokens = re.findall(r"[a-zа-яё0-9]+", text.lower())
    c = Counter(tokens)
    return [[word, cnt] for word, cnt in sorted(c.items(), key=lambda p: (-p[1], p[0]))[:k]]
'''

# решения задачи: имя → код; копии: (имя копии, имя оригинала, код копии, как замаскирована)
CORPUS = {
    "normalize_phones": {
        "solutions": {"эталон": None, "регулярное выражение (демо)": PHONES_GOOD, "частичное (демо)": PHONES_PARTIAL,
                      "fullmatch-шаблон": PHONES_ALT, "функциональный стиль": PHONES_FUNC},
        "copies": [("копия эталона", "эталон", PHONES_REF_COPY, "переименование, комментарий"),
                   ("копия демо-решения", "регулярное выражение (демо)", PHONES_COPY, "переименование")]},
    "allowed_requests": {
        "solutions": {"эталон": None, "фильтрация списка": RATE_LIST, "бинарный поиск": RATE_BISECT},
        "copies": [("копия эталона", "эталон", RATE_REF_COPY, "переименование, комментарии"),
                   ("копия с балластом", "эталон", RATE_REF_PADDED,
                    "переименование, неиспользуемые функция и вызовы логирования")]},
    "plural": {
        "solutions": {"эталон": None, "switch": PLURAL_SWITCH, "стрелочная функция": PLURAL_ARROW},
        "copies": [("копия эталона", "эталон", PLURAL_REF_COPY, "переименование, фигурные скобки, комментарий")]},
    "top_words": {
        "solutions": {"эталон": None, "посимвольный разбор": WORDS_LOOP, "re.split + Counter": WORDS_SPLIT},
        "copies": [("копия эталона", "эталон", WORDS_REF_COPY, "переименование, комментарий")]},
}


def _pairs() -> tuple[list, list]:
    """(сходство копий с оригиналами, сходство пар независимых решений) при текущих параметрах антиплагиата."""
    cs, ins = [], []
    for task in CODE_TASKS:
        corpus = CORPUS[task["entrypoint"]]
        lang, template = task["code_language"], task["starter_code"]
        sols = {k: (v if v is not None else task["reference_solution"]) for k, v in corpus["solutions"].items()}
        ins += [similarity(a, b, lang, template) for (_, a), (_, b) in combinations(sols.items(), 2)]
        cs += [similarity(code, sols[orig], lang, template) for _, orig, code, _ in corpus["copies"]]
    return cs, ins


def sweep() -> list[dict]:
    """Перебор длины k-граммы и окна winnowing: параметры выбраны на этом корпусе, перебор показан целиком."""
    k0, w0 = ap.K, ap.WINDOW
    rows = []
    try:
        for k in (4, 5, 6):
            for w in (3, 4):
                ap.K, ap.WINDOW = k, w
                cs, ins = _pairs()
                rows.append({"k": k, "window": w, "copies_detected": sum(s >= THRESHOLD for s in cs),
                             "copies_min": min(cs), "independent_false_positives": sum(s >= THRESHOLD for s in ins),
                             "independent_max": max(ins), "chosen": (k, w) == (k0, w0)})
    finally:
        ap.K, ap.WINDOW = k0, w0
    return rows


def main() -> dict:
    t0 = time.time()
    langs = available_languages()
    tasks, copies, independent, checked = [], [], [], []
    for task in CODE_TASKS:
        corpus = CORPUS[task["entrypoint"]]
        lang, template = task["code_language"], task["starter_code"]
        spec = SimpleNamespace(**task, time_limit_ms=4000, compare="exact")
        sols = {k: (v if v is not None else task["reference_solution"]) for k, v in corpus["solutions"].items()}
        # корректность корпуса: каждое решение и каждая копия исполняются на тестах задачи
        if lang in langs:
            for name, code in [*sols.items(), *((c[0], c[2]) for c in corpus["copies"])]:
                res = evaluate(spec, code)
                checked.append({"task": task["entrypoint"], "solution": name, "passed": res["passed"], "total": res["total"]})
        for (na, a), (nb, b) in combinations(sols.items(), 2):
            independent.append({"task": task["entrypoint"], "a": na, "b": nb, "similarity": similarity(a, b, lang, template)})
        for name, orig, code, how in corpus["copies"]:
            copies.append({"task": task["entrypoint"], "copy": name, "of": orig, "disguise": how,
                           "similarity": similarity(code, sols[orig], lang, template)})
        tasks.append({"entrypoint": task["entrypoint"], "language": lang, "solutions": len(sols),
                      "copies": len(corpus["copies"])})
    cs = [c["similarity"] for c in copies]
    ins = [p["similarity"] for p in independent]
    report = {
        "threshold": THRESHOLD, "tasks": tasks,
        "copies": {"n": len(cs), "detected": sum(s >= THRESHOLD for s in cs),
                   "detection_rate": r3(sum(s >= THRESHOLD for s in cs) / len(cs)), "min": min(cs),
                   "mean": r3(sum(cs) / len(cs)), "items": copies},
        "independent_pairs": {"n": len(ins), "false_positives": sum(s >= THRESHOLD for s in ins),
                              "false_positive_rate": r3(sum(s >= THRESHOLD for s in ins) / len(ins)), "max": max(ins),
                              "mean": r3(sum(ins) / len(ins)), "items": independent},
        "corpus_check": {"all_correct_or_expected_partial": all(
            c["passed"] == c["total"] or c["solution"].startswith("частичное") for c in checked), "items": checked},
        "parameters": {"k": ap.K, "window": ap.WINDOW, "sweep": sweep()},
        "runtime_sec": round(time.time() - t0, 1),
    }
    save_report("plagiarism_validation", report)
    return report


if __name__ == "__main__":
    r = main()
    print(f"Копии: обнаружено {r['copies']['detected']} из {r['copies']['n']}, минимум сходства {r['copies']['min']}")
    print(f"Независимые пары: ложных срабатываний {r['independent_pairs']['false_positives']} из "
          f"{r['independent_pairs']['n']}, максимум сходства {r['independent_pairs']['max']}")
    for c in r["copies"]["items"]:
        print(f"  {c['task']:17s} {c['copy']:22s} {c['similarity']:.3f}  ({c['disguise']})")
    for p in sorted(r["independent_pairs"]["items"], key=lambda x: -x["similarity"])[:6]:
        print(f"  {p['task']:17s} {p['a']} ~ {p['b']}: {p['similarity']:.3f}")
    for row in r["parameters"]["sweep"]:
        print("  k={k} окно={window}: копий найдено {copies_detected}, минимум {copies_min}; ложных {independent_false_positives}, "
              "максимум {independent_max}{m}".format(**row, m=" ← выбрано" if row["chosen"] else ""))
    print("корпус корректен:", r["corpus_check"]["all_correct_or_expected_partial"],
          [(c["solution"], c["passed"], c["total"]) for c in r["corpus_check"]["items"] if c["passed"] != c["total"]])
