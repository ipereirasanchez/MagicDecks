#!/usr/bin/env python3
"""Convierte los resumenes .md de cada baraja a PDF (A4) usando Chrome headless.
Salida: <nombre>_resumen.pdf junto a cada .md."""
import os, re, glob, subprocess, shutil, tempfile, markdown
from PIL import Image

JPEG_Q = 88  # calidad de las imagenes incrustadas en el PDF (los .md siguen usando los PNG)

HERE = os.path.dirname(os.path.abspath(__file__))
CHROME = shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser")

CSS = """
@page { size: A4; margin: 14mm 12mm; }
body { font-family: "DejaVu Sans", "Segoe UI", Arial, sans-serif; font-size: 10.5pt; line-height: 1.4; color: #222; }
h1 { font-size: 20pt; border-bottom: 2px solid #444; padding-bottom: 4px; }
h2 { font-size: 15pt; margin-top: 18pt; border-bottom: 1px solid #999; padding-bottom: 2px; page-break-after: avoid; }
h3 { font-size: 12pt; margin-top: 14pt; page-break-after: avoid; }
blockquote { color: #666; border-left: 3px solid #ccc; margin: 0; padding-left: 8px; font-size: 9.5pt; }
code { background: #f2f2f2; padding: 0 3px; border-radius: 3px; font-size: 9.5pt; }
table { border-collapse: collapse; page-break-inside: avoid; }
table.md { width: 100%; margin: 6pt 0; }
table.md th, table.md td { border: 1px solid #bbb; padding: 3px 6px; vertical-align: top; text-align: left; font-size: 9.5pt; }
table.md th { background: #eee; }
table:not(.md) td { padding: 4px; }
table:not(.md) img { width: 43mm; height: auto; display: block; margin: 0 auto; }
table:not(.md) sub { font-size: 8pt; color: #555; }
ul, ol { padding-left: 18pt; }
li { margin: 2pt 0; }
img[width="300"] { width: 60mm !important; }
"""

def build(md_path):
    text = open(md_path, encoding="utf-8").read()
    # sub-listas con 2 espacios -> 4 (Python-Markdown lo requiere)
    text = re.sub(r"(?m)^  (- )", r"    \1", text)
    body = markdown.markdown(text, extensions=["tables", "sane_lists"])
    # las tablas de texto (no las de cartas) llevan <thead>: marcarlas
    body = body.replace("<table>\n<thead>", '<table class="md">\n<thead>')
    # imagenes: JPEG comprimido en carpeta temporal para que el PDF no pese 50 MB
    imgtmp = tempfile.mkdtemp(prefix="mdpdf_img_")
    mddir = os.path.dirname(os.path.abspath(md_path))   # decks/ o decks/es/
    def to_jpeg(m):
        src = os.path.normpath(os.path.join(mddir, m.group(1)))
        dst = os.path.join(imgtmp, os.path.splitext(os.path.basename(src))[0] + ".jpg")
        if not os.path.exists(dst):
            Image.open(src).convert("RGB").save(dst, "JPEG", quality=JPEG_Q, optimize=True)
        return 'src="file://%s"' % dst
    body = re.sub(r'src="((?:\.\./)*img/[^"]+)"', to_jpeg, body)
    html = "<!doctype html><html><head><meta charset='utf-8'><style>%s</style></head><body>%s</body></html>" % (CSS, body)
    html_path = os.path.splitext(md_path)[0] + ".html"
    open(html_path, "w", encoding="utf-8").write(html)
    out = os.path.splitext(md_path)[0] + "_resumen.pdf"
    tmp_profile = tempfile.mkdtemp()
    cmd = [CHROME, "--headless=new", "--disable-gpu", "--no-sandbox", "--allow-file-access-from-files",
           "--user-data-dir=" + tmp_profile, "--no-pdf-header-footer",
           "--print-to-pdf=" + out, "file://" + os.path.abspath(html_path)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    shutil.rmtree(tmp_profile, ignore_errors=True)
    shutil.rmtree(imgtmp, ignore_errors=True)
    os.remove(html_path)
    ok = os.path.exists(out) and os.path.getsize(out) > 1000
    print(("OK  " if ok else "FAIL") , os.path.basename(out), "%.1f MB" % (os.path.getsize(out)/1e6) if ok else r.stderr[-400:])
    return ok

RESERVED_DIRS = {"_cache", "roles", "es", "img"}

def deck_files(base, ext):
    """Los ficheros <ext> de decks/: los sueltos y los de cada carpeta de propietario
    (decks/<Propietario>/x.dek). Las carpetas reservadas se ignoran."""
    out = sorted(glob.glob(os.path.join(base, "*" + ext)))
    for name in sorted(os.listdir(base)):
        d = os.path.join(base, name)
        if os.path.isdir(d) and name not in RESERVED_DIRS and not name.startswith("."):
            out += sorted(glob.glob(os.path.join(d, "*" + ext)))
    return out

if __name__ == "__main__":
    if not CHROME:
        raise SystemExit("No se encuentra Chrome/Chromium")
    mds = deck_files(HERE, ".md") + sorted(glob.glob(os.path.join(HERE, "es", "*.md")))
    for md in mds:
        build(md)
