"""Автораспознавание резюме из PDF: ФИО, контакты и ссылки, желаемая должность и зарплата, формат работы, город и
переезд, стаж, места работы, образование и курсы, навыки, языки, «О себе», роли и софт-скиллы.

Два режима.
  • Экспорт hh.ru распознаётся по фирменным заголовкам («Желаемая должность и зарплата», «Опыт работы — …»,
    «Резюме обновлено …»). Вёрстка у него двухколоночная: слева подписи и даты, справа содержимое, поэтому разбор идёт
    по координатам строк (pdfminer.six): даты места работы сопоставляются с текстом справа на той же высоте,
    компания и должность выделены кеглем, год окончания — с вузом, подпись «Знание языков» — с языками и т. д.
  • Произвольное резюме — разбор текста по распространённым заголовкам (RU/EN) и эвристикам по всему тексту.
Навыки: теги раздела «Навыки» сопоставляются с онтологией полностью, в тексте опыта и «О себе» — в строгом режиме без
общих слов («вёрстка», «мониторинг»), чтобы описание задач не порождало ложных навыков. ФИО — NER-модель natasha
(Slovnet) с эвристическим запасным вариантом. Пол, возраст, дату рождения и гражданство не извлекаем: для подбора они
не нужны (минимизация персональных данных, 152-ФЗ). Для каждого поля возвращается признак «найдено», а для
софт-скиллов, выведенных из опыта, — фрагмент-основание: кандидат проверяет всё перед сохранением.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass
from datetime import date
from functools import lru_cache

from app.services.nlp.salary import is_net, net_to_gross_monthly
from app.services.nlp.vacancy_parser import classify_specialization, extract_city, extract_format, extract_grades
from app.services.reference.skills import extract_skills
from app.services.reference.taxonomy import SOFT_SKILLS

# ------------------------------------------------------------------ словари и шаблоны

_MONTH_WORD = (r"(январ[ья]|феврал[ья]|марта?|апрел[ья]|ма[йя]|июн[ья]|июл[ья]|августа?|сентябр[ья]|октябр[ья]|"
               r"ноябр[ья]|декабр[ья]|янв\.?|фев\.?|мар\.?|апр\.?|июн\.?|июл\.?|авг\.?|сент?\.?|окт\.?|ноя\.?|дек\.?|"
               r"january|february|march|april|may|june|july|august|september|october|november|december|"
               r"jan\.?|feb\.?|mar\.?|apr\.?|jun\.?|jul\.?|aug\.?|sept?\.?|oct\.?|nov\.?|dec\.?)")
_MONTH_PREFIX = [("янв", 1), ("фев", 2), ("мар", 3), ("апр", 4), ("май", 5), ("мая", 5), ("июн", 6), ("июл", 7),
                 ("авг", 8), ("сен", 9), ("окт", 10), ("ноя", 11), ("дек", 12), ("jan", 1), ("feb", 2), ("mar", 3),
                 ("apr", 4), ("may", 5), ("jun", 6), ("jul", 7), ("aug", 8), ("sep", 9), ("oct", 10), ("nov", 11),
                 ("dec", 12)]
_PRESENT = r"(?:по\s+)?настоящ\w*\s+врем\w*|по\s+наст\w*|н\.\s*в\.?|сейчас|present|current(?:ly)?|now|till now"
START_RE = re.compile(rf"^{_MONTH_WORD}\s+(\d{{4}})\s*[—–-]\s*(.*)$", re.I)
END_RE = re.compile(rf"^(?:{_MONTH_WORD}\s+(\d{{4}})|{_PRESENT})$", re.I)
DURATION_RE = re.compile(r"^(?=\d)(?:\d+\s*(?:год|года|лет|years?)\b\s*)?(?:\d+\s*(?:месяц\w*|months?))?$", re.I)
FOOTER_RE = re.compile(r"резюме обновлено\s+\d{1,2}\s+\S+\s+\d{4}|resume updated|cv updated", re.I)
SALARY_RE = re.compile(r"(?:от\s*)?(\d{1,3}(?:\s?\d{3})+|\d{4,7}|\d{2,3})\s*(₽|руб\.?|rub|rur|р\.|тыс\.?|k(?![a-z])|к(?![а-я]))",
                       re.I)
LEVEL_RE = re.compile(r"^(высшее|неоконченное высшее|среднее специальное|среднее|бакалавр|магистр|специалист|"
                      r"кандидат наук|доктор наук|аспирантура|higher|incomplete higher|bachelor'?s?(?: degree)?|"
                      r"master'?s?(?: degree)?|phd|secondary)$", re.I)
EDU_RE = re.compile(r"университет|институт|академи|колледж|техникум|школа программирования|вшэ|мгу|мфти|мифи|мирэа|рту|"
                    r"итмо|мгту|бауман|спбгу|спбпу|урфу|нгу|тпу|кфу|мэи|маи|мисис|рэу|ранхигс|губкин|политех|"
                    r"бакалавр|магистр|специалитет|university|college|institute|academy", re.I)
POSITION_RE = re.compile(r"разработчик|developer|engineer|инженер|аналитик|analyst|тестировщик|\bqa\b|devops|\bsre\b|"
                         r"data scientist|дата-сайентист|программист|архитектор|тимлид|team ?lead|стажер|стажёр|intern|"
                         r"специалист|руководитель|менеджер|ml|cv", re.I)
LANG_NAMES = re.compile(r"^(русский|английский|немецкий|французский|испанский|итальянский|китайский|японский|корейский|"
                        r"турецкий|арабский|португальский|польский|украинский|белорусский|казахский|татарский|english|"
                        r"russian|german|french|spanish|italian|chinese|japanese|korean|turkish|arabic)\b", re.I)
LINK_RE = re.compile(r"(?:https?://)?(?:www\.)?((?:github\.com|gitlab\.com)/[\w.-]+|linkedin\.com/in/[\w%-]+|"
                     r"career\.habr\.com/[\w-]+|habr\.com/(?:ru/)?users/[\w-]+|kaggle\.com/[\w-]+|"
                     r"leetcode\.com/(?:u/)?[\w-]+|vk\.com/[\w.]+|hh\.ru/resume/\w+)", re.I)
LINK_KEYS = [("github.com", "github"), ("gitlab.com", "gitlab"), ("linkedin.com", "linkedin"), ("habr.com", "habr"),
             ("kaggle.com", "kaggle"), ("leetcode.com", "leetcode"), ("vk.com", "vk"), ("hh.ru", "hh")]

ROLE_CUES = {
    "mentoring": r"ментор|наставни|mentor|обучал\w* стаж|онбординг",
    "code_review": r"код[- ]?ревью|code review|ревью кода",
    "team_lead": r"тимлид|team ?lead|руководил\w* команд|руководитель группы|управлял\w* команд",
    "tech_lead": r"техлид|tech ?lead|технический лидер|ведущий разработчик",
    "architecture": r"архитектур|проектировал\w* систем|system design",
    "devops_practices": r"ci/cd|деплой|docker|kubernetes|развёртыван|развертыван",
    "analysis": r"анализ требований|постановк\w* задач|бизнес-требован",
    "testing": r"тестировал|автотест|unit-тест|юнит-тест",
    "research": r"исследован|эксперимент|r&d|research|дообучил|сравнени\w* (?:моделей|подходов)|после сравнения",
    "developer": r"разработ|developer|engineer|программист|инженер",
}
# Софт-скиллы, которые можно обоснованно вывести из описанного опыта (показываются с фрагментом-основанием)
SOFT_EVIDENCE = {
    "teamwork": r"хакатон\w*|hackathon|в команде из|командн\w* проект|кросс-?функциональн",
    "leadership": r"руковод\w* (?:команд|групп|отдел)|тимлид|возглав\w*|team ?lead|управлял\w* команд",
    "mentoring": r"наставни\w*|ментор\w*|обучал\w* (?:стаж|сотрудник|коллег|джун|новичк)|онбординг",
    "communication": r"выступ\w* с доклад|доклад\w* на|презентова\w*|защищ\w* проект|переговор\w*|взаимодейств\w* с заказчик",
    "critical_thinking": r"после сравнения|сравнил\w*|проанализировал\w*|анализировал\w* ошибк|выбрал\w* .{0,40}после",
    "responsibility": r"отвечал\w* за|вывел\w* в продакшен|в продакшен|в эксплуатацию",
    "initiative": r"по собственной инициативе|инициировал\w*|предложил\w* и (?:внедрил|реализовал)|с нуля",
    "learning": r"самостоятельно (?:изучил|освоил)|быстро (?:изучил|освоил)|прош\w+ курс",
}


def _norm(s: str) -> str:
    return (s.replace("\xa0", " ").replace(" ", " ").replace(" ", " ").replace("­", "")
            .replace("\x0c", "\n"))


def _month_num(word: str) -> int | None:
    w = word.lower().strip(".")
    for p, n in _MONTH_PREFIX:
        if w.startswith(p):
            return n
    return None


def _month_date(word: str, year: str) -> date | None:
    m = _month_num(word)
    return date(int(year), m, 1) if m else None


def parse_duration(s: str) -> float | None:
    y = re.search(r"(\d+)\s*(?:год|года|лет|years?)\b", s, re.I)
    m = re.search(r"(\d+)\s*(?:месяц\w*|months?)", s, re.I)
    if not y and not m:
        return None
    return round((int(y.group(1)) if y else 0) + (int(m.group(1)) if m else 0) / 12, 2)


def _end_from_text(s: str) -> tuple[bool, date | None]:
    """(распознано, дата окончания); None — по настоящее время."""
    s = s.strip()
    m = END_RE.match(s)
    if not m:
        return False, None
    if m.group(1) and m.group(2):
        return True, _month_date(m.group(1), m.group(2))
    return True, None


def _iso(d: date | None) -> str | None:
    return d.isoformat()[:7] if d else None


# ------------------------------------------------------------------ ФИО, контакты, ссылки

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


def _looks_like_name(line: str) -> bool:
    words = line.split()
    return 2 <= len(words) <= 3 and all(re.fullmatch(r"[А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)?", w) for w in words)


def extract_name(text: str) -> str | None:
    head = text[:400]
    for line in head.splitlines()[:3]:
        if _looks_like_name(line.strip()):
            return line.strip()
    nat = _natasha()
    if nat:
        seg, ner, _mv, Doc = nat
        doc = Doc(head)
        doc.segment(seg)
        doc.tag_ner(ner)
        for span in doc.spans:
            if span.type != "PER":
                continue
            # спан может захватить следующую строку («Иванов Иван\nМужчина») — берём только строку с именем
            line = span.text.split("\n")[0].strip()
            if _looks_like_name(line):
                return line
    for line in head.splitlines():
        if _looks_like_name(line.strip()):
            return line.strip()
    return None


def extract_contacts(text: str) -> dict:
    email = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    phone = re.search(r"(?:\+7|8)[\s(-]*\d{3}[\s)-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}", text)
    tg = re.search(r"(?:t\.me/|telegram[:\s—–-]*@?|tg[:\s]*@|(?<![\w.])@)([A-Za-z][\w]{4,31})", text, re.I)
    phone_norm = None
    if phone:
        digits = re.sub(r"\D", "", phone.group(0))
        if len(digits) == 11:
            digits = "7" + digits[1:]
            phone_norm = f"+{digits[0]} {digits[1:4]} {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
    tg_handle = tg.group(1) if tg else None
    if email and tg_handle and tg_handle.lower() in email.group(0).lower().split("@")[1]:
        tg_handle = None
    links = extract_links(text)
    return {"email": email.group(0) if email else None, "phone": phone_norm,
            "telegram": f"@{tg_handle}" if tg_handle else None, "github": links.get("github"), "links": links}


def extract_links(text: str) -> dict:
    out: dict[str, str] = {}
    for m in LINK_RE.finditer(text):
        url = m.group(1).rstrip(".,;)")
        for host, key in LINK_KEYS:
            if host in url.lower() and key not in out:
                out[key] = url
    return out


# ------------------------------------------------------------------ навыки, роли, софт-скиллы

def split_skill_tags(lines: list[str]) -> list[str]:
    tags: list[str] = []
    for ln in lines:
        for t in re.split(r"\s{2,}|[,;•·|]\s*", ln.strip()):
            t = t.strip(" .")
            if t and len(t) <= 40 and t.lower() not in ("навыки", "ключевые навыки", "skills", "key skills", "знание языков"):
                tags.append(t)
    return list(dict.fromkeys(tags))


def skills_from(tags: list[str], prose: str) -> tuple[list[str], list[str]]:
    """Навыки из тегов (полное сопоставление) и из текста (строгое). Возвращает (id навыков, нераспознанные теги)."""
    ids: list[str] = []
    unknown: list[str] = []
    for t in tags:
        found = [s["id"] for s in extract_skills(t)]
        if found:
            ids += found
        else:
            unknown.append(t)
    ids += [s["id"] for s in extract_skills(prose, strict=True)]
    return list(dict.fromkeys(ids)), unknown


def soft_skills_from(explicit_text: str, evidence_text: str) -> tuple[list[str], dict[str, str]]:
    low = explicit_text.lower()
    found = [k for k, (_, stems) in SOFT_SKILLS.items() if any(s in low for s in stems)]
    evidence: dict[str, str] = {}
    for key, pat in SOFT_EVIDENCE.items():
        m = re.search(pat, evidence_text, re.I)
        if m and key not in found:
            a, b = max(0, m.start() - 40), min(len(evidence_text), m.end() + 40)
            evidence[key] = "…" + " ".join(evidence_text[a:b].split()) + "…"
    return found + [k for k in evidence if k not in found], evidence


def roles_from(text: str) -> list[str]:
    low = text.lower()
    return [r for r, pat in ROLE_CUES.items() if re.search(pat, low)]


def parse_languages(lines: list[str]) -> list[dict]:
    out = []
    items = []
    for ln in lines:
        items += [x for x in re.split(r";|,(?=\s*[А-ЯЁA-Z][а-яёa-z]+\s*[—–-])", ln) if x.strip()]
    for ln in items:
        ln = ln.strip()
        if not LANG_NAMES.match(ln):
            continue
        parts = [p.strip() for p in re.split(r"\s+[—–-]\s+|:\s*", ln) if p.strip()]
        out.append({"name": parts[0], "level": " — ".join(parts[1:]) or None})
    return out


def parse_salary(text: str) -> int | None:
    for m in SALARY_RE.finditer(text):
        v = int(re.sub(r"\D", "", m.group(1)))
        if m.group(2).lower().startswith(("тыс", "k", "к")) or v < 1000:
            v *= 1000
        if 10_000 <= v <= 5_000_000:
            return v
    return None


def parse_formats(text: str) -> list[str]:
    low = text.lower()
    out = []
    if re.search(r"гибрид|hybrid|частично удал", low):
        out.append("hybrid")
    if re.search(r"удал[её]н|remote|дистанц", low):
        out.append("remote")
    if re.search(r"на месте работодателя|офис|office|on-?site", low):
        out.append("office")
    return out


def parse_relocation(text: str) -> bool | None:
    low = text.lower()
    if re.search(r"не готов\w* к переезду|not (?:ready|willing) to relocate", low):
        return False
    if re.search(r"готов\w* к переезду|ready to relocate|willing to relocate", low):
        return True
    return None


def claimed_grade_from(text_for_grade: str, years: float | None) -> str | None:
    grades, _ = extract_grades(text_for_grade)
    if grades:
        return grades[-1]
    if years is None:
        return None
    return "senior" if years >= 5 else "middle" if years >= 2 else "junior" if years >= 1 else "intern"


# ------------------------------------------------------------------ hh.ru: разбор по координатам

@dataclass
class Line:
    page: int
    x0: float
    y: float
    size: float
    text: str

    @property
    def key(self) -> tuple[int, float]:
        return self.page, -self.y


def pdf_lines(data: bytes) -> list[Line]:
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import LAParams, LTChar, LTTextContainer, LTTextLine

    out: list[Line] = []
    for pno, page in enumerate(extract_pages(io.BytesIO(data), laparams=LAParams()), 0):
        for el in page:
            if not isinstance(el, LTTextContainer):
                continue
            for line in el:
                if not isinstance(line, LTTextLine):
                    continue
                text = " ".join(_norm(line.get_text()).split("\n")).rstrip()
                if not text.strip():
                    continue
                sizes = [ch.size for ch in line if isinstance(ch, LTChar)]
                out.append(Line(pno, line.x0, line.y1, round(max(sizes) if sizes else line.height, 1), text.strip()))
    out.sort(key=lambda ln: (ln.page, -ln.y, ln.x0))
    return out


HH_HEADINGS = [
    (re.compile(r"^(желаемая должность и зарплата|desired position and salary)$", re.I), "desired"),
    (re.compile(r"^(опыт работы|work experience)(\s*[—–-].*)?$", re.I), "experience"),
    (re.compile(r"^(образование|education)$", re.I), "education"),
    (re.compile(r"^(повышение квалификации, курсы|тесты, экзамены|электронные сертификаты|"
                r"professional development, courses|tests, examinations|electronic certificates)$", re.I), "courses"),
    (re.compile(r"^(навыки|skills|key skills)$", re.I), "skills"),
    (re.compile(r"^(дополнительная информация|additional information)$", re.I), "about"),
    (re.compile(r"^(рекомендации|портфолио|гражданство, время в пути до работы|опыт вождения|"
                r"recommendations|portfolio|citizenship, travel time to work)$", re.I), "misc"),
]


def is_hh(text: str) -> bool:
    return bool(re.search(r"Желаемая должность и зарплата|Резюме обновлено|Desired position and salary", text)
                or re.search(r"^Опыт работы\s*[—–-]", text, re.M))


def _hh_heading(ln: Line, body_size: float) -> str | None:
    for pat, kind in HH_HEADINGS:
        if pat.match(ln.text.strip()):
            # «Навыки» встречается и подписью в левой колонке (мелким кеглем) — заголовок крупнее основного текста
            if kind in ("skills", "education", "about", "misc", "courses", "desired") and ln.size < body_size + 1:
                return None
            return kind
    return None


def _paragraphs(lines: list[Line]) -> list[list[Line]]:
    paras: list[list[Line]] = []
    for ln in lines:
        if paras and paras[-1] and ln.page == paras[-1][-1].page and paras[-1][-1].y - ln.y > max(ln.size, 9) * 2:
            paras.append([ln])
        elif not paras:
            paras.append([ln])
        else:
            paras[-1].append(ln)
    return paras


def _join(lines: list[Line]) -> str:
    """Текст абзацами: строки внутри абзаца склеиваются, между абзацами — перевод строки."""
    return "\n".join(" ".join(x.text for x in p) for p in _paragraphs(lines)).strip()


def parse_hh_layout(lines: list[Line]) -> dict:
    lines = [ln for ln in lines if not FOOTER_RE.search(ln.text)]
    sizes = sorted(ln.size for ln in lines)
    body_size = sizes[len(sizes) // 2] if sizes else 9.0
    left_edge = min((ln.x0 for ln in lines), default=40)
    col_split = left_edge + 45  # правая колонка начинается заметно правее левого поля

    sections: list[tuple[str, list[Line]]] = [("header", [])]
    for ln in lines:
        kind = _hh_heading(ln, body_size)
        if kind:
            sections.append((kind, [ln]))
        else:
            sections[-1][1].append(ln)
    by_kind: dict[str, list[list[Line]]] = {}
    for kind, ls in sections:
        by_kind.setdefault(kind, []).append(ls)

    res: dict = {}
    # Шапка: ФИО — самый крупный кегль; контакты; город и переезд
    header = by_kind.get("header", [[]])[0]
    header_text = "\n".join(x.text for x in header)
    big = max(header, key=lambda x: x.size, default=None)
    res["full_name"] = big.text if big and _looks_like_name(big.text) else extract_name(header_text)
    city = next((re.sub(r"^(проживает|город|city|lives in)\s*:\s*", "", x.text, flags=re.I) for x in header
                 if re.match(r"^(проживает|город|city|lives in)\s*:", x.text, re.I)), None)
    res["city"] = (city.split(",")[0].strip() if city else None) or extract_city(header_text)
    res["relocation"] = parse_relocation(header_text)
    res["header_text"] = header_text

    # Желаемая должность и зарплата
    desired = [x for blk in by_kind.get("desired", []) for x in blk[1:]]
    left_desired = [x for x in desired if x.x0 < col_split + 200]
    title = next((x for x in left_desired if x.size >= body_size + 2 and ":" not in x.text), None)
    res["headline"] = title.text if title else next((x.text for x in left_desired if ":" not in x.text
                                                     and not x.text.startswith("—")), None)
    res["hh_specializations"] = [re.sub(r"^[—–-]\s*", "", x.text).strip() for x in desired if re.match(r"^[—–-]\s", x.text)]
    salary_line = next((x.text for x in sorted(desired, key=lambda x: -x.size) if SALARY_RE.search(x.text)), None)
    res["desired_salary"] = parse_salary(salary_line) if salary_line else None
    if res["desired_salary"] and salary_line and is_net(salary_line):
        res["desired_salary_net"] = res["desired_salary"]
        res["desired_salary"] = net_to_gross_monthly(res["desired_salary"])
    fmt_text = " ".join(x.text for x in desired if re.match(r"^(формат работы|график работы|занятость|тип занятости|"
                                                            r"work format|schedule)", x.text, re.I))
    res["work_formats"] = parse_formats(fmt_text)

    # Опыт работы: даты слева, содержимое справа
    exp_blocks = by_kind.get("experience", [])
    total = None
    entries: list[dict] = []
    for blk in exp_blocks:
        head = blk[0].text
        tail = re.sub(r"^(опыт работы|work experience)\s*[—–-]?\s*", "", head, flags=re.I)
        total = total if total is not None else parse_duration(tail)
        left = [x for x in blk[1:] if x.x0 < col_split]
        right = [x for x in blk[1:] if x.x0 >= col_split]
        starts = [i for i, x in enumerate(left) if START_RE.match(x.text)]
        for k, i in enumerate(starts):
            m = START_RE.match(left[i].text)
            start = _month_date(m.group(1), m.group(2))
            end_ok, end = _end_from_text(m.group(3)) if m.group(3).strip() else (False, None)
            j = i + 1
            if not m.group(3).strip() and j < len(left):
                end_ok, end = _end_from_text(left[j].text)
                j += 1 if end_ok else 0
            lo = left[i].key
            hi = left[starts[k + 1]].key if k + 1 < len(starts) else (99, 0.0)
            content = [x for x in right if (lo[0], lo[1] - 4) <= x.key < (hi[0], hi[1] - 4)]
            bigs = [x for x in content if x.size >= body_size + 2]
            company = bigs[0].text if bigs else (content[0].text if content else "")
            position = bigs[1].text if len(bigs) > 1 else ""
            after = content[content.index(bigs[1]) + 1:] if len(bigs) > 1 else [x for x in content[1:] if not
                                                                                 x.text.startswith("•")]
            site = next((x.text for x in content if re.search(r"www\.|https?://|\.(?:ru|com|io)\b", x.text)), None)
            entries.append({"company": company[:160], "position": position[:160], "start": _iso(start),
                            "end": None if (end is None or end >= date.today().replace(day=1)) else _iso(end),
                            "description": _join(after)[:2000], "site": site})
    res["experience"] = entries
    res["experience_years"] = total if total is not None else _years_from_entries(entries)

    # Образование и курсы: год слева, учреждение (крупнее) и специальность справа
    def edu_entries(blocks: list[list[Line]], default_level: str | None) -> list[dict]:
        out = []
        for blk in blocks:
            left = [x for x in blk[1:] if x.x0 < col_split]
            right = [x for x in blk[1:] if x.x0 >= col_split]
            level = next((x.text for x in left if LEVEL_RE.match(x.text) and x.size >= body_size + 1), default_level)
            years = [x for x in left if re.fullmatch(r"\d{4}", x.text.strip())]
            heads = [x for x in right if x.size >= body_size + 2] or right[:1]
            for n, h in enumerate(heads):
                nxt = heads[n + 1].key if n + 1 < len(heads) else (99, 0.0)
                spec = [x.text for x in right if h.key < x.key < nxt]
                yr = min(years, key=lambda y: abs((y.page - h.page) * 1000 + (h.y - y.y)), default=None)
                out.append({"title": h.text[:200], "year": int(yr.text) if yr else None, "level": level,
                            "specialty": ", ".join(spec)[:300] or None})
        return out

    res["education"] = edu_entries(by_kind.get("education", []), None) + edu_entries(by_kind.get("courses", []), "Курсы")

    # Навыки: подписи слева («Знание языков», «Навыки») делят содержимое справа
    lang_lines: list[str] = []
    tag_lines: list[str] = []
    for blk in by_kind.get("skills", []):
        labels = [x for x in blk[1:] if x.x0 < col_split]
        right = [x for x in blk[1:] if x.x0 >= col_split]
        for x in right:
            lab = None
            for lb in labels:
                if lb.key <= (x.page, -x.y + 4):
                    lab = lb
            name = (lab.text if lab else "").lower()
            if "язык" in name or "language" in name or LANG_NAMES.match(x.text):
                lang_lines.append(x.text)
            else:
                tag_lines.append(x.text)
    res["languages"] = parse_languages(lang_lines)
    res["skill_tags"] = split_skill_tags(tag_lines)

    # О себе
    about = [x for blk in by_kind.get("about", []) for x in blk[1:] if x.x0 >= col_split
             or not re.match(r"^(обо мне|about me)$", x.text, re.I)]
    about = [x for x in about if not re.match(r"^(обо мне|about me)$", x.text, re.I)]
    res["about"] = _join(about)[:3000] or None
    res["experience_text"] = "\n".join(e["description"] for e in entries)
    return res


def _years_from_entries(entries: list[dict]) -> float | None:
    intervals = []
    for e in entries:
        try:
            a = date.fromisoformat((e["start"] or "") + "-01")
        except ValueError:
            continue
        b = date.fromisoformat(e["end"] + "-01") if e.get("end") else date.today()
        if b >= a:
            intervals.append((a, b))
    if not intervals:
        return None
    intervals.sort()
    total, (ca, cb) = 0.0, intervals[0]
    for a, b in intervals[1:]:
        if a <= cb:
            cb = max(cb, b)
        else:
            total += (cb - ca).days
            ca, cb = a, b
    total += (cb - ca).days
    return round(total / 365.25, 1)


# ------------------------------------------------------------------ произвольный текст

GENERIC_HEADINGS = {
    "experience": r"опыт работы|опыт|трудовая деятельность|work experience|experience|professional experience|employment",
    "education": r"образование|основное образование|education",
    "courses": r"курсы|повышение квалификации|сертификаты|courses|certificates|certifications",
    "skills": r"навыки|ключевые навыки|технические навыки|hard skills|стек|стек технологий|технологии|skills|key skills|"
              r"technical skills",
    "languages": r"языки|знание языков|languages",
    "about": r"о себе|обо мне|about|about me|summary|профиль|profile|дополнительная информация",
    "projects": r"проекты|projects|портфолио|portfolio",
    "desired": r"желаемая должность|цель|objective",
}
_GENERIC_RE = {k: re.compile(rf"^(?:{v})\s*:?\s*(.*)$", re.I) for k, v in GENERIC_HEADINGS.items()}
_RANGE_RE = re.compile(
    r"((?:[а-яa-z]{3,9}\.?\s*)?(?:\d{1,2}[./])?\d{4})\s*[—–-]\s*((?:[а-яa-z]{3,9}\.?\s*)?(?:\d{1,2}[./])?\d{4}|"
    rf"{_PRESENT})", re.I)


def _point(s: str) -> date | None:
    s = s.strip().lower()
    if re.search(_PRESENT, s, re.I):
        return date.today()
    m = re.search(r"(\d{1,2})[./](\d{4})", s)
    if m:
        return date(int(m.group(2)), max(1, min(12, int(m.group(1)))), 1)
    m = re.search(r"([а-яa-z]{3,9})\.?\s*(\d{4})", s)
    if m and _month_num(m.group(1)):
        return date(int(m.group(2)), _month_num(m.group(1)), 1)
    m = re.search(r"(\d{4})", s)
    return date(int(m.group(1)), 1, 1) if m else None


def _generic_sections(lines: list[str]) -> tuple[list[str], dict[str, list[str]]]:
    """Секции по заголовкам: отдельная короткая строка-заголовок или «Заголовок: содержимое» в одной строке."""
    head: list[str] = []
    sections: dict[str, list[str]] = {}
    cur = None
    for ln in lines:
        s = ln.strip()
        kind = None
        rest = ""
        if s:
            for k, rx in _GENERIC_RE.items():
                m = rx.match(s)
                if not m:
                    continue
                inline = re.match(r"^[^:]{1,40}:\s*\S", s) is not None
                if (not m.group(1) and len(s) <= 60) or inline:
                    kind = k
                    rest = m.group(1).strip()
                    break
        if kind:
            cur = kind
            sections.setdefault(kind, [])
            if rest:
                sections[kind].append(rest)
        elif cur is None:
            head.append(ln)
        else:
            sections[cur].append(ln)
    return head, sections


def _generic_experience(lines: list[str]) -> list[dict]:
    # «Май 2026 —» + «настоящее время» на следующей строке → одна строка
    joined: list[str] = []
    for ln in lines:
        s = ln.strip()
        if joined and re.search(r"[—–-]\s*$", joined[-1]) and (END_RE.match(s) or _point(s)):
            joined[-1] = joined[-1].rstrip() + " " + s
        else:
            joined.append(s)
    entries: list[dict] = []
    for i, ln in enumerate(joined):
        rm = _RANGE_RE.search(ln)
        if not rm:
            continue
        a, b = _point(rm.group(1)), _point(rm.group(2))
        if not a or not b or b < a or a.year < 1980:
            continue
        rest = [x for x in joined[i + 1:i + 8] if x and not _RANGE_RE.search(x) and not DURATION_RE.match(x)]
        same = _RANGE_RE.sub("", ln).strip(" |,—–-")
        company = same or (rest[0] if rest else "")
        pos_line = ""
        parts = [x.strip() for x in re.split(r",\s+|\s+[—–|]\s+", same) if x.strip()] if same else []
        if len(parts) >= 2:
            pos_idx = next((k for k in range(len(parts) - 1, -1, -1) if POSITION_RE.search(parts[k])), len(parts) - 1)
            pos_line = parts[pos_idx]
            company = ", ".join(x for k, x in enumerate(parts) if k != pos_idx)
        if not pos_line:
            pos_line = next((x for x in rest if POSITION_RE.search(x) and len(x) < 90 and x != company), "")
        nxt = next((j for j in range(i + 1, len(joined)) if _RANGE_RE.search(joined[j])), len(joined))
        desc = " ".join(x for x in joined[i + 1:nxt] if x and x not in (company, pos_line) and not DURATION_RE.match(x))
        entries.append({"company": company[:160], "position": pos_line[:160], "start": _iso(a),
                        "end": None if b >= date.today().replace(day=1) else _iso(b), "description": desc[:2000],
                        "site": None})
    return entries[:10]


def _merge_wrapped(lines: list[str], start: re.Pattern) -> list[str]:
    """Склеивает строки, разорванные переносом: продолжение не начинается как новая запись."""
    out: list[str] = []
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        cont = out and not start.search(s) and (re.search(r"[,–—-]$|\s(и|в|на|по)$", out[-1]) or s[:1].islower()
                                               or re.fullmatch(r"\d{4}\.?", s))
        if cont:
            out[-1] = out[-1].rstrip() + " " + s
        else:
            out.append(s)
    return out


def _edu_entry(line: str) -> dict:
    """«МГТУ им. Н. Э. Баумана, Программная инженерия, бакалавр, 2024» → учреждение, специальность, уровень, год."""
    yr = re.findall(r"\b(19[5-9]\d|20[0-4]\d)\b", line)
    parts = [x.strip(" .") for x in re.split(r",\s*", re.sub(r"\b(19[5-9]\d|20[0-4]\d)\b\.?", "", line)) if x.strip(" .")]
    level = next((x for x in parts[1:] if LEVEL_RE.match(x)), None)
    rest = [x for x in parts[1:] if x != level]
    return {"title": (parts[0] if parts else line)[:200], "year": int(yr[-1]) if yr else None, "level": level,
            "specialty": ", ".join(rest)[:300] or None}


def parse_generic(text: str) -> dict:
    lines = [_norm(ln) for ln in _norm(text).splitlines() if not FOOTER_RE.search(ln)]
    head, sec = _generic_sections(lines)
    full = "\n".join(lines)
    header_text = "\n".join(head) or full[:600]
    res: dict = {"full_name": extract_name(header_text) or extract_name(full), "header_text": header_text}
    city = re.search(r"(?:проживает|город|city)\s*:\s*([А-ЯЁA-Z][\w -]+)", full, re.I)
    res["city"] = city.group(1).strip() if city else (extract_city(header_text) or extract_city(full))
    res["relocation"] = parse_relocation(full)
    desired = "\n".join(sec.get("desired", []))
    m = re.search(r"(?:желаемая должность|должность|позиция|position)\s*:\s*([^\n]{3,80})", full, re.I)
    headline = m.group(1).strip() if m else None
    if not headline and desired.strip():
        headline = desired.strip().splitlines()[0][:80]
    if not headline:
        name = res["full_name"]
        for ln in lines[:8]:
            s = ln.strip()
            cand = s.split("—", 1)[1].strip() if name and s.startswith(name) and "—" in s else s
            if cand and cand != name and POSITION_RE.search(cand) and len(cand) < 90 and "@" not in cand:
                headline = cand
                break
    res["headline"] = headline
    res["hh_specializations"] = []
    sal = re.search(r"(?:желаем\w* (?:зарплат|доход)\w*|ожидани\w*(?: по (?:зарплат|доход)\w*)?|зарплат\w*|"
                    r"salary)[^\d\n]{0,20}([^\n]{0,30})", full, re.I)
    res["desired_salary"] = parse_salary(sal.group(1)) if sal else parse_salary(desired)
    sal_text = sal.group(0) if sal else desired
    if res["desired_salary"] and is_net(sal_text or ""):
        res["desired_salary_net"] = res["desired_salary"]
        res["desired_salary"] = net_to_gross_monthly(res["desired_salary"])
    fmt_line = re.search(r"(?:формат\w*(?: работы)?|график\w*(?: работы)?|work format|schedule)\s*:\s*([^\n]+)", full, re.I)
    res["work_formats"] = (parse_formats(fmt_line.group(1)) if fmt_line else []) or parse_formats(desired) or \
        ([extract_format(full)] if extract_format(full) else [])
    exp_lines = sec.get("experience") or lines
    entries = _generic_experience(exp_lines)
    res["experience"] = entries
    m = re.search(r"опыт работы[^\n\d]{0,10}((?:\d{1,2}\s*(?:год|года|лет)\w*\s*)?(?:\d{1,2}\s*месяц\w*)?)", full, re.I)
    total = parse_duration(m.group(1)) if m and m.group(1).strip() else None
    res["experience_years"] = total if total is not None else _years_from_entries(entries)
    edu_lines = _merge_wrapped(sec.get("education", []) + sec.get("courses", []), EDU_RE)
    if not edu_lines:
        edu_lines = [ln for ln in lines if EDU_RE.search(ln)]
    edu = []
    for ln in edu_lines:
        s = ln.strip(" •-")
        if not s or LEVEL_RE.match(s):
            continue
        if EDU_RE.search(s) or sec.get("education"):
            edu.append(_edu_entry(s))
    res["education"] = edu[:6]
    lang_lines = _merge_wrapped(sec.get("languages", []), re.compile(LANG_NAMES.pattern.lstrip("^"), re.I))
    res["languages"] = parse_languages(lang_lines or [ln for ln in lines if LANG_NAMES.match(ln.strip())])
    res["skill_tags"] = split_skill_tags(sec.get("skills", []))
    res["about"] = " ".join(x.strip() for x in sec.get("about", []) if x.strip())[:3000] or None
    res["experience_text"] = "\n".join(e["description"] for e in entries) or full
    return res


# ------------------------------------------------------------------ сборка результата

def _finalize(base: dict, full_text: str) -> dict:
    contacts = extract_contacts(base.get("header_text") or full_text)
    if not contacts["email"] or not contacts["phone"]:
        more = extract_contacts(full_text)
        for k in ("email", "phone", "telegram"):
            contacts[k] = contacts[k] or more[k]
    # Ссылки ищем вне описаний мест работы: адреса сайтов компаний профилю не нужны
    links = extract_links("\n".join([base.get("header_text") or "", base.get("about") or ""]))
    links = links or extract_links(full_text)
    prose = "\n".join([base.get("experience_text") or "", base.get("about") or ""])
    skills, unknown = skills_from(base.get("skill_tags") or [], prose)
    if not base.get("skill_tags") and not skills:
        skills = [s["id"] for s in extract_skills(full_text, strict=True)]
    soft, evidence = soft_skills_from("\n".join([base.get("about") or "", " ".join(base.get("skill_tags") or [])]), prose)
    years = base.get("experience_years")
    grade_text = "\n".join([base.get("headline") or "", base.get("about") or ""])
    spec_text = "\n".join([base.get("headline") or "", " ".join(base.get("hh_specializations") or []),
                           " ".join(base.get("skill_tags") or []), base.get("about") or ""])
    spec = classify_specialization(spec_text) if (skills or base.get("headline")) else None
    formats = base.get("work_formats") or []
    result = {
        "full_name": base.get("full_name"),
        "email": contacts["email"], "phone": contacts["phone"], "telegram": contacts["telegram"],
        "github": links.get("github"), "links": links,
        "city": base.get("city"), "relocation": base.get("relocation"),
        "headline": base.get("headline"),
        "desired_salary": base.get("desired_salary"), "desired_salary_net": base.get("desired_salary_net"),
        "work_formats": formats, "work_format": formats[0] if formats else None,
        "experience_years": years,
        "experience": [{k: v for k, v in e.items() if k != "site"} for e in base.get("experience") or []],
        "education": base.get("education") or [],
        "languages": base.get("languages") or [],
        "about": base.get("about"),
        "skills": skills, "skills_unrecognized": unknown,
        "roles": roles_from(prose),
        "soft_skills": soft, "soft_skills_evidence": evidence,
        "claimed_grade": claimed_grade_from(grade_text, years),
        "specialization": spec["specialization"] if spec else None,
        "specialization_confidence": spec["confidence"] if spec else None,
        "source": base.get("source", "text"),
    }
    result["found"] = {k: (v is not None and v != [] and v != {} and v != "")
                       for k, v in result.items() if k not in ("source", "soft_skills_evidence", "skills_unrecognized")}
    return result


def parse_resume_text(text: str) -> dict:
    base = parse_generic(text)
    base["source"] = "text"
    return _finalize(base, _norm(text))


def parse_resume_pdf(data: bytes) -> tuple[str, dict]:
    text = _norm(pdf_to_text(data))
    if is_hh(text):
        try:
            base = parse_hh_layout(pdf_lines(data))
            base["source"] = "hh"
            return text, _finalize(base, text)
        except Exception:  # noqa: BLE001 — нестандартная вёрстка: разбираем как обычный текст
            pass
    return text, parse_resume_text(text)
