"""Валидация NLP-модулей.

1. Разбор вакансий — 28 вручную написанных текстов разных стилей (validation/data/vacancies_eval.json) с эталоном:
   специализация (гибрид vs только модель vs только правила), грейды, навыки (P/R/F1), вилка, формат, город.
2. Разбор резюме — синтетические резюме в двух шаблонах (выгрузка «как с hh.ru» и свободная форма), отрендеренные
   в PDF (ReportLab) и распознанные обратно (pdfminer): точность ФИО, контактов, стажа, навыков, города.

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


def resume_text(c, rng: random.Random, style: str) -> tuple[str, dict]:
    email = f"{c.full_name.split()[1].lower()}.{c.idx}@mail-demo.ru"
    phone = f"+7 (9{rng.randint(10, 99)}) {rng.randint(100, 999)}-{rng.randint(10, 99)}-{rng.randint(10, 99)}"
    tg = f"dev_{c.idx}_{rng.randint(10, 99)}"
    skills = [SKILL_BY_ID[s].name for s in c.declared_skills if s in SKILL_BY_ID]
    months = sum(_months(e["start"], e["end"]) for e in c.experience)
    gold = {"full_name": c.full_name, "email": email, "phone_digits": "7" + phone.replace(" ", "").replace("(", "").replace(")", "")
            .replace("-", "")[2:], "telegram": f"@{tg}", "city": c.city, "skills": set(c.declared_skills),
            "years": months / 12}
    if style == "hh":
        y, m = divmod(months, 12)
        lines = [c.full_name, f"{rng.choice(['Мужчина', 'Женщина'])}, {rng.randint(21, 40)} лет", phone, email,
                 f"Telegram: @{tg}", f"Проживает: {c.city}", "Гражданство: Россия", "",
                 "Желаемая должность и зарплата", c.headline, f"{c.desired_salary:,} ₽".replace(",", " "), "",
                 f"Опыт работы — {y} лет {m} месяцев" if y else f"Опыт работы — {m} месяцев"]
        for e in c.experience:
            lines += ["", f"{_fmt_month(e['start'])} — {_fmt_month(e['end']) if e['end'] else 'настоящее время'}",
                      e["company"], e["position"], e["description"]]
        lines += ["", "Образование", "Высшее", c.education[0]["title"], "", "Навыки", ", ".join(skills), "",
                  "Обо мне", c.about]
    else:
        lines = [f"{c.full_name} — {c.headline}", f"{c.city} | {email} | {phone} | tg: @{tg}", "", f"О себе: {c.about}",
                 f"Стек: {', '.join(skills)}", "", "Опыт:"]
        for e in c.experience:
            s_y, s_m = e["start"].split("-")
            end = f"{e['end'].split('-')[1]}.{e['end'].split('-')[0]}" if e["end"] else "н. в."
            lines += [f"{s_m}.{s_y} – {end}  {e['company']}, {e['position']}", e["description"]]
        lines += ["", f"Образование: {c.education[0]['title']}"]
    return "\n".join(lines), gold


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


def resume_eval(n: int = 60, seed: int = 404) -> dict:
    rng = random.Random(seed)
    pop = [c for c in generate_population(n * 2, seed=seed) if c.experience][:n]
    stats = {"name": 0, "email": 0, "phone": 0, "telegram": 0, "city": 0, "years_within_0_5": 0}
    skill_f1, years_err = [], []
    by_style = {"hh": [], "free": []}
    for i, c in enumerate(pop):
        style = "hh" if i % 2 == 0 else "free"
        text, gold = resume_text(c, rng, style)
        _, p = parse_resume_pdf(text_to_pdf(text))
        ok_name = (p["full_name"] or "").replace("ё", "е") == gold["full_name"].replace("ё", "е")
        stats["name"] += ok_name
        stats["email"] += p["email"] == gold["email"]
        stats["phone"] += (p["phone"] or "").replace(" ", "").replace("-", "").replace("+", "") == gold["phone_digits"]
        stats["telegram"] += p["telegram"] == gold["telegram"]
        stats["city"] += p["city"] == gold["city"]
        err = abs((p["experience_years"] or 0) - gold["years"])
        years_err.append(err)
        stats["years_within_0_5"] += err <= 0.5
        f1 = prf(set(p["skills"]), gold["skills"])[2]
        skill_f1.append(f1)
        by_style[style].append(f1)
    return {
        "n": len(pop), "pipeline": "текст → PDF (ReportLab) → pdfminer.six → парсер",
        "field_accuracy": {k: r3(v / len(pop)) for k, v in stats.items()},
        "experience_mae_years": r3(np.mean(years_err)),
        "skills_f1": r3(np.mean(skill_f1)),
        "skills_f1_by_template": {k: r3(np.mean(v)) for k, v in by_style.items()},
    }


def main() -> dict:
    t0 = time.time()
    report = {"generated_at": time.strftime("%Y-%m-%d %H:%M"), "vacancies": vacancy_eval(), "resumes": resume_eval()}
    report["runtime_sec"] = round(time.time() - t0, 1)
    save_report("nlp_validation", report)
    return report


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False, indent=1))
