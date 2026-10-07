"""Разбор текстового описания потребности работодателя (вакансии) в структурированный запрос на подбор.

Специализация определяется гибридом двух моделей:
  1) TF-IDF (символьные n-граммы, устойчивы к русской морфологии) + логистическая регрессия,
     обученная на синтетическом корпусе, порождённом из онлайн-справочника навыков и ролевых фраз;
  2) «правила по онтологии»: вклад найденных навыков в характерные для специализаций наборы + сигнал из заголовка.
Итоговая вероятность — взвешенная смесь (0.4 · модель + 0.6 · правила); уверенность и топ-альтернативы возвращаются для UI.
"""
from __future__ import annotations

import math
import random
import re
from functools import lru_cache

from app.services.nlp.salary import is_net, net_to_gross_monthly
from app.services.reference.skills import SKILL_BY_ID, extract_skills, skills_for_spec
from app.services.reference.taxonomy import GRADE_CODES, SPEC_BY_CODE, SPECIALIZATIONS

ROLE_PHRASES = {
    "backend": ["бэкенд-разработчик", "backend developer", "разработка серверной части", "проектирование REST API",
                "высоконагруженные сервисы", "интеграции с внешними системами", "оптимизация запросов к базе данных",
                "микросервисная архитектура", "серверная разработка", "разработка API для мобильных и веб-клиентов",
                "брокеры сообщений", "бизнес-логика платёжного сервиса", "Python-разработчик", "Java-разработчик",
                "Go-разработчик", "разработчик серверных приложений", "backend engineer"],
    "frontend": ["фронтенд-разработчик", "frontend developer", "разработка пользовательских интерфейсов",
                 "адаптивная вёрстка", "SPA-приложение", "UI-компоненты и дизайн-система", "кроссбраузерная вёрстка",
                 "интерфейсы личного кабинета", "оптимизация производительности в браузере", "работа с макетами в Figma",
                 "React-разработчик", "фронтенд разработчик", "разработчик интерфейсов", "Vue-разработчик",
                 "JavaScript-разработчик", "frontend engineer"],
    "fullstack": ["fullstack-разработчик", "фулстек-разработчик", "full stack developer", "полный цикл разработки веб-приложений",
                  "и фронтенд, и бэкенд", "от интерфейса до базы данных", "разработка фич end-to-end",
                  "разработчик полного цикла", "fullstack engineer"],
    "ml": ["data scientist", "ML-инженер", "машинное обучение", "обучение и вывод моделей в продакшен",
           "feature engineering", "нейросетевые модели", "рекомендательная система", "компьютерное зрение",
           "обработка естественного языка", "эксперименты с моделями", "LLM и RAG", "инженер машинного обучения",
           "ML-разработчик"],
    "data_analyst": ["аналитик данных", "продуктовый аналитик", "data analyst", "построение дашбордов",
                     "проведение A/B-тестов", "продуктовые метрики", "отчётность для бизнеса", "BI-аналитика",
                     "исследование поведения пользователей", "SQL-запросы к хранилищу"],
    "devops": ["DevOps-инженер", "SRE-инженер", "инфраструктура как код", "настройка CI/CD", "эксплуатация Kubernetes",
               "мониторинг и алертинг", "отказоустойчивость сервисов", "администрирование Linux", "автоматизация деплоя",
               "облачная инфраструктура", "инженер DevOps", "инфраструктурный инженер", "platform engineer"],
    "qa": ["QA-инженер", "тестировщик", "инженер по тестированию", "тест-кейсы и чек-листы", "регрессионное тестирование",
           "автоматизация тестирования", "заведение баг-репортов", "тестирование API", "контроль качества релизов",
           "тест-дизайн", "QA automation engineer", "разработчик автотестов"],
}
TITLE_CUES = {
    "backend": r"back[- ]?end|бэк[- ]?энд|бекенд|бэкенд|серверн",
    "frontend": r"front[- ]?end|фронт[- ]?енд|фронтенд|верстальщик|react[- ]разработ|vue[- ]разработ",
    "fullstack": r"full[- ]?stack|фулл?[- ]?стек",
    "ml": r"data scien|ml[- ]|machine learning|машинн\w* обучени|нейросет|computer vision|nlp",
    "data_analyst": r"аналитик|analyst|bi[- ]",
    "devops": r"devops|sre|инфраструктур|платформенн|администратор linux",
    "qa": r"\bqa\b|тестировщ|тестирован|quality assurance|aqa|автотест",
}
_NOISE = ["Мы — продуктовая команда.", "Гибкий график и ДМС.", "Работаем по Scrum.", "Современный стек и код-ревью.",
          "Белая зарплата.", "Обучение за счёт компании.", "Команда из 8 человек.", "Релизы каждую неделю."]


def _synthetic_corpus(n_per_class: int = 220, seed: int = 7) -> tuple[list[str], list[str]]:
    rng = random.Random(seed)
    texts, labels = [], []
    for sp in SPECIALIZATIONS:
        code = sp["code"]
        own = [s.name for s in skills_for_spec(code)]
        other = [s.name for s in SKILL_BY_ID.values() if code not in s.specs]
        front = [s.name for s in skills_for_spec("frontend")]
        back = [s.name for s in skills_for_spec("backend")]
        for _ in range(n_per_class):
            parts = rng.sample(ROLE_PHRASES[code], rng.randint(1, 3))
            if code == "fullstack":  # фулстек — это сочетание сигналов фронтенда и бэкенда
                parts += rng.sample(front, rng.randint(1, 3)) + rng.sample(back, rng.randint(1, 3))
            parts += rng.sample(own, min(len(own), rng.randint(2, 6)))
            parts += rng.sample(other, rng.randint(0, 2))
            parts += rng.sample(_NOISE, rng.randint(0, 2))
            rng.shuffle(parts)
            texts.append(". ".join(parts))
            labels.append(code)
    return texts, labels


@lru_cache(maxsize=1)
def _model():
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline

    texts, labels = _synthetic_corpus()
    pipe = make_pipeline(TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True, min_df=2),
                         LogisticRegression(max_iter=2000, C=4.0))
    pipe.fit(texts, labels)
    return pipe


def _softmax(scores: dict[str, float]) -> dict[str, float]:
    m = max(scores.values())
    ex = {k: math.exp(v - m) for k, v in scores.items()}
    s = sum(ex.values())
    return {k: v / s for k, v in ex.items()}


def classify_specialization(text: str, title: str = "") -> dict:
    full = f"{title}. {text}".strip()
    model = _model()
    proba = dict(zip(model.classes_, model.predict_proba([full])[0], strict=True))
    found = extract_skills(full)
    rules = {sp["code"]: 0.0 for sp in SPECIALIZATIONS}
    for s in found:
        sk = SKILL_BY_ID[s["id"]]
        for spec in sk.specs:
            rules[spec] += min(s["count"], 3) / max(len(sk.specs), 1)
    low_title = (title or full[:120]).lower()
    for code, pat in TITLE_CUES.items():
        if re.search(pat, low_title):
            rules[code] += 4.0
    # fullstack = одновременно сильные сигналы фронта и бэка
    rules["fullstack"] += 0.5 * min(rules["frontend"], rules["backend"])
    rules_p = _softmax({k: v / 1.5 for k, v in rules.items()})
    combined = {k: float(0.4 * proba.get(k, 0) + 0.6 * rules_p[k]) for k in rules}
    best = max(combined, key=combined.get)
    ranked = sorted(combined.items(), key=lambda kv: -kv[1])
    return {"specialization": best, "confidence": round(combined[best], 3),
            "alternatives": [{"code": k, "p": round(v, 3)} for k, v in ranked[:3]],
            "model_p": {str(k): round(float(v), 3) for k, v in proba.items()}, "rules_p": {k: round(v, 3) for k, v in rules_p.items()}}


_GRADE_WORDS = [
    ("senior", r"\bsenior\b|сеньор|синьор|ведущ\w+|старш\w+|\blead\b|тимлид|техлид|лид\b|руководител"),
    ("middle", r"\bmiddle\b|мидл|middle\+"),
    ("junior", r"\bjunior\b|джун|младш\w+"),
    ("intern", r"стаж[её]р|стажировк|\bintern\b|без опыта|студент"),
]


def extract_grades(text: str) -> tuple[list[str], int | None]:
    low = text.lower()
    grades = {g for g, pat in _GRADE_WORDS if re.search(pat, low)}
    years = None
    m = re.search(r"опыт\w*[^.\n]{0,40}?(?:от|не менее|более|больше)?\s*(\d{1,2})\s*(?:\+|-х|х)?\s*(?:лет|года|год)", low)
    if m is None:
        m = re.search(r"(\d{1,2})\+?\s*(?:years|year)", low)
    if m:
        years = int(m.group(1))
        g = "senior" if years >= 5 else "middle" if years >= 2 else "junior" if years >= 1 else "intern"
        grades.add(g)
    ordered = [g for g in GRADE_CODES if g in grades]
    return ordered, years


def _money(num: str, suffix: str | None) -> int:
    v = float(num.replace(" ", "").replace(" ", "").replace(",", "."))
    suf = (suffix or "").lower()
    if suf.startswith(("k", "к", "тыс")) or v < 1000:
        v *= 1000
    return int(v)


_NUM = r"(\d[\d  ]{0,9}(?:[.,]\d+)?)"
_SUF = r"\s*(k|к|тыс\.?|000)?"


def extract_salary(text: str) -> tuple[int | None, int | None]:
    low = text.lower()
    m = re.search(rf"от\s*{_NUM}{_SUF}\s*(?:₽|руб\.?)?\s*до\s*{_NUM}{_SUF}", low)
    if m:
        return _money(m.group(1), m.group(2) or m.group(4)), _money(m.group(3), m.group(4))
    m = re.search(rf"{_NUM}{_SUF}\s*(?:₽|руб\.?)?\s*[-–—]\s*{_NUM}{_SUF}\s*(?:₽|руб|тыс|k|к)", low)
    if m:
        return _money(m.group(1), m.group(2) or m.group(4)), _money(m.group(3), m.group(4))
    m_from = re.search(rf"(?:зарплата|доход|оклад|вилка)?[^.\n]{{0,20}}от\s*{_NUM}{_SUF}\s*(?:₽|руб)", low)
    m_to = re.search(rf"до\s*{_NUM}{_SUF}\s*(?:₽|руб)", low)
    lo = _money(m_from.group(1), m_from.group(2)) if m_from else None
    hi = _money(m_to.group(1), m_to.group(2)) if m_to else None
    return lo, hi


CITIES = ["Москва", "Санкт-Петербург", "Казань", "Новосибирск", "Екатеринбург", "Нижний Новгород", "Томск", "Иннополис",
          "Самара", "Краснодар", "Владивосток", "Ростов-на-Дону", "Пермь", "Уфа", "Воронеж", "Калининград", "Тюмень",
          "Челябинск", "Красноярск", "Омск", "Саратов", "Ярославль", "Сочи"]
_CITY_STEMS = {c: c.lower()[: max(4, len(c) - 2)] for c in CITIES}
_CITY_STEMS["Санкт-Петербург"] = "петербург"
_CITY_STEMS["Москва"] = "москв"


def extract_city(text: str) -> str | None:
    low = text.lower()
    for city, stem in _CITY_STEMS.items():
        if stem in low:
            return city
    return None


def extract_format(text: str) -> str | None:
    low = text.lower()
    if re.search(r"гибрид|hybrid|частично удал", low):
        return "hybrid"
    if re.search(r"удал[её]н|remote|дистанц|из любой точки", low):
        return "remote"
    if re.search(r"офис|office|on-?site", low):
        return "office"
    return None


_NICE_RE = re.compile(r"будет плюсом|плюсом будет|желательно|nice to have|преимуществ|приветствуется|будет здорово|"
                      r"бонусом|дополнительно", re.I)
_MUST_HDR = re.compile(r"требовани|ожидаем|необходим|обязательн|что нужно|что важно|must have|нам важно", re.I)


def split_must_nice(text: str) -> tuple[list[str], list[str]]:
    must: list[str] = []
    nice: list[str] = []
    mode = "must"
    for line in re.split(r"[\n;]+|(?<=[.!?])\s+", text):
        if not line.strip():
            continue
        if _NICE_RE.search(line):
            mode = "nice"
        elif _MUST_HDR.search(line):
            mode = "must"
        ids = [s["id"] for s in extract_skills(line, context=text)]
        target = nice if (mode == "nice" or _NICE_RE.search(line)) else must
        for i in ids:
            if i not in must and i not in nice:
                target.append(i)
    return must, nice


def detect_language(skills: list[str], spec: str) -> str | None:
    langs = SPEC_BY_CODE[spec]["languages"]
    order = {"python": ["python", "django", "fastapi", "flask"], "java": ["java", "kotlin", "spring"],
             "go": ["go", "gin"], "javascript": ["javascript", "typescript", "nodejs", "react"]}
    for lang in langs:
        if any(s in skills for s in order[lang]):
            return lang
    return langs[0]


def parse_need(text: str, title: str = "") -> dict:
    full = f"{title}\n{text}"
    spec = classify_specialization(text, title)
    must, nice = split_must_nice(full)
    grades, years = extract_grades(full)
    s_from, s_to = extract_salary(full)
    # единое соглашение: суммы до вычета НДФЛ; «на руки» в тексте пересчитываем в gross
    salary_net = bool((s_from or s_to) and is_net(full))
    if salary_net:
        s_from = net_to_gross_monthly(s_from) if s_from else None
        s_to = net_to_gross_monthly(s_to) if s_to else None
    code = spec["specialization"]
    return {
        "specialization": code,
        "specialization_confidence": spec["confidence"],
        "specialization_alternatives": spec["alternatives"],
        "grades": grades or ["middle"],
        "grades_detected": bool(grades),
        "experience_years": years,
        "must_skills": must[:12],
        "nice_skills": nice[:12],
        "language": detect_language(must + nice, code),
        "work_format": extract_format(full),
        "city": extract_city(full),
        "salary_from": s_from,
        "salary_to": s_to,
        "salary_basis": "gross",
        "salary_note": "В тексте сумма «на руки» — пересчитано до вычета НДФЛ" if salary_net else None,
        "require_fsp": bool(re.search(r"фсп|спортивн\w+ программировани|олимпиад|хакатон", full.lower())),
    }
