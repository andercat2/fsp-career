"""Сводный отчёт нагрузочного тестирования: loadtest/results/SUMMARY.md и график docs/figures/load.png.

    python loadtest/report.py        (нужен matplotlib — только для графика)

Берёт summary.json всех прогонов из loadtest/results/. Пары «<сценарий>-before» / «<сценарий>-after» сравниваются.
"""
from __future__ import annotations

import json
import platform
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
FIG = ROOT.parent / "docs" / "figures" / "load.png"
ORDER = ["smoke", "load", "exam", "steps"]


def load() -> dict[str, dict]:
    out = {}
    for p in sorted(RESULTS.glob("*/summary.json")):
        out[p.parent.name] = json.loads(p.read_text(encoding="utf-8"))
    return out


def ms(x: float) -> str:
    return f"{x:,.0f}".replace(",", " ")


def num(x: float, d: int = 1) -> str:
    return f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


def fail_pct(t: dict) -> str:
    return num(100 * t["failures"] / max(1, t["count"]), 2) + "%"


def machine() -> str:
    """Процессор (название модели, а не семейства) и ресурсы Docker — для описания стенда."""
    cpu = platform.processor() or "CPU"
    try:
        if platform.system() == "Windows":
            import winreg

            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
                cpu = winreg.QueryValueEx(k, "ProcessorNameString")[0].strip()
        elif Path("/proc/cpuinfo").exists():
            cpu = next(ln.split(":", 1)[1].strip() for ln in Path("/proc/cpuinfo").read_text().splitlines()
                       if ln.startswith("model name"))
    except (OSError, StopIteration):
        pass
    try:
        import subprocess

        ncpu, mem = subprocess.run(["docker", "info", "--format", "{{.NCPU}} {{.MemTotal}}"], capture_output=True,
                                   text=True, timeout=20).stdout.split()
        return f"{cpu}; Docker — {ncpu} vCPU, {num(int(mem) / 2**30)} ГБ"
    except (OSError, ValueError, subprocess.SubprocessError):
        return cpu


STEP = 100  # шаг ступеней сценария steps (STEP_USERS)
FAIL_FPS = 0.05  # ступень «с ошибками»: в среднем больше 0,05 ошибки в секунду


def step_of(users: int) -> int:
    """Ступень по числу пользователей: часть виртуальных пользователей может выбыть (ошибка входа), поэтому их число
    на ступени «плавает» — относим точку к ближайшей ступени сверху."""
    return -(-users // STEP) * STEP


def steady(h: list[dict], step: int) -> list[dict]:
    """Точки истории на ступени без первых 20 секунд (разгон ступени)."""
    pts = [x for x in h if x["users"] and step_of(x["users"]) == step]
    if not pts:
        return []
    t0 = pts[0]["t"]
    return [x for x in pts if x["t"] - t0 >= 20] or pts


def step_table(s: dict) -> list[dict]:
    rows = []
    for u in sorted({step_of(x["users"]) for x in s["history"] if x["users"]}):
        pts = steady(s["history"], u)
        if len(pts) < 5:
            continue
        p95 = sorted(x["p95"] for x in pts)[len(pts) // 2]
        rows.append({"users": u, "rps": round(sum(x["rps"] for x in pts) / len(pts), 1), "p95": p95,
                     "fps": round(sum(x["fps"] for x in pts) / len(pts), 2)})
    return rows


def scenario_md(name: str, s: dict) -> list[str]:
    t = s["total"]
    out = [f"### {name}", "", s["about"].capitalize() + ".", "",
           f"Запросов: {t['count']:,}".replace(",", " ") + f", ошибок: {t['failures']} ({fail_pct(t)}), "
           f"в среднем {num(t['rps'])} запр/с; время ответа p50 / p95 / p99 — {ms(t['p50'])} / {ms(t['p95'])} / "
           f"{ms(t['p99'])} мс.", "",
           "| Запрос | Число | p50, мс | p95, мс | p99, мс | Ошибок |", "|---|---|---|---|---|---|"]
    for e in s["endpoints"][:12]:
        out.append(f"| `{e['name']}` | {e['count']} | {ms(e['p50'])} | {ms(e['p95'])} | {ms(e['p99'])} | {e['failures']} |")
    c = s["containers"]
    if c:
        out += ["", "Пиковая загрузка контейнеров: " + "; ".join(
            f"{k.split('-')[-2] if k.count('-') >= 2 else k} — CPU {v['cpu_max']:.0f}% (в среднем {v['cpu_avg']:.0f}%), "
            f"память {v['mem_max_mb']:.0f} МБ" for k, v in c.items() if v["cpu_max"] > 1) + "."]
    if s["failures"]:
        out += ["", "Ошибки: " + "; ".join(f"`{f['name']}` — {f['error']} ({f['count']})" for f in s["failures"][:5]) + "."]
    if name.startswith("steps"):
        rows = step_table(s)
        out += ["", "| Пользователей | Запр/с | p95, мс | Ошибок/с |", "|---|---|---|---|"]
        out += [f"| {r['users']} | {num(r['rps'])} | {ms(r['p95'])} | {num(r['fps'], 2)} |" for r in rows]
    return out + [""]


def compare_md(runs: dict[str, dict]) -> list[str]:
    out = []
    for base in ORDER:
        b, a = runs.get(f"{base}-before"), runs.get(f"{base}-after")
        if not (a and b):
            continue
        out += [f"### {base}: до и после оптимизации", "",
                "| Показатель | До | После |", "|---|---|---|",
                f"| Запросов в секунду | {num(b['total']['rps'])} | {num(a['total']['rps'])} |",
                f"| p50 / p95 / p99, мс | {ms(b['total']['p50'])} / {ms(b['total']['p95'])} / {ms(b['total']['p99'])} | "
                f"{ms(a['total']['p50'])} / {ms(a['total']['p95'])} / {ms(a['total']['p99'])} |",
                f"| Ошибок | {fail_pct(b['total'])} | {fail_pct(a['total'])} |"]
        names = {e["name"] for e in b["endpoints"]} & {e["name"] for e in a["endpoints"]}
        bb = {e["name"]: e for e in b["endpoints"]}
        aa = {e["name"]: e for e in a["endpoints"]}
        for n in sorted(names, key=lambda n: (-bb[n]["p95"], -aa[n]["p95"], n))[:8]:
            out.append(f"| `{n}`: p95, мс | {ms(bb[n]['p95'])} | {ms(aa[n]['p95'])} |")
        out.append("")
    return out


def figure(runs: dict[str, dict]) -> None:
    steps = {k: v for k, v in runs.items() if k.startswith("steps")}
    if not steps:
        return
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    for f in (ROOT.parent / "backend" / "app" / "assets" / "fonts").glob("*.ttf"):
        font_manager.fontManager.addfont(str(f))
    plt.rcParams.update({"font.family": ["Montserrat", "DejaVu Sans"], "font.size": 10, "axes.spines.top": False,
                         "axes.spines.right": False, "axes.edgecolor": "#C9C4D8", "axes.titleweight": "bold",
                         "axes.titlecolor": "#310F53", "xtick.color": "#64748b", "ytick.color": "#64748b"})
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4))
    style = {"steps-before": ("#8A83D1", "до оптимизации"), "steps-after": ("#FF0053", "после оптимизации"),
             "steps": ("#FF0053", "")}
    muted = "#64748b"
    for k in sorted(steps, key=lambda k: (not k.endswith("-before"), k)):
        rows = step_table(steps[k])
        color, label = style.get(k, ("#310F53", k))
        ok = [r for r in rows if r["fps"] < FAIL_FPS]
        ax1.plot([r["users"] for r in rows], [r["rps"] for r in rows], marker="o", color=color, lw=2, label=label or None)
        # Время ответа — только на ступенях без ошибок: когда сервер завис, Locust считает перцентиль по немногим
        # завершившимся запросам (в основном статике nginx), и он выглядит обманчиво низким
        ax2.plot([r["users"] for r in ok], [r["p95"] for r in ok], marker="o", color=color, lw=2, label=label or None)
        bad = next((r for r in rows if r["fps"] >= FAIL_FPS), None)
        if bad:
            ax1.annotate(f"с {bad['users']}: ошибки\nи таймауты", (bad["users"], bad["rps"]), xytext=(14, 18),
                         textcoords="offset points", color=muted, fontsize=9)
            ax2.axvline(bad["users"], color=color, lw=1.2, ls="--")
            ax2.annotate(f"{label or k}:\nотказ с {bad['users']}", (bad["users"], 0.6), xycoords=("data", "axes fraction"),
                         xytext=(6, 0), textcoords="offset points", va="center", color=muted, fontsize=9)
    ax1.set_title("Пропускная способность")
    ax1.set_xlabel("одновременных пользователей")
    ax1.set_ylabel("запросов в секунду")
    ax2.set_title("Время ответа, 95-й перцентиль")
    ax2.set_xlabel("одновременных пользователей")
    ax2.set_ylabel("миллисекунд")
    ax2.set_ylim(bottom=0)
    for ax in (ax1, ax2):
        ax.grid(axis="y", color="#EEEAF5")
        if len(steps) > 1:
            ax.legend(loc="upper left", facecolor="white", edgecolor="none", framealpha=1)
    fig.tight_layout()
    fig.savefig(FIG, dpi=160)
    print("график:", FIG)


def main() -> None:
    runs = load()
    lines = ["# Нагрузочное тестирование", "",
             f"Стенд — `docker compose` на одной машине вместе с генератором нагрузки (Locust): {machine()}; "
             "700 кандидатов и 5 компаний демо-данных. Профиль ролей и сценарии — `loadtest/locustfile.py`, запуск — "
             "`python loadtest/run.py <сценарий>`, отчёт — `python loadtest/report.py`.", ""]
    lines += compare_md(runs)
    for base in ORDER:
        for k in sorted(runs):
            if k == base or k.startswith(base + "-"):
                lines += scenario_md(k, runs[k])
    (RESULTS / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print("отчёт:", RESULTS / "SUMMARY.md")
    figure(runs)


if __name__ == "__main__":
    main()
