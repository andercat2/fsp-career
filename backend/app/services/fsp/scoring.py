"""Оценка достижений ФСП и подготовка их к показу работодателю.

Каждое достижение даёт сигнал s = уровень × место × релевантность дисциплины специализации × свежесть.
Сигналы агрегируются «шумным ИЛИ»: 1 − Π(1 − 0.85·sᵢ) — несколько средних результатов дают больше одного,
но счёт насыщается и не уходит в бесконечность. Отсутствие истории ФСП даёт 0 и не штрафует кандидата:
это бонус к силе профиля, а не условие попадания в выдачу.
"""
from __future__ import annotations

from datetime import date

from app.services.reference.taxonomy import FSP_DISCIPLINES, FSP_LEVELS, FSP_RELEVANCE

LEVEL_W = {"regional": 0.35, "interregional": 0.5, "national": 0.8, "international": 1.0}
RANK_BONUS = {"МС": 0.15, "КМС": 0.10, "1 разряд": 0.05}


def place_weight(place: int | None, participants: int | None) -> float:
    if place == 1:
        return 1.0
    if place == 2:
        return 0.85
    if place == 3:
        return 0.7
    if place and participants and place <= max(3, participants // 10):
        return 0.55  # финалист / топ-10%
    return 0.25  # участие


def achievement_signal(a: dict, spec: str | None, today: date | None = None) -> float:
    today = today or date.today()
    lvl = LEVEL_W.get(a.get("level"), 0.3)
    pw = place_weight(a.get("place"), a.get("participants"))
    rel = FSP_RELEVANCE.get(spec or "", {}).get(a.get("discipline"), 0.6)
    try:
        years = max(0.0, (today - date.fromisoformat(a["date"][:10])).days / 365.25)
    except (KeyError, ValueError):
        years = 2.0
    decay = 0.5 ** (years / 3)
    return lvl * pw * rel * decay


def fsp_score(profile: dict | None, spec: str | None) -> float:
    if not profile:
        return 0.0
    prod = 1.0
    for a in profile.get("achievements", []):
        prod *= 1 - 0.85 * achievement_signal(a, spec)
    score = 1 - prod
    score += RANK_BONUS.get(profile.get("sport_rank") or "", 0.0)
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
            "signal": round(achievement_signal(a, spec), 3),
        })
    prizes = [i for i in items if i["place"] in (1, 2, 3)]
    best = max(items, key=lambda i: i["signal"], default=None)
    headline = None
    if prizes:
        top_level = max(prizes, key=lambda i: LEVEL_W.get(i["level"], 0))["level_name"]
        headline = f"Призёр ФСП ×{len(prizes)}, уровень до «{top_level}»"
    elif items:
        headline = f"Участник соревнований ФСП ×{len(items)}"
    return {
        "linked": True, "score": fsp_score(profile, spec), "achievements": items, "headline": headline,
        "best": best, "sport_rank": profile.get("sport_rank"), "rating": profile.get("rating"),
        "region": profile.get("region"), "events_count": len(items), "prizes_count": len(prizes),
    }
