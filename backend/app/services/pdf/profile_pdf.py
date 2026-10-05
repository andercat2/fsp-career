"""Генерация стандартизированного PDF-профиля кандидата (ReportLab, шрифт Montserrat, цвета ФСП).

Структура одинакова для всех кандидатов — работодатель сравнивает профили «один к одному»:
категория и грейд по тесту → оценки по доменам → подтверждённые/заявленные навыки → ФСП → опыт → образование.
"""
from __future__ import annotations

import io
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.db import utcnow
from app.services.reference.skills import SKILL_BY_ID
from app.services.reference.taxonomy import DOMAINS, GRADE_NAMES, SPEC_NAMES, WORK_FORMATS

FONT_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"
PINK = colors.HexColor("#FF0053")
PURPLE = colors.HexColor("#310F53")
LAVENDER = colors.HexColor("#8A83D1")
LIGHT = colors.HexColor("#FFD6E4")
DARK = colors.HexColor("#1C1D22")
GREY = colors.HexColor("#6B6B7B")

_registered = False


def _fonts() -> None:
    global _registered
    if _registered:
        return
    pdfmetrics.registerFont(TTFont("Mont", str(FONT_DIR / "Montserrat-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("Mont-Bold", str(FONT_DIR / "Montserrat-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("Mont-Semi", str(FONT_DIR / "Montserrat-SemiBold.ttf")))
    _registered = True


def _styles() -> dict[str, ParagraphStyle]:
    return {
        "name": ParagraphStyle("name", fontName="Mont-Bold", fontSize=20, leading=24, textColor=colors.white),
        "head": ParagraphStyle("head", fontName="Mont", fontSize=10.5, leading=14, textColor=LIGHT),
        "h2": ParagraphStyle("h2", fontName="Mont-Bold", fontSize=12, leading=16, textColor=PURPLE, spaceBefore=8,
                             spaceAfter=4),
        "body": ParagraphStyle("body", fontName="Mont", fontSize=9.5, leading=13, textColor=DARK, alignment=TA_LEFT),
        "small": ParagraphStyle("small", fontName="Mont", fontSize=8, leading=10.5, textColor=GREY),
        "badge": ParagraphStyle("badge", fontName="Mont-Bold", fontSize=10, leading=13, textColor=colors.white),
    }


def _p(text, style):
    return Paragraph(escape(str(text)) if text is not None else "—", style)


def _bar(score: float, width: float = 60 * mm) -> Table:
    filled = max(0.02, min(1.0, score))
    t = Table([["", ""]], colWidths=[width * filled, width * (1 - filled)], rowHeights=[3.2 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), PINK), ("BACKGROUND", (1, 0), (1, 0), LIGHT),
                           ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    return t


def render_profile_pdf(view: dict) -> bytes:
    """view — словарь из services.candidates.employer_view / own_view (уже с учётом приватности)."""
    _fonts()
    st = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm, topMargin=12 * mm,
                            bottomMargin=14 * mm, title=f"Профиль кандидата {view.get('public_id')}",
                            author="ФСП Карьера")
    story = []
    cat = view.get("category") or {}
    grade_txt = (f"{cat.get('specialization_name')} · {cat.get('grade_name')}" if cat.get("grade")
                 else "Категория не присвоена — тестирование не пройдено")
    header = Table([
        [_p(view.get("display_name"), st["name"]), _p(grade_txt, st["badge"])],
        [_p(view.get("headline") or "", st["head"]),
         _p(f"Выше {cat.get('percentile')}% кандидатов" if cat.get("percentile") is not None else "", st["head"])],
    ], colWidths=[118 * mm, 64 * mm])
    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PURPLE), ("BACKGROUND", (1, 0), (1, 0), PINK),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story += [header, Spacer(1, 6)]

    facts = []
    if view.get("city"):
        facts.append(f"Город: {view['city']}{' (готов к переезду)' if view.get('relocation') else ''}")
    if view.get("experience_years") is not None:
        facts.append(f"Опыт: {view['experience_years']:g} г.")
    if view.get("work_formats"):
        facts.append("Формат: " + ", ".join(WORK_FORMATS.get(f, f) for f in view["work_formats"]))
    if view.get("desired_salary"):
        facts.append(f"Ожидания: от {view['desired_salary']:,} ₽".replace(",", " "))
    story.append(_p("   •   ".join(facts), st["body"]))
    contacts = view.get("contacts")
    if contacts:
        c = [v for v in (contacts.get("email"), contacts.get("phone"), contacts.get("telegram")) if v]
        story.append(_p("Контакты: " + ", ".join(c), st["body"]))
    if view.get("about"):
        story += [Spacer(1, 4), _p(view["about"], st["body"])]

    domains = (view.get("test") or {}).get("domains") or {}
    if domains:
        story.append(_p("Результаты тестирования по доменам", st["h2"]))
        rows = []
        for d, v in sorted(domains.items(), key=lambda kv: -kv[1].get("score", 0)):
            rows.append([_p(DOMAINS.get(d, d), st["body"]), _bar(v.get("score", 0)),
                         _p(f"{round(v.get('score', 0) * 100)}%  ({v.get('correct')}/{v.get('n')})", st["small"])])
        t = Table(rows, colWidths=[62 * mm, 64 * mm, 40 * mm])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
        story.append(t)
        story.append(_p("Оценка — вероятность решить типичное задание уровня заявленного грейда. Задания адаптивные "
                        "и уникальные для каждого кандидата.", st["small"]))

    verified = set(view.get("verified_skills") or [])
    skills = view.get("skills") or []
    if skills or verified:
        story.append(_p("Навыки", st["h2"]))
        ver = [SKILL_BY_ID[s].name for s in verified if s in SKILL_BY_ID]
        dec = [SKILL_BY_ID[s].name for s in skills if s in SKILL_BY_ID and s not in verified]
        if ver:
            story.append(_p("✓ Подтверждены тестом: " + ", ".join(ver), st["body"]))
        if dec:
            story.append(_p("Заявлены кандидатом: " + ", ".join(dec), st["body"]))

    fsp = view.get("fsp") or {}
    story.append(_p("Достижения ФСП", st["h2"]))
    if fsp.get("achievements"):
        rows = [[_p(a["date"][:7], st["small"]), _p(a["event"], st["body"]),
                 _p(f"{a['level_name']}, {a['place_label']}", st["small"])] for a in fsp["achievements"][:8]]
        t = Table(rows, colWidths=[18 * mm, 110 * mm, 54 * mm])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -2), 0.3, LIGHT)]))
        story.append(t)
        story.append(_p("Данные получены из реестра ФСП по привязанному ФСП ID.", st["small"]))
    elif fsp.get("linked"):
        story.append(_p("ФСП ID привязан, достижений в реестре пока нет.", st["body"]))
    else:
        story.append(_p("История участия в соревнованиях ФСП не привязана.", st["body"]))

    exp = view.get("experience") or []
    if exp:
        story.append(_p("Опыт работы", st["h2"]))
        for e in exp[:6]:
            period = f"{e.get('start') or ''} — {e.get('end') or 'н. в.'}"
            block = [_p(f"{e.get('position') or 'Должность не указана'} · {e.get('company') or 'Компания скрыта'}",
                        ParagraphStyle("x", parent=st["body"], fontName="Mont-Semi")),
                     _p(period, st["small"])]
            if e.get("description"):
                block.append(_p(e["description"], st["body"]))
            story.append(KeepTogether(block + [Spacer(1, 3)]))
    edu = view.get("education") or []
    if edu:
        story.append(_p("Образование", st["h2"]))
        for e in edu:
            if not isinstance(e, dict):
                story.append(_p(str(e), st["body"]))
                continue
            details = ", ".join(str(x) for x in (e.get("level"), e.get("specialty"), e.get("year")) if x)
            story.append(_p(f"{e.get('title')}" + (f" — {details}" if details else ""), st["body"]))
    langs = view.get("languages") or []
    if langs:
        story.append(_p("Языки", st["h2"]))
        story.append(_p(" · ".join(f"{x.get('name')}" + (f" — {x.get('level')}" if x.get("level") else "") for x in langs),
                        st["body"]))

    story += [Spacer(1, 10), _p(f"Профиль сформирован платформой «ФСП Карьера» {utcnow():%d.%m.%Y}. Код профиля "
                                 f"{view.get('public_id')}. Категория и оценки получены по результатам адаптивного "
                                 f"тестирования, а не из самоописания.", st["small"])]

    def _page(canvas, _doc):
        canvas.saveState()
        canvas.setFillColor(PINK)
        canvas.rect(0, 0, A4[0], 3 * mm, stroke=0, fill=1)
        canvas.setFont("Mont", 7.5)
        canvas.setFillColor(GREY)
        canvas.drawRightString(A4[0] - 14 * mm, 6 * mm, f"ФСП Карьера · {view.get('public_id')} · стр. {_doc.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_page, onLaterPages=_page)
    return buf.getvalue()


def spec_grade_label(spec: str | None, grade: str | None) -> str:
    if not spec or not grade:
        return "—"
    return f"{SPEC_NAMES.get(spec, spec)} · {GRADE_NAMES.get(grade, grade)}"
