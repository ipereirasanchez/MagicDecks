#!/usr/bin/env python3
"""Genera un PDF imprimible (cartas a tamano real) por cada archivo .dek usando imagenes de Scryfall."""
import os, re, sys, json, time, html, glob, hashlib
import xml.etree.ElementTree as ET
import requests
from PIL import Image, ImageFile
ImageFile.MAXBLOCK = 64 * 1024 * 1024   # PIL necesita buffer grande con optimize=True
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(BASE, "_cache")
IMGDIR = os.path.join(CACHE, "img")
os.makedirs(IMGDIR, exist_ok=True)
DATA_CACHE = os.path.join(CACHE, "cards.json")

CARD_W, CARD_H = 63.5*mm, 88.9*mm
COLS, ROWS = 3, 3
PAGE_W, PAGE_H = A4
MX = (PAGE_W - COLS*CARD_W) / 2
MY = (PAGE_H - ROWS*CARD_H) / 2

S = requests.Session()
S.headers.update({"User-Agent": "DeckProxyPDF/1.0", "Accept": "application/json"})

def load_cache():
    if os.path.exists(DATA_CACHE):
        with open(DATA_CACHE) as f: return json.load(f)
    return {}

def save_cache(c):
    with open(DATA_CACHE, "w") as f: json.dump(c, f)

def parse_dek(path):
    """Devuelve [(nombre, cantidad)]. En los .dek de Commander el comandante viene
    marcado como Sideboard="true"; lo colocamos el primero."""
    tree = ET.parse(path)
    main, commanders = [], []
    for c in tree.getroot().findall("Cards"):
        entry = (c.get("Name"), int(c.get("Quantity", "1")))
        if (c.get("Sideboard") or "false").lower() == "true":
            commanders.append(entry)
        else:
            main.append(entry)
    return commanders + main

def fetch_cards(names, cache):
    """Rellena cache[nombre] con datos de Scryfall. Usa /cards/collection por lotes."""
    missing = [n for n in names if n not in cache]
    for i in range(0, len(missing), 75):
        batch = missing[i:i+75]
        r = S.post("https://api.scryfall.com/cards/collection",
                   json={"identifiers": [{"name": n} for n in batch]}, timeout=60)
        r.raise_for_status()
        data = r.json()
        for card in data.get("data", []):
            for n in batch:
                if n.lower() == card["name"].lower() or card["name"].lower().startswith(n.lower() + " //"):
                    cache[n] = card
            cache.setdefault(card["name"], card)
        for nf in data.get("not_found", []):
            nm = nf.get("name")
            # segundo intento: busqueda difusa
            try:
                rr = S.get("https://api.scryfall.com/cards/named", params={"fuzzy": nm}, timeout=30)
                if rr.status_code == 200:
                    cache[nm] = rr.json()
                else:
                    cache[nm] = None
            except Exception:
                cache[nm] = None
            time.sleep(0.12)
        time.sleep(0.15)
    save_cache(cache)

def image_urls(card):
    """URLs de imagen (una por cara)."""
    if not card: return []
    if card.get("image_uris"):
        return [card["image_uris"].get("png") or card["image_uris"].get("large")]
    urls = []
    for face in card.get("card_faces", []) or []:
        iu = face.get("image_uris") or {}
        u = iu.get("png") or iu.get("large")
        if u: urls.append(u)
    return urls

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
            os.remove(fn)          # descarga truncada: reintentar
            time.sleep(1.0)
    raise RuntimeError("no se pudo descargar una imagen valida: " + url)

def verify(fn):
    try:
        with Image.open(fn) as im:
            im.load()
        return True
    except Exception:
        return False

def to_jpeg(fn, quality=92):
    """Convierte a JPEG (mucho mas ligero que PNG para el PDF, sin perdida visible al imprimir)."""
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
            im.save(out, "JPEG", quality=quality, subsampling=0)   # sin optimize
    return out

def build_pdf(deck_name, images, out_path):
    c = canvas.Canvas(out_path, pagesize=A4)
    c.setPageCompression(1)
    c.setTitle(deck_name)
    readers = {}   # una sola copia embebida por imagen repetida (tierras basicas, etc.)
    for idx, img in enumerate(images):
        slot = idx % (COLS*ROWS)
        if slot == 0 and idx > 0:
            c.showPage()
        col = slot % COLS
        row = slot // COLS
        x = MX + col*CARD_W
        y = PAGE_H - MY - (row+1)*CARD_H
        if img not in readers:
            readers[img] = ImageReader(img)
        c.drawImage(readers[img], x, y, width=CARD_W, height=CARD_H, mask=None)
        # marca de corte tenue
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
    cache = load_cache()
    decks = deck_files(BASE, ".dek")
    all_names = []
    parsed = {}
    for d in decks:
        entries = parse_dek(d)
        parsed[d] = entries
        all_names += [n for n, q in entries]
    fetch_cards(sorted(set(all_names)), cache)

    report = []
    for d in decks:
        deck_name = os.path.splitext(os.path.basename(d))[0].strip("_").replace("_", " ")
        images, missing, extra_faces = [], [], 0
        total = 0
        for name, qty in parsed[d]:
            card = cache.get(name)
            urls = image_urls(card)
            if not urls:
                missing.append(name)
                continue
            total += qty
            for _ in range(qty):
                images.append(get_image(urls[0]))
            if len(urls) > 1:          # caras traseras: una copia por carta
                for u in urls[1:]:
                    for _ in range(qty):
                        images.append(get_image(u))
                        extra_faces += 1
        out = os.path.join(BASE, os.path.splitext(os.path.basename(d))[0] + ".pdf")
        build_pdf(deck_name, images, out)
        report.append((os.path.basename(out), total, extra_faces, len(images), missing))
        print(f"OK {os.path.basename(out)}: {total} cartas (+{extra_faces} reversos) -> {len(images)} imgs")
        if missing: print("   NO ENCONTRADAS:", missing)

    print("\n--- RESUMEN ---")
    for r in report:
        print(f"{r[0]}: {r[1]} cartas, {r[2]} reversos, {r[3]} imagenes" + (f", FALTAN: {r[4]}" if r[4] else ""))

if __name__ == "__main__":
    main()
