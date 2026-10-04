"""Синтетический реестр участников ФСП (детерминированный). Тот же набор отдаёт mock-сервис ФСП
(fsp-mock/app/data/participants.json генерируется командой `python -m app.seed.fsp_data`)."""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

REGIONS = ["Москва", "Санкт-Петербург", "Республика Татарстан", "Новосибирская область", "Свердловская область",
           "Нижегородская область", "Томская область", "Краснодарский край", "Самарская область", "Пермский край",
           "Республика Башкортостан", "Приморский край"]
EVENTS = [
    ("Чемпионат России по спортивному программированию", "national", ["product", "algorithmic", "security", "drones"]),
    ("Кубок России по спортивному программированию", "national", ["product", "algorithmic", "security"]),
    ("Всероссийский хакатон ФСП", "national", ["product"]),
    ("Международные соревнования по спортивному программированию", "international", ["algorithmic", "product"]),
    ("Межрегиональный чемпионат по спортивному программированию", "interregional", ["product", "algorithmic", "robotics"]),
    ("Чемпионат федерального округа по спортивному программированию", "interregional", ["product", "algorithmic", "security"]),
    ("Региональный чемпионат по спортивному программированию", "regional", ["product", "algorithmic", "security", "drones",
                                                                            "robotics"]),
    ("Студенческая лига ФСП", "regional", ["algorithmic", "product"]),
]
TEAMS = ["Byte Busters", "NullPointer", "Сигма", "Код Красный", "Stack Overflowers", "Дедлайн", "Квант", "Git Gud",
         "404 Not Found", "Рекурсия", "Hello World", "Синтаксис", "Бит и Байт", "Ctrl+Z", "Полный стек"]
FIRST_M = ["Иван", "Алексей", "Дмитрий", "Максим", "Артём", "Никита", "Кирилл", "Егор", "Михаил", "Тимур", "Роман",
           "Андрей", "Даниил", "Илья", "Павел", "Сергей", "Ринат", "Арсений", "Глеб", "Матвей"]
FIRST_F = ["Анна", "Мария", "Екатерина", "Дарья", "Полина", "Алина", "София", "Виктория", "Елена", "Ксения", "Алиса",
           "Валерия", "Диана", "Камила", "Ольга", "Татьяна", "Юлия", "Вера"]
LAST = ["Иванов", "Смирнов", "Кузнецов", "Попов", "Васильев", "Петров", "Соколов", "Михайлов", "Новиков", "Фёдоров",
        "Морозов", "Волков", "Алексеев", "Лебедев", "Семёнов", "Егоров", "Павлов", "Козлов", "Степанов", "Николаев",
        "Орлов", "Андреев", "Макаров", "Никитин", "Захаров", "Зайцев", "Соловьёв", "Борисов", "Яковлев", "Григорьев",
        "Романов", "Воробьёв", "Сергеев", "Кузьмин", "Фролов", "Александров", "Дмитриев", "Королёв", "Гусев", "Киселёв",
        "Ильин", "Максимов", "Поляков", "Сорокин", "Виноградов", "Ковалёв", "Белов", "Медведев", "Антонов", "Тарасов",
        "Жуков", "Баранов", "Филиппов", "Комаров", "Давыдов", "Беляев", "Герасимов", "Богданов", "Осипов", "Сидоров",
        "Галиев", "Хабибуллин", "Гарипов", "Сафин", "Валиев"]


def person_name(rng: random.Random) -> tuple[str, str]:
    female = rng.random() < 0.35
    first = rng.choice(FIRST_F if female else FIRST_M)
    last = rng.choice(LAST)
    if female:
        last = last[:-1] + "ва" if last.endswith(("ов", "ев", "ёв")) else (last + "а" if last.endswith("ин") else last)
    return f"{last} {first}", ("f" if female else "m")


def _achievement(rng: random.Random, quality: float, year_from: int = 2022) -> dict:
    name, level, disciplines = rng.choice(EVENTS)
    participants = rng.choice([40, 60, 90, 120, 180, 250])
    # Чем выше «качество» участника, тем выше место (с шумом)
    pos = max(1, int(participants * (1 - min(0.999, max(0.0, rng.gauss(quality, 0.18))))) + 1)
    pos = min(pos, participants)
    month = rng.randint(1, 12)
    year = rng.randint(year_from, 2026 if month <= 9 else 2025)
    disc = rng.choice(disciplines)
    return {
        "event_id": f"EV-{year}-{rng.randint(100, 999)}", "event": name, "discipline": disc, "level": level,
        "date": f"{year}-{month:02d}-{rng.randint(1, 28):02d}", "place": pos, "participants": participants,
        "team": rng.choice(TEAMS), "role": rng.choice(["капитан", "участник", "участник", "разработчик"]),
        "result_url": f"https://fsp-russia.com/results/{year}/{rng.randint(1000, 9999)}", "verified": True,
    }


def generate_participants(n: int = 180, seed: int = 2026) -> list[dict]:
    rng = random.Random(seed)
    out = []
    for i in range(n):
        quality = rng.random()  # латентное «качество» спортсмена, связывается с θ кандидата в сиде
        name, _ = person_name(rng)
        n_ach = 0 if rng.random() < 0.18 else rng.choice([1, 1, 2, 2, 3, 4, 5])
        ach = [_achievement(rng, quality) for _ in range(n_ach)]
        rank = None
        if any(a["place"] <= 3 and a["level"] in ("national", "international") for a in ach):
            rank = rng.choice(["КМС", "МС", "1 разряд"])
        elif any(a["place"] <= 3 for a in ach):
            rank = rng.choice(["1 разряд", None])
        out.append({
            "fsp_id": f"FSP-{24 + i % 3}-{100000 + i * 37 % 900000:06d}", "full_name": name,
            "email": f"participant{i}@fsp-mail.local", "region": rng.choice(REGIONS),
            "birth_year": rng.randint(1996, 2008), "sport_rank": rank,
            "rating": {"points": int(200 + quality * 1800 + rng.randint(-100, 100)),
                       "season": "2025/2026"},
            "quality": round(quality, 3), "achievements": sorted(ach, key=lambda a: a["date"], reverse=True),
        })
    # Фиксированные учётные записи для живой демонстрации привязки ФСП ID
    out.append({"fsp_id": "FSP-DEMO-000001", "full_name": "Демидова Алиса", "email": "alice.demo@fsp-mail.local",
                "region": "Республика Татарстан", "birth_year": 2003, "sport_rank": "КМС",
                "rating": {"points": 1650, "season": "2025/2026"}, "quality": 0.85,
                "achievements": [
                    {"event_id": "EV-2025-501", "event": "Чемпионат России по спортивному программированию",
                     "discipline": "product", "level": "national", "date": "2025-11-20", "place": 2, "participants": 150,
                     "team": "Byte Busters", "role": "капитан", "result_url": "https://fsp-russia.com/results/2025/5011",
                     "verified": True},
                    {"event_id": "EV-2025-210", "event": "Всероссийский хакатон ФСП", "discipline": "product",
                     "level": "national", "date": "2025-04-12", "place": 5, "participants": 120, "team": "Byte Busters",
                     "role": "капитан", "result_url": "https://fsp-russia.com/results/2025/2101", "verified": True},
                    {"event_id": "EV-2024-033", "event": "Региональный чемпионат по спортивному программированию",
                     "discipline": "algorithmic", "level": "regional", "date": "2024-10-05", "place": 1,
                     "participants": 60, "team": "Byte Busters", "role": "участник",
                     "result_url": "https://fsp-russia.com/results/2024/3301", "verified": True},
                ]})
    out.append({"fsp_id": "FSP-DEMO-000002", "full_name": "Новиков Глеб", "email": "gleb.demo@fsp-mail.local",
                "region": "Москва", "birth_year": 2005, "sport_rank": None, "rating": {"points": 0, "season": "2025/2026"},
                "quality": 0.0, "achievements": []})
    return out


DEMO_LOGINS = {"FSP-DEMO-000001": ("alice", "fsp12345"), "FSP-DEMO-000002": ("gleb", "fsp12345")}


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[3] / "fsp-mock" / "app" / "data"
    target.mkdir(parents=True, exist_ok=True)
    data = generate_participants()
    (target / "participants.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Записано {len(data)} участников в {target / 'participants.json'}")
