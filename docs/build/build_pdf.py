"""Сборка документации: Markdown → DOCX (docx-js) → PDF (LibreOffice), оглавление с номерами страниц в два прохода.

Запуск из корня репозитория:  python docs/build/build_pdf.py
Нужны Node.js с пакетом docx (npm install в docs/build), LibreOffice и PyMuPDF (pip install pymupdf).
Пути к node и soffice можно задать переменными NODE и SOFFICE.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import fitz  # PyMuPDF

DOCS = Path(__file__).resolve().parents[1]
BUILD = DOCS / "build"
NAME = "fsp-career-documentation"
NODE = os.environ.get("NODE", "node")
SOFFICE = os.environ.get("SOFFICE", r"C:\Program Files\LibreOffice\program\soffice.exe")


def run(cmd: list[str]) -> None:
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        sys.exit(f"Ошибка: {' '.join(cmd)}\n{res.stdout}\n{res.stderr}")
    if res.stdout.strip():
        print(res.stdout.strip())


def build(tmp: Path, pages: dict[str, int] | None) -> tuple[Path, list[dict]]:
    docx = tmp / f"{NAME}.docx"
    pages_file = tmp / "pages.json"
    if pages:
        pages_file.write_text(json.dumps(pages), encoding="utf-8")
    run([NODE, str(BUILD / "build_docx.js"), str(DOCS / "documentation.md"), str(docx)] + ([str(pages_file)] if pages else []))
    profile = (tmp / "lo_profile").as_uri()
    run([SOFFICE, f"-env:UserInstallation={profile}", "--headless", "--convert-to", "pdf", "--outdir", str(tmp), str(docx)])
    headings = json.loads((tmp / f"{NAME}.headings.json").read_text(encoding="utf-8"))
    return tmp / f"{NAME}.pdf", headings


def norm(s: str) -> str:
    return " ".join(s.replace("\u00a0", " ").split())


def locate(pdf: Path, headings: list[dict]) -> dict[str, int]:
    """Страница каждого заголовка. Первое вхождение текста — строка оглавления, поэтому ищем после его конца."""
    doc = fitz.open(pdf)
    texts = [norm(p.get_text()) for p in doc]
    last = norm(headings[-1]["text"])
    toc_end = next(i for i, t in enumerate(texts) if last in t)
    out, start = {}, toc_end + 1
    for h in headings:
        key = norm(h["text"])[:60]
        page = next((i for i in range(start, len(texts)) if key in texts[i]), None)
        if page is None:
            sys.exit(f"Заголовок не найден в PDF: {h['text']}")
        out[h["id"]] = page + 1
        start = page
    return out


def main() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        pdf, headings = build(tmp, None)
        pages = locate(pdf, headings)
        for _ in range(3):  # номера страниц в оглавлении не меняют его длину, обычно хватает одного прохода
            pdf, headings = build(tmp, pages)
            check = locate(pdf, headings)
            if check == pages:
                break
            pages = check
        shutil.copy(tmp / f"{NAME}.docx", DOCS / f"{NAME}.docx")
        shutil.copy(pdf, DOCS / f"{NAME}.pdf")
        n = fitz.open(DOCS / f"{NAME}.pdf").page_count
        print(f"Готово: docs/{NAME}.docx, docs/{NAME}.pdf — {n} стр.")


if __name__ == "__main__":
    main()
