"""Антиплагиат для решений с кодом: сходство по структуре, а не по тексту.

Код превращается в поток токенов, где имена переменных и функций заменены на ID, строки — на STR, числа — на NUM,
комментарии и пробелы отброшены, а в JavaScript — и необязательные фигурные скобки и точки с запятой: переименование
переменных и переформатирование не скрывают копию. По токенам строятся отпечатки k-грамм (k = 5) с отбором
winnowing (окно 4) — как в системе MOSS. Сходство двух решений — доля общих отпечатков от меньшего набора. Отпечатки
шаблона-заготовки работодателя вычитаются: общий шаблон — не плагиат. Параметры и порог проверены на корпусе
замаскированных копий и независимых решений (validation/plagiarism_validation.py). Одинаковые решения у разных
кандидатов — также сигнал генерации одной и той же подсказкой LLM.
"""
from __future__ import annotations

import hashlib
import io
import keyword
import re
import tokenize

K, WINDOW = 5, 4
THRESHOLD = 0.85  # с этого порога решение помечается как вероятная копия
MIN_TOKENS = 30  # короткие решения не сравниваем: в них неизбежно совпадение

PY_BUILTINS = {"len", "range", "print", "sorted", "sum", "min", "max", "enumerate", "zip", "map", "filter", "list", "dict",
               "set", "tuple", "int", "str", "float", "bool", "abs", "any", "all", "reversed", "isinstance", "open"}
JS_KEYWORDS = {"function", "return", "const", "let", "var", "if", "else", "for", "while", "do", "of", "in", "new",
               "class", "extends", "this", "null", "undefined", "true", "false", "break", "continue", "switch", "case",
               "default", "try", "catch", "finally", "throw", "typeof", "instanceof", "async", "await", "yield", "export",
               "import", "from", "Math", "Object", "Array", "Map", "Set", "JSON", "String", "Number"}
JS_TOKEN_RE = re.compile(r"""//[^\n]*|/\*.*?\*/|`(?:\\.|[^`])*`|"(?:\\.|[^"])*"|'(?:\\.|[^'])*'|\d+(?:\.\d+)?|"""
                         r"""[A-Za-z_$][\w$]*|===|!==|=>|\*\*|&&|\|\||[+\-*/%=<>!&|^~?:;,.(){}\[\]]""", re.S)


def _py_tokens(code: str) -> list[str]:
    out: list[str] = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(code).readline):
            if tok.type in (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.ENCODING, tokenize.ENDMARKER):
                continue
            if tok.type == tokenize.NAME:
                out.append(tok.string if keyword.iskeyword(tok.string) or tok.string in PY_BUILTINS else "ID")
            elif tok.type == tokenize.STRING:
                out.append("STR")
            elif tok.type == tokenize.NUMBER:
                out.append("NUM")
            elif tok.type == tokenize.INDENT:
                out.append("{")
            elif tok.type == tokenize.DEDENT:
                out.append("}")
            else:
                out.append(tok.string)
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return _js_tokens(code)  # синтаксически неполный код — грубая токенизация
    return out


def _js_tokens(code: str) -> list[str]:
    out = []
    for t in JS_TOKEN_RE.findall(code):
        if t.startswith(("//", "/*")) or t in ("{", "}", ";"):  # скобки вокруг одного оператора и «;» необязательны
            continue
        if t[0] in "\"'`":
            out.append("STR")
        elif t[0].isdigit():
            out.append("NUM")
        elif re.match(r"[A-Za-z_$]", t):
            out.append(t if t in JS_KEYWORDS else "ID")
        else:
            out.append(t)
    return out


def tokens(code: str, language: str) -> list[str]:
    return _py_tokens(code) if language == "python" else _js_tokens(code)


def fingerprints(code: str, language: str) -> set[int]:
    toks = tokens(code or "", language)
    if len(toks) < K:
        return set()
    hashes = [int(hashlib.md5(" ".join(toks[i:i + K]).encode()).hexdigest()[:12], 16) for i in range(len(toks) - K + 1)]
    picked = set()
    for i in range(max(1, len(hashes) - WINDOW + 1)):
        picked.add(min(hashes[i:i + WINDOW]))
    return picked


def similarity(a: str, b: str, language: str, template: str | None = None) -> float:
    """Доля общих отпечатков (от меньшего набора) без отпечатков шаблона."""
    if len(tokens(a, language)) < MIN_TOKENS or len(tokens(b, language)) < MIN_TOKENS:
        return 0.0
    base = fingerprints(template, language) if template else set()
    fa, fb = fingerprints(a, language) - base, fingerprints(b, language) - base
    if not fa or not fb:
        return 0.0
    return round(len(fa & fb) / min(len(fa), len(fb)), 3)
