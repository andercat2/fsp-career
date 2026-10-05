"""Таблица эндпоинтов для документации из живой спецификации OpenAPI.

Запуск (стенд должен работать): python docs/gen_api_table.py [http://localhost:8080/openapi.json]
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080/openapi.json"
OUT = Path(__file__).resolve().parent / "api_endpoints.md"
PREFIX = "/api/v1"
# Порядок групп в таблице повторяет путь пользователя
ORDER = ["Аутентификация", "Справочники", "Кандидат: профиль", "Кандидат: опрос и тестирование",
         "Кандидат: приглашения, вакансии, задания", "Вакансии", "Работодатель", "Интеграция с ФСП",
         "Публичное: методика и оценка", "Администрирование"]


def main() -> None:
    spec = json.loads(urllib.request.urlopen(URL, timeout=20).read().decode("utf-8"))
    rows = []
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            tags = op.get("tags") or ["—"]
            group = "Администрирование" if "Администрирование" in tags else tags[0]
            codes = ", ".join(sorted(op.get("responses", {})))
            auth = "да" if op.get("security") else "нет"
            rows.append((group, method.upper(), path.removeprefix(PREFIX), op.get("summary", ""), codes, auth))
    rank = {g: i for i, g in enumerate(ORDER)}
    rows.sort(key=lambda r: (rank.get(r[0], len(ORDER)), r[2], r[1]))
    lines = ["| Группа | Метод | Путь | Назначение | Коды ответа | JWT |", "|---|---|---|---|---|---|"]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(rows)} эндпоинтов, {len(spec.get('components', {}).get('schemas', {}))} схем → {OUT.name}")


if __name__ == "__main__":
    main()
