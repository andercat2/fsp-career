"""Презентация решения на шаблоне организаторов «ЛЦТ 2026 · ФСП».

python build_deck.py <шаблон.pptx> <папка скриншотов> <out.pptx>

Скриншоты снимает shots.js (Chrome headless по работающему стенду), иллюстрации — docs/figures/make_figures.py.
Слайды шаблона переставляются и заполняются: фоны, логотипы организаторов, «пилюли» заголовков, рамки устройств
и иконки берутся из самого шаблона; диаграммы — нативные (редактируются в PowerPoint).
"""
from __future__ import annotations

import copy
import io
import sys
import tempfile
from pathlib import Path

from lxml import etree
from PIL import Image, ImageFont
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.opc.packuri import PackURI
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

TEMPLATE, SHOTS, OUT = (Path(a) for a in sys.argv[1:4])
REPO = Path(__file__).resolve().parents[3]
FIG = REPO / "docs" / "figures"
BOLD_FONT = REPO / "backend" / "app" / "assets" / "fonts" / "Montserrat-Bold.ttf"
ASSETS = Path(tempfile.gettempdir()) / "fsp_career_deck_assets"  # промежуточные обрезки и иконки
ASSETS.mkdir(parents=True, exist_ok=True)

PINK, BLUSH, LAV, PURPLE, DEEP, INK, MUTED, WHITE = ("FF0053", "FFD6E3", "8A83D1", "520977", "2D1451", "1C1D22",
                                                     "5B6475", "FFFFFF")
EMU = 914400

# Слайды шаблона в порядке презентации (номера — как в исходном шаблоне)
ORDER = [7, 8, 9, 10, 11, 4, 24, 27, 26, 18, 21, 22, 16, 23, 19, 17, 20, 13, 29, 14, 15, 25, 12]


# ------------------------------------------------------------------ текст

def rgb(h: str) -> RGBColor:
    return RGBColor.from_string(h)


def _set_fill(rPr, color: str) -> None:
    for tag in ("a:noFill", "a:solidFill", "a:gradFill", "a:blipFill", "a:pattFill", "a:grpFill"):
        for el in rPr.findall(qn(tag)):
            rPr.remove(el)
    fill = etree.Element(qn("a:solidFill"))
    etree.SubElement(fill, qn("a:srgbClr"), val=color)
    ln = rPr.find(qn("a:ln"))
    rPr.insert(list(rPr).index(ln) + 1 if ln is not None else 0, fill)


def write(shape, paras, *, size=None, color=None, bold=None, align=None, after=None, line=None, bullet=None,
          anchor=None, keep=True):
    """Заменяет текст фигуры, сохраняя оформление первого абзаца и первого фрагмента шаблона.

    paras — список абзацев: строка или список фрагментов (текст, {bold, color, size, italic})."""
    body = shape.text_frame._txBody
    fit = body.find(qn("a:bodyPr")).find(qn("a:normAutofit"))
    if fit is not None:
        fit.attrib.pop("fontScale", None)
        fit.attrib.pop("lnSpcReduction", None)
    ps = body.findall(qn("a:p"))
    tpl_pPr = tpl_rPr = None
    if keep and ps:
        if ps[0].find(qn("a:pPr")) is not None:
            tpl_pPr = copy.deepcopy(ps[0].find(qn("a:pPr")))
        r0 = next((p.find(qn("a:r")) for p in ps if p.find(qn("a:r")) is not None), None)
        if r0 is not None and r0.find(qn("a:rPr")) is not None:
            tpl_rPr = copy.deepcopy(r0.find(qn("a:rPr")))
    for p in ps:
        body.remove(p)
    for para in paras:
        runs = [(para, {})] if isinstance(para, str) else para
        p = etree.SubElement(body, qn("a:p"))
        pPr = copy.deepcopy(tpl_pPr) if tpl_pPr is not None else etree.Element(qn("a:pPr"))
        p.append(pPr)
        if align:
            pPr.set("algn", {"l": "l", "c": "ctr", "r": "r"}[align])
        if after is not None or line is not None:
            for tag in ("a:lnSpc", "a:spcBef", "a:spcAft"):
                el = pPr.find(qn(tag))
                if el is not None and ((tag == "a:spcAft" and after is not None) or (tag == "a:lnSpc" and line is not None)):
                    pPr.remove(el)
            # порядок дочерних элементов pPr: lnSpc, spcBef, spcAft, bu*
            if line is not None:
                ls = etree.Element(qn("a:lnSpc"))
                etree.SubElement(ls, qn("a:spcPct"), val=str(int(line * 100000)))
                pPr.insert(0, ls)
            if after is not None:
                sa = etree.Element(qn("a:spcAft"))
                etree.SubElement(sa, qn("a:spcPts"), val=str(int(after * 100)))
                idx = 0
                for i, ch in enumerate(pPr):
                    if ch.tag in (qn("a:lnSpc"), qn("a:spcBef")):
                        idx = i + 1
                pPr.insert(idx, sa)
        if bullet is not None:
            for tag in ("a:buNone", "a:buChar", "a:buAutoNum", "a:buFont", "a:buClr", "a:buSzPct"):
                for el in pPr.findall(qn(tag)):
                    pPr.remove(el)
            if bullet:
                pPr.set("marL", "228600")
                pPr.set("indent", "-228600")
                bc = etree.SubElement(pPr, qn("a:buClr"))
                etree.SubElement(bc, qn("a:srgbClr"), val=bullet if isinstance(bullet, str) else PINK)
                etree.SubElement(pPr, qn("a:buFont"), typeface="Arial")
                etree.SubElement(pPr, qn("a:buChar"), char="•")
            else:
                pPr.set("marL", "0")
                pPr.set("indent", "0")
                etree.SubElement(pPr, qn("a:buNone"))
        for text, st in runs:
            r = etree.SubElement(p, qn("a:r"))
            rPr = copy.deepcopy(tpl_rPr) if tpl_rPr is not None else etree.Element(qn("a:rPr"))
            r.append(rPr)
            rPr.set("lang", "ru-RU")
            rPr.attrib.pop("dirty", None)
            s = st.get("size", size)
            if s:
                rPr.set("sz", str(int(s * 100)))
            b = st.get("bold", bold)
            if b is not None:
                rPr.set("b", "1" if b else "0")
            if st.get("italic"):
                rPr.set("i", "1")
            c = st.get("color", color)
            if c:
                _set_fill(rPr, c)
            t = etree.SubElement(r, qn("a:t"))
            t.text = text
    if anchor:
        shape.text_frame.vertical_anchor = {"t": MSO_ANCHOR.TOP, "m": MSO_ANCHOR.MIDDLE, "b": MSO_ANCHOR.BOTTOM}[anchor]
    return shape


def textbox(slide, x, y, w, h, paras, *, size=14, color=INK, bold=None, align=None, after=None, line=None, bullet=None,
            anchor="t", name=None, wrap=True):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = wrap
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    if name:
        tb.name = name
    write(tb, paras, size=size, color=color, bold=bold, align=align, after=after, line=line, bullet=bullet,
          anchor=anchor, keep=False)
    return tb


def ph(slide, idx):
    for s in slide.placeholders:
        if s.placeholder_format.idx == idx:
            return s
    raise KeyError(f"нет плейсхолдера {idx}")


def by_name(slide, name, nth=0):
    """n-я (в порядке документа) фигура с точно таким именем — в шаблоне имена повторяются."""
    found = [s for s in slide.shapes if s.name == name]
    return found[nth]


def by_text(slide, fragment):
    return next(s for s in slide.shapes if s.has_text_frame and fragment in s.text_frame.text)


def remove(shape):
    el = shape._element
    el.getparent().remove(el)


def to_back(slide, shape):
    tree = slide.shapes._spTree
    el = shape._element
    tree.remove(el)
    tree.insert(2, el)  # после nvGrpSpPr и grpSpPr


_FONT = ImageFont.truetype(str(BOLD_FONT), 200)


def text_width_in(text: str, pt: float) -> float:
    return _FONT.getlength(text) / 200 * pt / 72


def pill_title(slide, title: str, *, add_pill_color=None, color=None):
    """Заголовок на «пилюле» шаблона: ширина пилюли подгоняется под текст; на светлых слайдах без пилюли — добавляется."""
    t = slide.shapes.title
    pills = [s for s in slide.shapes if s.shape_type == 1 and abs(s.top / EMU - 0.35) < 0.15 and abs(s.height / EMU - 0.68) < 0.1]
    width = text_width_in(title, 20) + 0.62
    if pills:
        pill = pills[0]
    elif add_pill_color:
        pill = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.38), Inches(0.35), Inches(width), Inches(0.68))
        pill.adjustments[0] = 0.18706
        pill.fill.solid()
        pill.fill.fore_color.rgb = rgb(add_pill_color)
        pill.line.fill.background()
        pill.shadow.inherit = False
        pill.name = "Пилюля заголовка"
        to_back(slide, pill)
    else:
        pill = None
    if pill is not None:
        pill.width = Inches(width)
        t.left, t.top, t.width, t.height = pill.left + Inches(0.2), pill.top + Inches(0.12), Inches(width - 0.25), Inches(0.44)
    write(t, [title], color=color)
    t.text_frame.word_wrap = False
    return t


def set_slide_number(slide, n):
    """Номер слайда: в полях slidenum обновляется сохранённое значение, статичные надписи переписываются."""
    for s in slide.shapes:
        if s.name.startswith("Номер слайда") and s.has_text_frame:
            fld = s._element.find(".//" + qn("a:fld"))
            if fld is None:
                write(s, [str(n)])
            elif fld.find(qn("a:t")) is not None:
                fld.find(qn("a:t")).text = str(n)


def notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text


def clone_slide(prs, src):
    """Новый слайд на макете src с копиями всех его фигур (рамки устройств, «пилюля», плейсхолдеры). Фигуры шаблона
    без связей (картинок нет), поэтому копируются как XML; вызывать до того, как src заполнен содержимым."""
    new = prs.slides.add_slide(src.slide_layout)
    # имя части по числу слайдов (slideN.xml) может совпасть с уже существующим слайдом шаблона — берём свободное
    used = {str(p.partname) for p in prs.part.package.iter_parts()}
    n = next(k for k in range(100, 1000) if f"/ppt/slides/slide{k}.xml" not in used)
    new.part.partname = PackURI(f"/ppt/slides/slide{n}.xml")
    for sh in list(new.shapes):
        remove(sh)
    for sh in src.shapes:
        new.shapes._spTree.append(copy.deepcopy(sh._element))
    bg = src._element.cSld.find(qn("p:bg"))  # фон слайда — картинка: копируем и связываем с тем же изображением
    if bg is not None:
        bg = copy.deepcopy(bg)
        for blip in bg.iter(qn("a:blip")):
            rel = src.part.rels[blip.get(qn("r:embed"))]
            blip.set(qn("r:embed"), new.part.relate_to(rel.target_part, rel.reltype))
        new._element.cSld.insert(0, bg)
    return new


def move_slide(prs, slide, index):
    lst = prs.slides._sldIdLst
    el = next(e for e in lst if e.get("id") == str(slide.slide_id))
    lst.remove(el)
    lst.insert(index, el)


# ------------------------------------------------------------------ изображения

def crop_aspect(src: Path, aspect: float, name: str, box=None, anchor="top") -> Path:
    """Обрезает изображение до соотношения сторон w/h (по умолчанию от верхнего края) и сохраняет в ASSETS."""
    im = Image.open(src).convert("RGB")
    if box:
        im = im.crop(box)
    w, h = im.size
    if w / h > aspect:
        nw = int(h * aspect)
        x0 = (w - nw) // 2
        im = im.crop((x0, 0, x0 + nw, h))
    else:
        nh = int(w / aspect)
        y0 = 0 if anchor == "top" else (h - nh) // 2
        im = im.crop((0, y0, w, y0 + nh))
    out = ASSETS / f"{name}.png"
    im.save(out, optimize=True)
    return out


def crop_box(src: Path, box, name: str) -> Path:
    out = ASSETS / f"{name}.png"
    Image.open(src).convert("RGB").crop(box).save(out, optimize=True)
    return out


def fit_picture(slide, path: Path, x, y, w, h, *, rounded=False, border=None, align="c"):
    im = Image.open(path)
    a = im.width / im.height
    if w / h > a:
        pw, ph_ = h * a, h
    else:
        pw, ph_ = w, w / a
    px = x + (w - pw) / 2 if align == "c" else x
    py = y + (h - ph_) / 2
    pic = slide.shapes.add_picture(str(path), Inches(px), Inches(py), Inches(pw), Inches(ph_))
    if rounded:
        pic.auto_shape_type = MSO_SHAPE.ROUNDED_RECTANGLE
        av = pic._element.spPr.find(qn("a:prstGeom")).find(qn("a:avLst"))
        etree.SubElement(av, qn("a:gd"), name="adj", fmla="val 4000")  # небольшой радиус скругления
    if border:
        pic.line.color.rgb = rgb(border)
        pic.line.width = Pt(0.75)
    return pic


def fill_picture_ph(slide, idx, path: Path, box=None):
    """Картинка в плейсхолдер слайда. insert_picture теряет собственные координаты слайда и берёт координаты
    макета, поэтому геометрия восстанавливается явно; изображение заранее обрезается до пропорций рамки."""
    p = ph(slide, idx)
    geom = (p.left, p.top, p.width, p.height)
    src = crop_aspect(path, p.width / p.height, f"{path.stem}_{idx}_{round(p.width / p.height, 3)}", box=box)
    pic = p.insert_picture(str(src))
    pic.left, pic.top, pic.width, pic.height = geom
    return pic


def blank_layout_prompts(prs):
    """LibreOffice рисует текстовые плейсхолдеры макетов как объекты мастер-страницы вместе с подсказками
    («Образец текста»); PowerPoint их не показывает. Подсказки очищаются, оформление (lstStyle) остаётся."""
    used = {id(sl.slide_layout.part): sl.slide_layout for sl in prs.slides}
    for lay in used.values():
        for p in lay.placeholders:
            if p.placeholder_format.idx not in (0, 1, 2, 3, 4) and p.has_text_frame:
                for t in p._element.iter(qn("a:t")):
                    t.text = ""


def template_icon(src_prs, slide_no: int, k: int, color: str | None = None) -> Path:
    """Иконка из библиотеки шаблона (слайды 32–36): k — номер по порядку сверху вниз, слева направо."""
    s = src_prs.slides[slide_no - 1]
    pics = sorted(((sh.top, sh.left, sh.image.blob) for sh in s.shapes if sh.shape_type == 13), key=lambda t: (t[0], t[1]))
    im = Image.open(io.BytesIO(pics[k][2])).convert("RGBA")
    if color:
        r, g, b = (int(color[i:i + 2], 16) for i in (0, 2, 4))
        alpha = im.getchannel("A")
        im = Image.new("RGBA", im.size, (r, g, b, 255))
        im.putalpha(alpha)
    out = ASSETS / f"icon_{slide_no}_{k}_{color or 'white'}.png"
    im.save(out)
    return out


# ------------------------------------------------------------------ диаграммы

def style_chart(chart, *, label_color, axis_color, grid_color, legend=True, max_value=100, pct=True, size=11,
                major=20, value_axis=True):
    chart.has_title = False
    chart.font.size = Pt(size)
    chart.font.color.rgb = rgb(axis_color)
    plot = chart.plots[0]
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.number_format = '0"%"' if pct else "0"
    dl.number_format_is_linked = False
    dl.font.size = Pt(size)
    dl.font.bold = True
    dl.font.color.rgb = rgb(label_color)
    dl.position = XL_LABEL_POSITION.OUTSIDE_END
    dl.show_value = True
    va = chart.value_axis
    va.minimum_scale, va.maximum_scale = 0, max_value
    va.major_unit = major
    va.visible = value_axis
    va.has_major_gridlines = True
    va.major_gridlines.format.line.color.rgb = rgb(grid_color)
    va.major_gridlines.format.line.width = Pt(0.5)
    va.format.line.fill.background()
    va.tick_labels.font.size = Pt(size - 1)
    va.tick_labels.font.color.rgb = rgb(axis_color)
    va.tick_labels.number_format = '0"%"' if pct else "0"
    va.tick_labels.number_format_is_linked = False
    ca = chart.category_axis
    ca.tick_labels.font.size = Pt(size)
    ca.tick_labels.font.color.rgb = rgb(axis_color)
    ca.format.line.color.rgb = rgb(grid_color)
    ca.has_major_gridlines = False
    chart.has_legend = legend
    if legend:
        chart.legend.position = XL_LEGEND_POSITION.BOTTOM
        chart.legend.include_in_layout = False
        chart.legend.font.size = Pt(size)
        chart.legend.font.color.rgb = rgb(axis_color)


def color_series(chart, colors):
    for s, c in zip(chart.series, colors, strict=False):
        s.format.fill.solid()
        s.format.fill.fore_color.rgb = rgb(c)
        s.format.line.fill.background()


def color_points(series, colors):
    for i, c in enumerate(colors):
        pt = series.points[i]
        pt.format.fill.solid()
        pt.format.fill.fore_color.rgb = rgb(c)
        pt.format.line.fill.background()


# ------------------------------------------------------------------ сборка

def reorder(prs):
    lst = prs.slides._sldIdLst
    ids = list(lst)
    for el in ids:
        lst.remove(el)
    for n in ORDER:
        lst.append(ids[n - 1])
    for i, el in enumerate(ids, 1):
        if i not in ORDER:
            prs.part.rels.pop(el.get(qn("r:id")))


def main():
    src = Presentation(TEMPLATE)  # отдельная копия — источник иконок
    prs = Presentation(TEMPLATE)
    reorder(prs)
    blank_layout_prompts(prs)
    S = list(prs.slides)
    shot = lambda n: SHOTS / f"{n}.png"  # noqa: E731
    ic = lambda sl, k, c=None: template_icon(src, sl, k, c)  # noqa: E731
    code_s = clone_slide(prs, S[7])  # «Задачи с кодом» — на макете «Пути кандидата» (две рамки браузера)
    move_slide(prs, code_s, 12)  # после «Механики подбора»

    # 1 ── Титульный: команда, задача, логотип постановщика (ФСП) ───────────────────────────
    s = S[0]
    write(s.shapes.title, [[("ФСП Карьера", {"size": 44, "bold": True})],
                           [("Команда «Название команды»", {"size": 20, "bold": False, "color": BLUSH})]], line=1.0)
    write(ph(s, 12), ["Задача ФСП: цифровая платформа-агрегатор ИТ-вакансий с верифицированным профилем "
                      "достижений участника Федерации спортивного программирования"])
    notes(s, "Мы — команда «…». Наше решение для задачи ФСП — платформа «ФСП Карьера»: подбор ИТ-специалистов с "
             "обратной механикой, где уровень подтверждает тест, а инициатива — у работодателя.")

    # 2 ── О команде и решении ───────────────────────────────────────────────────────────────
    s = S[1]
    fill_picture_ph(s, 10, shot("landing"))
    t = s.shapes.title
    write(t, ["О команде и решении"], color=DEEP, size=20)
    write(by_text(s, "Капитан:"), [
        [("Капитан: ", {"bold": True}), ("[ФИО, специальность]", {})],
        [("Участников: ", {"bold": True}), ("[N человек]", {})],
        [("О команде: ", {"bold": True}), ("[как собралась команда, место учёбы или работы]", {})],
        [("Город и регион: ", {"bold": True}), ("[город, регион]", {})],
    ])
    essence = by_text(s, "В чем суть вашего решения")
    essence.height = Inches(1.75)
    write(essence, [
        "ФСП Карьера — платформа подбора ИТ-специалистов с обратной механикой: кандидат подтверждает уровень "
        "адаптивным тестом и получает категорию, работодатель находит категорию и сам приглашает конкретного "
        "человека — с вилкой зарплаты. Контакты открываются после согласия кандидата."], size=12)
    uniq = by_text(s, "Что делает ваше решение")
    uniq.height = Inches(1.5)
    write(uniq, [
        "Тест, устойчивый к утечкам: свои варианты заданий при одинаковой сложности (IRT) и прокторинг. "
        "Категория — по тесту, а не по резюме, до трёх специализаций; ФСП усиливает профиль без штрафа за отсутствие. "
        "Задачи с кодом — в песочнице с антиплагиатом."], size=12)
    notes(s, "Кратко о команде (заполните поля) и суть решения: обратная механика найма на основе подтверждённого уровня.")

    # 3 ── Команда ──────────────────────────────────────────────────────────────────────────
    s = S[2]
    pill_title(s, "КОМАНДА «НАЗВАНИЕ»")
    notes(s, "Участники, роли и контакты. Заполните ФИО, роли, мессенджеры, телефоны и место учёбы или работы; "
             "фото вставляются в круглые рамки карточек.")

    # 4 ── История, выбор задачи, сложности ─────────────────────────────────────────────────
    s = S[3]
    pill_title(s, "КАК МЫ РАБОТАЛИ")
    write(ph(s, 27), ["[Как собралась команда, в каких хакатонах и проектах участвовали вместе, интересные факты]"])
    why = by_text(s, "Что вас вдохновило")
    write(why, [
        "Задача соединяет психометрику (как честно измерить навык), ML и NLP для подбора и продуктовую механику "
        "найма — и её результат можно доказать числами, построив собственную процедуру валидации."])
    hard = by_text(s, "Расскажите о самых интересных")
    write(hard, [
        "1) Нет эталонных данных → синтетическая популяция с известной «истиной» для проверки теста и подбора",
        "2) Утечки против сопоставимости → семейства заданий с уникальными вариантами на общей шкале IRT",
        "3) Первые версии подбора уступали фильтрам → разобрали ошибки и довели P@10 до 0,84 против 0,75"])
    why.width = Inches(11.2)
    hard.width, hard.height = Inches(11.2), Inches(1.3)
    notes(s, "История команды — заполните. Почему задача: измеримость результата. Главные сложности — отсутствие "
             "разметки, компромисс «утечки против сопоставимой сложности» и качество подбора, которое мы доказали валидацией.")

    # 5 ── Коротко о решении ────────────────────────────────────────────────────────────────
    s = S[4]
    pill_title(s, "КОРОТКО О РЕШЕНИИ")
    write(ph(s, 38), [
        "Адаптивный тест IRT (3PL): 359 семейств заданий, свой вариант каждому, прокторинг",
        "Категория = специализация × грейд по тесту; до трёх специализаций; смена — раз в месяц",
        "Подбор: NLP-разбор вакансии → категории → ранжирование с объяснением",
        "ФСП ID по OpenID Connect (пути Keycloak); резюме из PDF, включая экспорт hh.ru",
        "Задачи с кодом: песочница без сети, скрытые тесты, антиплагиат",
        "FastAPI, PostgreSQL, React; Docker, 104 метода OpenAPI, 520 автотестов",
    ], size=14, after=9)
    write(ph(s, 42), [
        "Работодатель видит только кандидатов с подтверждённым уровнем и рынок категории до найма",
        "Кандидат получает предложения с вилкой до начала общения — без откликов вслепую",
        "ФСП получает канал трудоустройства участников и аргумент для вовлечения в соревнования",
        "Развитие: пилот с ФСП и партнёрами, ATS-интеграции, тарифы для компаний",
    ], size=14, after=9)
    notes(s, "Техническая суть — адаптивный тест и объяснимый подбор; маркетинговая — ценность для каждой из трёх сторон.")

    # 6 ── Структура презентации решения ────────────────────────────────────────────────────
    s = S[5]
    write(by_text(s, "РЕКОМЕНДУЕМАЯ СТРУКТУРА"), ["ПРЕЗЕНТАЦИЯ РЕШЕНИЯ"])
    by_name(s, "Скругленный прямоугольник 1").width = Inches(text_width_in("ПРЕЗЕНТАЦИЯ РЕШЕНИЯ", 20) + 0.9)
    sub = by_text(s, "Для продуктовых решений")
    write(sub, ["Шесть разделов по рекомендуемой структуре"])
    sub.width = Inches(8)
    ranges = ["слайды 7–16", "слайд 17", "слайд 18", "слайды 19–21", "слайд 22", "слайд 23"]
    boxes = sorted([sh for sh in s.shapes if sh.name.startswith("Скругленный прямоугольник") and sh.height / EMU > 1.5],
                   key=lambda b: (round(b.top / EMU, 1), b.left))
    for b, r in zip(boxes, ranges, strict=True):
        textbox(s, b.left / EMU + 1.1, b.top / EMU + 0.3, 1.3, 0.3, [r], size=10, color=LAV, align="r")
    notes(s, "Дальше — по рекомендуемой структуре: описание решения и механик, маркетинг, бизнес, техника, "
             "уникальность и планы.")

    # 7 ── 01 · Проблема → как сейчас → решение ────────────────────────────────────────────
    s = S[6]
    pill_title(s, "01 · ПРОБЛЕМА И РЕШЕНИЕ")
    for name in ("Google Shape;2829;p94", "Google Shape;2818;p94", "Google Shape;2805;p94"):
        remove(by_name(s, name))
    frames = sorted([sh for sh in s.shapes if sh.name.startswith("Скругленный прямоугольник") and abs(sh.width / EMU - 1.65) < 0.05],
                    key=lambda b: b.left)
    for fr, (sl, k) in zip(frames, [(36, 62), (33, 3), (33, 2)], strict=True):
        fit_picture(s, ic(sl, k), fr.left / EMU + 0.4, fr.top / EMU + 0.33, 0.85, 0.85)
    cards = sorted([sh for sh in s.shapes if sh.name.startswith("Скругленный прямоугольник") and sh.height / EMU > 3],
                   key=lambda b: b.left)
    heads = {33: "Проблема", 34: "Как ищут сейчас", 35: "Наше решение"}
    for (idx, txt), card, di in zip(heads.items(), cards, (26, 31, 32), strict=True):
        lp = next(p for p in s.slide_layout.placeholders if p.placeholder_format.idx == idx)
        s.shapes.clone_placeholder(lp)
        hd = write(ph(s, idx), [txt], color=DEEP, bullet=False, size=17)
        hd.left, hd.top, hd.width, hd.height = card.left + Inches(0.25), card.top + Inches(0.25), card.width - Inches(0.5), Inches(0.45)
        d = ph(s, di)
        d.left, d.top, d.width, d.height = card.left + Inches(0.25), card.top + Inches(0.85), card.width - Inches(0.5), Inches(2.4)
    write(ph(s, 26), ["Резюме не подтверждает навыки: отбор сводится к ключевым словам, работодатель вручную разбирает "
                      "сотни откликов, кандидат откликается вслепую и узнаёт условия последним."], size=15, color=INK)
    write(ph(s, 31), ["Универсальные площадки: поиск по самоописанию. Единый тест быстро расходится между кандидатами, "
                      "а уникальные задания от нейросети несопоставимы по сложности."], size=15, color=INK)
    write(ph(s, 32), ["Категория по адаптивному тесту с уникальными вариантами на общей шкале IRT. Работодатель находит "
                      "категорию и приглашает кандидата с вилкой; контакты — после согласия."], size=15, color=INK)
    notes(s, "Проблема — резюме не доказывает квалификацию. Существующие подходы либо доверяют самоописанию, либо "
             "дают тест, который утекает. Мы подтверждаем уровень тестом, устойчивым к утечкам, и меняем направление инициативы.")

    # 8 ── 01 · Путь кандидата (два экрана) ─────────────────────────────────────────────────
    s = S[7]
    pill_title(s, "01 · ПУТЬ КАНДИДАТА")
    fill_picture_ph(s, 14, shot("runner"))
    fill_picture_ph(s, 18, shot("grade"))
    for grp in (sh for sh in s.shapes if sh.shape_type == 6):
        for sub in grp.shapes:
            if sub.has_text_frame and "lider" in sub.text_frame.text:
                write(sub, ["localhost:8080 · ФСП Карьера"])
    write(ph(s, 15), [[("Опрос → адаптивный тест. ", {"bold": True, "color": DEEP}),
                       ("12–24 задания, свой вариант каждому, время по сложности задания. Снимок экрана — "
                        "предупреждение, повтор — завершение со штрафом. Без регистрации — экспресс-тест за 7 минут.", {})]],
          size=13, color=INK)
    write(ph(s, 16), [[("Категории и профиль. ", {"bold": True, "color": DEEP}),
                       ("До трёх резюме под разные специализации — у каждого свой тест и категория. Грейд не "
                        "понижается.", {})]], size=13, color=INK)
    notes(s, "Кандидат проходит опрос и адаптивный тест под прокторингом; задания подстраиваются под уровень, у каждого "
             "свои данные и свой код, время зависит от сложности. На выходе — категория, профиль компетенций и понятные "
             "правила пересдачи; вторая специализация — отдельное резюме со своим тестом и категорией. Проверить тест на "
             "себе можно без регистрации: экспресс-режим — 8 заданий за ≈ 7 минут, вероятный грейд и вероятности всех "
             "грейдов; категорию он не присваивает.")

    # 9 ── 01 · Путь работодателя (подборка на планшете) ────────────────────────────────────
    s = S[8]
    pill_title(s, "01 · ПУТЬ РАБОТОДАТЕЛЯ")
    p = ph(s, 14)
    src_sel = crop_aspect(shot("selection_full"), p.width / p.height, "selection_tablet", box=(560, 150, 2860, 2000))
    p.insert_picture(str(src_sel))
    steps = [("1. Потребность текстом. ", "NLP определяет специализацию, грейд, обязательные и желательные навыки, вилку, формат и город."),
             ("2. Категории и рынок. ", "Сколько кандидатов, медиана ожиданий, доля в вашей вилке, сколько с достижениями ФСП."),
             ("3. Кандидаты с объяснением. ", "Причины «за/против», фильтры без потери подборки, приглашение с обязательной вилкой.")]
    for idx, (h, d) in zip((15, 16, 17), steps, strict=True):
        write(ph(s, idx), [[(h, {"bold": True, "color": DEEP}), (d, {})]], size=13, color=INK)
    notes(s, "Работодатель пишет потребность обычным текстом. Система показывает подходящие категории с рынком и "
             "ранжированных кандидатов с объяснением, а дальше — приглашение с вилкой конкретному человеку.")

    # 10 ── 01 · Механика тестирования (6 пунктов) ──────────────────────────────────────────
    s = S[9]
    pill_title(s, "01 · МЕХАНИКА ТЕСТИРОВАНИЯ")
    items = [("Семейства заданий", "359 шаблонов по 27 доменам с откалиброванной трудностью; 125 — параметрические."),
             ("Свой вариант каждому", "Данные, код на языке кандидата и верный ответ генерируются из seed сессии."),
             ("Общая шкала IRT", "Модель 3PL и оценка уровня EAP: результаты с разными заданиями сопоставимы."),
             ("Адаптивный выбор", "Максимум информации, баланс доменов, случайный из топ-4, экспозиция ≤ 30%."),
             ("Решение по грейду", "Подтверждён при P(θ ≥ границы) ≥ 0,6; не прошёл — грейд ниже по тому же тесту (верно в 99,8%)."),
             ("Детекторы и прокторинг", "«Чужой вариант», дрейф заданий, person-fit; снимок экрана: предупреждение → штраф.")]
    for k, (h, d) in enumerate(items):
        write(ph(s, 49 + k), [f"{k + 1:02d}"], color=PINK)
        write(ph(s, 37 + 2 * k), [h], color=DEEP, size=15, bullet=False)
        write(ph(s, 38 + 2 * k), [d], color=INK, size=12, bullet=False)
    notes(s, "Ключ к устойчивости — семейства: структура задания и трудность фиксированы, а данные и ответ у каждого свои. "
             "Общая шкала IRT делает результаты сопоставимыми, адаптивный алгоритм — коротким тест, детекторы ловят списывание.")

    # 11 ── 01 · Устойчивость к утечкам (диаграмма + 3 меры) ────────────────────────────────
    s = S[10]
    pill_title(s, "01 · УСТОЙЧИВОСТЬ К УТЕЧКАМ")
    gf = next(sh for sh in s.shapes if sh.has_chart)
    gf.left, gf.top, gf.width, gf.height = Inches(0.38), Inches(1.9), Inches(6.3), Inches(4.9)
    cd = CategoryChartData()
    cd.categories = ["Честно", "K = 5", "K = 25", "K = 100"]
    cd.add_series("Фиксированный тест", (25.7, 96.8, 96.8, 96.8))
    cd.add_series("ФСП Карьера: незамеченное завышение", (12.1, 15.6, 13.0, 10.8))
    ch = gf.chart
    ch.replace_data(cd)
    style_chart(ch, label_color=WHITE, axis_color=WHITE, grid_color="7E4FA0", major=20)
    color_series(ch, [BLUSH, PINK])
    textbox(s, 0.45, 1.25, 6.2, 0.6, [[("Доля нечестных кандидатов, незаметно завысивших грейд, если «слита» база "
                                         "из K предыдущих прохождений", {})]], size=12, color=WHITE)
    boxes = [("Свой вариант у каждого", "Ответ из слитой базы не подходит к своему варианту: данные и ключ уникальны для каждого показа."),
             ("Детектор «чужого варианта»", "Ответ, совпавший с ключом чужого варианта, помечает сессию: 72–82% нечестных при 0,6% ложных."),
             ("Прокторинг и дрейф", "Снимок экрана: предупреждение, повтор — завершение со штрафом; «утёкшее» задание уходит из ротации.")]
    for (h, d), (hi, di) in zip(boxes, ((21, 18), (22, 23), (24, 25)), strict=True):
        write(ph(s, hi), [h], size=16, color=DEEP, bullet=False)
        write(ph(s, di), [d], size=12, color=INK, bullet=False)
    notes(s, "Эксперимент: нечестный кандидат знает все задания K предыдущих участников. Фиксированный тест завышают 97%, "
             "у нас незамеченное завышение остаётся на уровне честного прохождения — около 12%: списанное либо не подходит "
             "к своему варианту, либо помечается детектором и уходит на перепроверку. Снимки экрана ловит прокторинг.")

    # 12 ── 01 · Механика подбора (веса + 4 пункта) ─────────────────────────────────────────
    s = S[11]
    pill_title(s, "01 · МЕХАНИКА ПОДБОРА")
    gf = next(sh for sh in s.shapes if sh.has_chart)
    gf.left, gf.top, gf.width, gf.height = Inches(0.38), Inches(1.95), Inches(6.4), Inches(4.4)
    cd = CategoryChartData()
    cd.categories = ["Текст", "Условия", "Категория", "Сила профиля", "Навыки"]
    cd.add_series("Вес компоненты", (10, 15, 20, 25, 30))
    ch = gf.chart
    ch.replace_data(cd)
    style_chart(ch, label_color=DEEP, axis_color=INK, grid_color="E5E1EF", legend=False, max_value=35, size=12,
                major=10, value_axis=False)
    color_points(ch.series[0], [LAV, BLUSH, PURPLE, LAV, PINK])
    ch.plots[0].gap_width = 60
    textbox(s, 0.45, 1.25, 6.3, 0.6, [[("Оценка соответствия = взвешенная сумма компонент × доступность "
                                         "(город, формат, ожидания по доходу)", {})]], size=12, color=INK)
    items = [("Пул — категории по тесту", "Основная, соседние грейды, смежные; грейд не подтверждён — кандидат в выдаче со статусом и ниже, а не скрыт."),
             ("Навыки по свидетельствам теста", "«Подтверждён», «заявлен» или «не подтвердился» на уровне требований вакансии."),
             ("Сила профиля", "0,6 · тест + 0,25 · ФСП + 0,15 · регулярные задания; нет истории ФСП — нет штрафа."),
             ("Объяснение и отклик", "Причины «за/против» у каждого кандидата и вероятность, что он примет приглашение.")]
    for (h, d), (hi, di) in zip(items, ((21, 18), (22, 23), (24, 25), (26, 27)), strict=True):
        write(ph(s, hi), [h], size=15, color=DEEP, bullet=False)
        write(ph(s, di), [d], size=12, color=INK, bullet=False)
    notes(s, "Выдача строится из категорий, подтверждённых тестом. Внутри — пять понятных компонент; навыки "
             "проверяются тестом на уровне требований, а каждая карточка объясняет, почему кандидат в подборке. "
             "Как советовали постановщики, кандидат, чей грейд тест не подтвердил, не скрывается: он виден со статусом "
             "«не подтверждён» и ниже подтверждённых. На валидации это повышает точность и возвращает в выдачу "
             "кандидатов, которых тест ошибочно не подтвердил.")

    # 13 ── 01 · Задачи с кодом (новый слайд: кандидат и работодатель) ──────────────────────
    s = code_s
    pill_title(s, "01 · ЗАДАЧИ С КОДОМ")
    fill_picture_ph(s, 14, shot("code_cand"))
    fill_picture_ph(s, 18, shot("code_emp"))
    for grp in (sh for sh in s.shapes if sh.shape_type == 6):
        for sub in grp.shapes:
            if sub.has_text_frame and "lider" in sub.text_frame.text:
                write(sub, ["localhost:8080 · ФСП Карьера"])
    write(ph(s, 15), [[("Кандидат решает в браузере. ", {"bold": True, "color": DEEP}),
                       ("Запуск на открытых примерах в песочнице без сети; по скрытым тестам — только «пройден / нет».",
                        {})]], size=13, color=INK)
    write(ph(s, 16), [[("Работодатель видит всё. ", {"bold": True, "color": DEEP}),
                       ("Все тесты, антиплагиат по структуре кода (6 из 6 копий, 0 ложных) и вставки из буфера.",
                        {})]], size=13, color=INK)
    notes(s, "По рекомендации постановщиков задания пишет работодатель, а проверяет система: функция, открытые и скрытые "
             "тесты и эталон, который проверяет сами тесты. Код кандидата исполняется в контейнере без сети с лимитами; "
             "ответы скрытых тестов туда не передаются. Антиплагиат сравнивает структуру кода — переименование не "
             "спасает копию, — а вставки из буфера и уходы со вкладки показывают, не подсказала ли решение нейросеть.")

    # 13 ── 01 · Валидация: главное (4 карточки) ────────────────────────────────────────────
    s = S[12]
    pill_title(s, "01 · ВАЛИДАЦИЯ: ГЛАВНОЕ")
    stats = [("0,84", "Точность подбора", "Доля релевантных в топ-10. Фильтры по резюме — 0,75, поиск по ключевым словам — 0,27."),
             ("3,1%", "Завышение грейда", "Тест завышает грейд у 3,1% кандидатов, самооценка в резюме — у 36%. Грейд ±1 — 95%."),
             ("0,80", "Стабильность грейда", "Взвешенная κ при повторном тесте с другими заданиями; дискриминативность D = 0,42."),
             ("13%", "Незамеченное завышение", "При «слитой» базе из 25 прохождений — уровень честного теста (12%). Фиксированный тест — 97%.")]
    for k, (num, h, d) in enumerate(stats):
        n = ph(s, 49 + k)
        n.width = Inches(2.5)
        n.top = n.top - Inches(0.1)
        n.height = Inches(0.7)
        write(n, [num], color=PINK, size=34, bold=True)
        hd = ph(s, 37 + 2 * k)
        hd.top = hd.top + Inches(0.15)
        write(hd, [h], color=DEEP, size=15, bullet=False)
        dd = ph(s, 38 + 2 * k)
        dd.top = dd.top + Inches(0.1)
        write(dd, [d], color=INK, size=14, bullet=False)
    textbox(s, 0.4, 6.9, 11.4, 0.3, ["Monte-Carlo-валидация на синтетической популяции с известной истиной (1500 кандидатов; "
                                     "900 × 60 пар) · воспроизводится: python -m validation.run_all"], size=10, color=BLUSH)
    notes(s, "Готовой разметки нет, поэтому мы проверяем на популяции с известной истиной — тем же кодом, что в продукте. "
             "Подбор точнее фильтров по резюме, тест почти не завышает грейд, результат стабилен при пересдаче, а утечка "
             "базы не даёт незаметного преимущества.")

    # 14 ── 01 · Валидация подбора (диаграмма P@10) ─────────────────────────────────────────
    s = S[13]
    pill_title(s, "01 · ВАЛИДАЦИЯ ПОДБОРА")
    old = next(sh for sh in s.shapes if sh.has_chart)
    remove(old)
    cd = CategoryChartData()
    cd.categories = ["Поиск по ключевым словам", "Категория из резюме (абляция)", "Фильтры по самоописанию",
                     "ФСП Карьера: текст → NLP", "ФСП Карьера"]
    cd.add_series("P@10", (27, 72, 75, 84, 84))
    gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.38), Inches(1.95), Inches(6.6), Inches(4.6), cd)
    ch = gf.chart
    style_chart(ch, label_color=DEEP, axis_color=INK, grid_color="E5E1EF", legend=False, size=11, major=20)
    color_points(ch.series[0], [LAV, LAV, LAV, PINK, PINK])
    ch.plots[0].gap_width = 55
    textbox(s, 0.45, 1.25, 6.4, 0.6, [[("Доля релевантных кандидатов в первой десятке выдачи (P@10), "
                                         "900 кандидатов × 60 потребностей", {})]], size=12, color=INK)
    items = [("Категория по тесту — главный вклад", "Если брать категорию из резюме, P@10 падает с 0,84 до 0,72, а «завысивших себя» в топ-10 — в 7 раз больше."),
             ("Сквозной сценарий", "Текст вакансии → NLP → подборка: 0,84 — без потерь против структурированного запроса."),
             ("Честные абляции", "Без ФСП — 0,84, без проверки навыков тестом — 0,86: в синтетике резюме перечисляют 92% навыков честно."),
             ("Скорость", "Ранжирование пула до 900 кандидатов — 55 мс; подборка на стенде — 0,1–0,2 с.")]
    for (h, d), (hi, di) in zip(items, ((21, 18), (22, 23), (24, 25), (26, 27)), strict=True):
        write(ph(s, hi), [h], size=15, color=DEEP, bullet=False)
        write(ph(s, di), [d], size=12, color=INK, bullet=False)
    notes(s, "Главный вклад в качество даёт категория по тесту: стоит заменить её самоописанием — и точность падает, а "
             "«завысивших себя» в топе становится в 7 раз больше. Абляции мы показываем честно.")

    # 15 ── 01 · Интеграция с ФСП ───────────────────────────────────────────────────────────
    s = S[14]
    pill_title(s, "01 · ИНТЕГРАЦИЯ С ФСП")
    write(ph(s, 14), [
        [("ФСП ID по OpenID Connect: ", {"bold": True, "color": DEEP}), ("code + PKCE, проверка id_token по JWKS. Пути как у Keycloak — "
                                                                          "для боевого ФСП ID достаточно сменить адрес и ключи клиента.", {})],
        [("Реестр достижений: ", {"bold": True, "color": DEEP}), ("соревнование, уровень, дисциплина, место, команда, ссылка на протокол.", {})],
        [("Сила профиля: ", {"bold": True, "color": DEEP}), ("результативность и число соревнований, дисциплины равнозначны — "
                                                             "как советовали постановщики; ФСП двигает внутри категории, грейд — только тест.", {})],
    ], size=12, color=INK, bullet=True, after=4)
    for idx in (10, 11, 12):
        remove(ph(s, idx))
    fit_picture(s, FIG / "oidc_sequence.png", 0.45, 3.4, 7.4, 3.75, rounded=True, border="E5E1EF")
    fsp = crop_box(shot("fsp_candidate_full"), (1840, 1596, 2804, 2536), "fsp_card")
    fit_picture(s, fsp, 8.2, 1.15, 4.75, 5.65, rounded=True, border="E5E1EF")
    notes(s, "Профиль связывается с ФСП ID по OpenID Connect — так же, как будет работать ФСП ID на Keycloak. Из реестра "
             "приходят достижения с протоколами; работодатель видит их в карточке. Нет истории — нет штрафа.")

    # 16 ── 02 · Маркетинговая часть ────────────────────────────────────────────────────────
    s = S[15]
    pill_title(s, "02 · МАРКЕТИНГОВАЯ ЧАСТЬ", add_pill_color=PURPLE)
    cards = [("Кандидаты", "Участники соревнований ФСП, студенты ИТ-вузов, разработчики уровня Junior–Senior.",
              "Ценность: подтверждённый уровень вместо резюме, предложения с вилкой, достижения ФСП как карьерный актив.",
              "Каналы: сообщество ФСП, соревнования, вузы-партнёры."),
             ("Работодатели", "ИТ-компании и ИТ-подразделения, партнёры и спонсоры соревнований.",
              "Ценность: кандидаты с проверенным грейдом, рынок категории до найма, меньше часов техспециалистов на отбор.",
              "Каналы: партнёры ФСП, HR-сообщества, отраслевые события."),
             ("ФСП", "Оператор и партнёр платформы.",
              "Ценность: канал трудоустройства участников, данные о востребованных навыках, новые партнёры.",
              "Метрики пилота: доля принятых приглашений, время до найма, NPS обеих сторон.")]
    for k, (h, who, val, ch_) in enumerate(cards):
        write(ph(s, 49 + k), [f"{k + 1:02d}"], color=PINK)
        write(ph(s, 37 + 2 * k), [h], color=DEEP, size=16)
        write(ph(s, 38 + 2 * k), [who, val, ch_], color=INK, size=12, after=6)
    notes(s, "Три аудитории и для каждой — своя ценность. Кандидатам — доказанный уровень и честные условия, работодателям — "
             "экономия времени технических специалистов, ФСП — карьерный трек для участников.")

    # 17 ── 03 · Бизнес-модель ──────────────────────────────────────────────────────────────
    s = S[16]
    pill_title(s, "03 · БИЗНЕС-МОДЕЛЬ")
    write(ph(s, 14), [
        [("Кандидатам — бесплатно. ", {"bold": True, "color": DEEP}), ("Платят работодатели: за доступ к кандидатам "
                                                                        "с подтверждённым уровнем и за инструменты найма.", {})],
        [("ФСП — оператор и партнёр: ", {"bold": True, "color": DEEP}), ("бренд, сообщество и реестр достижений; "
                                                                          "доход направляется на развитие соревнований.", {})],
        [("Ключевая метрика: ", {"bold": True, "color": DEEP}), ("стоимость найма через платформу против часов "
                                                                  "технических специалистов на разбор откликов и собеседования.", {})],
    ], size=13, color=INK, after=10)
    rows = ["Freemium для компаний: базовые подборки бесплатно, тариф — по числу приглашений и подборок",
            "Тест по вакансии: собственный блюпринт и задания работодателя",
            "Интеграция с ATS и API — корпоративный тариф",
            "Спонсорские регулярные задания для категорий — бренд работодателя",
            "Совместные программы с ФСП: стажировки и гранты для призёров"]
    for idx, r in zip(range(15, 20), rows, strict=True):
        write(ph(s, idx), [r], size=12, color=INK, anchor="m")
    notes(s, "Модель простая: кандидатам бесплатно, монетизация — на стороне работодателя. Конкретные цены — предмет "
             "пилота; ключевая метрика — стоимость найма против времени технических специалистов.")

    # 18 ── 04 · Техническая проработка ─────────────────────────────────────────────────────
    s = S[17]
    t = s.shapes.title
    write(t, ["04 · ТЕХНИЧЕСКАЯ ПРОРАБОТКА"])
    t.width = Inches(8)
    remove(ph(s, 1))
    fit_picture(s, FIG / "architecture.png", 0.6, 1.62, 8.6, 5.15)
    facts = [("104", "метода API, OpenAPI / Swagger"), ("520", "автотестов: банк заданий, сценарии, песочница, антиплагиат"),
             ("0,1 с", "подборка по 700 кандидатам на стенде"), ("1 команда", "docker compose up: 6 контейнеров, ≈ 2,5 ГБ RAM")]
    for k, (big, small) in enumerate(facts):
        y = 1.85 + k * 1.2
        textbox(s, 9.55, y, 3.2, 0.5, [big], size=26, color=PINK, bold=True)
        textbox(s, 9.55, y + 0.5, 3.2, 0.6, [small], size=11, color=INK)
    notes(s, "Модульный монолит: API, тестирование, подбор, NLP и интеграции — отдельные слои; ядро теста не зависит от БД "
             "и используется в валидации. Код кандидатов исполняется в отдельной песочнице без сети. Всё поднимается "
             "одной командой Docker. LLM используется только в админке — для черновиков новых вопросов: локальная "
             "qwen3:14b через Ollama, решение по каждому вопросу принимает эксперт, принятые проходят пилотную калибровку.")

    # 19 ── 04 · Мобильная версия ───────────────────────────────────────────────────────────
    s = S[18]
    pill_title(s, "04 · МОБИЛЬНАЯ ВЕРСИЯ")
    for idx, n in zip((14, 15, 16, 17), ("m_landing", "m_runner", "m_invitation", "m_selection"), strict=True):
        fill_picture_ph(s, idx, shot(n))
    caps = ["Главная: механика и цифры платформы", "Тест: задание, таймер, прогресс",
            "Приглашение: вилка и условия до общения", "Подборка: категории и рынок"]
    for idx, c in zip((18, 19, 20, 21), caps, strict=True):
        write(ph(s, idx), [c], size=14, color=DEEP, bold=True, anchor="m", align="c", bullet=False)
    notes(s, "Интерфейс адаптивный: оба кабинета и тест работают на телефоне без горизонтальной прокрутки.")

    # 20 ── 04 · Безопасность и доверие ─────────────────────────────────────────────────────
    s = S[19]
    write(s.shapes.title, ["04 · БЕЗОПАСНОСТЬ И ДОВЕРИЕ"], color=DEEP, size=18)
    s.shapes.title.width = Inches(5.3)
    write(ph(s, 14), [
        [("152-ФЗ: ", {"bold": True, "color": DEEP}), ("отдельные согласия на обработку и публикацию, журнал согласий, выгрузка и удаление данных.", {})],
        [("Контакты скрыты ", {"bold": True, "color": DEEP}), ("до принятия приглашения или отклика; по умолчанию — анонимный код вместо имени.", {})],
        [("Защита доступа: ", {"bold": True, "color": DEEP}), ("Argon2id для паролей, HMAC для кодов, JWT, лимиты попыток, проверка роли и владельца.", {})],
        [("Недобросовестные работодатели: ", {"bold": True, "color": DEEP}), ("лимит 60 приглашений в сутки, индекс доверия, жалобы, отказ от предложений ниже ожиданий; ATS — webhook.", {})],
        [("Честный тест: ", {"bold": True, "color": DEEP}), ("прокторинг снимков экрана, печати и копирования; сохраняются только события, экран не записывается.", {})],
        [("Песочница: ", {"bold": True, "color": DEEP}), ("код кандидатов — в контейнере без сети, с лимитами; ответы скрытых тестов туда не передаются.", {})],
    ], size=12, color=INK, bullet=True, after=6)
    remove(ph(s, 10))
    priv = crop_box(shot("cand_settings_full"), (1716, 384, 2812, 1500), "privacy")
    fit_picture(s, priv, 7.0, 0.85, 5.95, 6.2, rounded=True)
    notes(s, "Персональные данные под контролем кандидата: согласия, видимость, выгрузка и удаление. Работодателя "
             "ограничивают лимиты, индекс доверия и жалобы.")

    # 21 ── 05 · Уникальность (сравнение) ───────────────────────────────────────────────────
    s = S[20]
    pill_title(s, "05 · УНИКАЛЬНОСТЬ РЕШЕНИЯ", add_pill_color=PURPLE)
    rows = [("Чем подтверждается уровень", "Самоописание в резюме", "Адаптивный тест на шкале IRT и достижения ФСП"),
            ("Кто проявляет инициативу", "Кандидат откликается вслепую", "Работодатель приглашает конкретного человека"),
            ("Когда видны условия", "Часто — после собеседования", "Вилка в каждом приглашении до начала общения"),
            ("Тест и утечки", "Единый набор заданий быстро расходится", "Свой вариант каждому, прокторинг; код — в песочнице с антиплагиатом"),
            ("Объяснимость выдачи", "Совпадение ключевых слов", "Причины «за/против» и аналитика рынка категории")]
    textbox(s, 4.25, 1.3, 3.9, 0.35, ["Универсальные площадки"], size=12, color=MUTED, bold=True)
    textbox(s, 8.45, 1.3, 4.4, 0.35, ["ФСП Карьера"], size=12, color=PINK, bold=True)
    for k, (crit, them, us) in enumerate(rows):
        p = ph(s, 15 + k)
        p.width = Inches(3.5)
        write(p, [crit], size=13, color=DEEP, bold=True, anchor="m")
        y, h = p.top / EMU, p.height / EMU
        textbox(s, 4.25, y, 3.9, h, [them], size=12, color=MUTED, anchor="m")
        textbox(s, 8.45, y, 4.4, h, [us], size=12, color=INK, bold=True, anchor="m")
    notes(s, "Отличие — в трёх вещах: уровень подтверждает тест, инициатива у работодателя, условия видны сразу. "
             "И всё это объяснимо для обеих сторон.")

    # 22 ── 06 · Планы по развитию ──────────────────────────────────────────────────────────
    s = S[21]
    pill_title(s, "06 · ПЛАНЫ ПО РАЗВИТИЮ")
    stages = {26: ("Пилот с ФСП", "ФСП ID на Keycloak и реестр; 100–200 участников; экспертная проверка грейдов"),
              32: ("Калибровка", "Онлайн-калибровка банка на реальных ответах; разметка релевантности работодателями"),
              28: ("Банк 800+ заданий", "Черновики от LLM с проверкой эксперта уже в админке; дальше — параметрические шаблоны и код в тесте"),
              34: ("Доверие и ATS", "Верификация компаний, модерация вакансий, коннекторы к ATS, изоляция запусков"),
              30: ("Масштаб", "Обучение ранжирования на исходах найма, мобильное приложение, новые направления ФСП")}
    for hi, (h, d) in stages.items():
        write(ph(s, hi), [h], size=14, color=PINK, bullet=False)
        write(ph(s, hi + 1), [d], size=11, color=INK, bullet=False)
    notes(s, "Ближайший шаг — пилот с ФСП: реальный ФСП ID, экспертная проверка грейдов и калибровка банка на живых "
             "ответах. Дальше — рост банка, интеграции с ATS и обучение ранжирования на исходах найма.")

    # 23 ── Финал ───────────────────────────────────────────────────────────────────────────
    s = S[22]
    write(s.shapes.title, ["СПАСИБО!"], color=DEEP, size=28)
    write(ph(s, 1), [
        [("Демо: ", {"bold": True, "color": DEEP}), ("docker compose up --build → http://localhost:8080", {})],
        [("Репозиторий: ", {"bold": True, "color": DEEP}), ("github.com/andercat2/fsp-career", {})],
        [("Документация: ", {"bold": True, "color": DEEP}), ("docs/fsp-career-documentation.pdf", {})],
        [("Демо-аккаунты ", {"bold": True, "color": DEEP}), ("(пароль demo12345): employer@demo.ru, candidate@demo.ru, newbie@demo.ru", {})],
        [("ФСП ID (тестовый): ", {"bold": True, "color": DEEP}), ("alice / gleb, пароль fsp12345", {})],
        [("Контакты команды: ", {"bold": True, "color": DEEP}), ("[Telegram капитана]", {})],
    ], size=14, color=INK, bullet=True, after=10)
    notes(s, "Спасибо! Стенд поднимается одной командой, демо-аккаунты — на слайде. Готовы ответить на вопросы.")

    for i, sl in enumerate(prs.slides, 1):
        set_slide_number(sl, i)
    prs.save(OUT)
    print(f"Сохранено: {OUT} · слайдов: {len(prs.slides)}")


if __name__ == "__main__":
    main()
