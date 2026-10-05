"""Иллюстрации для сопроводительной документации и презентации.

Запуск: python docs/figures/make_figures.py  (нужен matplotlib; данные — backend/validation/reports/*.json)
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
REPORTS = ROOT / "backend" / "validation" / "reports"
FONTS = ROOT / "backend" / "app" / "assets" / "fonts"
for f in FONTS.glob("*.ttf"):
    font_manager.fontManager.addfont(str(f))
plt.rcParams.update({"font.family": ["Montserrat", "DejaVu Sans"], "font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.edgecolor": "#C9C4D8", "axes.labelcolor": "#475569",
                     "xtick.color": "#64748b", "ytick.color": "#64748b", "axes.titleweight": "bold",
                     "axes.titlesize": 12, "axes.titlecolor": "#310F53"})

PINK, LAV, PURPLE, DEEP, AMBER, INK = "#FF0053", "#8A83D1", "#8E24AA", "#310F53", "#E8A33D", "#1C1D22"
SOFT = "#F6F4FA"


def box(ax, x, y, w, h, title, sub="", color=DEEP, fill="white", tsize=10.5):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.02", fc=fill, ec=color, lw=1.6))
    ax.text(x + w / 2, y + h * (0.66 if sub else 0.5), title, ha="center", va="center", fontsize=tsize,
            fontweight="bold", color=color)
    if sub:
        ax.text(x + w / 2, y + h * 0.3, sub, ha="center", va="center", fontsize=8, color="#475569")


def arrow(ax, a, b, text="", color="#64748b", rad=0.0, ls="-"):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=12, color=color, lw=1.4, linestyle=ls,
                                 connectionstyle=f"arc3,rad={rad}"))
    if text:
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        ax.text(mx, my + 0.018, text, ha="center", va="bottom", fontsize=7.5, color="#475569",
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.9))


def architecture():
    fig, ax = plt.subplots(figsize=(12, 6.6))
    ax.set_xlim(-0.012, 1.012)
    ax.set_ylim(0, 1)
    ax.axis("off")
    box(ax, 0.01, 0.42, 0.12, 0.16, "Браузер", "кандидат,\nработодатель", color=INK)
    box(ax, 0.19, 0.40, 0.16, 0.2, "Frontend", "React + Vite\nnginx: SPA + прокси", color=PINK, fill="#FFF5F8")
    ax.add_patch(FancyBboxPatch((0.41, 0.04), 0.37, 0.82, boxstyle="round,pad=0.01,rounding_size=0.02",
                                fc=SOFT, ec=LAV, lw=1.2))
    ax.text(0.595, 0.825, "Backend · FastAPI (модульный монолит)", ha="center", fontsize=10.5, fontweight="bold",
            color=DEEP)
    layers = [("API (REST, OpenAPI)", "auth · candidate · testing\nemployer · fsp · public · admin"),
              ("Тестирование", "IRT 3PL · CAT · 359 семейств заданий\nдетекторы утечки и дрейфа"),
              ("Подбор", "категории · сила профиля\nранжирование · объяснения"),
              ("NLP и документы", "разбор вакансий и резюме (PDF)\nPDF-профиль кандидата"),
              ("Интеграции", "OIDC-клиент ФСП ID · реестр ФСП\nSMTP · ATS-webhook")]
    for i, (t, s) in enumerate(layers):
        box(ax, 0.43, 0.66 - i * 0.148, 0.33, 0.125, t, s, color=DEEP, tsize=9.5)
    box(ax, 0.865, 0.66, 0.13, 0.17, "ФСП ID", "OIDC-провайдер\n(пути Keycloak)", color=PURPLE, fill="#F8F0FB")
    box(ax, 0.865, 0.40, 0.13, 0.17, "Реестр ФСП", "профили и\nдостижения", color=PURPLE, fill="#F8F0FB")
    box(ax, 0.865, 0.10, 0.13, 0.17, "PostgreSQL", "пользователи,\nпрофили, сессии,\nприглашения", color=DEEP)
    box(ax, 0.19, 0.08, 0.16, 0.14, "Mailpit / SMTP", "коды подтверждения,\nуведомления", color=AMBER, fill="#FFF9EE")
    arrow(ax, (0.13, 0.5), (0.19, 0.5), "HTTPS")
    arrow(ax, (0.35, 0.5), (0.43, 0.5), "/api")
    for y, label in ((0.745, "token,\nJWKS"), (0.485, "REST,\nAPI key"), (0.185, "SQL")):
        arrow(ax, (0.79, y), (0.865, y), label)
    arrow(ax, (0.43, 0.09), (0.35, 0.15), "SMTP")
    # браузер уходит на страницу входа ФСП ID и возвращается с кодом авторизации
    ax.plot([0.07, 0.07, 0.93, 0.93], [0.58, 0.95, 0.95, 0.86], color=PURPLE, lw=1.4, ls="--")
    ax.add_patch(FancyArrowPatch((0.93, 0.87), (0.93, 0.835), arrowstyle="-|>", mutation_scale=12, color=PURPLE,
                                 lw=1.4))
    ax.text(0.5, 0.958, "вход и согласие на странице ФСП ID (редирект браузера), возврат с кодом авторизации",
            ha="center", va="bottom", fontsize=8, color=PURPLE)
    fig.savefig(OUT / "architecture.png", dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def oidc_sequence():
    actors = ["Кандидат\n(браузер)", "Backend", "ФСП ID\n(OIDC)", "Реестр ФСП"]
    xs = [0.1, 0.37, 0.64, 0.89]
    msgs = [
        (0, 1, "«Привязать ФСП ID»"),
        (1, 0, "authorize_url (state, nonce, PKCE S256)"),
        (0, 2, "страница входа ФСП ID → логин и согласие"),
        (2, 0, "redirect: /fsp/callback?code&state"),
        (0, 1, "code, state"),
        (1, 2, "POST /token: code + verifier + client_secret"),
        (2, 1, "access_token, id_token (RS256)"),
        (1, 2, "GET /certs → проверка подписи, iss, aud, nonce"),
        (1, 3, "GET /participants/{fsp_id}"),
        (3, 1, "профиль и достижения (или 404 — нет истории)"),
        (1, 0, "redirect в кабинет: ФСП ID привязан"),
    ]
    fig, ax = plt.subplots(figsize=(11, 6.8))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, len(msgs) + 2.2)
    ax.axis("off")
    top = len(msgs) + 1
    for x, a in zip(xs, actors, strict=True):
        box(ax, x - 0.085, top + 0.05, 0.17, 0.9, a, color=PURPLE if x == xs[2] else DEEP, fill="white", tsize=9.5)
        ax.plot([x, x], [0.2, top + 0.05], color="#D6D1E4", lw=1.2, ls="--", zorder=0)
    for i, (a, b, t) in enumerate(msgs):
        y = top - 0.6 - i
        col = PURPLE if 2 in (a, b) else (PINK if 3 in (a, b) else DEEP)
        ax.add_patch(FancyArrowPatch((xs[a], y), (xs[b], y), arrowstyle="-|>", mutation_scale=11, color=col, lw=1.3))
        ax.text((xs[a] + xs[b]) / 2, y + 0.12, t, ha="center", va="bottom", fontsize=8, color=INK,
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none"))
    fig.savefig(OUT / "oidc_sequence.png", dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def cat_flow():
    fig, ax = plt.subplots(figsize=(12, 4.8))
    ax.set_xlim(-0.015, 1.015)
    ax.set_ylim(-0.03, 1)
    ax.axis("off")
    steps = [("Опрос", "специализация,\nязык, грейд"), ("Блюпринт", "доли доменов\nспециализации"),
             ("Выбор задания", "домен с отставанием,\nmax информации,\nслучайно из топ-4"),
             ("Свой вариант", "seed сессии →\nданные, код,\nверный ответ"),
             ("Ответ → θ", "EAP-оценка\nна сетке,\nобщий prior"),
             ("Стоп?", "SE ≤ 0.28 или\nуверенное решение,\n12–24 задания")]
    w, gap = 0.125, 0.045
    xs = [0.01 + i * (w + gap) for i in range(len(steps))]
    y0, h = 0.36, 0.36
    for i, (t, s) in enumerate(steps):
        hot = i in (2, 3)
        box(ax, xs[i], y0, w, h, t, s, color=PINK if hot else DEEP, fill="#FFF5F8" if hot else "white", tsize=9.5)
    for i in range(len(steps) - 1):  # стрелки поверх рамок; 0.013 — внешний отступ скруглённой рамки
        arrow(ax, (xs[i] + w + 0.013, y0 + h / 2), (xs[i + 1] - 0.013, y0 + h / 2))
    arrow(ax, (xs[5] + w / 2, y0 + h), (xs[2] + w / 2, y0 + h), color=LAV, rad=0.28)
    ax.text((xs[2] + xs[5] + w) / 2, 0.905, "нет — следующее задание", ha="center", va="center", fontsize=8.5,
            color="#475569", bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="none"))
    box(ax, 0.6, 0.0, 0.39, 0.22, "Решение по грейду",
        "P(θ ≥ нижней границы) ≥ 0.6 → грейд подтверждён\nP(θ ≥ верхней границы) ≥ 0.8 → «уверенно»",
        color=PURPLE, fill="#F8F0FB", tsize=9.5)
    arrow(ax, (xs[5] + w / 2, y0), (xs[5] + w / 2, 0.22), "да")
    fig.savefig(OUT / "cat_flow.png", dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def validation_charts():
    cat = json.loads((REPORTS / "cat_validation.json").read_text(encoding="utf-8"))
    mv = json.loads((REPORTS / "matching_validation.json").read_text(encoding="utf-8"))

    # 1. восстановление уровня и грейда
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    pts = cat["recovery"]["scatter_sample"]
    axes[0].scatter([p[0] for p in pts], [p[1] for p in pts], s=10, color=PINK, alpha=0.45, edgecolors="none")
    axes[0].plot([-3, 3], [-3, 3], color="#94a3b8", lw=1, ls="--")
    for c in cat["config"]["theta_cuts"]:
        axes[0].axvline(c, color="#E5E1EF", lw=1)
    axes[0].set(xlim=(-3, 3), ylim=(-3, 3), xlabel="истинный уровень θ", ylabel="оценка θ по тесту",
                title=f"Оценка уровня: r = {cat['recovery']['pearson_r']}, RMSE = {cat['recovery']['rmse']}")
    g = cat["grades"]
    labels = ["Тест: точно", "Тест: ±1", "Самооценка:\nточно", "Завышение:\nтест", "Завышение:\nсамооценка"]
    vals = [g["grade_exact_accuracy"], g["grade_within_one"], g["self_declared_exact_accuracy"],
            g["overgrading_rate_test"], g["overgrading_rate_self_declared"]]
    cols = [PINK, PINK, LAV, PINK, LAV]
    bars = axes[1].bar(labels, vals, color=cols, width=0.62)
    for b, v in zip(bars, vals, strict=True):
        axes[1].text(b.get_x() + b.get_width() / 2, v + 0.015, f"{v * 100:.1f}%", ha="center", fontsize=9, color=INK)
    axes[1].set(ylim=(0, 1.08), title="Грейд по тесту против самооценки в резюме")
    axes[1].tick_params(axis="x", labelsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "validation_cat.png", dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    # 2. атака «слитой базой»
    la = cat["leak_attack"]
    ks = ["0", "5", "25", "100"]
    series = [("Фиксированный тест", la["inflation_rate"]["fixed_form"], AMBER),
              ("Адаптивный без вариантов", la["inflation_rate"]["static_bank"], LAV),
              ("ФСП Карьера: завышение", la["inflation_rate"]["ours"], PURPLE),
              ("ФСП Карьера: незамеченное", la["undetected_inflation_rate"]["ours"], PINK)]
    fig, ax = plt.subplots(figsize=(11, 4.2))
    width = 0.2
    for i, (name, d, c) in enumerate(series):
        xs = [j + (i - 1.5) * width for j in range(len(ks))]
        bars = ax.bar(xs, [d[k] for k in ks], width=width * 0.92, color=c, label=name)
        for b, k in zip(bars, ks, strict=True):
            ax.text(b.get_x() + b.get_width() / 2, d[k] + 0.012, f"{d[k] * 100:.0f}%", ha="center", fontsize=7.5,
                    color=INK)
    ax.set_xticks(range(len(ks)), ["честно (K=0)", "K = 5", "K = 25", "K = 100"])
    ax.set(ylim=(0, 1.1), ylabel="доля завысивших грейд",
           title="Атака «слитой базой»: K предыдущих кандидатов поделились заданиями")
    ax.legend(frameon=False, fontsize=8.5, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    fig.savefig(OUT / "validation_leak.png", dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    # 3. подбор
    names = {"keyword": "Поиск по ключевым словам", "filters": "Фильтры по самоописанию",
             "ours_self_declared_category": "Абляция: категория из резюме", "ours_no_fsp": "Абляция: без ФСП",
             "ours_no_verification": "Абляция: без проверки навыков", "ours_nlp": "ФСП Карьера (текст → NLP)",
             "ours": "ФСП Карьера"}
    keys = list(names)
    s = mv["summary"]
    fig, ax = plt.subplots(figsize=(11, 4.4))
    ys = range(len(keys))
    ax.barh(ys, [s[k]["p10"] for k in keys], color=[PINK if k in ("ours", "ours_nlp") else LAV for k in keys],
            height=0.6, xerr=[s[k]["p10_ci95"] for k in keys], error_kw=dict(ecolor="#94a3b8", lw=1, capsize=3))
    for y, k in zip(ys, keys, strict=True):
        ax.text(s[k]["p10"] + s[k]["p10_ci95"] + 0.02, y,
                f"P@10 {s[k]['p10']:.2f} · nDCG {s[k]['ndcg10']:.2f} · завысивших {s[k]['inflated_in_top10'] * 100:.0f}%",
                va="center", fontsize=8.5, color=INK)
    ax.set_yticks(list(ys), [names[k] for k in keys])
    ax.set(xlim=(0, 1.45), xlabel="P@10 — доля релевантных в первой десятке (± 95% ДИ)",
           title=f"Подбор: {mv['setup']['needs']} потребностей × {mv['setup']['candidates']} кандидатов, "
                 "истина — латентная")
    ax.invert_yaxis()
    fig.savefig(OUT / "validation_matching.png", dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    # 4. информационные функции
    info = cat["information"]
    fig, ax = plt.subplots(figsize=(11, 3.8))
    for spec, c, n in (("backend", PINK, "Backend"), ("frontend", LAV, "Frontend"), ("qa", PURPLE, "QA"),
                       ("data_analyst", AMBER, "Аналитик данных")):
        ax.plot(info["theta"], info["info"][spec], color=c, lw=2, label=n)
    for c in cat["config"]["theta_cuts"]:
        ax.axvline(c, color="#E5E1EF", lw=1, ls="--")
    for x, t in ((-2.0, "Стажёр"), (-0.5, "Junior"), (0.5, "Middle"), (2.0, "Senior")):
        ax.text(x, ax.get_ylim()[1] * 0.97, t, ha="center", fontsize=8.5, color="#64748b")
    ax.set(xlabel="уровень θ", ylabel="информация теста I(θ)",
           title="Информация теста из 20 заданий по блюпринту: SE = 1/√I ≈ 0.32–0.36 в зоне junior–middle")
    ax.legend(frameon=False, fontsize=8.5, ncol=4, loc="lower center")
    fig.savefig(OUT / "information.png", dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    architecture()
    oidc_sequence()
    cat_flow()
    validation_charts()
    print("Готово:", sorted(p.name for p in OUT.glob("*.png")))
