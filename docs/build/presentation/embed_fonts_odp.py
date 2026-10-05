"""Встраивает TTF-шрифты в ODP (ODF font-face-src), чтобы LibreOffice отрисовал их при экспорте в PDF без установки в систему.

python embed_fonts_odp.py in.odp out.odp Family=path1.ttf,path2.ttf [Family2=...]
"""
import re
import sys
import zipfile
from pathlib import Path

src, dst, *specs = sys.argv[1:]
families = {}
for spec in specs:
    fam, files = spec.split("=", 1)
    families[fam] = [Path(f) for f in files.split(",")]

zin = zipfile.ZipFile(src)
items = {n: zin.read(n) for n in zin.namelist()}

font_entries = []
uris = {}
for fam, files in families.items():
    parts = []
    for i, f in enumerate(files):
        name = f"Fonts/{fam.replace(' ', '_')}_{i}.ttf"
        items[name] = f.read_bytes()
        font_entries.append(name)
        parts.append(f'<svg:font-face-uri xlink:href="{name}" xlink:type="simple"><svg:font-face-format svg:string="truetype"/></svg:font-face-uri>')
    uris[fam] = "<svg:font-face-src>" + "".join(parts) + "</svg:font-face-src>"


def patch(xml: str) -> str:
    for fam, src_el in uris.items():
        # существующее объявление семейства: самозакрывающийся тег или с телом
        pat = re.compile(r'<style:font-face style:name="' + re.escape(fam) + r'"([^>]*?)(/>|>.*?</style:font-face>)', re.S)
        if pat.search(xml):
            xml = pat.sub(lambda m: f'<style:font-face style:name="{fam}"{m.group(1)}>{src_el}</style:font-face>', xml, count=1)
        else:
            decl = (f'<style:font-face style:name="{fam}" svg:font-family="&apos;{fam}&apos;" '
                    f'style:font-family-generic="swiss" style:font-pitch="variable">{src_el}</style:font-face>')
            xml = xml.replace("<office:font-face-decls>", "<office:font-face-decls>" + decl, 1)
    return xml


for part in ("content.xml", "styles.xml"):
    items[part] = patch(items[part].decode("utf-8")).encode("utf-8")

man = items["META-INF/manifest.xml"].decode("utf-8")
add = "".join(f'<manifest:file-entry manifest:full-path="{n}" manifest:media-type="application/x-font-ttf"/>' for n in font_entries)
man = man.replace("</manifest:manifest>", add + "</manifest:manifest>")
items["META-INF/manifest.xml"] = man.encode("utf-8")

if "settings.xml" in items:
    s = items["settings.xml"].decode("utf-8")
    if 'config:name="EmbedFonts"' in s:
        s = re.sub(r'(<config:config-item config:name="EmbedFonts" config:type="boolean">)\w+(</config:config-item>)', r"\1true\2", s)
    items["settings.xml"] = s.encode("utf-8")

with zipfile.ZipFile(dst, "w") as zout:
    zout.writestr(zipfile.ZipInfo("mimetype"), items.pop("mimetype"), compress_type=zipfile.ZIP_STORED)
    for n, data in items.items():
        zout.writestr(n, data, compress_type=zipfile.ZIP_DEFLATED)
print("embedded:", font_entries)
