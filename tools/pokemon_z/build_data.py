#!/usr/bin/env python3
"""Convierte la "Guía Oficial de Pokémon Z" (PDF exportado de Google Docs) en
docs/pokemon/z/data/data.js, el fichero de datos de la guía web de Pokémon Z.

Uso:  python3 tools/pokemon_z/build_data.py /ruta/a/guia_pokemon_z.pdf

El PDF no forma parte del repositorio. Necesita `pdftohtml` (poppler-utils) e ImageMagick
(`convert`) para identificar los sprites de los combates: la guía solo muestra la imagen de
cada Pokémon de los jefes, así que `sprites.json` traduce el hash de cada imagen a su nombre
(y `icons.json` cada icono de tipo a su tipo). Solo biblioteca estándar.

Salida: capítulos (la historia principal partida por medallas/actos y los apéndices), cada
uno como una lista de bloques (encabezados, párrafos, listas, equipos de jefe, tablas de
stats, tablas de MTs/megapiedras/Pokédex), más el mapa de sprites de PokeAPI.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
from collections import OrderedDict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT_FILE = ROOT / "docs" / "pokemon" / "z" / "data" / "data.js"
POKEAPI_FILE = ROOT / "tools" / "pokemon_rocket" / "pokeapi_pokemon.json"
SPRITES_FILE = HERE / "sprites.json"
ICONS_FILE = HERE / "icons.json"

PAGE_CENTER = 447  # A4 a 1,5x: 894 px de ancho
WARNINGS: list[str] = []


def warn(msg: str) -> None:
    WARNINGS.append(msg)


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if not unicodedata.combining(c))


# ---------------------------------------------------------------------------
# Capítulos: (página, inicio del texto de la línea ancla, id, grupo, título corto)
# ---------------------------------------------------------------------------
CHAPTERS = [
    (3, "Dudas Frecuentes", "dudas", "Antes de empezar", "Dudas frecuentes"),
    (6, "Modos del Z", "modos", "Antes de empezar", "Modos de juego"),
    (7, "Kalos, hace 300 años", "c01", "Acto I", "Pueblo Lienzo y la primera medalla"),
    (30, "Ruta 4", "c02", "Acto I", "Bosque Ladera y Ciudad Óleo (2ª medalla)"),
    (49, "CHATEAU ROSILLON", "c03", "Acto I", "Chateau Rosillon y Pueblo Profano"),
    (70, "CIUDAD NOVARTE", "c04", "Acto I", "Ciudad Novarte y el Taller Quemado (3ª medalla)"),
    (82, "Ruta 8", "c05", "Acto I", "Chateau Lanto y Pueblo Bodegón (4ª medalla)"),
    (110, "Ruta 9", "c06", "Acto I", "Pueblo Petroglifo y Fort Leviatán"),
    (128, "Ruta 11", "c07", "Acto I", "Ciudad Relieve y el barco del Capitán Loto (5ª medalla)"),
    (141, "Regresar a hacer cosas con el poder de Surf", "c08", "Acto I", "Surf, los perros legendarios y Viejo Vánitas (6ª medalla)"),
    (163, "Ruta 13", "c09", "Acto I", "Ciudad Luminalia"),
    (178, "PALACIO LUMINALIA", "c10", "Acto I", "Palacio Luminalia y Cámaras de Reflexión"),
    (199, "COMIENZO DEL SEGUNDO ACTO", "c11", "Acto II", "Prisión del Olvido"),
    (216, "PIRINEOS DE KALOS", "c12", "Acto II", "Pirineos, Ciudad Batik y Torre Oscura (7ª medalla)"),
    (234, "Ruta 14", "c13", "Acto II", "Ciudad Romantis y la Fábrica de Pokéball (8ª medalla)"),
    (260, "Ruta 15", "c14", "Acto II", "Pueblo Fresco, Gruta Helada y Ciudad Fluxus (9ª medalla)"),
    (293, "Ruta 19", "c15", "Acto II", "Pueblo Mosaico y Ciudad Fractal (10ª medalla)"),
    (317, "CAMPAMENTO DE CRISANTO", "c16", "Acto II", "La batalla de Kalos Este"),
    (324, "COMIENZO DEL TERCER ACTO", "c17", "Acto III", "Ruta 21, el balneario y los Regis"),
    (330, "Xerneas", "c18", "Acto III", "Xerneas: Bosque Errante y Manantial Profundo"),
    (340, "Yveltal", "c19", "Acto III", "Yveltal: Pueblo Sanguino y la Pesadilla de Circo"),
    (356, "Zygarde", "c20", "Acto III", "Zygarde: Luminalia y la Torre Prisma"),
    (367, "El camino a Yantra", "c21", "Acto III", "El camino a Yantra"),
    (372, "Ciudad Yantra", "c22", "Acto III", "Ciudad Yantra"),
    (380, "TORRE BATALLA", "c23", "Acto III", "Torre Batalla (opcional)"),
    (404, "Un último intento", "c24", "Acto III", "Un último intento: el Arma Definitiva"),
    (430, "Postgame", "post", "Después de la historia", "Postgame"),
    (437, "Listado de Habitantes de Acrílico", "acrilico", "Apéndices", "Habitantes de Pueblo Acrílico"),
    (439, "LISTADO DE UBICACIÓN DE RECETAS", "recetas", "Apéndices", "Recetas y objetos crafteables"),
    (443, "LISTADO DE MTS", "mts", "Apéndices", "MTs y dónde encontrarlas"),
    (447, "NIDOS ALFA", "nidos", "Apéndices", "Nidos Alfa"),
    (448, "LEGENDARIOS", "legendarios", "Apéndices", "Legendarios y dónde capturarlos"),
    (485, "LISTADO DE MEGAPIEDRAS", "megapiedras", "Apéndices", "Megapiedras"),
    (490, "FORMAS Y NUEVAS EVOLUCIONES", "formas", "Apéndices", "Formas regionales y evoluciones nuevas"),
    (505, "NUEVAS MEGAEVOLUCIONES", "megas", "Apéndices", "Nuevas megaevoluciones"),
    (509, "GUÍA DE CAPTURA DE LA POKÉDEX", "pokedex", "Apéndices", "Pokédex: cómo conseguir cada Pokémon"),
    (559, "CRÉDITOS DE LA GUÍA", "creditos", "Apéndices", "Créditos"),
]

CALLOUTS = [
    (r"^(nota( \d+)?|notas)\s*:", "note"),
    (r"^importante\s*:", "important"),
    (r"^(pistas? (para|de) entrenador(es)?)\s*:", "tip"),
    (r"^dato útil\s*:", "tip"),
    (r"^datos importantes", "important"),
    (r"^consejos de (batalla|combate)\s*:", "tips"),
    (r"^misi[oó]n secundaria\s*:", "quest"),
    (r"^¡aviso!", "important"),
    (r"^advertencia", "important"),
]

TYPE_ORDER = ["Normal", "Lucha", "Volador", "Veneno", "Tierra", "Roca", "Bicho", "Fantasma", "Acero",
              "Fuego", "Agua", "Planta", "Eléctrico", "Psíquico", "Hielo", "Dragón", "Siniestro", "Hada"]


# ---------------------------------------------------------------------------
# 1. PDF -> fragmentos de texto e imágenes (pdftohtml -xml)
# ---------------------------------------------------------------------------
class Frag:
    __slots__ = ("page", "top", "left", "width", "height", "size", "bold", "italic", "text", "href")

    def __init__(self, page, top, left, width, height, size, bold, italic, text, href):
        self.page, self.top, self.left, self.width, self.height = page, top, left, width, height
        self.size, self.bold, self.italic, self.text, self.href = size, bold, italic, text, href

    @property
    def right(self):
        return self.left + self.width

    @property
    def cx(self):
        return self.left + self.width / 2


class Img:
    __slots__ = ("page", "top", "left", "width", "height", "src", "hash")

    def __init__(self, page, top, left, width, height, src):
        self.page, self.top, self.left, self.width, self.height, self.src = page, top, left, width, height, src
        self.hash = None


def run_pdftohtml(pdf: Path, workdir: Path) -> Path:
    base = workdir / "guia"
    subprocess.run(["pdftohtml", "-xml", "-q", str(pdf), str(base)], check=True)
    return workdir / "guia.xml"


def parse_xml(xml_path: Path) -> tuple[list[Frag], list[Img]]:
    x = nfc(xml_path.read_text(encoding="utf-8", errors="replace"))
    sizes = {i: int(s) for i, s in re.findall(r'<fontspec id="(\d+)" size="(\d+)"', x)}
    frags: list[Frag] = []
    imgs: list[Img] = []
    for pm in re.finditer(r'<page number="(\d+)"[^>]*>(.*?)</page>', x, re.S):
        page = int(pm.group(1))
        body = pm.group(2)
        for im in re.finditer(r'<image top="(\d+)" left="(\d+)" width="(\d+)" height="(\d+)" src="([^"]+)"', body):
            top, left, w, h = map(int, im.group(1, 2, 3, 4))
            imgs.append(Img(page, top, left, w, h, str(xml_path.parent / Path(im.group(5)).name)))
        for t in re.finditer(r'<text top="(\d+)" left="(\d+)" width="(\d+)" height="(\d+)" font="(\d+)">(.*?)</text>', body, re.S):
            raw = t.group(6)
            href = None
            mh = re.search(r'<a href="([^"]+)">', raw)
            if mh:
                href = html.unescape(mh.group(1))
            text = html.unescape(re.sub(r"<[^>]+>", "", raw))
            if not text.strip():
                continue
            frags.append(Frag(page, int(t.group(1)), int(t.group(2)), int(t.group(3)), int(t.group(4)),
                              sizes.get(t.group(5), 17), "<b>" in raw, "<i>" in raw, text, href))
    return frags, imgs


# ---------------------------------------------------------------------------
# 2. Fragmentos -> líneas
# ---------------------------------------------------------------------------
class Line:
    __slots__ = ("page", "top", "frags")

    def __init__(self, page, top, frags):
        self.page, self.top, self.frags = page, top, frags

    @property
    def left(self):
        return min(f.left for f in self.frags)

    @property
    def right(self):
        return max(f.right for f in self.frags)

    @property
    def size(self):
        return max(f.size for f in self.frags)

    @property
    def bold(self):
        return all(f.bold for f in self.frags if f.text.strip())

    @property
    def centered(self):
        return abs((self.left + self.right) / 2 - PAGE_CENTER) < 30 and self.left > 125

    @property
    def text(self):
        out = ""
        prev = None
        for f in self.frags:
            if prev is not None and f.left - prev.right > 3 and not out.endswith(" ") and not f.text.startswith(" "):
                out += " "
            out += f.text
            prev = f
        return re.sub(r"\s+", " ", out).strip()

    def html(self):
        out = ""
        prev = None
        for f in self.frags:
            s = html.escape(f.text)
            if f.href:
                s = f'<a href="{html.escape(f.href)}" target="_blank" rel="noopener">{s.strip() or html.escape(f.href)}</a>'
            elif f.bold and f.text.strip() and f.size <= 18:
                s = f"<strong>{s}</strong>"
            if f.italic and f.text.strip():
                s = f"<em>{s}</em>"
            if prev is not None and f.left - prev.right > 3 and not out.endswith(" ") and not f.text.startswith(" "):
                out += " "
            out += s
            prev = f
        return re.sub(r"\s+", " ", out).strip()


def split_frags(frags: list[Frag]) -> list[Frag]:
    """Separa celdas pegadas en un mismo fragmento ("60  105 ", "Pokémon  HP  ATK") repartiendo el ancho."""
    out: list[Frag] = []
    for f in frags:
        parts = [p for p in re.split(r"\s{2,}", f.text.strip()) if p]
        if len(parts) <= 1:
            out.append(f)
            continue
        total = sum(len(p) for p in parts) + 2 * (len(parts) - 1)
        x = f.left
        for p in parts:
            w = f.width * len(p) / total
            out.append(Frag(f.page, f.top, int(x), int(w), f.height, f.size, f.bold, f.italic, p, f.href))
            x += f.width * (len(p) + 2) / total
    return out


def build_lines(frags: list[Frag]) -> list[Line]:
    lines: list[Line] = []
    by_page: dict[int, list[Frag]] = {}
    for f in frags:
        by_page.setdefault(f.page, []).append(f)
    for page in sorted(by_page):
        rows: list[list[Frag]] = []
        for f in sorted(by_page[page], key=lambda f: (f.top, f.left)):
            # misma línea si el centro vertical está dentro del fragmento anterior
            placed = False
            for r in rows:
                r0 = r[0]
                if abs((f.top + f.height / 2) - (r0.top + r0.height / 2)) <= max(6, min(f.height, r0.height) * 0.45):
                    r.append(f)
                    placed = True
                    break
            if not placed:
                rows.append([f])
        for r in rows:
            r.sort(key=lambda f: f.left)
            lines.append(Line(page, min(f.top for f in r), r))
    lines.sort(key=lambda l: (l.page, l.top))
    return lines


# ---------------------------------------------------------------------------
# 3. Sprites e iconos de tipo
# ---------------------------------------------------------------------------
def image_hash(path: str) -> str:
    out = subprocess.run(["convert", path, "-alpha", "remove", "-background", "black", "-resize", "48x48!",
                          "-depth", "8", "rgb:-"], capture_output=True, check=True).stdout
    return hashlib.md5(out).hexdigest()[:12]


WHOLE_WORDS = {"ESPADA", "CUERPO", "CARGA", "PUÑO", "GARRA", "BOLA", "RAYO", "ONDA", "FUERZA", "DANZA", "PULSO", "COLMILLO",
               "TAJO", "GOLPE", "PATADA", "CABEZA", "PICO", "VOZ", "PAZ", "FOCO", "HOJA", "PLANCHA", "VELO", "CAMPO", "AGUA",
               "ROCA", "LANZA", "TRAMPA", "FUEGO", "VIENTO", "VOLTIO", "CANTO", "LUZ", "COLA", "ESFERA", "LLAMA", "MURO",
               "SOMBRA", "DOBLE", "TRIPLE", "RED", "HUESO", "HIERBA", "TIERRA", "BRILLO", "PUNTA", "GEMA", "CINTA", "BAYA",
               "HIERRO", "JOYA", "ESPACIO", "ALA", "RUEDA", "SALTO", "CORTE", "DIA", "DÍA", "PIEDRA", "SEMILLA", "PALO"}


def join_cell(parts: list[str]) -> str:
    """Une las líneas de una celda: palabra partida sin guion (celdas estrechas) vs. dos palabras."""
    out = ""
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if not out:
            out = p
            continue
        last = out.split(" ")[-1]
        if out.endswith("-"):
            out = out[:-1] + (" " if last[:-1] in WHOLE_WORDS else "") + p
        elif out.endswith("/"):
            out = out + p
        elif p == "Z" or p.startswith("Z ") or p.startswith("("):
            out = out + " " + p
        elif len(last) >= 10 or (len(last) >= 8 and len(p) <= 3) or (p[:1].islower() and len(last) >= 4):
            out = out + p
        else:
            out = out + " " + p
    return re.sub(r"\s+", " ", out).strip()


def cell_title(s: str) -> str:
    s = s.strip()
    if s in ("", "-", "—"):
        return ""
    return s


# ---------------------------------------------------------------------------
# 4. Bloques
# ---------------------------------------------------------------------------
BULLET_RE = re.compile(r"^[●○■▪•]\s*")
SMALL_WORDS = {"de", "la", "del", "el", "los", "las", "y", "a", "en", "con", "contra", "para", "por", "al", "lo", "un", "una", "o", "e", "sin", "tras"}


def nice_heading(text: str) -> str:
    """Pasa a mayúscula inicial los encabezados que la guía escribe en mayúsculas ("PUEBLO LIENZO")."""
    text = re.sub(r"\s+", " ", text).strip().rstrip(":").strip()
    letters = [c for c in text if c.isalpha()]
    if not letters or sum(1 for c in letters if c.isupper()) < len(letters) * 0.9:
        return text
    words = text.lower().split(" ")
    out = []
    for i, w in enumerate(words):
        if i and w in SMALL_WORDS:
            out.append(w)
        elif w.startswith("(") and len(w) > 1:
            out.append("(" + w[1].upper() + w[2:])
        elif w in ("n°", "nº", "n.º"):
            out.append("n.º")
        else:
            out.append(w[:1].upper() + w[1:])
    res = " ".join(out)
    res = re.sub(r"\b(\d)[ºo°]\b", r"\1.ª", res)  # "1º MEDALLA" -> "1.ª medalla"
    res = re.sub(r"(\d\.ª) Medalla", r"\1 medalla", res)
    res = re.sub(r"(\d\.ª) Visita", r"\1 visita", res)
    res = re.sub(r"\b[Nn][°º.]*\s*(\d)", r"n.º \1", res)
    res = re.sub(r"\((Opcional|Interior|Exterior|Celdas|Isla|Materiales)\)", lambda m: "(" + m.group(1).lower() + ")", res)
    res = res.replace(" Y ", " y ")
    return res



def slug(s: str) -> str:
    s = fold(s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:60] or "x"


class Parser:
    def __init__(self, lines: list[Line], imgs: list[Img], sprite_names: dict, icon_types: dict, resolve):
        self.lines = lines
        self.imgs = imgs
        self.sprite_names = sprite_names
        self.icon_types = icon_types
        self.resolve = resolve
        self.i = 0
        self.blocks: list[dict] = []
        self.used_names: set[str] = set()

    # -- utilidades ---------------------------------------------------------
    def peek(self, k=0):
        j = self.i + k
        return self.lines[j] if 0 <= j < len(self.lines) else None

    def gap(self, a: Line, b: Line) -> int:
        if a.page != b.page:
            return 999
        return b.top - a.top

    def heading_level(self, ln: Line):
        s = ln.size
        if s >= 39:
            return 1
        if s >= 27:
            return 1 if ln.page >= 437 else 2
        if s == 24:
            return 2
        if s == 23 or (s >= 20 and ln.bold):
            return 3
        return None

    def sprite_near(self, page: int, top: int):
        best = None
        for im in self.imgs:
            if im.page != page or im.left > 270 or not (60 <= im.width <= 180):
                continue
            if -40 <= im.top - top <= 150 and (best is None or abs(im.top - top) < abs(best.top - top)):
                best = im
        return best

    def icons_near(self, page: int, top: int) -> list[str]:
        out = []
        for im in self.imgs:
            if im.page == page and (im.width, im.height) == (27, 32) and -40 <= im.top - top <= 170 and im.left < 260:
                t = self.icon_types.get(im.hash)
                if t and t not in out:
                    out.append(t)
        return out

    # -- tablas de jefe ------------------------------------------------------
    def is_boss_header(self, ln: Line) -> bool:
        return ln is not None and ln.text.replace(" ", "") == "NIVELOBJETOHABILIDADNATURALEZA" and len(ln.frags) >= 4

    def parse_boss(self) -> dict:
        hdr = self.peek()
        cols = [f.cx for f in split_frags([f for f in hdr.frags if f.text.strip()])]
        page, top = hdr.page, hdr.top
        self.i += 1
        cells: list[list[str]] = [[] for _ in cols]
        # filas de datos hasta MOVIMIENTOS
        while self.peek() is not None and self.peek().text.replace(" ", "") != "MOVIMIENTOS":
            ln = self.peek()
            if self.is_boss_header(ln) or self.heading_level(ln) or ln.left < 200 and ln.size <= 18 and not ln.text.isupper():
                break
            for f in split_frags([f for f in ln.frags if f.text.strip()]):
                k = min(range(len(cols)), key=lambda j: abs(cols[j] - f.cx))
                cells[k].append(f.text)
            self.i += 1
        moves: list[str] = []
        if self.peek() is not None and self.peek().text.replace(" ", "") == "MOVIMIENTOS":
            self.i += 1
            mfr: list[Frag] = []
            while self.peek() is not None:
                ln = self.peek()
                if self.is_boss_header(ln) or self.heading_level(ln):
                    break
                txt = ln.text
                if not txt.isupper() or ln.left < 200 and len(txt) > 45 or BULLET_RE.match(txt):
                    break
                if mfr and ln.page == mfr[-1].page and ln.top - mfr[-1].top > 45:
                    break
                if mfr and ln.page != mfr[-1].page and ln.top > 260:
                    break
                mfr.extend(split_frags([f for f in ln.frags if f.text.strip()]))
                self.i += 1
            # agrupa por columnas (centros x)
            mfr.sort(key=lambda f: f.cx)
            groups: list[list[Frag]] = []
            for f in mfr:
                if groups and f.cx - groups[-1][-1].cx < 60:
                    groups[-1].append(f)
                else:
                    groups.append([f])
            for g in groups:
                g.sort(key=lambda f: (f.page, f.top))
                moves.append(join_cell([f.text for f in g]))
        level = join_cell(cells[0]) if cells else ""
        item = cell_title(join_cell(cells[1])) if len(cells) > 1 else ""
        ability = cell_title(join_cell(cells[2])) if len(cells) > 2 else ""
        nature = cell_title(join_cell(cells[3])) if len(cells) > 3 else ""
        nature = re.sub(r"\s*([+-])", r" \1", nature).strip()
        nature = re.sub(r"^\+(.*?) -", r"+\1 / −", nature) if nature.startswith("+") and " -" in nature else nature
        nature = re.sub(r"^-(.*?) \+", r"−\1 / +", nature) if nature.startswith("-") and " +" in nature else nature
        im = self.sprite_near(page, top)
        name = self.sprite_names.get(im.hash, "?") if im else "?"
        if name == "?":
            warn(f"[boss] p{page} sprite sin identificar ({im.src if im else 'sin imagen'})")
        types = self.icons_near(page, top)
        mon = {"name": name, "level": level, "item": item, "ability": ability, "nature": nature,
               "moves": [m for m in moves if m][:4], "types": types}
        if name != "?":
            self.used_names.add(name)
        return mon

    # -- tablas de stats ----------------------------------------------------
    def is_stats_header(self, ln: Line) -> bool:
        t = ln.text
        return t.startswith("Pokémon") and "HP" in t and "ATK" in t

    def parse_stats(self) -> dict:
        hdr = self.peek()
        frs = split_frags([f for f in hdr.frags if f.text.strip()])
        hp_x = next(f.cx for f in frs if f.text.strip() == "HP")
        abil_x = []
        for k in (-1, 0, 1):
            ln = self.peek(k)
            if ln and ln.page == hdr.page:
                abil_x += [f.cx for f in split_frags(ln.frags) if f.text.strip().startswith("HABILIDAD")]
        abil_x = sorted(set(round(x) for x in abil_x))
        self.i += 1
        if self.peek() and self.peek().page == hdr.page and self.peek().top - hdr.top < 30:
            self.i += 1  # "ESP ESP NORMAL OCULTA"
        region: list[Frag] = []
        last: Line | None = None
        while self.peek() is not None:
            ln = self.peek()
            if self.is_stats_header(ln) or self.heading_level(ln) or BULLET_RE.match(ln.text):
                break
            if ln.text.startswith("ATK.") and self.peek(1) is not None and self.is_stats_header(self.peek(1)):
                break
            if fold(ln.text).startswith(("nota", "si deseas", "http")):
                break
            if last is not None and ln.page != last.page and not (ln.top < 260 and (ln.text[:1].isupper() or ln.text[:1].isdigit())):
                break
            if last is not None and ln.page == last.page and self.gap(last, ln) > 75:
                break
            region.extend(split_frags([f for f in ln.frags if f.text.strip()]))
            last = ln
            self.i += 1
        is_num = lambda f: re.fullmatch(r"\d{1,3}", f.text.strip()) and f.cx > hp_x - 40
        nums = [f for f in region if is_num(f)]
        # filas: grupos de >=6 números con la misma altura
        rowtops: list[tuple[int, int]] = []
        for f in sorted(nums, key=lambda f: (f.page, f.top)):
            if rowtops and rowtops[-1][0] == f.page and abs(rowtops[-1][1] - f.top) <= 8:
                continue
            same = [g for g in nums if g.page == f.page and abs(g.top - f.top) <= 8]
            if len(same) >= 6:
                rowtops.append((f.page, f.top))
        rows = []

        def nearest_row(f: Frag):
            cands = [(abs(f.top - t), (pg, t)) for pg, t in rowtops if pg == f.page]
            return min(cands)[1] if cands else None

        for page, top in rowtops:
            own = [f for f in region if f.page == page and abs(f.top - top) <= 30]
            rnums = sorted([f for f in own if is_num(f)], key=lambda f: f.cx)
            name_frs = [f for f in region if f.page == page and abs(f.top - top) <= 70 and f.cx < hp_x - 40
                        and not is_num(f) and nearest_row(f) == (page, top)]
            name_parts = [f.text for f in sorted(name_frs, key=lambda f: (f.top, f.left))]
            ab: list[list[str]] = [[] for _ in abil_x] or [[]]
            for f in sorted(own, key=lambda f: (f.top, f.left)):
                if is_num(f) or f.cx < hp_x - 40:
                    continue
                k = min(range(len(abil_x)), key=lambda j: abs(abil_x[j] - f.cx)) if abil_x else 0
                ab[k].append(f.text)
            row = {"name": join_cell(name_parts), "stats": [int(f.text) for f in rnums[:6]],
                   "ability": join_cell(ab[0]) if ab[0] else "", "hidden": join_cell(ab[1]) if len(ab) > 1 and ab[1] else ""}
            row["name"] = re.sub(r"\s+", " ", row["name"]).strip()
            rows.append(row)
            self.used_names.add(row["name"])
        return {"t": "stats", "rows": rows}

    # -- tablas de dos columnas (MTs, megapiedras) --------------------------
    def is_two_col_header(self, ln: Line) -> bool:
        t = ln.text.replace(" ", "")
        return t in ("MTSUBICACIÓN", "MEGAPIEDRAUBICACIÓN") and len(ln.frags) >= 2

    def parse_two_col(self) -> dict:
        hdr = self.peek()
        frs = split_frags([f for f in hdr.frags if f.text.strip()])
        head = [f.text.strip().title() for f in frs]
        split_x = (frs[0].right + frs[1].left) / 2
        self.i += 1
        rows: list[list[list[str]]] = []
        last: Line | None = None
        while self.peek() is not None:
            ln = self.peek()
            if self.heading_level(ln) or BULLET_RE.match(ln.text) or self.is_two_col_header(ln):
                break
            if ln.text.lower().startswith(("nota", "si deseas", "¡aviso")):
                break
            sf = split_frags([f for f in ln.frags if f.text.strip()])
            c1 = [f.text for f in sf if f.cx < split_x]
            c2 = [f.text for f in sf if f.cx >= split_x]
            new_row = last is None or self.gap(last, ln) > 30 or (c1 and rows and rows[-1][0])
            if new_row:
                rows.append([[], []])
            rows[-1][0].extend(c1)
            rows[-1][1].extend(c2)
            last = ln
            self.i += 1
        out = [[join_cell(r[0]), join_cell(r[1])] for r in rows if r[0] or r[1]]
        # celdas de ubicación partidas en líneas: ya unidas por join_cell con espacio si son cortas;
        # para frases largas separa por espacio siempre
        out = [[re.sub(r"\s+", " ", a), " ".join(r[1]).strip() if len(" ".join(r[1])) > 24 else b] for (a, b), r in zip(out, [r for r in rows if r[0] or r[1]])]
        return {"t": "table", "head": head, "rows": out, "kind": "mt" if head[0].lower().startswith("mt") else "mega"}

    # -- Pokédex (tres columnas) --------------------------------------------
    def is_dex_header(self, ln: Line) -> bool:
        t = fold(ln.text)
        return t.startswith("numero") and "obtencion" in t

    def parse_dex(self) -> dict:
        hdr = self.peek()
        frs = split_frags([f for f in hdr.frags if f.text.strip()])
        x1 = (frs[0].right + frs[1].left) / 2 if len(frs) >= 2 else 170
        x2 = (frs[1].right + frs[2].left) / 2 if len(frs) >= 3 else 300
        self.i += 1
        groups: list[list[Line]] = []
        last: Line | None = None
        while self.peek() is not None:
            ln = self.peek()
            if self.heading_level(ln) or self.is_dex_header(ln) or BULLET_RE.match(ln.text):
                break
            if last is None or self.gap(last, ln) > 27:
                groups.append([])
            groups[-1].append(ln)
            last = ln
            self.i += 1
        rows: list[dict] = []
        for g in groups:
            frs = [f for ln in g for f in split_frags([f for f in ln.frags if f.text.strip()])]
            numlines = [ln for ln in g if any(re.fullmatch(r"\d{3,4}", f.text.strip()) and f.cx < x1 for f in split_frags(ln.frags))]
            if not numlines:
                if rows:
                    self.dex_append(rows[-1], frs, x1, x2)
                continue
            for ln in g:
                nl = min(numlines, key=lambda n: abs(n.top - ln.top))
                if ln is nl:
                    rows.append({"num": "", "name": "", "how": ""})
                    self.dex_append(rows[-1], split_frags([f for f in ln.frags if f.text.strip()]), x1, x2)
                else:
                    # pertenece a la fila del número más cercano; si esa fila aún no existe, va a la siguiente
                    target = None
                    k = numlines.index(nl)
                    rows_for = len(rows) - len(numlines) + k  # índice de fila ya creada
                    if ln.top < nl.top and k == 0 and len(rows) == 0:
                        pass
                    if ln.top < nl.top:
                        # línea por encima de su número: la fila se crea al llegar al número; guarda temporalmente
                        rows.append({"num": "", "name": "", "how": "", "_pre": True})
                        self.dex_append(rows[-1], split_frags([f for f in ln.frags if f.text.strip()]), x1, x2)
                    else:
                        target = rows[-1]
                        self.dex_append(target, split_frags([f for f in ln.frags if f.text.strip()]), x1, x2)
            # fusiona filas "_pre" con la siguiente fila con número
            merged: list[dict] = []
            for r in rows:
                if merged and merged[-1].get("_pre") and not merged[-1]["num"]:
                    pre = merged.pop()
                    r["name"] = (pre["name"] + " " + r["name"]).strip()
                    r["how"] = (pre["how"] + " " + r["how"]).strip()
                merged.append(r)
            rows = merged
        for r in rows:
            r.pop("_pre", None)
            r["name"] = re.sub(r"\s+", " ", r["name"]).strip()
            r["how"] = re.sub(r"\s+", " ", r["how"]).strip()
            self.used_names.add(r["name"])
        return {"t": "dex", "rows": [r for r in rows if r["num"] or r["name"]]}

    def parse_dex_loose(self) -> dict:
        """Filas de Pokédex sin cabecera de tabla: "NNN  Nombre  método", con líneas de continuación."""
        rows: list[dict] = []
        last: Line | None = None
        while self.peek() is not None:
            ln = self.peek()
            if self.heading_level(ln) or BULLET_RE.match(ln.text) or self.is_dex_header(ln):
                break
            m = re.match(r"^(\d{3,4})\s{2,}(\S.*?)\s{2,}(\S.*)$", ln.text) or re.match(r"^(\d{3,4})\s{2,}(\S+)\s+(.*)$", ln.text)
            if m:
                rows.append({"num": m.group(1), "name": m.group(2).strip(), "how": m.group(3).strip()})
            elif rows and last is not None and self.gap(last, ln) <= 40:
                rows[-1]["how"] = (rows[-1]["how"] + " " + ln.text).strip()
            else:
                break
            last = ln
            self.i += 1
        for r in rows:
            self.used_names.add(r["name"])
        return {"t": "dex", "rows": rows}

    @staticmethod
    def dex_append(row: dict, frs: list[Frag], x1: float, x2: float) -> None:
        for f in frs:
            t = f.text.strip()
            if f.cx < x1 and re.fullmatch(r"\d{3,4}", t):
                row["num"] = t
            elif f.cx < x2 and f.cx >= x1 - 15:
                row["name"] += " " + t
            elif f.cx < x1:
                row["name"] += " " + t
            else:
                row["how"] += " " + t

    # -- listas ---------------------------------------------------------------
    def parse_list(self) -> dict:
        items: list[dict] = []
        last: Line | None = None
        while self.peek() is not None:
            ln = self.peek()
            txt = ln.text
            if BULLET_RE.match(txt):
                h = BULLET_RE.sub("", ln.html(), count=1)
                h = re.sub(r"^(<strong>)?[●○■▪•]\s*", r"\1", h)
                items.append({"html": h.strip()})
                last = ln
                self.i += 1
                continue
            # continuación: sangría y poca separación
            if last is not None and items and not self.heading_level(ln) and ln.size <= 18 \
                    and (self.gap(last, ln) <= 27 or (ln.page == last.page + 1 and ln.top < 200 and txt[:1].islower())) \
                    and (ln.left >= 140 or txt[:1].islower()) and not self.is_boss_header(ln) and not self.is_stats_header(ln):
                items[-1]["html"] += " " + ln.html()
                last = ln
                self.i += 1
                continue
            break
        for it in items:
            self.annotate_item(it)
        kind = "wild" if sum(1 for it in items if it.get("pct")) >= max(1, len(items) // 2) else "plain"
        return {"t": "ul", "items": items, "kind": kind}

    def annotate_item(self, it: dict) -> None:
        plain = re.sub(r"<[^>]+>", "", it["html"])
        plain = html.unescape(plain).strip()
        m = re.match(r"^(\d+(?:[,.]\d+)?)\s*%\s*([A-ZÁÉÍÓÚÑ][\w'’.\-]*(?:\s+(?:Z|Regional|Hisui|Galar|Alola|Paldea|Hembra|Macho|de\s+\w+|[A-Z][\w'’.\-]*))?)",
                     plain)
        if not m:
            m = re.match(r"^([A-ZÁÉÍÓÚÑ][\w'’.\-]*(?:\s+(?:Z|Regional|Hisui|Galar|Alola|Paldea|[A-Z][\w'’.\-]*))?)\s*(?:\([^)]*\))?\s*(\d+(?:[,.]\d+)?)\s*%", plain)
            if m:
                name, pct = m.group(1), m.group(2)
            else:
                name, pct = None, None
        else:
            pct, name = m.group(1), m.group(2)
        if name:
            name = re.sub(r"\s+(de|del)$", "", name.strip(" .,:"))
            cands = [name]
            if "." in name:
                cands.append(name.split(".")[0].strip())
            if " " in name:
                cands.append(name.split(" ")[0].strip(" .,:"))
            for cand in cands:
                r = self.resolve(cand)
                if r["id"] is not None or (r["badge"] and r.get("exact")):
                    it["pct"] = pct + "%"
                    it["mon"] = cand
                    self.used_names.add(cand)
                    return
        # "Nombre: ..." (legendarios, entrenadores, nidos)
        m = re.match(r"^([A-ZÁÉÍÓÚÑ][\w'’.\-]*(?:\s+[A-Za-zÁÉÍÓÚÑáéíóúñ][\w'’.\-]*){0,2})\s*(?:\([^)]*\))?\s*[:,]", plain)
        if m:
            cand = m.group(1).strip()
            cand = re.sub(r"\s+(Regional|regional)$", " Z", cand)
            r = self.resolve(cand)
            if r["id"] is not None and r.get("exact"):
                it["mon"] = cand
                self.used_names.add(cand)

    # -- párrafos -------------------------------------------------------------
    def parse_paragraph(self) -> dict | None:
        ln = self.peek()
        parts = [ln.html()]
        centered = [ln.centered]
        last = ln
        self.i += 1
        while self.peek() is not None:
            nx = self.peek()
            if self.heading_level(nx) or BULLET_RE.match(nx.text) or self.is_boss_header(nx) or self.is_stats_header(nx) \
                    or self.is_two_col_header(nx) or self.is_dex_header(nx) or nx.size > 18:
                break
            g = self.gap(last, nx)
            cont_page = nx.page == last.page + 1 and nx.top < 200 and not re.search(r"[.:!?”\"]\s*$", last.text) and nx.left < 140
            if g > 27 and not cont_page:
                break
            if nx.text[:1].isupper() and last.text.rstrip().endswith((".", ":", "!", "?")) and nx.left < 125 and last.centered != nx.centered:
                break
            parts.append(nx.html())
            centered.append(nx.centered)
            last = nx
            self.i += 1
        text = " ".join(parts)
        plain = html.unescape(re.sub(r"<[^>]+>", "", text)).strip()
        if re.fullmatch(r"[-+•·_=\s]+", plain):
            return None
        kind = None
        low = fold(plain)
        for pat, k in CALLOUTS:
            if re.match(pat, low):
                kind = k
                break
        return {"t": "p", "html": text, "kind": kind, "center": sum(centered) > len(centered) / 2}

    # -- bucle principal -------------------------------------------------------
    def run(self) -> list[dict]:
        pending_heading: dict | None = None
        while self.peek() is not None:
            ln = self.peek()
            txt = ln.text
            if ln.page <= 2:
                self.i += 1
                continue
            if self.is_boss_header(ln):
                mon = self.parse_boss()
                if self.blocks and self.blocks[-1]["t"] == "boss":
                    self.blocks[-1]["mons"].append(mon)
                else:
                    self.blocks.append({"t": "boss", "mons": [mon]})
                continue
            if self.is_stats_header(ln):
                self.blocks.append(self.parse_stats())
                continue
            if self.is_two_col_header(ln):
                self.blocks.append(self.parse_two_col())
                continue
            if self.is_dex_header(ln):
                self.blocks.append(self.parse_dex())
                continue
            if re.match(r"^\d{3,4}\s{2,}\S", ln.text) and self.blocks and self.blocks[-1]["t"] in ("h", "dex") and ln.page >= 509:
                self.blocks.append(self.parse_dex_loose())
                continue
            # cabecera de stats partida: "ATK. DEF. HABILIDAD HABILIDAD" precede a "Pokémon HP ..."
            if txt.startswith("ATK.") and self.peek(1) is not None and self.is_stats_header(self.peek(1)):
                self.i += 1
                continue
            if txt.replace(" ", "") in ("MOVIMIENTOS",) or re.fullmatch(r"[A-ZÁÉÍÓÚÑ.+\- /]{2,}", txt) and ln.size <= 18 and len(txt) < 14 and ln.left > 200 and self.blocks and self.blocks[-1]["t"] == "boss":
                # restos de tabla (celdas sueltas): los ignora
                self.i += 1
                continue
            lvl = self.heading_level(ln)
            if lvl:
                parts = [txt]
                last = ln
                self.i += 1
                while self.peek() is not None and self.heading_level(self.peek()) == lvl and self.gap(last, self.peek()) <= 40 \
                        and not re.search(r"[?!.]$", last.text) and self.peek().size == ln.size:
                    parts.append(self.peek().text)
                    last = self.peek()
                    self.i += 1
                text = re.sub(r"\s+", " ", " ".join(parts)).strip()
                if re.fullmatch(r"[-+•·_=\s]+", text):
                    continue
                if lvl != 3 or not text.startswith(("¿", "¡")):
                    text = nice_heading(text)
                self.blocks.append({"t": "h", "level": lvl, "text": text, "page": ln.page})
                continue
            if BULLET_RE.match(txt):
                self.blocks.append(self.parse_list())
                continue
            # etiqueta corta (nombre de entrenador, "Objetos obtenibles en X:")
            nxt = self.peek(1)
            short = len(txt) <= 60 and ln.size <= 18 and not txt[:1].islower()
            follows_struct = nxt is not None and (BULLET_RE.match(nxt.text) or self.is_boss_header(nxt) or self.is_stats_header(nxt))
            follows_struct_soon = follows_struct or (self.peek(2) is not None and (self.is_boss_header(self.peek(2)) or BULLET_RE.match(self.peek(2).text)) and nxt is not None and len(nxt.text) < 80 and self.gap(ln, nxt) > 27)
            if short and (ln.bold or follows_struct or (follows_struct_soon and not re.search(r"[.!?]\s*$", txt) or txt.endswith(":"))) \
                    and not re.match(r"^(nota|importante|pista|dato|consejos|misi[oó]n|¡aviso)", fold(txt)) \
                    and (nxt is None or self.gap(ln, nxt) > 0):
                self.blocks.append({"t": "h", "level": 4, "text": nice_heading(txt), "page": ln.page})
                self.i += 1
                continue
            p = self.parse_paragraph()
            if p:
                self.blocks.append(p)
        return self.blocks


# ---------------------------------------------------------------------------
# 5. Sprites de PokeAPI
# ---------------------------------------------------------------------------
NAME_FIX = {
    "farfetch'd": "farfetchd", "farfetch’d": "farfetchd", "sirfetch'd": "sirfetchd", "mr. mime": "mr-mime", "mr mime": "mr-mime",
    "mime jr.": "mime-jr", "mr. rime": "mr-rime", "ho-oh": "ho-oh", "porygon-z": "porygon-z", "porygon2": "porygon2",
    "nidoran (hembra)": "nidoran-f", "nidoran (macho)": "nidoran-m", "nidoran♀": "nidoran-f", "nidoran♂": "nidoran-m",
    "nidoran hembra": "nidoran-f", "nidoran macho": "nidoran-m", "flabébé": "flabebe", "type: null": "type-null",
    "jangmo-o": "jangmo-o", "hakamo-o": "hakamo-o", "kommo-o": "kommo-o", "tapu koko": "tapu-koko", "tapu lele": "tapu-lele",
    "tapu bulu": "tapu-bulu", "tapu fini": "tapu-fini", "wo-chien": "wo-chien", "chien-pao": "chien-pao", "ting-lu": "ting-lu",
    "chi-yu": "chi-yu", "giratina": "giratina-altered", "shaymin": "shaymin-land", "deoxys": "deoxys-normal",
    "meloetta": "meloetta-aria", "keldeo": "keldeo-ordinary", "darmanitan": "darmanitan-standard", "tornadus": "tornadus-incarnate",
    "thundurus": "thundurus-incarnate", "landorus": "landorus-incarnate", "enamorus": "enamorus-incarnate",
    "aegislash": "aegislash-shield", "pumpkaboo": "pumpkaboo-average", "gourgeist": "gourgeist-average", "zygarde": "zygarde-50",
    "minior": "minior-red-meteor", "mimikyu": "mimikyu-disguised", "wishiwashi": "wishiwashi-solo", "toxtricity": "toxtricity-amped",
    "eiscue": "eiscue-ice", "indeedee": "indeedee-male", "morpeko": "morpeko-full-belly", "urshifu": "urshifu-single-strike",
    "meowstic": "meowstic-male", "maushold": "maushold-family-of-four", "squawkabilly": "squawkabilly-green-plume",
    "palafin": "palafin-zero", "tatsugiri": "tatsugiri-curly", "dudunsparce": "dudunsparce-two-segment", "basculegion": "basculegion-male",
    "basculin": "basculin-red-striped", "oricorio": "oricorio-baile", "lycanroc": "lycanroc-midday", "wormadam": "wormadam-plant",
    "oinkologne": "oinkologne-male", "lugia oscuro": "lugia", "lugia sombrío": "lugia", "shiny lugia": "lugia",
    "rotom guillotina": "rotom", "rotom lavadora": "rotom-wash", "rotom calor": "rotom-heat", "rotom frío": "rotom-frost",
    "rotom ventilador": "rotom-fan", "rotom corte": "rotom-mow", "kyurem blanco": "kyurem-white", "kyurem negro": "kyurem-black",
    "necrozma melena crepuscular": "necrozma-dusk", "necrozma alas del alba": "necrozma-dawn", "calyrex jinete glacial": "calyrex-ice",
    "calyrex jinete espectral": "calyrex-shadow", "zacian": "zacian", "zamazenta": "zamazenta", "eternatus": "eternatus",
    "ursaluna luna carmesí": "ursaluna-bloodmoon", "ogerpon": "ogerpon", "terapagos": "terapagos", "pecharunt": "pecharunt",
    "archaludon": "archaludon", "archadulon": "archaludon", "missigno": None, "missingno": None,
    "código cero": "type-null", "codigo cero": "type-null", "flamingo": "flamigo", "formantis": "fomantis", "mr.rime": "mr-rime",
    "overqwill": "overqwil", "passimiam": "passimian", "revaroom": "revavroom", "squawkabilly": "squawkabilly-green-plumage",
    "zamacenta": "zamazenta", "tododile": "totodile", "drillbur": "drilbur", "minum": "minun", "vibraba": "vibrava",
    "porygon -z": "porygon-z", "porygon -z z": "porygon-z", "zigzagoon de galar": "zigzagoon-galar", "linoone de galar": "linoone-galar",
    "lugia oscuro": "lugia",
}
FAKEMON = {"missingno", "missigno", "cherrilier", "serdupla", "zanghoul", "royaleon", "fobeto", "luvourne", "marolier", "sudrasil", "auretosk",
           "cefireon", "freyjynx", "constellar", "gourmaus", "halcombate", "maidible", "zippectre", "soundow", "aure"}
FORM_WORDS = [
    (r"\s+hisui(ano|ana)?$", "-hisui", "Hisui"), (r"\s+galar(iano|iana)?$", "-galar", "Galar"), (r"\s+alola(no|na)?$", "-alola", "Alola"),
    (r"\s+paldea(no|na)?$", "-paldea", "Paldea"), (r"\s+therian$", "-therian", "Therian"), (r"\s+origen$", "-origin", "Origen"),
    (r"\s+origin$", "-origin", "Origen"), (r"\s+(z|\(z\))$", "", "Z"), (r"\s+regional(\s*\([^)]*\))?$", "", "Z"),
    (r"\s+de\s+hisui$", "-hisui", "Hisui"), (r"\s+de\s+galar$", "-galar", "Galar"), (r"\s+de\s+alola$", "-alola", "Alola"),
    (r"\s+de\s+paldea$", "-paldea", "Paldea"),
]


def make_resolver(pokeapi_file: Path):
    data = json.loads(pokeapi_file.read_text())
    slug2id = {r["name"]: int(r["url"].rstrip("/").split("/")[-1]) for r in data["results"]}

    def slugify(s: str) -> str:
        s = fold(s).replace("’", "").replace("'", "").replace(".", "").replace("♀", "-f").replace("♂", "-m")
        return re.sub(r"[^a-z0-9\-]+", "-", s.replace(" ", "-")).strip("-")

    def lookup(sl: str):
        if sl in slug2id:
            return slug2id[sl]
        return None

    cache: dict[str, dict] = {}

    def resolve(name: str) -> dict:
        key = re.sub(r"\s+", " ", name.strip())
        if key in cache:
            return cache[key]
        low = fold(key)
        low = re.sub(r"\s*\((z)\)", " z", low)
        badge = ""
        mega = False
        if low.startswith("mega ") or low.startswith("mega-"):
            mega = True
            low = low[5:].strip()
        for pat, sfx, b in FORM_WORDS:
            if re.search(pat, low):
                low = re.sub(pat, "", low).strip()
                badge = b
                if sfx:
                    low_sfx = low + sfx
                    if lookup(slugify(low_sfx)) is not None:
                        low = low_sfx
                        badge = b
                break
        res = {"id": None, "badge": "", "exact": False}
        if low in FAKEMON or NAME_FIX.get(low, "x") is None:
            res = {"id": None, "badge": ("Mega" if mega else badge) or "Nuevo", "exact": True}
        else:
            fixed = NAME_FIX.get(low, low)
            sl = slugify(fixed)
            cands = [sl]
            if mega:
                cands = [sl + "-mega", sl + "-mega-x"] + cands
                m = re.match(r"^(.*)\s+([xy])$", low)
                if m:
                    cands = [slugify(NAME_FIX.get(m.group(1), m.group(1))) + "-mega-" + m.group(2)] + cands
            for c in cands:
                pid = lookup(c)
                if pid is not None:
                    b = badge
                    if mega:
                        b = "Mega" if (c.endswith("-mega") or "-mega-" in c) and not badge else ("Mega " + badge).strip() if badge else "Mega"
                        if (c.endswith("-mega") or "-mega-" in c) and badge == "":
                            b = ""
                    res = {"id": pid, "badge": b, "exact": c == sl or c.startswith(sl + "-")}
                    break
            if res["id"] is None:
                # Pokémon con forma por defecto en PokeAPI (p. ej. "tornadus-incarnate")
                for suffix in ("-incarnate", "-standard", "-male", "-average", "-altered", "-land", "-normal", "-disguised", "-single-strike"):
                    pid = lookup(sl + suffix)
                    if pid is not None:
                        res = {"id": pid, "badge": "Mega" if mega else badge, "exact": True}
                        break
        if mega and res["id"] is not None and not res["badge"]:
            res["badge"] = "Mega"
        cache[key] = res
        return res

    return resolve


# ---------------------------------------------------------------------------
# 6. Capítulos
# ---------------------------------------------------------------------------
def split_chapters(blocks: list[dict]) -> list[dict]:
    anchors = []
    for page, start, cid, group, title in CHAPTERS:
        idx = None
        for k, b in enumerate(blocks):
            if b["t"] == "h" and b.get("page") == page and fold(b["text"]).startswith(fold(start)):
                idx = k
                break
        if idx is None:
            for k, b in enumerate(blocks):
                if b["t"] in ("h", "p") and b.get("page", 0) == page and fold(html.unescape(re.sub("<[^>]+>", "", b.get("text") or b.get("html", "")))).startswith(fold(start)):
                    idx = k
                    break
        if idx is None:
            warn(f"[capítulo] ancla no encontrada: p{page} '{start}'")
            continue
        anchors.append((idx, cid, group, title))
    anchors.sort()
    chapters = []
    for n, (idx, cid, group, title) in enumerate(anchors):
        end = anchors[n + 1][0] if n + 1 < len(anchors) else len(blocks)
        chunk = blocks[idx:end]
        # si el ancla es un párrafo (no encabezado), conviértelo en encabezado
        if chunk and chunk[0]["t"] == "p":
            chunk[0] = {"t": "h", "level": 1, "text": html.unescape(re.sub("<[^>]+>", "", chunk[0]["html"])), "page": chunk[0].get("page", 0)}
        # ids de sección únicos dentro del capítulo
        seen: dict[str, int] = {}
        sections = []
        for b in chunk:
            if b["t"] == "h" and b["level"] <= 3:
                base = slug(b["text"])
                seen[base] = seen.get(base, 0) + 1
                b["id"] = base if seen[base] == 1 else f"{base}-{seen[base]}"
                if b["level"] <= 2:
                    sections.append({"id": b["id"], "title": b["text"], "level": b["level"]})
        first_page = next((b.get("page") for b in chunk if b.get("page")), None)
        chapters.append({"id": cid, "group": group, "title": title, "page": first_page, "sections": sections, "blocks": chunk})
    return chapters


def strip_pages(blocks: list[dict]) -> None:
    for b in blocks:
        b.pop("page", None)


# ---------------------------------------------------------------------------
def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    pdf = Path(sys.argv[1]).expanduser()
    if not pdf.is_file():
        print(f"No existe {pdf}")
        return 2
    sprite_names = json.loads(SPRITES_FILE.read_text()) if SPRITES_FILE.exists() else {}
    icon_types = json.loads(ICONS_FILE.read_text()) if ICONS_FILE.exists() else {}
    resolve = make_resolver(POKEAPI_FILE)

    cache_dir = os.environ.get("POKEMON_Z_CACHE")  # opcional: reutiliza el XML y los hashes entre ejecuciones
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(cache_dir) if cache_dir else Path(tmp)
        work.mkdir(parents=True, exist_ok=True)
        xml_path = work / "guia.xml"
        if not xml_path.exists():
            xml_path = run_pdftohtml(pdf, work)
        hashes_file = work / "hashes.json"
        hashes = json.loads(hashes_file.read_text()) if hashes_file.exists() else {}
        frags, imgs = parse_xml(xml_path)
        for im in imgs:
            if (im.width, im.height) == (27, 32) or (im.left <= 270 and 60 <= im.width <= 180):
                key = Path(im.src).name
                if key not in hashes:
                    try:
                        hashes[key] = image_hash(im.src)
                    except subprocess.CalledProcessError:
                        hashes[key] = None
                im.hash = hashes[key]
        if cache_dir:
            hashes_file.write_text(json.dumps(hashes))
    lines = build_lines(frags)
    parser = Parser(lines, imgs, sprite_names, icon_types, resolve)
    blocks = parser.run()
    chapters = split_chapters(blocks)
    for ch in chapters:
        strip_pages(ch["blocks"])

    # sprites de todos los nombres usados
    sprites: dict[str, dict] = {}
    for n in sorted(parser.used_names):
        if not n or n == "?":
            continue
        r = resolve(n)
        sprites[n] = {"id": r["id"], "badge": r["badge"]}
        if r["id"] is None and fold(n) not in FAKEMON and not fold(n).startswith("mega "):
            warn(f"[sprite] sin sprite: {n}")

    nav = [{"id": c["id"], "group": c["group"], "title": c["title"], "sections": c["sections"]} for c in chapters]
    data = {
        "meta": {"title": "Pokémon Z", "subtitle": "Guía oficial · Eric_Lostie", "pages": max(l.page for l in lines), "generated": True},
        "nav": nav,
        "chapters": {c["id"]: {k: v for k, v in c.items() if k != "sections"} for c in chapters},
        "sprites": sprites,
        "types": TYPE_ORDER,
    }
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text("window.GUIDE_Z = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")

    n_boss = sum(len(b["mons"]) for c in chapters for b in c["blocks"] if b["t"] == "boss")
    n_blocks = sum(len(c["blocks"]) for c in chapters)
    print(f"OK {OUT_FILE.relative_to(ROOT)}: {len(chapters)} capítulos, {n_blocks} bloques, {n_boss} Pokémon de jefe, "
          f"{sum(1 for v in sprites.values() if v['id'])}/{len(sprites)} sprites, {OUT_FILE.stat().st_size // 1024} KB")
    if WARNINGS:
        seen = set()
        for w in WARNINGS:
            if w not in seen:
                seen.add(w)
                print("WARN", w)
        print(f"{len(seen)} avisos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
