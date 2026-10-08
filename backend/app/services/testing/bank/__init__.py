"""Банк заданий. Импорт модулей регистрирует семейства в REGISTRY."""
from collections import defaultdict

from app.services.testing.bank import algorithms, backend, data, devops, frontend, languages, qa  # noqa: F401
from app.services.testing.bank.core import REGISTRY, ItemFamily, Rendered, check_answer, mcq

BY_DOMAIN: dict[str, list[ItemFamily]] = defaultdict(list)
for _fam in REGISTRY.values():
    BY_DOMAIN[_fam.domain].append(_fam)


def bank_summary() -> dict:
    out = {}
    for dom, fams in sorted(BY_DOMAIN.items()):
        out[dom] = {
            "families": len(fams),
            "parametric": sum(f.parametric for f in fams),
            "levels": {lvl: sum(f.level == lvl for f in fams) for lvl in range(1, 6)},
        }
    return out


def add_drafted_family(fid: str, domain: str, level: int, prompt: str, correct: str, wrong: list[str], *, topic: str,
                       code: str | None = None, code_lang: str | None = None, explain: str = "") -> ItemFamily:
    """Вопрос, принятый экспертом из черновиков LLM, → статичное пилотное семейство банка (в этом же процессе, без
    перезапуска; при старте приложения принятые черновики регистрируются заново из БД)."""
    if fid not in REGISTRY:
        fam = mcq(fid, domain, level, prompt, correct, wrong, topic=topic, code=code, code_lang=code_lang,
                  explain=explain, show=len(wrong) + 1, time_limit=120 if code else 90, pretest=True)
        BY_DOMAIN[domain].append(fam)
    return REGISTRY[fid]


__all__ = ["BY_DOMAIN", "REGISTRY", "ItemFamily", "Rendered", "add_drafted_family", "bank_summary", "check_answer"]
