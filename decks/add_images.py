#!/usr/bin/env python3
"""Inserta miniaturas de las cartas en los .md de cada baraja.

- Reutiliza la cache de imagenes de make_pdfs.py / make_pdfs_es.py (_cache/img).
- Usa la impresion en INGLES a maxima resolucion (PNG de Scryfall) por defecto.
- Copia las imagenes a img/ y las inserta:
    * imagen del comandante bajo el titulo,
    * fila de cartas citadas en cada seccion "### ..." de combos,
    * galeria del "Top 10 de relevancia".
Se puede volver a ejecutar: borra las filas que insertó antes y las regenera.
"""
import os, re, json, hashlib, sys, shutil, urllib.request

def _Image():
    """Pillow solo hace falta para redimensionar o convertir (no con FULL_RES y PNG en cache)."""
    from PIL import Image
    return Image

LANG = "en"          # "en" -> siempre inglés; "es" -> español con fallback a inglés
FULL_RES = True      # True: copia el PNG de Scryfall tal cual (745x1040, sin perdida)
THUMB_W = 240        # ancho de las miniaturas si FULL_RES = False
PER_ROW = 4          # cartas por fila
SHOW_W_SECTION = 210 # ancho mostrado por carta (4 por fila)
SHOW_W_TOP = 210
SHOW_W_CMD = 300
MAX_PER_SECTION = 8

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "_cache")
IMGDIR = os.path.join(CACHE, "img")
OUT = os.path.join(HERE, "img")
os.makedirs(OUT, exist_ok=True)

EN = json.load(open(os.path.join(CACHE, "cards.json")))
ES = json.load(open(os.path.join(CACHE, "cards_es.json"))) if os.path.exists(os.path.join(CACHE, "cards_es.json")) else {}
BASICS = {"Plains", "Island", "Swamp", "Mountain", "Forest", "Snow-Covered Mountain"}
RESERVED_DIRS = {"_cache", "roles", "es", "img"}

MARK_START = "<!-- cards:start -->"
MARK_END = "<!-- cards:end -->"

def front_png(card):
    if not card:
        return None
    if card.get("image_uris"):
        return card["image_uris"].get("png") or card["image_uris"].get("large")
    faces = card.get("card_faces") or []
    if faces and faces[0].get("image_uris"):
        return faces[0]["image_uris"].get("png") or faces[0]["image_uris"].get("large")
    return None

def cached_path(url):
    ext = ".png" if ".png" in url else ".jpg"
    base = os.path.join(IMGDIR, hashlib.md5(url.encode()).hexdigest())
    for p in (base + ext, base + "_p.jpg"):
        if os.path.exists(p):
            return p
    # no esta en cache: intentar descargar
    try:
        urllib.request.urlretrieve(url, base + ext)
        return base + ext
    except Exception as e:
        print("  ! no se pudo descargar", url, e)
        return None

def slug(name):
    s = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")
    return s

IMG_PREFIX = "img/"   # lo fija process() segun donde este el .md


def thumb_for(name):
    """Devuelve ruta relativa (img/xxx.jpg) de la miniatura, creandola si hace falta."""
    ext = ".png" if FULL_RES else ".jpg"
    out = os.path.join(OUT, slug(name) + ext)
    if os.path.exists(out):
        return IMG_PREFIX + os.path.basename(out)
    card = None
    if LANG == "es" and ES.get(name) and front_png(ES[name]):
        card = ES[name]
    if card is None:
        card = EN.get(name)
    url = front_png(card)
    if not url:
        print("  ! sin imagen:", name)
        return None
    src = cached_path(url)
    if not src:
        return None
    if FULL_RES:
        if src.endswith(".png"):
            shutil.copyfile(src, out)
        else:  # solo hay JPEG comprimido en cache: reconvertir sin reescalar
            _Image().open(src).convert("RGB").save(out, "PNG")
    else:
        im = _Image().open(src).convert("RGB")
        h = int(im.height * THUMB_W / im.width)
        im = im.resize((THUMB_W, h), _Image().LANCZOS)
        im.save(out, "JPEG", quality=82, optimize=True)
    return IMG_PREFIX + os.path.basename(out)

def deck_names(dek_path):
    xml = open(dek_path, encoding="utf-8").read()
    names, cmd = [], None
    for m in re.finditer(r'Sideboard="(true|false)" Name="([^"]*)"', xml):
        n = m.group(2).replace("&apos;", "'").replace("&amp;", "&")
        if m.group(1) == "true":
            cmd = n
        if n not in BASICS and n not in names:
            names.append(n)
    return names, cmd

def aliases(names):
    """Nombre corto (antes de la coma) cuando es inequivoco: 'Vito', 'Mikaeus', 'Yawgmoth'..."""
    al = {}
    for n in names:
        if ", " not in n:
            continue
        short = n.split(", ")[0]
        clash = [m for m in names if m != n and m.startswith(short)]
        if not clash and short not in al:
            al[short] = n
    return al

def find_names(text, names):
    """Nombres de cartas citados en el texto (completos o abreviados), por orden de aparicion."""
    found = []
    work = text
    for n in sorted(names, key=len, reverse=True):
        pat = re.compile(r"(?<![\w'])" + re.escape(n) + r"(?![\w])")
        m = pat.search(work)
        if m:
            found.append((m.start(), n))
            work = pat.sub(lambda mm: " " * len(mm.group(0)), work)
    for short, n in aliases(names).items():
        if any(n == f for _, f in found):
            continue
        m = re.search(r"(?<![\w'])" + re.escape(short) + r"(?![\w])", work)
        if m:
            found.append((m.start(), n))
    found.sort()
    return [n for _, n in found]

def img_row(names, width, cls):
    """Tabla HTML con PER_ROW cartas por fila y el nombre debajo de cada una."""
    cells = []
    for n in names:
        p = thumb_for(n)
        if p:
            cells.append('<td align="center"><img src="%s" alt="%s" title="%s" width="%d"><br><sub>%s</sub></td>' % (p, n, n, width, n))
    if not cells:
        return ""
    rows = []
    for i in range(0, len(cells), PER_ROW):
        rows.append("<tr>" + "".join(cells[i:i + PER_ROW]) + "</tr>")
    return "%s\n<table>\n%s\n</table>\n%s\n" % (MARK_START, "\n".join(rows), MARK_END)

def strip_old(md):
    return re.sub(re.escape(MARK_START) + r".*?" + re.escape(MARK_END) + r"\n?", "", md, flags=re.S)

def process(md_path, dek_path):
    global IMG_PREFIX
    rel = os.path.relpath(OUT, os.path.dirname(os.path.abspath(md_path)))
    IMG_PREFIX = rel.replace(os.sep, "/") + "/"
    names, cmd = deck_names(dek_path)
    md = strip_old(open(md_path, encoding="utf-8").read())
    lines = md.split("\n")
    out = []
    i = 0
    # 1) comandante bajo el bloque de cita inicial
    while i < len(lines):
        out.append(lines[i])
        if lines[i].startswith(">"):
            # fin de la cita: siguiente linea vacia
            i += 1
            while i < len(lines) and lines[i].startswith(">"):
                out.append(lines[i]); i += 1
            out.append("")
            if cmd:
                out.append(img_row([cmd], SHOW_W_CMD, "cmd").rstrip("\n"))
            break
        i += 1
    rest = lines[i:]
    # 2) secciones ### -> fila de cartas citadas
    text = "\n".join(rest)
    blocks = re.split(r"(?m)^(?=#{2,3} )", text)
    result = []
    for b in blocks:
        if b.startswith("### "):
            head, _, body = b.partition("\n")
            cited = [n for n in find_names(head + "\n" + body, names) if n != cmd][:MAX_PER_SECTION]
            result.append(head + "\n" + img_row(cited, SHOW_W_SECTION, "sec") + body)
        elif b.startswith("## Cartes clau") or b.startswith("## Cartas clave"):
            # galeria del top 10
            def repl(m):
                line = m.group(0)
                top = find_names(line, names)
                return line + "\n\n" + img_row(top, SHOW_W_TOP, "top")
            b = re.sub(r"(?m)^\*\*Top 10 de (?:rellevància|relevancia)\*\*:.*$", repl, b)
            result.append(b)
        else:
            result.append(b)
    final = "\n".join(out) + "\n" + "".join(result)
    final = re.sub(r"\n{3,}", "\n\n", final)
    open(md_path, "w", encoding="utf-8").write(final)
    print("OK", os.path.basename(md_path), "(comandante:", cmd, ")")

if __name__ == "__main__":
    deks = sorted(f for f in os.listdir(HERE) if f.endswith(".dek"))
    deks = [os.path.join(HERE, f) for f in deks]
    for name in sorted(os.listdir(HERE)):
        d = os.path.join(HERE, name)
        if os.path.isdir(d) and name not in RESERVED_DIRS and not name.startswith("."):
            deks += [os.path.join(d, f) for f in sorted(os.listdir(d)) if f.endswith(".dek")]
    for dek in deks:
        md = os.path.splitext(dek)[0] + ".md"
        if os.path.exists(md):
            process(md, dek)
        else:
            print("sin .md para", dek)
