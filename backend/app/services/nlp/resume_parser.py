"""Автораспознавание резюме из PDF: ФИО, контакты, стек, грейд, роли, стаж, софт-скиллы, опыт, образование.

Текст извлекается pdfminer.six. ФИО — NER-модель natasha (Slovnet, PER) с эвристическим запасным вариантом,
навыки — онтология с синонимами, стаж — явная фраза «Опыт работы N лет M месяцев» (формат hh.ru) или сумма
непересекающихся интервалов дат. Для каждого поля возвращается признак «найдено», чтобы интерфейс подсветил
автозаполненные поля для проверки кандидатом.
"""
from __future__ import annotations

import io
import re
from datetime import date
from functools import lru_cache

from app.services.nlp.vacancy_parser import classify_specialization, extract_city, extract_format, extract_grades
from app.services.reference.skills import extract_skills
from app.services.reference.taxonomy import SOFT_SKILLS

MONTHS = {
    "янв": 1, "фев": 2, "мар": 3, "апр": 4, "мая": 5, "май": 5, "июн": 6, "июл": 7, "авг": 8, "сен": 9, "окт": 10,
    "ноя": 11, "дек": 12, "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9,
    "oct": 10, "nov": 11, "dec": 12,
}
ROLE_CUES = {
    "mentoring": r"ментор|наставни|mentor|обучал\w* стаж|онбординг",
    "code_review": r"код[- ]?ревью|code review|ревью кода",
    "team_lead": r"тимлид|team ?lead|руководил\w* команд|руководитель группы|управлял\w* команд",
    "tech_lead": r"техлид|tech ?lead|технический лидер|ведущий разработчик",
    "architecture": r"архитектур|проектировал\w* систем|system design",
    "devops_practices": r"ci/cd|пайплайн|pipeline|деплой",
    "analysis": r"анализ требований|постановк\w* задач|бизнес-требован",
    "testing": r"тестировал|автотест|unit-тест|юнит-тест",
    "research": r"исследован|эксперимент|r&d|research",
    "developer": r"разработ|developer|engineer|программист",
}
EDU_RE = re.compile(r"университет|институт|академи|колледж|техникум|вшэ|мгу|мфти|итмо|мгту|спбгу|кфу|бакалавр|магистр|"
                    r"специалитет|university", re.I)
POSITION_RE = re.compile(r"разработчик|developer|engineer|инженер|аналитик|analyst|тестировщик|qa|devops|sre|"
                         r"data scientist|программист|архитектор|тимлид", re.I)


def pdf_to_text(data: bytes) -> str:
    from pdfminer.high_level import extract_text

    return extract_text(io.BytesIO(data)) or ""


@lru_cache(maxsize=1)
def _natasha():
    try:
        from natasha import Doc, MorphVocab, NewsEmbedding, NewsNERTagger, Segmenter

        emb = NewsEmbedding()
        return Segmenter(), NewsNERTagger(emb), MorphVocab(), Doc
    except Exception:  # noqa: BLE001 — модель опциональна, работает эвристика
        return None


def extract_name(text: str) -> str | None:
    head = text[:400]
    nat = _natasha()
    if nat:
        seg, ner, _mv, Doc = nat
        doc = Doc(head)
        doc.segment(seg)
        doc.tag_ner(ner)
        for span in doc.spans:
            words = span.text.split()
            if span.type == "PER" and 2 <= len(words) <= 3:
                return span.text.strip()
    for line in head.splitlines():
        words = line.strip().split()
        if 2 <= len(words) <= 3 and all(re.fullmatch(r"[А-ЯЁ][а-яё-]+", w) for w in words):
            return line.strip()
    return None


def extract_contacts(text: str) -> dict:
    email = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    phone = re.search(r"(?:\+7|8)[\s(-]*\d{3}[\s)-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}", text)
    tg = re.search(r"(?:t\.me/|telegram[:\s]*@?|tg[:\s]*@|(?<![\w.])@)([A-Za-z][\w]{4,31})", text, re.I)
    gh = re.search(r"github\.com/[\w-]+", text, re.I)
    phone_norm = None
    if phone:
        digits = re.sub(r"\D", "", phone.group(0))
        if len(digits) == 11:
            digits = "7" + digits[1:]
            phone_norm = f"+{digits[0]} {digits[1:4]} {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
    tg_handle = tg.group(1) if tg else None
    if email and tg_handle and tg_handle.lower() in email.group(0).lower().split("@")[1]:
        tg_handle = None
    return {"email": email.group(0) if email else None, "phone": phone_norm,
            "telegram": f"@{tg_handle}" if tg_handle else None, "github": gh.group(0) if gh else None}


def _parse_point(s: str) -> date | None:
    s = s.strip().lower()
    if re.search(r"наст|сейчас|по н\.?в|present|current|now", s):
        return date.today()
    m = re.search(r"(\d{1,2})[./](\d{4})", s)
    if m:
        return date(int(m.group(2)), max(1, min(12, int(m.group(1)))), 1)
    m = re.search(r"([а-яa-z]{3})[а-яa-z]*\.?\s*(\d{4})", s)
    if m and m.group(1) in MONTHS:
        return date(int(m.group(2)), MONTHS[m.group(1)], 1)
    m = re.search(r"(\d{4})", s)
    if m:
        return date(int(m.group(1)), 1, 1)
    return None


_RANGE_RE = re.compile(
    r"((?:[а-яa-z]{3,9}\.?\s*)?(?:\d{1,2}[./])?\d{4})\s*[—–-]\s*((?:[а-яa-z]{3,9}\.?\s*)?(?:\d{1,2}[./])?\d{4}|"
    r"наст\w*\.?\s*врем\w*|по наст\w*|сейчас|present|current|now)", re.I)


def extract_experience(text: str) -> tuple[float | None, list[dict]]:
    m = re.search(r"опыт работы[^\n\d]{0,10}(\d{1,2})\s*(?:год|лет)\w*\s*(?:(\d{1,2})\s*месяц\w*)?", text, re.I)
    explicit = (int(m.group(1)) + (int(m.group(2)) / 12 if m.group(2) else 0)) if m else None
    lines = [ln.strip() for ln in text.splitlines()]
    intervals: list[tuple[date, date]] = []
    entries: list[dict] = []
    for i, ln in enumerate(lines):
        rm = _RANGE_RE.search(ln)
        if not rm:
            continue
        a, b = _parse_point(rm.group(1)), _parse_point(rm.group(2))
        if not a or not b or b < a or a.year < 1980:
            continue
        intervals.append((a, b))
        rest = [x for x in lines[i + 1:i + 6] if x and not _RANGE_RE.search(x)]
        same = _RANGE_RE.sub("", ln).strip(" |,—–-")
        company = same or (rest[0] if rest else "")
        pos_line = next((x for x in rest if POSITION_RE.search(x)), "")
        desc = " ".join(x for x in rest[1:4] if x != pos_line)[:400]
        if len(entries) < 6:
            entries.append({"company": company[:120], "position": pos_line[:120], "start": a.isoformat()[:7],
                            "end": None if b >= date.today().replace(day=1) else b.isoformat()[:7], "description": desc})
    total = 0.0
    if intervals:
        intervals.sort()
        cur_a, cur_b = intervals[0]
        for a, b in intervals[1:]:
            if a <= cur_b:
                cur_b = max(cur_b, b)
            else:
                total += (cur_b - cur_a).days
                cur_a, cur_b = a, b
        total += (cur_b - cur_a).days
    years = explicit if explicit is not None else (round(total / 365.25, 1) if intervals else None)
    return years, entries


def extract_desired_salary(text: str) -> int | None:
    m = re.search(r"(?:желаем\w* (?:зарплат|доход)\w*|ожидани\w* по (?:зарплат|доход)\w*|зарплат\w*)[^\d]{0,15}"
                  r"(\d[\d  ]{2,9})\s*(k|к|тыс)?", text, re.I)
    if not m:
        return None
    v = int(re.sub(r"\D", "", m.group(1)))
    if m.group(2) or v < 1000:
        v *= 1000
    return v if 10_000 <= v <= 5_000_000 else None


def extract_headline(text: str, name: str | None) -> str | None:
    m = re.search(r"(?:желаемая должность|должность|позиция)[:\s]+([^\n]{3,80})", text, re.I)
    if m:
        return m.group(1).strip()
    for ln in text.splitlines()[:15]:
        if ln.strip() and ln.strip() != name and POSITION_RE.search(ln) and len(ln) < 90:
            return ln.strip()
    return None


def parse_resume_text(text: str) -> dict:
    name = extract_name(text)
    contacts = extract_contacts(text)
    skills = [s["id"] for s in extract_skills(text)]
    years, experience = extract_experience(text)
    grades, _ = extract_grades(text)
    if years is not None:
        by_years = "senior" if years >= 5 else "middle" if years >= 2 else "junior" if years >= 1 else "intern"
        grade = grades[-1] if grades else by_years
    else:
        grade = grades[-1] if grades else None
    low = text.lower()
    roles = [r for r, pat in ROLE_CUES.items() if re.search(pat, low)]
    soft = [k for k, (_, stems) in SOFT_SKILLS.items() if any(s in low for s in stems)]
    education = [ln.strip()[:160] for ln in text.splitlines() if EDU_RE.search(ln)][:4]
    spec = classify_specialization(text) if skills else None
    result = {
        "full_name": name,
        **contacts,
        "city": extract_city(text),
        "headline": extract_headline(text, name),
        "skills": skills,
        "experience_years": years,
        "experience": experience,
        "claimed_grade": grade,
        "roles": roles,
        "soft_skills": soft,
        "education": [{"title": e} for e in education],
        "desired_salary": extract_desired_salary(text),
        "work_format": extract_format(text),
        "specialization": spec["specialization"] if spec else None,
        "specialization_confidence": spec["confidence"] if spec else None,
    }
    result["found"] = {k: bool(v) for k, v in result.items() if k != "found"}
    return result


def parse_resume_pdf(data: bytes) -> tuple[str, dict]:
    text = pdf_to_text(data)
    return text, parse_resume_text(text)
