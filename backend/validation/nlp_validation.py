"""Валидация NLP-модулей.

1. Разбор вакансий — 28 вручную написанных текстов разных стилей (validation/data/vacancies_eval.json) с эталоном:
   специализация (гибрид vs только модель vs только правила), грейды, навыки (P/R/F1), вилка, формат, город.
2. Разбор резюме — синтетические резюме в двух шаблонах: вёрстка экспорта hh.ru (две колонки, кегли и подписи как
   в оригинале) и свободная форма; рендер в PDF (ReportLab) и распознавание (pdfminer): точность каждого поля —
   ФИО, контакты, GitHub, город, переезд, должность, зарплата, формат, стаж, места работы, вуз, языки, «О себе», навыки.

Запуск: python -m validation.nlp_validation
"""
from __future__ import annotations

import io
import json
import random
import time
from datetime import date
from pathlib import Path

import numpy as np

from app.seed.synthetic import generate_population
from app.services.nlp.resume_parser import parse_resume_pdf
from app.services.nlp.vacancy_parser import _model, classify_specialization, parse_need
from app.services.reference.skills import SKILL_BY_ID
from validation.common import r3, save_report

DATA = Path(__file__).resolve().parent / "data"
MONTHS_RU = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь",
             "Декабрь"]


def prf(pred: set, gold: set) -> tuple[float, float, float]:
    tp = len(pred & gold)
    p = tp / len(pred) if pred else 1.0
    r = tp / len(gold) if gold else 1.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def vacancy_eval() -> dict:
    items = json.loads((DATA / "vacancies_eval.json").read_text(encoding="utf-8"))
    model = _model()
    res = {"spec_hybrid": 0, "spec_model_only": 0, "spec_rules_only": 0, "grades_exact": 0, "grades_overlap": 0,
           "salary_exact": 0, "salary_n": 0, "format": 0, "city": 0}
    skill_scores, must_split = [], []
    errors = []
    for it in items:
        g = it["gold"]
        parsed = parse_need(it["text"], it["title"])
        cls = classify_specialization(it["text"], it["title"])
        model_pred = model.classes_[int(np.argmax(model.predict_proba([f"{it['title']}. {it['text']}"])[0]))]
        rules_pred = max(cls["rules_p"], key=cls["rules_p"].get)
        res["spec_hybrid"] += parsed["specialization"] == g["specialization"]
        res["spec_model_only"] += model_pred == g["specialization"]
        res["spec_rules_only"] += rules_pred == g["specialization"]
        res["grades_exact"] += set(parsed["grades"]) == set(g["grades"])
        res["grades_overlap"] += bool(set(parsed["grades"]) & set(g["grades"]))
        if g["salary_from"] or g["salary_to"]:
            res["salary_n"] += 1
            res["salary_exact"] += parsed["salary_from"] == g["salary_from"] and parsed["salary_to"] == g["salary_to"]
        res["format"] += parsed["work_format"] == g["work_format"]
        res["city"] += parsed["city"] == g["city"]
        pred_sk = set(parsed["must_skills"]) | set(parsed["nice_skills"])
        gold_sk = set(g["must"]) | set(g["nice"])
        skill_scores.append(prf(pred_sk, gold_sk))
        if g["nice"]:
            must_split.append(len(set(parsed["nice_skills"]) & set(g["nice"])) / len(g["nice"]))
        if parsed["specialization"] != g["specialization"] or set(parsed["grades"]) != set(g["grades"]):
            errors.append({"title": it["title"], "gold": [g["specialization"], g["grades"]],
                           "pred": [parsed["specialization"], parsed["grades"]]})
    n = len(items)
    return {
        "n": n,
        "specialization_accuracy": {"hybrid": r3(res["spec_hybrid"] / n), "model_only": r3(res["spec_model_only"] / n),
                                    "rules_only": r3(res["spec_rules_only"] / n)},
        "grades_exact": r3(res["grades_exact"] / n), "grades_overlap": r3(res["grades_overlap"] / n),
        "skills": {"precision": r3(np.mean([s[0] for s in skill_scores])), "recall": r3(np.mean([s[1] for s in skill_scores])),
                   "f1": r3(np.mean([s[2] for s in skill_scores]))},
        "nice_to_have_detected": r3(np.mean(must_split)) if must_split else None,
        "salary_exact": r3(res["salary_exact"] / max(1, res["salary_n"])),
        "work_format": r3(res["format"] / n), "city": r3(res["city"] / n),
        "errors": errors,
    }


# --------------------------------------------------------------------------- резюме

SPECIALTIES = ["Программная инженерия", "Прикладная математика и информатика", "Информатика и вычислительная техника",
               "Информационная безопасность", "Бизнес-информатика", "Математическое обеспечение и администрирование ИС"]
HH_FORMAT = {"office": "на месте работодателя", "hybrid": "гибрид", "remote": "удалённо"}
FREE_FORMAT = {"office": "офис", "hybrid": "гибрид", "remote": "удалённо"}
LANG_POOL = [("Английский", ["A2 — Элементарный", "B1 — Средний", "B2 — Средне-продвинутый", "C1 — Продвинутый"]),
             ("Немецкий", ["A1 — Начальный", "A2 — Элементарный"]), ("Французский", ["A1 — Начальный"])]


def _fmt_month(ym: str) -> str:
    y, m = ym.split("-")
    return f"{MONTHS_RU[int(m) - 1]} {y}"


def _months(start: str, end: str | None) -> int:
    y1, m1 = map(int, start.split("-"))
    if end:
        y2, m2 = map(int, end.split("-"))
    else:
        y2, m2 = date.today().year, date.today().month
    return max(0, (y2 - y1) * 12 + (m2 - m1))


def _union_months(entries: list[dict]) -> int:
    """Стаж без двойного счёта пересекающихся мест работы (так считает и hh.ru)."""
    spans = []
    for e in entries:
        y1, m1 = map(int, e["start"].split("-"))
        y2, m2 = map(int, e["end"].split("-")) if e["end"] else (date.today().year, date.today().month)
        spans.append((y1 * 12 + m1, y2 * 12 + m2))
    spans.sort()
    total, (a, b) = 0, spans[0]
    for x, y in spans[1:]:
        if x <= b:
            b = max(b, y)
        else:
            total += b - a
            a, b = x, y
    return total + (b - a)


def _plural(n: int, one: str, few: str, many: str) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def _duration(months: int) -> str:
    y, m = divmod(months, 12)
    parts = []
    if y:
        parts.append(f"{y} {_plural(y, 'год', 'года', 'лет')}")
    if m or not y:
        parts.append(f"{m} {_plural(m, 'месяц', 'месяца', 'месяцев')}")
    return " ".join(parts)


def _gold(c, rng: random.Random) -> dict:
    """Эталон резюме синтетического кандидата и сгенерированные для него «бумажные» поля."""
    login = f"dev{c.idx}{rng.randint(10, 99)}"
    phone = f"+7 (9{rng.randint(10, 99)}) {rng.randint(100, 999)}-{rng.randint(10, 99)}-{rng.randint(10, 99)}"
    langs = [("Русский", "Родной")]
    for name, levels in rng.sample(LANG_POOL, rng.randint(1, 2)):
        langs.append((name, rng.choice(levels)))
    uni = c.education[0]["title"].split(",")[0]
    months = _union_months(c.experience)
    return {
        "full_name": c.full_name, "email": f"{login}@mail-demo.ru", "phone": phone,
        "phone_digits": "7" + "".join(ch for ch in phone if ch.isdigit())[1:], "telegram": f"@{login}_tg",
        "github": f"github.com/{login}" if rng.random() < 0.6 else None, "city": c.city, "relocation": c.relocation,
        "headline": c.headline, "salary": c.desired_salary, "formats": set(c.work_formats), "months": months,
        "experience": c.experience, "university": uni, "edu_year": 2026 - rng.randint(0, 12),
        "specialty": rng.choice(SPECIALTIES), "languages": langs, "skills": set(c.declared_skills),
        "skill_names": [SKILL_BY_ID[s].name for s in c.declared_skills if s in SKILL_BY_ID], "about": c.about,
    }


def hh_pdf(c, g: dict, rng: random.Random) -> bytes:
    """Резюме в вёрстке экспорта hh.ru: две колонки (подписи и даты слева на x≈42, содержимое справа на x≈128),
    кегли как в оригинале (ФИО 25, заголовки 11, компания и должность 12, текст 9, даты 8), колонтитул на каждой странице."""
    import textwrap

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    from app.services.pdf.profile_pdf import _fonts

    _fonts()
    buf = io.BytesIO()
    cv = canvas.Canvas(buf, pagesize=A4)
    W, H = A4
    L, R, BUL = 42.5, 127.6, 141.7
    y = H - 61
    surname_name = " ".join(g["full_name"].split()[:2])

    def footer():
        cv.setFont("Mont", 8)
        cv.drawString(L, 28.7, f"{surname_name}  •  Резюме обновлено 28 сентября 2026 в 11:10")

    def need(h: float):
        nonlocal y
        if y - h < 60:
            footer()
            cv.showPage()
            y = H - 55

    def put(x: float, s: str, size: float, bold: bool = False, at: float | None = None):
        cv.setFont("Mont-Bold" if bold else "Mont", size)
        cv.drawString(x, y if at is None else at, s)

    put(L, g["full_name"], 25, True)
    y -= 27
    for s in [f"{rng.choice(['Мужчина', 'Женщина'])}, {rng.randint(21, 40)} лет", "",
              f"{g['phone']} — предпочитаемый способ связи", g["email"], f"telegram: {g['telegram']}", "",
              f"Проживает: {g['city']}", "Гражданство: Россия, есть разрешение на работу: Россия",
              ("Готов к переезду" if g["relocation"] else "Не готов к переезду") + ", готов к редким командировкам"]:
        if s:
            put(L, s, 9)
        y -= 13
    gh_in_header = bool(g["github"]) and rng.random() < 0.4
    if gh_in_header:
        put(L, f"Мой профиль: https://{g['github']}", 9)
        y -= 13
    y -= 24
    put(L, "Желаемая должность и зарплата", 11, True)
    y -= 20
    put(L, g["headline"], 12, True)
    put(449.8, f"{g['salary']:,} ₽ на руки".replace(",", " "), 16, True)
    y -= 18
    put(L, "Специализации:", 9)
    y -= 13
    put(56.7, "—  Программист, разработчик", 9)
    y -= 13
    put(L, "Тип занятости: полная занятость", 9)
    y -= 13
    put(L, "Формат работы: " + ", ".join(HH_FORMAT[f] for f in sorted(g["formats"])), 9)
    y -= 37
    need(60)
    put(L, f"Опыт работы — {_duration(g['months'])}", 11, True)
    y -= 20
    for e in g["experience"]:
        desc = textwrap.wrap(e["description"], 95) or [""]
        need(110)
        top = y
        put(L, f"{_fmt_month(e['start'])} —", 8, at=top)
        put(L, _fmt_month(e["end"]) if e["end"] else "настоящее время", 8, at=top - 11)
        put(L, _duration(_months(e["start"], e["end"])), 8, at=top - 22)
        put(R, e["company"], 12, True, at=top)
        put(R, f"Россия, www.{rng.choice(['alpha', 'neo', 'stream', 'logos'])}{c.idx}.ru/", 9, at=top - 15)
        put(R, "Информационные технологии, системная интеграция, интернет", 9, at=top - 28)
        put(BUL, "• Разработка программного обеспечения", 9, at=top - 41)
        y = top - 59
        put(R, e["position"], 12, True)
        y -= 21
        for ln in desc:
            need(14)
            put(R, ln, 9)
            y -= 13
        y -= 24
    need(80)
    put(L, "Образование", 11, True)
    y -= 20
    put(L, "Высшее", 11, True)
    y -= 26
    put(L, str(g["edu_year"]), 8)
    put(R, g["university"], 12, True)
    y -= 15
    put(R, f"{g['specialty']}, факультет информационных технологий", 9)
    y -= 40
    need(90)
    put(L, "Навыки", 11, True)
    y -= 20
    put(L, "Знание языков", 8)
    for name, level in g["languages"]:
        put(R, f"{name} — {level}", 9)
        y -= 13
    y -= 20
    put(L, "Навыки", 8)
    row, rows = "", []
    for t in g["skill_names"]:
        cand = (row + "      " + t) if row else t
        if len(cand) > 70:
            rows.append(row)
            row = t
        else:
            row = cand
    rows.append(row)
    for r in rows:
        need(18)
        put(R, r, 10)
        y -= 18
    y -= 22
    need(60)
    put(L, "Дополнительная информация", 11, True)
    y -= 20
    put(L, "Обо мне", 8)
    about = g["about"] + (f" Код: {g['github']}." if g["github"] and not gh_in_header else "")
    for ln in textwrap.wrap(about, 95):
        need(14)
        put(R, ln, 9)
        y -= 13
    footer()
    cv.save()
    return buf.getvalue()


def free_text(g: dict) -> str:
    lines = [f"{g['full_name']} — {g['headline']}",
             f"{g['city']} | {g['email']} | {g['phone']} | tg: {g['telegram']}"
             + (f" | https://{g['github']}" if g["github"] else ""),
             ("Готов к переезду" if g["relocation"] else "Не готов к переезду")
             + f". Формат: {', '.join(FREE_FORMAT[f] for f in sorted(g['formats']))}",
             f"Ожидания по зарплате: {g['salary']:,} ₽".replace(",", " "), "",
             f"О себе: {g['about']}", f"Стек: {', '.join(g['skill_names'])}", "", "Опыт работы"]
    for e in g["experience"]:
        s_y, s_m = e["start"].split("-")
        end = f"{e['end'].split('-')[1]}.{e['end'].split('-')[0]}" if e["end"] else "н. в."
        lines += [f"{s_m}.{s_y} – {end}  {e['company']}, {e['position']}", e["description"]]
    lines += ["", f"Образование: {g['university']}, {g['specialty']}, {g['edu_year']}",
              "Языки: " + "; ".join(f"{n} — {lv}" for n, lv in g["languages"])]
    return "\n".join(lines)


def text_to_pdf(text: str) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    from app.services.pdf.profile_pdf import _fonts

    _fonts()
    st = ParagraphStyle("r", fontName="Mont", fontSize=10, leading=13)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    story = []
    for ln in text.split("\n"):
        story.append(Paragraph(ln.replace("&", "&amp;").replace("<", "&lt;"), st) if ln.strip() else Spacer(1, 6))
    doc.build(story)
    return buf.getvalue()


def _norm(s: str | None) -> str:
    return " ".join((s or "").lower().replace("ё", "е").split())


def resume_eval(n: int = 80, seed: int = 404) -> dict:
    """Синтетические резюме в вёрстке hh.ru (две колонки, как в настоящем экспорте) и в свободной форме → PDF →
    распознавание. Сравнение с эталоном по каждому полю."""
    rng = random.Random(seed)
    pop = [c for c in generate_population(n * 2, seed=seed) if c.experience][:n]
    fields = ["name", "email", "phone", "telegram", "github", "city", "relocation", "headline", "salary", "formats",
              "years_within_0_5", "experience_count", "company", "position", "start_date", "university", "edu_year",
              "languages", "about"]
    stats = {s: {f: [] for f in fields} for s in ("hh", "free")}
    skill_f1 = {"hh": [], "free": []}
    years_err = []
    for i, c in enumerate(pop):
        style = "hh" if i % 2 == 0 else "free"
        g = _gold(c, rng)
        data = hh_pdf(c, g, rng) if style == "hh" else text_to_pdf(free_text(g))
        _, p = parse_resume_pdf(data)
        st = stats[style]
        st["name"].append(_norm(p["full_name"]) == _norm(g["full_name"]))
        st["email"].append(p["email"] == g["email"])
        st["phone"].append("".join(ch for ch in (p["phone"] or "") if ch.isdigit()) == g["phone_digits"])
        st["telegram"].append(p["telegram"] == g["telegram"])
        if g["github"]:
            st["github"].append((p["github"] or "").lower() == g["github"].lower())
        st["city"].append(p["city"] == g["city"])
        st["relocation"].append(p["relocation"] == g["relocation"])
        st["headline"].append(_norm(p["headline"]) == _norm(g["headline"]))
        st["salary"].append(p["desired_salary"] == g["salary"])
        st["formats"].append(set(p["work_formats"]) == g["formats"])
        err = abs((p["experience_years"] or 0) - g["months"] / 12)
        years_err.append(err)
        st["years_within_0_5"].append(err <= 0.5)
        pe, ge = p["experience"], g["experience"]
        st["experience_count"].append(len(pe) == len(ge))
        for k, e in enumerate(ge):
            q = pe[k] if k < len(pe) else {}
            st["company"].append(_norm(q.get("company")) == _norm(e["company"]))
            st["position"].append(_norm(q.get("position")) == _norm(e["position"]))
            st["start_date"].append(q.get("start") == e["start"])
        edu = p["education"][0] if p["education"] else {}
        st["university"].append(_norm(g["university"]) in _norm(edu.get("title")))
        st["edu_year"].append(edu.get("year") == g["edu_year"])
        st["languages"].append({x["name"] for x in p["languages"]} == {n_ for n_, _ in g["languages"]})
        st["about"].append(bool(p["about"]) and _norm(g["about"])[:40] in _norm(p["about"]))
        skill_f1[style].append(prf(set(p["skills"]), g["skills"])[2])
    acc = {s: {f: r3(np.mean(v)) if v else None for f, v in st.items()} for s, st in stats.items()}
    overall = {f: r3(np.mean(stats["hh"][f] + stats["free"][f])) if stats["hh"][f] + stats["free"][f] else None
               for f in fields}
    return {
        "n": len(pop), "pipeline": "эталон → PDF (вёрстка hh.ru на ReportLab или свободный текст) → pdfminer.six → парсер",
        "field_accuracy": overall,
        "field_accuracy_by_template": acc,
        "experience_mae_years": r3(np.mean(years_err)),
        "skills_f1": r3(np.mean(skill_f1["hh"] + skill_f1["free"])),
        "skills_f1_by_template": {k: r3(np.mean(v)) for k, v in skill_f1.items()},
    }


def main() -> dict:
    t0 = time.time()
    report = {"generated_at": time.strftime("%Y-%m-%d %H:%M"), "vacancies": vacancy_eval(), "resumes": resume_eval()}
    report["runtime_sec"] = round(time.time() - t0, 1)
    save_report("nlp_validation", report)
    return report


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False, indent=1))
