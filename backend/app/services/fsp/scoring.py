"""Оценка достижений ФСП и подготовка их к показу работодателю.

По рекомендациям постановщиков (Q&A): все соревнования и дисциплины равнозначны — внутреннего рейтинга
«чемпионат России выше хакатона» нет; учитываются результативность и число соревнований; одни участия без результата
дают небольшой вклад с потолком, чтобы профиль нельзя было «набить» онлайн-явками; свежий результат весит больше.
Роль в команде (капитан, участник) не учитывается: FSP ID не гарантирует, кто что делал.

  сигнал результата  sᵢ = вес результата × свежесть: победитель 1.0, призёр (2–3 место) 0.8, финалист (топ-10%) 0.5;
  результаты         R = 1 − Π(1 − 0.8·sᵢ) — несколько результатов дают больше одного, но счёт насыщается;
  участия            P = min(0.15, 0.05·Σ свежесть участий без результата);
  итог               R + (1 − R)·P + бонус разряда (МС 0.10, КМС 0.07, I разряд 0.03), не больше 1.

Отсутствие истории ФСП даёт 0 и не штрафует: это бонус к силе профиля, а не условие попадания в выдачу.
"""
from __future__ import annotations

from datetime import date

from app.services.reference.taxonomy import FSP_DISCIPLINES, FSP_LEVELS

RESULT_W = {"winner": 1.0, "prize": 0.8, "finalist": 0.5, "participant": 0.0}
RESULT_NAMES = {"winner": "победитель", "prize": "призёр", "finalist": "финалист", "participant": "участник"}
PARTICIPATION_STEP, PARTICIPATION_CAP = 0.05, 0.15
RANK_BONUS = {"МС": 0.10, "КМС": 0.07, "1 разряд": 0.03}
HALF_LIFE_YEARS = 3


def result_tier(place: int | None, participants: int | None) -> str:
    if place == 1:
        return "winner"
    if place in (2, 3):
        return "prize"
    if place and participants and place <= max(3, participants // 10):
        return "finalist"
    return "participant"


def recency(a: dict, today: date | None = None) -> float:
    today = today or date.today()
    try:
        years = max(0.0, (today - date.fromisoformat(a["date"][:10])).days / 365.25)
    except (KeyError, ValueError):
        years = 2.0
    return 0.5 ** (years / HALF_LIFE_YEARS)


def achievement_signal(a: dict, spec: str | None = None, today: date | None = None) -> float:
    """Сигнал результата; spec не используется — дисциплины равнозначны (параметр оставлен для совместимости)."""
    return RESULT_W[result_tier(a.get("place"), a.get("participants"))] * recency(a, today)


def fsp_score(profile: dict | None, spec: str | None = None) -> float:
    if not profile:
        return 0.0
    prod, participations = 1.0, 0.0
    for a in profile.get("achievements", []):
        s = achievement_signal(a)
        if s > 0:
            prod *= 1 - 0.8 * s
        else:
            participations += recency(a)
    results = 1 - prod
    part = min(PARTICIPATION_CAP, PARTICIPATION_STEP * participations)
    score = results + (1 - results) * part + RANK_BONUS.get(profile.get("sport_rank") or "", 0.0)
    return round(min(score, 1.0), 4)


def place_label(place: int | None, participants: int | None) -> str:
    if place in (1, 2, 3):
        return f"{place} место"
    if place and participants and place <= max(3, participants // 10):
        return f"финалист ({place} из {participants})"
    return "участник"


def fsp_summary(profile: dict | None, spec: str | None) -> dict:
    """Компактная сводка для карточки кандидата и объяснения выдачи."""
    if not profile:
        return {"linked": False, "score": 0.0, "achievements": [], "headline": None}
    items = []
    for a in sorted(profile.get("achievements", []), key=lambda x: x.get("date", ""), reverse=True):
        items.append({
            "event": a.get("event"), "discipline": a.get("discipline"),
            "discipline_name": FSP_DISCIPLINES.get(a.get("discipline"), a.get("discipline")),
            "level": a.get("level"), "level_name": FSP_LEVELS.get(a.get("level"), a.get("level")),
            "date": a.get("date"), "place": a.get("place"), "participants": a.get("participants"),
            "place_label": place_label(a.get("place"), a.get("participants")), "team": a.get("team"),
            "role": a.get("role"), "result_url": a.get("result_url"),
            "result": result_tier(a.get("place"), a.get("participants")),
            "signal": round(achievement_signal(a), 3),
        })
    prizes = [i for i in items if i["result"] in ("winner", "prize")]
    finals = [i for i in items if i["result"] == "finalist"]
    best = max(items, key=lambda i: (i["signal"], i["date"] or ""), default=None)
    headline = None
    counts = [(sum(1 for i in items if i["result"] == r), name) for r, name in
              (("winner", "победитель"), ("prize", "призёр"), ("finalist", "финалист"))]
    parts = [f"{name} ×{n}" for n, name in counts if n]
    if parts:
        headline = " · ".join(parts + [f"соревнований ФСП: {len(items)}"])
        headline = headline[0].upper() + headline[1:]
    elif items:
        headline = f"Участник соревнований ФСП ×{len(items)}"
    return {
        "linked": True, "score": fsp_score(profile, spec), "achievements": items, "headline": headline,
        "best": best, "sport_rank": profile.get("sport_rank"), "rating": profile.get("rating"),
        "region": profile.get("region"), "events_count": len(items), "prizes_count": len(prizes),
    }
