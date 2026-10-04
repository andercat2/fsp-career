"""Банк заданий. Импорт модулей регистрирует семейства в REGISTRY."""
from collections import defaultdict

from app.services.testing.bank import algorithms, backend, data, devops, frontend, languages, qa  # noqa: F401
from app.services.testing.bank.core import REGISTRY, ItemFamily, Rendered, check_answer

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


__all__ = ["BY_DOMAIN", "REGISTRY", "ItemFamily", "Rendered", "bank_summary", "check_answer"]
