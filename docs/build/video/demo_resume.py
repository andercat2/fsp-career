"""Синтетическое PDF-резюме для демонстрационного видео: вёрстка экспорта hh.ru (тот же генератор, что в валидации
разбора резюме — validation/nlp_validation.py), Backend · Python · Middle. Персональных данных нет: кандидат
сгенерирован, контакты заведомо демонстрационные (домен example.com).

    .venv/Scripts/python docs/build/video/demo_resume.py <out.pdf>
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend"))

from app.seed.synthetic import generate_population  # noqa: E402
from validation.nlp_validation import _gold, hh_pdf  # noqa: E402

NAME = "Смирнова Анна Сергеевна"

rng = random.Random(2026)
cand = next(c for c in generate_population(400, seed=2026)
            if c.spec == "backend" and c.lang == "python" and c.grade_true == "middle" and not c.inflated and c.experience)
gold = _gold(cand, rng) | {"full_name": NAME, "email": "anna.smirnova@example.com", "phone": "+7 (900) 000-00-00",
                           "telegram": "@anna_smirnova_example", "github": None}
out = Path(sys.argv[1])
out.write_bytes(hh_pdf(cand, gold, rng))
print(f"{out}: {NAME}, {cand.headline}, {cand.desired_salary:,} ₽".replace(",", " "))
