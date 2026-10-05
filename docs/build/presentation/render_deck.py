"""PDF-версия презентации со шрифтом шаблона (Montserrat) без установки шрифта в систему.

python render_deck.py <deck.pptx> <out.pdf> [папка_для_превью]

PPTX → ODP (LibreOffice) → в ODP встраиваются TTF Montserrat → PDF (LibreOffice). Превью страниц — PyMuPDF.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import fitz

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
FONTS = REPO / "backend" / "app" / "assets" / "fonts"
SOFFICE = os.environ.get("SOFFICE", r"C:\Program Files\LibreOffice\program\soffice.exe")


def soffice(args: list[str], tmp: Path) -> None:
    profile = (tmp / "lo_profile").as_uri()
    subprocess.run([SOFFICE, f"-env:UserInstallation={profile}", "--headless", *args], check=True,
                   capture_output=True, timeout=600)


def main() -> None:
    deck, out_pdf = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    preview = Path(sys.argv[3]).resolve() if len(sys.argv) > 3 else None
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        soffice(["--convert-to", "odp", "--outdir", str(tmp), str(deck)], tmp)
        odp = tmp / (deck.stem + ".odp")
        fonts = ",".join(str(FONTS / f) for f in ("Montserrat-Regular.ttf", "Montserrat-Bold.ttf", "Montserrat-SemiBold.ttf"))
        emb = tmp / "embedded" / (deck.stem + ".odp")
        emb.parent.mkdir()
        subprocess.run([sys.executable, str(HERE / "embed_fonts_odp.py"), str(odp), str(emb), f"Montserrat={fonts}"],
                       check=True, capture_output=True)
        soffice(["--convert-to", "pdf", "--outdir", str(tmp / "embedded"), str(emb)], tmp)
        shutil.copy(tmp / "embedded" / (deck.stem + ".pdf"), out_pdf)
    doc = fitz.open(out_pdf)
    print(f"PDF: {out_pdf} · {doc.page_count} стр.")
    if preview:
        preview.mkdir(parents=True, exist_ok=True)
        for old in preview.glob("slide-*.png"):
            old.unlink()
        for i, page in enumerate(doc, 1):
            page.get_pixmap(dpi=110).save(preview / f"slide-{i:02d}.png")
        print(f"Превью: {preview}")


if __name__ == "__main__":
    main()
