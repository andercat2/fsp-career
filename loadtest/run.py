"""Прогон нагрузочного сценария: Locust без интерфейса и замер CPU и памяти контейнеров (docker stats).

    python loadtest/run.py <сценарий> [--host http://localhost:8080] [--label after]

Параметры ступеней (STEP_USERS, STEP_SECONDS, MAX_USERS) можно переопределить переменными окружения.

Сценарии — SCENARIOS ниже. Результаты — loadtest/results/<сценарий>[-метка]/: CSV и HTML-отчёт Locust, замеры
контейнеров (docker.csv) и сводка summary.json; общий отчёт по всем прогонам — python loadtest/report.py.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCENARIOS = {
    "smoke": {"users": 20, "rate": 5, "time": "60s", "classes": [],
              "about": "проверка сценариев: 20 пользователей всех ролей, 1 минута"},
    "load": {"users": 300, "rate": 10, "time": "5m", "classes": [],
             "about": "смешанная нагрузка: 300 одновременных пользователей всех ролей, 5 минут"},
    "exam": {"users": 300, "rate": 10, "time": "6m", "classes": ["TestTaker"],
             "about": "день тестирования: 300 кандидатов одновременно проходят тест, 6 минут"},
    "steps": {"users": None, "rate": None, "time": None, "classes": [],
              "env": {"LOAD_SHAPE": "steps", "STEP_USERS": "100", "STEP_SECONDS": "90", "MAX_USERS": "800"},
              "about": "ступенчатая нагрузка: +{STEP_USERS} пользователей каждые {STEP_SECONDS} секунд до {MAX_USERS} — поиск предела"},
}
PREFIX = os.environ.get("STACK_PREFIX", "fsp-")  # замеряем только контейнеры стенда
UNITS = {"B": 1 / 2**20, "KiB": 1 / 1024, "MiB": 1, "GiB": 1024, "kB": 1 / 1024, "MB": 1, "GB": 1024}


def _mb(s: str) -> float:
    m = re.match(r"([\d.]+)\s*([A-Za-z]+)", s.strip())
    return round(float(m.group(1)) * UNITS.get(m.group(2), 1), 1) if m else 0.0


def sample_docker(path: Path, stop: threading.Event) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["t", "container", "cpu_pct", "mem_mb"])
        t0 = time.time()
        while not stop.is_set():
            out = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{.Name}};{{.CPUPerc}};{{.MemUsage}}"],
                                 capture_output=True, text=True, encoding="utf-8").stdout
            t = round(time.time() - t0, 1)
            for line in out.splitlines():
                parts = line.split(";")
                if len(parts) == 3 and parts[0].startswith(PREFIX):
                    w.writerow([t, parts[0], parts[1].rstrip("%"), _mb(parts[2].split("/")[0])])
            f.flush()
            stop.wait(3)


def _rows(path: Path) -> list[dict]:
    """CSV Locust: UTF-8 (запуск с PYTHONUTF8=1) или кодировка системы — на случай запуска Locust вручную."""
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "cp1251"):
        try:
            return list(csv.DictReader(raw.decode(enc).splitlines()))
        except UnicodeDecodeError:
            continue
    return list(csv.DictReader(raw.decode("utf-8", errors="replace").splitlines()))


def _f(x: str) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def summarize(out: Path, name: str, sc: dict, wall: float) -> dict:
    rows = _rows(out / "locust_stats.csv")
    endpoints, total = [], None
    for r in rows:
        label = r["Name"] if not r["Type"] or r["Name"].startswith(r["Type"] + " ") else f"{r['Type']} {r['Name']}"
        item = {"name": label, "count": int(r["Request Count"]),
                "failures": int(r["Failure Count"]), "rps": round(_f(r["Requests/s"]), 2), "p50": _f(r["50%"]),
                "p95": _f(r["95%"]), "p99": _f(r["99%"]), "max": round(_f(r["Max Response Time"]))}
        if r["Name"] == "Aggregated":
            total = item
        else:
            endpoints.append(item)
    endpoints.sort(key=lambda x: -x["p95"])
    hist_rows = [r for r in _rows(out / "locust_stats_history.csv") if r["Name"] == "Aggregated"]
    t0 = _f(hist_rows[0]["Timestamp"]) if hist_rows else 0.0
    history = [{"t": round(_f(r["Timestamp"]) - t0), "users": int(_f(r["User Count"])), "rps": round(_f(r["Requests/s"]), 1),
                "fps": round(_f(r["Failures/s"]), 2), "p50": _f(r["50%"]), "p95": _f(r["95%"])} for r in hist_rows]
    failures = [{"method": r["Method"], "name": r["Name"], "error": r["Error"][:200], "count": int(r["Occurrences"])}
                for r in _rows(out / "locust_failures.csv")]
    docker: dict[str, dict] = {}
    for r in csv.DictReader((out / "docker.csv").open(encoding="utf-8")):
        d = docker.setdefault(r["container"], {"cpu": [], "mem": []})
        d["cpu"].append(_f(r["cpu_pct"]))
        d["mem"].append(_f(r["mem_mb"]))
    containers = {k: {"cpu_max": max(v["cpu"]), "cpu_avg": round(sum(v["cpu"]) / len(v["cpu"]), 1),
                      "mem_max_mb": max(v["mem"])} for k, v in docker.items() if v["cpu"]}
    return {"scenario": name, "about": sc["about"], "wall_sec": round(wall), "total": total, "endpoints": endpoints,
            "failures": failures, "containers": containers, "history": history,
            "generated_at": time.strftime("%Y-%m-%d %H:%M")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario", choices=SCENARIOS)
    ap.add_argument("--host", default="http://localhost:8080")
    ap.add_argument("--label", default="")
    a = ap.parse_args()
    sc = SCENARIOS[a.scenario]
    env = sc.get("env", {}) | dict(os.environ) | {"PYTHONUTF8": "1"}  # переменные окружения важнее настроек сценария
    sc = sc | {"about": sc["about"].format(**env)}
    name = a.scenario + (f"-{a.label}" if a.label else "")
    out = ROOT / "results" / name
    out.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "locust", "-f", str(ROOT / "locustfile.py"), "--headless", "-H", a.host,
           "--csv", str(out / "locust"), "--html", str(out / "report.html"), "--only-summary", "--stop-timeout", "20",
           "--loglevel", "WARNING"]
    if sc["users"]:
        cmd += ["-u", str(sc["users"]), "-r", str(sc["rate"]), "-t", sc["time"]]
    cmd += sc["classes"]
    stop = threading.Event()
    sampler = threading.Thread(target=sample_docker, args=(out / "docker.csv", stop), daemon=True)
    sampler.start()
    t0 = time.time()
    print(f"[{name}] {sc['about']}", flush=True)
    subprocess.run(cmd, env=env, check=False)
    stop.set()
    sampler.join(timeout=10)
    summary = summarize(out, name, sc, time.time() - t0)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    t = summary["total"]
    print(f"[{name}] запросов {t['count']}, ошибок {t['failures']}, {t['rps']} запр/с, p50 {t['p50']} мс, "
          f"p95 {t['p95']} мс, p99 {t['p99']} мс", flush=True)


if __name__ == "__main__":
    main()
