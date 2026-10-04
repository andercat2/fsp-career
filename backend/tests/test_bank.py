"""Самопроверка банка: каждое семейство рендерится на многих seed'ах и языках, эталонный ответ проходит проверку,
варианты ответов уникальны, а варианты одного семейства действительно различаются."""
import pytest

from app.services.reference.taxonomy import DOMAINS, SPECIALIZATIONS, resolve_blueprint
from app.services.testing.bank import BY_DOMAIN, REGISTRY, check_answer

LANGS = [None, "python", "javascript", "java", "go"]


@pytest.mark.parametrize("fid", sorted(REGISTRY))
def test_family_renders_and_key_is_correct(fid):
    fam = REGISTRY[fid]
    for seed in range(40):
        r = fam.render(seed * 7919 + 13, LANGS[seed % len(LANGS)])
        assert r.prompt.strip()
        assert r.kind == fam.kind
        if r.kind in ("single", "multi"):
            texts = [o["text"] for o in r.options]
            assert len(texts) == len(set(texts)), f"{fid}: дубли вариантов {texts}"
            assert len(texts) >= 3
            ids = {o["id"] for o in r.options}
            keys = [r.key] if r.kind == "single" else r.key
            assert set(keys) <= ids and keys
        assert check_answer(r.kind, r.key, r.key, tolerance=r.tolerance, accepted=r.accepted, norm=r.norm)


@pytest.mark.parametrize("fid", sorted(f for f, fam in REGISTRY.items() if fam.parametric))
def test_parametric_variants_differ(fid):
    fam = REGISTRY[fid]
    rendered = [fam.render(s, "python") for s in range(25)]
    keys = {f"{r.key}{r.prompt}{r.code}" for r in rendered}
    assert len(keys) >= 3, f"{fid}: варианты почти не различаются"


def test_every_blueprint_domain_has_items():
    for sp in SPECIALIZATIONS:
        for lang in sp["languages"]:
            for dom in resolve_blueprint(sp["code"], lang):
                assert dom in DOMAINS
                assert len(BY_DOMAIN[dom]) >= 6, f"мало заданий в домене {dom}"
