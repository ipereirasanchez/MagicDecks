#!/usr/bin/env python3
"""Genera los mismos PDFs imprimibles pero con las cartas en ESPANOL (cuando existe
impresion en espanol en Scryfall). Reutiliza el cache de imagenes de make_pdfs.py."""
import os, sys, json, time, glob, hashlib
import xml.etree.ElementTree as ET
import requests
from PIL import Image, ImageFile
ImageFile.MAXBLOCK = 64 * 1024 * 1024
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(BASE, "_cache")
IMGDIR = os.path.join(CACHE, "img")
os.makedirs(IMGDIR, exist_ok=True)
DATA_CACHE = os.path.join(CACHE, "cards.json")       # ingles (ya existente)
ES_CACHE = os.path.join(CACHE, "cards_es.json")      # espanol

CARD_W, CARD_H = 63.5*mm, 88.9*mm
COLS, ROWS = 3, 3
PAGE_W, PAGE_H = A4
MX = (PAGE_W - COLS*CARD_W) / 2
MY = (PAGE_H - ROWS*CARD_H) / 2

S = requests.Session()
S.headers.update({"User-Agent": "DeckProxyPDF/1.0", "Accept": "application/json"})

def load(path, default):
    if os.path.exists(path):
        with open(path) as f: return json.load(f)
    return default

def save(path, data):
    with open(path, "w") as f: json.dump(data, f)

def parse_dek(path):
    tree = ET.parse(path)
    main, commanders = [], []
    for c in tree.getroot().findall("Cards"):
        entry = (c.get("Name"), int(c.get("Quantity", "1")))
        if (c.get("Sideboard") or "false").lower() == "true":
            commanders.append(entry)
        else:
            main.append(entry)
    return commanders + main

def has_images(card):
    if card.get("image_uris"): return True
    return any((f.get("image_uris") or {}) for f in card.get("card_faces") or [])

def pick_best(prints):
    """Mejor impresion espanola: primero alta resolucion, luego la mas reciente."""
    ok = [c for c in prints if c.get("lang") == "es" and has_images(c)]
    if not ok: return None
    ok.sort(key=lambda c: (bool(c.get("highres_image")), c.get("released_at") or ""), reverse=True)
    return ok[0]

def search_es(name, en_card):
    """Busca impresion en espanol. Devuelve la carta o None."""
    queries = []
    oid = (en_card or {}).get("oracle_id")
    if oid: queries.append("oracleid:%s lang:es" % oid)
    queries.append('!"%s" lang:es' % name.replace('"', ''))
    for q in queries:
        try:
            r = S.get("https://api.scryfall.com/cards/search",
                      params={"q": q, "include_multilingual": "true", "unique": "prints"},
                      timeout=45)
            time.sleep(0.12)
            if r.status_code != 200:
                continue
            best = pick_best(r.json().get("data", []))
            if best: return best
        except Exception as e:
            print("   aviso: fallo la busqueda de", name, "->", e)
            time.sleep(1.0)
    return None

def image_urls(card):
    if not card: return []
    if card.get("image_uris"):
        return [card["image_uris"].get("png") or card["image_uris"].get("large")]
    urls = []
    for face in card.get("card_faces", []) or []:
        iu = face.get("image_uris") or {}
        u = iu.get("png") or iu.get("large")
        if u: urls.append(u)
    return urls

def verify(fn):
    try:
        with Image.open(fn) as im: im.load()
        return True
    except Exception:
        return False

def to_jpeg(fn, quality=92):
    out = os.path.splitext(fn)[0] + "_p.jpg"
    if not os.path.exists(out) or os.path.getsize(out) == 0:
        im = Image.open(fn)
        if im.mode in ("RGBA", "LA", "P"):
            bg = Image.new("RGB", im.size, (255, 255, 255))
            im = im.convert("RGBA")
            bg.paste(im, mask=im.split()[-1])
            im = bg
        else:
            im = im.convert("RGB")
        try:
            im.save(out, "JPEG", quality=quality, optimize=True, subsampling=0)
        except OSError:
            im.save(out, "JPEG", quality=quality, subsampling=0)
    return out

def get_image(url):
    ext = ".png" if ".png" in url else ".jpg"
    fn = os.path.join(IMGDIR, hashlib.md5(url.encode()).hexdigest() + ext)
    for attempt in range(4):
        if os.path.exists(fn) and os.path.getsize(fn) > 0 and verify(fn):
            return to_jpeg(fn)
        try:
            r = S.get(url, timeout=60)
            r.raise_for_status()
            with open(fn, "wb") as f: f.write(r.content)
            time.sleep(0.1)
        except Exception:
            time.sleep(1.5)
        if os.path.exists(fn) and not verify(fn):
            os.remove(fn)
            time.sleep(1.0)
    raise RuntimeError("no se pudo descargar una imagen valida: " + url)

def build_pdf(deck_name, images, out_path):
    c = canvas.Canvas(out_path, pagesize=A4)
    c.setPageCompression(1)
    c.setTitle(deck_name)
    readers = {}
    for idx, img in enumerate(images):
        slot = idx % (COLS*ROWS)
        if slot == 0 and idx > 0:
            c.showPage()
        col, row = slot % COLS, slot // COLS
        x = MX + col*CARD_W
        y = PAGE_H - MY - (row+1)*CARD_H
        if img not in readers:
            readers[img] = ImageReader(img)
        c.drawImage(readers[img], x, y, width=CARD_W, height=CARD_H, mask=None)
        c.setStrokeColorRGB(0.75, 0.75, 0.75)
        c.setLineWidth(0.25)
        c.rect(x, y, CARD_W, CARD_H, stroke=1, fill=0)
    c.save()

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

def main():
    en = load(DATA_CACHE, {})
    es = load(ES_CACHE, {})
    decks = deck_files(BASE, ".dek")
    parsed = {d: parse_dek(d) for d in decks}
    names = sorted({n for d in decks for n, q in parsed[d]})

    pending = [n for n in names if n not in es]
    print("Buscando version en espanol de %d cartas (%d ya en cache)..." % (len(pending), len(names)-len(pending)))
    for i, n in enumerate(pending, 1):
        es[n] = search_es(n, en.get(n))
        if i % 25 == 0:
            save(ES_CACHE, es)
            print("   %d/%d" % (i, len(pending)))
    save(ES_CACHE, es)

    sin_es = sorted({n for n in names if not es.get(n)})
    print("\nSin impresion en espanol (se usara la inglesa): %d" % len(sin_es))
    for n in sin_es: print("   -", n)

    report = []
    for d in decks:
        deck_name = os.path.splitext(os.path.basename(d))[0].strip("_").replace("_", " ") + " (ES)"
        images, missing, en_fallback, extra_faces, total = [], [], [], 0, 0
        for name, qty in parsed[d]:
            card = es.get(name)
            if not card:
                card = en.get(name)
                if card: en_fallback.append(name)
            urls = image_urls(card)
            if not urls:
                missing.append(name); continue
            total += qty
            for _ in range(qty):
                images.append(get_image(urls[0]))
            for u in urls[1:]:
                for _ in range(qty):
                    images.append(get_image(u)); extra_faces += 1
        out = os.path.join(BASE, os.path.splitext(os.path.basename(d))[0] + "_ES.pdf")
        build_pdf(deck_name, images, out)
        report.append((os.path.basename(out), total, extra_faces, len(images), missing, en_fallback))
        print("OK %s: %d cartas (+%d reversos) -> %d imgs, %d en ingles"
              % (os.path.basename(out), total, extra_faces, len(images), len(en_fallback)))

    print("\n--- RESUMEN ---")
    for r in report:
        print("%s: %d cartas, %d reversos, %d imagenes, %d sin version ES" % (r[0], r[1], r[2], r[3], len(r[5])))
        if r[5]: print("   en ingles:", ", ".join(sorted(set(r[5]))))
        if r[4]: print("   FALTAN:", r[4])

if __name__ == "__main__":
    main()
