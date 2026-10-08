"""Банк заданий: семейства (item families) и их рендеринг в конкретный вариант.

Семейство — это шаблон задания с известной трудностью. Каждый показ — уникальный вариант, порождаемый
seed'ом: другие числа, данные, имена переменных, набор и порядок вариантов, идентификаторы ответов.
Правильный ответ вычисляется генератором, поэтому «слитый» ответ одного кандидата не подходит другому.
Параметры IRT принадлежат семейству: все варианты изоморфны по трудности, что и обеспечивает сопоставимость.
"""
from __future__ import annotations

import hashlib
import random
import re
import string
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

LEVEL_B = {1: -1.6, 2: -0.8, 3: 0.0, 4: 0.8, 5: 1.6}


@dataclass
class Rendered:
    prompt: str
    kind: str  # single | multi | input | numeric
    key: Any
    options: list[dict] | None = None
    code: str | None = None
    code_lang: str | None = None
    explanation: str = ""
    tolerance: float = 0.0
    accepted: list[str] = field(default_factory=list)
    norm: str = "tokens"  # для input: tokens | exact | lower
    placeholder: str | None = None


@dataclass
class ItemFamily:
    id: str
    domain: str
    level: int
    kind: str
    topic: str
    generator: Callable[[random.Random, str | None], Rendered]
    parametric: bool
    a: float
    b: float
    c: float
    time_limit: int
    langs: tuple[str, ...] | None = None
    pretest: bool = False

    def render(self, seed: int, lang: str | None = None) -> Rendered:
        rng = random.Random(seed)
        r = self.generator(rng, lang)
        if r.options:
            # Идентификаторы вариантов случайны в каждом показе: «правильный — B» ничего не говорит другому кандидату.
            ids = _option_ids(rng, len(r.options))
            remap = {}
            for opt, new_id in zip(r.options, ids, strict=True):
                remap[opt["id"]] = new_id
                opt["id"] = new_id
            if r.kind == "single":
                r.key = remap[r.key]
            elif r.kind == "multi":
                r.key = sorted(remap[k] for k in r.key)
        return r


REGISTRY: dict[str, ItemFamily] = {}


def _hash_unit(s: str) -> float:
    return int(hashlib.md5(s.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


def _option_ids(rng: random.Random, n: int) -> list[str]:
    ids: set[str] = set()
    while len(ids) < n:
        ids.add("".join(rng.choice(string.ascii_lowercase + string.digits) for _ in range(5)))
    return list(ids)


def _default_params(fid: str, level: int, kind: str, parametric: bool) -> tuple[float, float, float]:
    """Априорные параметры IRT по экспертному уровню (уточняются онлайн-калибровкой, см. validation/)."""
    jitter = _hash_unit(fid) - 0.5
    b = LEVEL_B[level] + 0.4 * jitter
    a = (1.5 if parametric else 1.15) + 0.5 * (_hash_unit(fid + "a") - 0.5)
    c = {"single": 0.2, "multi": 0.05, "input": 0.0, "numeric": 0.0}[kind]
    return round(a, 3), round(b, 3), c


def register(fam: ItemFamily) -> ItemFamily:
    if fam.id in REGISTRY:
        raise ValueError(f"Дублирующийся id семейства: {fam.id}")
    REGISTRY[fam.id] = fam
    return fam


def family(fid: str, domain: str, level: int, kind: str, topic: str, *, time_limit: int = 120,
           langs: tuple[str, ...] | None = None, pretest: bool = False):
    """Декоратор параметрического семейства: функция (rng, lang) -> Rendered."""

    def deco(fn: Callable[[random.Random, str | None], Rendered]):
        a, b, c = _default_params(fid, level, kind, True)
        register(ItemFamily(fid, domain, level, kind, topic, fn, True, a, b, c, time_limit, langs, pretest))
        return fn

    return deco


def mcq(fid: str, domain: str, level: int, prompt: str, correct: str, wrong: list[str], *, topic: str = "",
        code: str | None = None, code_lang: str | None = None, explain: str = "", show: int = 4,
        time_limit: int = 90, pretest: bool = False) -> ItemFamily:
    """Статичный вопрос с одним ответом. Дистракторы выбираются из пула, порядок перемешивается.
    pretest=True — пилотное семейство: показывается без влияния на оценку, пока трудность не откалибрована."""

    def gen(rng: random.Random, _lang: str | None) -> Rendered:
        opts = [{"id": "k", "text": correct}] + [
            {"id": f"w{i}", "text": t} for i, t in enumerate(rng.sample(wrong, min(show - 1, len(wrong))))
        ]
        rng.shuffle(opts)
        return Rendered(prompt=prompt, kind="single", key="k", options=opts, code=code, code_lang=code_lang,
                        explanation=explain)

    a, b, c = _default_params(fid, level, "single", False)
    c = round(1.0 / min(show, len(wrong) + 1), 3)
    return register(ItemFamily(fid, domain, level, "single", topic or prompt[:60], gen, False, a, b, c, time_limit,
                               pretest=pretest))


def multi(fid: str, domain: str, level: int, prompt: str, correct: list[str], wrong: list[str], *, topic: str = "",
          code: str | None = None, code_lang: str | None = None, explain: str = "", show: int = 5,
          time_limit: int = 120) -> None:
    """Вопрос с несколькими верными ответами: в каждый показ попадает случайное подмножество верных."""

    def gen(rng: random.Random, _lang: str | None) -> Rendered:
        k = rng.randint(max(1, min(2, len(correct))), min(len(correct), show - 1))
        chosen_c = rng.sample(correct, k)
        chosen_w = rng.sample(wrong, min(show - k, len(wrong)))
        opts = [{"id": f"c{i}", "text": t} for i, t in enumerate(chosen_c)] + [
            {"id": f"w{i}", "text": t} for i, t in enumerate(chosen_w)
        ]
        rng.shuffle(opts)
        return Rendered(prompt=prompt + "\n\n_Выберите все верные варианты._", kind="multi",
                        key=[o["id"] for o in opts if o["id"].startswith("c")], options=opts, code=code,
                        code_lang=code_lang, explanation=explain)

    a, b, c = _default_params(fid, level, "multi", False)
    register(ItemFamily(fid, domain, level, "multi", topic or prompt[:60], gen, False, a, b, c, time_limit))


def options_from(rng: random.Random, correct: Any, distractors: list[Any], fmt: Callable[[Any], str] = str,
                 n: int = 4) -> tuple[list[dict], str]:
    """Собирает варианты для параметрического single-вопроса, убирая дубли правильного ответа."""
    seen = {fmt(correct)}
    uniq = []
    for d in distractors:
        s = fmt(d)
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    rng.shuffle(uniq)
    opts = [{"id": "k", "text": fmt(correct)}] + [{"id": f"w{i}", "text": t} for i, t in enumerate(uniq[: n - 1])]
    rng.shuffle(opts)
    return opts, "k"


# ---------- проверка ответа ----------

def _norm_tokens(s: str) -> str:
    return " ".join(re.findall(r"[\w.\-]+", str(s).lower().replace("ё", "е")))


def check_answer(r_kind: str, key: Any, answer: Any, *, tolerance: float = 0.0, accepted: list[str] | None = None,
                 norm: str = "tokens") -> bool:
    if answer is None:
        return False
    if r_kind == "single":
        return str(answer) == str(key)
    if r_kind == "multi":
        ans = answer if isinstance(answer, list) else [answer]
        return sorted(map(str, ans)) == sorted(map(str, key))
    if r_kind == "numeric":
        try:
            val = float(str(answer).replace(",", ".").replace(" ", ""))
        except ValueError:
            return False
        return abs(val - float(key)) <= max(tolerance, 1e-9)
    if r_kind == "input":
        variants = [str(key), *(accepted or [])]
        if norm == "exact":
            return str(answer).strip() in [v.strip() for v in variants]
        if norm == "lower":
            return str(answer).strip().lower() in [v.strip().lower() for v in variants]
        return _norm_tokens(answer) in [_norm_tokens(v) for v in variants]
    return False


def pick_lang(lang: str | None, supported: tuple[str, ...] = ("python", "javascript", "java", "go")) -> str:
    return lang if lang in supported else supported[0]


def var_name(rng: random.Random) -> str:
    return rng.choice(["data", "items", "nums", "values", "arr", "xs", "seq", "buf"])
