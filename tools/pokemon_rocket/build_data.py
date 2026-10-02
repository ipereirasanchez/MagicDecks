#!/usr/bin/env python3
"""Convierte los .txt / .pdf de "INFORMACIÓN ÚTIL" (Pokémon Team Rocket Edition) en
docs/pokemon/rocket/data/data.js, el fichero de datos de la guía Pokémon del sitio.

Uso:  python3 tools/pokemon_rocket/build_data.py "/ruta/a/INFORMACIÓN ÚTIL"

La carpeta fuente no forma parte del repositorio (viene con la descarga del hack). Imprime un
informe de validación (líneas no reconocidas, Pokémon sin sprite, etc.). Solo biblioteca
estándar más `pdftotext` (poppler-utils) para el PDF de misiones secundarias.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT_FILE = ROOT / "docs" / "pokemon" / "rocket" / "data" / "data.js"

WARNINGS: list[str] = []


def warn(msg: str) -> None:
    WARNINGS.append(msg)


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def find_dir(base: Path, *fragments: str) -> Path:
    """Localiza un subdirectorio ignorando acentos NFD/NFC y espacios iniciales."""
    want = [nfc(f).strip().upper() for f in fragments]
    for p in sorted(base.iterdir()):
        name = nfc(p.name).strip().upper()
        if all(w in name for w in want):
            return p
    raise FileNotFoundError(f"No encontrado {fragments} en {base}")


def find_file(base: Path, *fragments: str) -> Path:
    want = [nfc(f).strip().upper() for f in fragments]
    for p in sorted(base.rglob("*")):
        if p.is_file() and all(w in nfc(p.name).upper() for w in want):
            return p
    raise FileNotFoundError(f"No encontrado fichero {fragments} en {base}")


def read(p: Path) -> str:
    return nfc(p.read_text(encoding="utf-8", errors="replace")).replace("\r\n", "\n")


# ---------------------------------------------------------------------------
# Combates
# ---------------------------------------------------------------------------
RE_RULE = re.compile(r"^-{5,}\s*$")
RE_DIFF = re.compile(r"^\s*-{3,}\s*(F[ÁA]CIL|DIF[ÍI]CIL)\s*-{3,}\s*$", re.I)
RE_POKE = re.compile(r"^\s*-\s+(?P<name>[^(|]+?)\s*\(Nv\.?\s*(?P<lvl>\d+)\)\s*(?P<rest>.*)$")
RE_MOV = re.compile(r"^\s*Mov:\s*(.*)$", re.I)
RE_IV = re.compile(r"^\s*IVs?:\s*(?P<ivs>[^|]*?)\s*(\|\s*EVs?:\s*(?P<evs>.*))?$", re.I)
RE_VS = re.compile(r"^VS\s+(.*)$")


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip(" .")


def parse_pokemon_line(m: re.Match) -> dict:
    name = clean(m.group("name"))
    rest = m.group("rest").strip()
    item = nature = ability = None
    if rest.startswith("|"):
        parts = [clean(x) for x in rest.strip("|").split("|")]
        parts = [p for p in parts if p != ""]
        if len(parts) >= 1:
            item = parts[0]
        if len(parts) >= 2:
            nature = parts[1]
        if len(parts) >= 3:
            ability = "/".join(parts[2:])
    elif rest.startswith("-"):
        item = clean(rest.lstrip("- "))
    if item and item.lower() in ("no item", "sin objeto", "-"):
        item = None
    if nature and nature.lower().startswith("nat"):
        nature = None
    if nature == "-":
        nature = None
    return {
        "name": name,
        "level": int(m.group("lvl")),
        "item": item,
        "nature": nature,
        "ability": ability,
        "moves": [],
        "ivs": None,
        "evs": None,
    }


def parse_battle_file(text: str, label: str) -> list[dict]:
    """Devuelve lista de secciones: {title, trainers:[{name, notes, teams:{normal|facil|dificil:[pkm]}}]}"""
    lines = text.split("\n")
    sections: list[dict] = []
    section = None
    trainer = None
    diff = "normal"
    cur_pkm = None
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()
        nxt = lines[i + 1] if i + 1 < n else ""
        if not stripped or stripped == "]":
            i += 1
            continue
        # Encabezado de sección: línea seguida de una regla de guiones
        if RE_RULE.match(nxt) and not RE_POKE.match(line) and not RE_DIFF.match(line) and not RE_VS.match(stripped):
            section = {"title": clean(stripped), "trainers": []}
            sections.append(section)
            trainer = None
            diff = "normal"
            cur_pkm = None
            i += 2
            continue
        if RE_RULE.match(stripped):
            i += 1
            continue
        m = RE_DIFF.match(stripped)
        if m:
            d = m.group(1).upper()
            diff = "facil" if d.startswith("F") else "dificil"
            if trainer is None and section is not None:
                trainer = {"name": section["title"], "notes": [], "teams": {}}
                section["trainers"].append(trainer)
            cur_pkm = None
            i += 1
            continue
        m = RE_VS.match(stripped)
        if m:
            if section is None:
                section = {"title": "Sin sección", "trainers": []}
                sections.append(section)
            trainer = {"name": clean(m.group(1)), "notes": [], "teams": {}}
            section["trainers"].append(trainer)
            diff = "normal"
            cur_pkm = None
            i += 1
            continue
        if stripped.startswith("*"):
            if trainer is not None:
                trainer["notes"].append(clean(stripped.lstrip("* ")))
            else:
                warn(f"[{label}] nota sin entrenador: {stripped}")
            i += 1
            continue
        m = RE_POKE.match(line)
        if m:
            if trainer is None:
                if section is None:
                    section = {"title": "Sin sección", "trainers": []}
                    sections.append(section)
                trainer = {"name": section["title"], "notes": [], "teams": {}}
                section["trainers"].append(trainer)
            cur_pkm = parse_pokemon_line(m)
            trainer["teams"].setdefault(diff, []).append(cur_pkm)
            i += 1
            continue
        m = RE_MOV.match(line)
        if m and cur_pkm is not None:
            cur_pkm["moves"] = [clean(x).capitalize() for x in m.group(1).split(",") if clean(x)]
            i += 1
            continue
        m = RE_IV.match(line)
        if m and cur_pkm is not None:
            cur_pkm["ivs"] = clean(m.group("ivs")) or None
            cur_pkm["evs"] = clean(m.group("evs") or "") or None
            if cur_pkm["evs"] in ("-", ""):
                cur_pkm["evs"] = None
            i += 1
            continue
        # Línea sin "VS" que actúa como título de entrenador (p. ej. "BASE CAOBA - COMBATE TRIPLE (1er adversario)")
        core = re.sub(r"\([^)]*\)", "", stripped).strip()
        if section is not None and core and core == core.upper() and re.search(r"[A-ZÁÉÍÓÚÑ]", core):
            trainer = {"name": clean(stripped), "notes": [], "teams": {}}
            section["trainers"].append(trainer)
            diff = "normal"
            cur_pkm = None
            i += 1
            continue
        warn(f"[{label}] línea no reconocida: {stripped!r}")
        i += 1
    return sections


def merge_battles(normal: list[dict], fd: list[dict] | None, label: str) -> list[dict]:
    """Une el fichero normal con el de fácil/difícil emparejando (sección, entrenador, ocurrencia)."""
    if fd is None:
        return normal
    key_counts: dict[tuple, int] = {}
    fd_index: dict[tuple, dict] = {}
    for s in fd:
        for t in s["trainers"]:
            k0 = (s["title"].upper(), t["name"].upper())
            key_counts[k0] = key_counts.get(k0, 0) + 1
            fd_index[(k0, key_counts[k0])] = t
    used = set()
    counts: dict[tuple, int] = {}
    for s in normal:
        for t in s["trainers"]:
            k0 = (s["title"].upper(), t["name"].upper())
            counts[k0] = counts.get(k0, 0) + 1
            k = (k0, counts[k0])
            other = fd_index.get(k)
            if other is None:
                # Intento tolerante: mismo nombre de entrenador en cualquier sección
                cands = [kk for kk in fd_index if kk[0][1] == k0[1] and kk not in used]
                if not cands:
                    # Misma sección y primera palabra del nombre coincidente (p. ej. "ZEUS 4TA VEZ" ~ "ZEUS RUINAS ALFA")
                    first = k0[1].split()[0]
                    cands = [kk for kk in fd_index if kk[0][0] == k0[0] and kk not in used and kk[0][1].split()[0] == first]
                if not cands:
                    # Último recurso: único entrenador sin emparejar en la misma sección
                    cands = [kk for kk in fd_index if kk[0][0] == k0[0] and kk not in used]
                    if len(cands) != 1:
                        cands = []
                other = fd_index[cands[0]] if cands else None
                if other is not None:
                    k = cands[0]
            if other is None:
                warn(f"[{label}] sin versión fácil/difícil: {s['title']} / {t['name']}")
                continue
            used.add(k)
            for d in ("facil", "dificil"):
                if d in other["teams"]:
                    t["teams"][d] = other["teams"][d]
            if "normal" in other["teams"] and "normal" not in t["teams"]:
                t["teams"]["normal"] = other["teams"]["normal"]
            for note in other["notes"]:
                if note not in t["notes"]:
                    t["notes"].append(note)
    for k, t in fd_index.items():
        if k not in used:
            warn(f"[{label}] entrenador solo en fácil/difícil: {k[0][0]} / {k[0][1]}")
    return normal


SEASONS = [
    {"id": "t1", "num": 1, "name": "Kanto", "main": ("T1 - KANTO",), "mainfd": ("T1 - DIFICIL",), "side": ("KANTO.txt",), "sidefd": ("T1 - F",)},
    {"id": "t2", "num": 2, "name": "Archipiélago Sete", "short": "Archi7", "main": ("T2 - ARCHI7",), "mainfd": ("T2 - DIFICIL",), "side": ("ARCHI7.txt",), "sidefd": ("T2 - F",)},
    {"id": "t3", "num": 3, "name": "Johto", "main": ("T3 - JOHTO",), "mainfd": ("T3 - DIFICIL",), "side": ("JOHTO.txt",), "sidefd": ("T3 - F",)},
    {"id": "t4", "num": 4, "name": "DLC", "main": ("T4 - DLC",), "mainfd": ("T4 - DIF",), "side": ("DLC.txt",), "sidefd": ("T4 - F",)},
    {"id": "t5", "num": 5, "name": "Hoenn", "main": ("T5 - HOENN",), "mainfd": ("T5 - DIFICIL",), "side": ("HOENN.txt",), "sidefd": ("T5 - F",)},
]


def load_battles(src: Path) -> list[dict]:
    jefes = find_dir(src, "COMBATES DE JEFE")
    principales = find_dir(jefes, "PRINCIPALES")
    secundarias = find_dir(jefes, "SECUNDARIAS")
    out = []
    for s in SEASONS:
        season = {"id": s["id"], "num": s["num"], "name": s["name"], "short": s.get("short", s["name"]), "main": [], "side": []}
        # principales
        main_file = next(p for p in principales.iterdir() if p.is_file() and nfc(p.name).upper().startswith(s["main"][0]))
        fd_dir = next(p for p in principales.iterdir() if p.is_dir() and nfc(p.name).upper().startswith(s["mainfd"][0]))
        fd_file = next(p for p in fd_dir.iterdir() if p.suffix == ".txt")
        season["main"] = merge_battles(
            parse_battle_file(read(main_file), f"{s['id']} main"),
            parse_battle_file(read(fd_file), f"{s['id']} main F/D"),
            f"{s['id']} main",
        )
        side_file = next(p for p in secundarias.iterdir() if p.is_file() and nfc(p.name).upper() == s["side"][0].upper())
        sfd_dir = next(p for p in secundarias.iterdir() if p.is_dir() and nfc(p.name).upper().startswith(s["sidefd"][0]))
        sfd_file = next(p for p in sfd_dir.iterdir() if p.suffix == ".txt")
        season["side"] = merge_battles(
            parse_battle_file(read(side_file), f"{s['id']} side"),
            parse_battle_file(read(sfd_file), f"{s['id']} side F/D"),
            f"{s['id']} side",
        )
        out.append(season)
    return out


# ---------------------------------------------------------------------------
# Pokédex de obtención
# ---------------------------------------------------------------------------
RE_DEX = re.compile(r"^(?P<name>[A-ZÁÉÍÓÚÑ0-9_.' /&-]+?)\s*-?\s+(?P<num>\d{1,4})\s*(?:-\s*(?P<how>.*))?$")


def classify_method(how: str) -> list[str]:
    h = how.lower()
    tags = []
    if not h.strip():
        return ["no-disponible"]
    if re.search(r"salvaje|surf|pesca|caña|golpe roca|hierba|zona de hierba|\d+%", h):
        tags.append("salvaje")
    if re.search(r"evoluci|evoluciona|uso de piedra|usando (la )?piedra|usando .*sobre|subiendo (de|un) nivel|\bnv\.|por felicidad|preevoluci", h):
        tags.append("evolucion")
    if re.search(r"regalo|premio|huevo|te lo da", h):
        tags.append("regalo")
    if re.search(r"venta|se vende|a la venta|\d+\s*¥|fichas|casino", h):
        tags.append("compra")
    if re.search(r"misi[oó]n|secundaria|derrotar|tras completar|robado|combate singular|capturable|obtenible tras", h):
        tags.append("mision")
    if not tags:
        tags.append("otro")
    return tags


def parse_dex(text: str) -> list[dict]:
    entries = []
    pending_extra = None
    exclusive = False
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("---"):
            continue
        if "EXCLUSIVOS DEL JUEGO" in line.upper():
            exclusive = True
            continue
        m = RE_DEX.match(line)
        if m and (line[0].isupper()):
            name = clean(m.group("name"))
            how = clean(m.group("how") or "")
            e = {"name": name, "num": int(m.group("num")), "how": how, "exclusive": exclusive}
            e["tags"] = classify_method(how)
            entries.append(e)
            pending_extra = e
        else:
            # Línea de continuación (p. ej. "Evoluciona de Farfetch'D con Piedra Sagrada." o "FORMAS ATAQUE/DEFENSA...")
            if pending_extra is not None:
                pending_extra["how"] = clean(pending_extra["how"] + " " + line)
                pending_extra["tags"] = classify_method(pending_extra["how"])
            else:
                warn(f"[dex] línea suelta: {line!r}")
    return entries


# ---------------------------------------------------------------------------
# Evoluciones
# ---------------------------------------------------------------------------
def parse_evolutions(text: str) -> dict:
    out = {"note": "", "changed": [], "new": []}
    target = "changed"
    for raw in text.split("\n"):
        line = raw.strip()
        if not line or set(line) <= {"-"}:
            continue
        if line.upper().startswith("NOTA"):
            out["note"] = clean(line.split(":", 1)[1]) if ":" in line else line
            continue
        if "NUEVOS POKEMON" in line.upper():
            target = "new"
            continue
        m = re.match(r"^(.*?)\s+a\s+(.*?)\s+-\s+(.*)$", line)
        if not m:
            warn(f"[evo] línea no reconocida: {line!r}")
            continue
        frm, to, method = (clean(x) for x in m.groups())
        both = "(y viceversa)" in to
        to = clean(to.replace("(y viceversa)", ""))
        out[target].append({"from": frm, "to": to, "method": method, "both": both})
    return out


# ---------------------------------------------------------------------------
# Stats (Oficial vs Hackrom), nuevos Pokémon
# ---------------------------------------------------------------------------
RE_STATLINE = re.compile(
    r"^(?P<label>[^:]+?):?\s*Ps\s*(?P<hp>\d+),\s*At\s*(?P<atk>\d+),\s*Def\s*(?P<def>\d+),\s*At\.?esp\s*(?P<spa>\d+)[,.]\s*Def\.?esp\s*(?P<spd>\d+),\s*Veloci?d?\.?\s*(?P<spe>\d+)\.?\s*(?:Total:?\s*(?P<total>\d+))?",
    re.I,
)


def parse_statline(line: str) -> dict | None:
    m = RE_STATLINE.match(line.strip())
    if not m:
        return None
    stats = [int(m.group(k)) for k in ("hp", "atk", "def", "spa", "spd", "spe")]
    return {"label": clean(m.group("label")), "stats": stats, "total": sum(stats)}


def is_heading(line: str) -> bool:
    s = line.strip()
    if not s or s.endswith(":") and parse_statline(s) is None and len(s) < 40 and s[:-1].isupper():
        return bool(s)
    return s.isupper() and not any(c.isdigit() for c in s[:2]) and ":" not in s and len(s) < 60


def parse_stat_blocks(text: str, label: str) -> list[dict]:
    """Bloques: TÍTULO, líneas de stats (Oficial/Hackrom/Forma), 'Habilidades: ...', 'Tipo: ...'."""
    blocks: list[dict] = []
    cur = None
    for raw in text.split("\n"):
        line = raw.strip()
        if not line or set(line) <= {"-", " "} or line.startswith("+"):
            continue
        sl = parse_statline(line)
        if sl:
            if cur is None:
                warn(f"[{label}] stats sin título: {line!r}")
                continue
            cur["lines"].append(sl)
            continue
        low = line.lower()
        if low.startswith("tipo"):
            if cur is None:
                continue
            # "Tipo: X/Y | Habilidad: A/B"
            parts = [p.strip() for p in line.split("|")]
            for p in parts:
                if p.lower().startswith("tipo oficial"):
                    cur["type_official"] = clean(p.split(":", 1)[1])
                elif p.lower().startswith("tipo hackrom"):
                    cur["type"] = clean(p.split(":", 1)[1])
                elif p.lower().startswith("tipo"):
                    cur["type"] = clean(p.split(":", 1)[1])
                elif p.lower().startswith("habilidad"):
                    cur["abilities"] = [clean(a) for a in p.split(":", 1)[1].split("/") if clean(a)]
            continue
        if low.startswith("habilidad"):
            if cur is not None:
                cur["abilities"] = [clean(a) for a in line.split(":", 1)[1].split("/") if clean(a)]
            continue
        if low.startswith("notas") or low.startswith("- ") or low.startswith("nota"):
            if cur is not None and cur.get("_notes_target") is not None:
                cur["_notes_target"].append(clean(line.lstrip("- ")))
            continue
        # Título de bloque
        title = clean(line.rstrip(":"))
        cur = {"title": title, "lines": [], "type": None, "abilities": [], "_notes_target": None}
        blocks.append(cur)
    for b in blocks:
        b.pop("_notes_target", None)
    return blocks


def parse_new_pokemon_file(text: str, label: str) -> list[dict]:
    """Ficheros de nuevos Pokémon: pueden tener grupos (PROTOTIPOS DE NIVEL I ...) con notas."""
    groups: list[dict] = []
    cur_group = {"title": "", "notes": [], "blocks": []}
    groups.append(cur_group)
    cur = None
    for raw in text.split("\n"):
        line = raw.strip()
        if not line or set(line) <= {"-", " "}:
            continue
        sl = parse_statline(line)
        if sl:
            if cur is None:
                warn(f"[{label}] stats sin título: {line!r}")
                continue
            cur["lines"].append(sl)
            continue
        low = line.lower()
        if low.startswith("tipo"):
            if cur is None:
                continue
            for p in [p.strip() for p in line.split("|")]:
                if p.lower().startswith("tipo"):
                    cur["type"] = clean(p.split(":", 1)[1])
                elif p.lower().startswith("habilidad"):
                    cur["abilities"] = [clean(a) for a in p.split(":", 1)[1].split("/") if clean(a)]
            continue
        if low.startswith("habilidad"):
            if cur is not None:
                cur["abilities"] = [clean(a) for a in line.split(":", 1)[1].split("/") if clean(a)]
            continue
        if low.startswith("nota"):
            continue
        if low.startswith("- "):
            cur_group["notes"].append(clean(line[2:]))
            continue
        # ¿Encabezado de grupo?
        if re.match(r"^(PROTOTIPOS|FUERTES V[ÍI]NCULO DE|POKEMON ANTIGUOS|FORMAS PRIMIGENIAS)", line.upper()):
            if cur_group["blocks"] or cur_group["notes"] or cur_group["title"]:
                cur_group = {"title": "", "notes": [], "blocks": []}
                groups.append(cur_group)
            cur_group["title"] = clean(line)
            cur = None
            continue
        title = clean(line.rstrip(":"))
        cur = {"title": title, "lines": [], "type": None, "abilities": []}
        cur_group["blocks"].append(cur)
    return [g for g in groups if g["blocks"]]


# ---------------------------------------------------------------------------
# Movimientos
# ---------------------------------------------------------------------------
def parse_moves(text: str) -> list[dict]:
    moves = []
    cur = None
    side = None
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            continue
        if set(line) <= {"-"}:
            continue
        m = re.match(r"^(Oficial|Hackrom)\s*\((Tipo\s+)?(?P<type>[^)]+)\):?$", line, re.I)
        if m:
            side = "official" if m.group(1).lower() == "oficial" else "hack"
            if cur is not None:
                cur[side] = {"type": clean(m.group("type")).capitalize()}
            continue
        m = re.match(r"^(Potencia|Precisi[oó]n|Ef\.?\s*Secundario|PP)\s*-\s*(.*)$", line, re.I)
        if m and cur is not None and side is not None:
            key = m.group(1).lower()
            k = "power" if key.startswith("pot") else "acc" if key.startswith("pre") else "pp" if key == "pp" else "effect"
            cur[side][k] = clean(m.group(2))
            continue
        if line.isupper():
            cur = {"name": clean(line).title(), "official": {}, "hack": {}}
            moves.append(cur)
            side = None
            continue
        warn(f"[moves] línea no reconocida: {line!r}")
    return moves


# ---------------------------------------------------------------------------
# Objetos
# ---------------------------------------------------------------------------
def parse_item_sections(text: str, label: str) -> list[dict]:
    """Secciones encabezadas por TÍTULO + regla. Dentro: 'Nombre: descripción' con posibles líneas extra."""
    lines = text.split("\n")
    sections: list[dict] = []
    cur = None
    item = None
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        s = line.strip()
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if not s:
            i += 1
            continue
        if re.match(r"^-{5,}$", nxt) and not s.startswith("-"):
            cur = {"title": clean(s), "note": "", "items": []}
            sections.append(cur)
            item = None
            i += 2
            continue
        if re.match(r"^-{5,}$", s):
            i += 1
            continue
        if cur is None:
            cur = {"title": "", "note": "", "items": []}
            sections.append(cur)
        if s.lower().startswith("nota"):
            cur["note"] = clean(cur["note"] + " " + s.split(":", 1)[-1])
            i += 1
            continue
        m = re.match(r"^(?P<name>[^:]{2,45}):\s*(?P<desc>.*)$", s)
        if m and not s.startswith("-") and not s.startswith("("):
            item = {"name": clean(m.group("name")), "desc": clean(m.group("desc")), "extra": []}
            cur["items"].append(item)
            i += 1
            continue
        # Continuación
        if item is not None:
            txt = clean(s.lstrip("- "))
            mstage = re.match(r"^\((T\d:[^)]*)\)\s*(.*)$", s)
            if mstage:
                item.setdefault("stage", mstage.group(1))
                if mstage.group(2):
                    item["extra"].append(clean(mstage.group(2)))
            else:
                item["extra"].append(txt)
        else:
            cur["note"] = clean(cur["note"] + " " + s.lstrip("- "))
        i += 1
    # Extraer etapa "(T1: Kanto)" del final de la descripción
    for sec in sections:
        for it in sec["items"]:
            m = re.search(r"\((T\d:[^)]*)\)\s*$", it["desc"])
            if m:
                it["stage"] = m.group(1)
                it["desc"] = clean(it["desc"][: m.start()])
            # MTs: "MT01 - Puño certero"
            mm = re.match(r"^(MT\d+)\s*-\s*(.*)$", it["name"])
            if mm:
                it["code"] = mm.group(1)
                it["name"] = mm.group(2)
    return sections


# ---------------------------------------------------------------------------
# FAQ / QoL
# ---------------------------------------------------------------------------
def parse_faq(text: str) -> dict:
    intro = []
    qas = []
    cur = None
    for raw in text.split("\n"):
        s = raw.strip()
        if not s or set(s) <= {"-"}:
            continue
        if s.upper().startswith("PREGUNTAS FRECUENTES"):
            continue
        if s.startswith("+"):
            cur = {"q": clean(s.lstrip("+ ")), "a": []}
            qas.append(cur)
            continue
        if cur is None:
            intro.append(s)
            continue
        cur["a"].append(clean(s.lstrip("- ")) if s.startswith("- ") and not cur["a"] else s)
    return {"intro": intro, "items": qas}


def parse_qol(text: str) -> dict:
    notes = []
    sections = []
    cur = None
    for raw in text.split("\n"):
        s = raw.strip()
        if not s or set(s) <= {"-"}:
            continue
        if s.upper().startswith("QUALITIES OF LIFE"):
            continue
        if s.lower().startswith("nota"):
            notes.append(clean(s.split(":", 1)[-1]))
            continue
        if s.startswith("+"):
            cur = {"title": clean(s.lstrip("+ ")).rstrip(":"), "lines": []}
            sections.append(cur)
            continue
        if s.upper() == "OBJETOS Y MECÁNICAS ÚTILES":
            sections.append({"title": "Objetos y mecánicas útiles", "lines": [], "heading": True})
            cur = None
            continue
        if cur is None:
            continue
        cur["lines"].append(s)
    return {"notes": notes, "sections": sections}


# ---------------------------------------------------------------------------
# PDF de misiones secundarias
# ---------------------------------------------------------------------------
def parse_sidequests_pdf(pdf: Path) -> list[dict]:
    try:
        txt = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, check=True).stdout
    except Exception as e:  # noqa: BLE001
        warn(f"[pdf] no se pudo extraer: {e}")
        return []
    txt = nfc(txt).replace("\f", "\n")
    regions: list[dict] = []
    region = None
    quest = None
    mode = None
    lines = txt.split("\n")
    RE_KEY = re.compile(r"^(Recompensas?|Prerrequisitos?|Requisitos?|Video tutorial|Ubicaci[oó]n[^:]*|Subcategor[ií]a)\s*:\s*(.*)$", re.I)
    RE_TITLE = re.compile(r"^(?P<title>[A-ZÁÉÍÓÚÑ][^:]{3,70}):\s*(?P<desc>.*)$")

    def new_quest(title: str, desc: str, kind: str = "quest") -> dict:
        q = {"title": clean(title), "desc": clean(desc), "rewards": [], "prereq": "", "video": "", "bullets": [], "extra": [], "kind": kind}
        region["quests"].append(q)
        return q

    for i, raw in enumerate(lines):
        s_ = raw.strip()
        indented = raw.startswith("    ") or raw.startswith("\t")
        if not s_ or s_.startswith("MISIONES SECUNDARIAS") or s_.startswith("╔") or s_.startswith("╚") or set(s_) <= {"═"}:
            continue
        prev = lines[i - 1].strip() if i > 0 else ""
        if s_.isupper() and len(s_) < 30 and prev.startswith("╔"):
            region = {"name": s_.title().replace("Dlc", "DLC"), "quests": []}
            regions.append(region)
            quest = None
            mode = None
            continue
        if region is None:
            continue
        m = RE_KEY.match(s_)
        if m:
            key = m.group(1).lower()
            val = clean(m.group(2))
            if key.startswith("subcat"):
                quest = new_quest(val, "", kind="group")
                mode = "desc"
            elif quest is None:
                continue
            elif key.startswith("recomp"):
                mode = "rewards"
                if val:
                    quest["rewards"].append(val)
            elif key.startswith("prer") or key.startswith("requi"):
                mode = "prereq"
                quest["prereq"] = val
            elif key.startswith("video"):
                mode = None
                quest["video"] = val
            else:
                mode = None
            continue
        if s_.startswith("•"):
            if quest is not None:
                quest["bullets"].append(clean(s_.lstrip("• ")))
                mode = "bullets"
            continue
        if s_.startswith("-") and mode == "rewards" and quest is not None:
            quest["rewards"].append(clean(s_.lstrip("- ")))
            continue
        mt = RE_TITLE.match(s_)
        if mt and not indented and not s_.startswith("-"):
            quest = new_quest(mt.group("title"), mt.group("desc"))
            mode = "desc"
            continue
        if quest is None:
            continue
        if mode == "desc":
            quest["desc"] = clean(quest["desc"] + " " + s_)
        elif mode == "prereq":
            quest["prereq"] = clean(quest["prereq"] + " " + s_)
        elif mode == "rewards" and quest["rewards"] and indented:
            quest["rewards"][-1] = clean(quest["rewards"][-1] + " " + s_)
        elif mode == "bullets":
            if indented and quest["bullets"]:
                quest["bullets"][-1] = clean(quest["bullets"][-1] + " " + s_)
            else:
                quest["extra"].append(s_)
        else:
            quest["extra"].append(s_)
    return regions


# ---------------------------------------------------------------------------
# Sprites
# ---------------------------------------------------------------------------
# Nombres en español (o fan) -> slug PokeAPI base
NAME_FIX = {
    "mr.mime": "mr-mime", "mr mime": "mr-mime", "mr.rime": "mr-rime", "mr_rime": "mr-rime", "mr_mime": "mr-mime",
    "mime_jr": "mime-jr", "ho-oh": "ho-oh", "ho oh": "ho-oh", "porygon-z": "porygon-z", "porygonz": "porygon-z",
    "porygon_z": "porygon-z", "porygon2": "porygon2", "type_null": "type-null", "type full": "type-null",
    "nidoran_f": "nidoran-f", "nidoran_m": "nidoran-m", "farfetch'd": "farfetchd", "farfetchd": "farfetchd",
    "sirfetch'd": "sirfetchd", "sirfetchd": "sirfetchd", "jangmo_o": "jangmo-o", "hakamo_o": "hakamo-o", "kommo_o": "kommo-o",
    "kommo-o": "kommo-o", "tapu_koko": "tapu-koko", "tapu_lele": "tapu-lele", "tapu_bulu": "tapu-bulu", "tapu_fini": "tapu-fini",
    "tapu lele": "tapu-lele", "flabebe": "flabebe", "wo chien": "wo-chien", "chien pao": "chien-pao", "ting lu": "ting-lu", "chi yu": "chi-yu",
    "varppm": "varoom", "lycanrock": "lycanroc", "salamance": "salamence", "honchcrow": "honchkrow", "vikabolt": "vikavolt",
    "eeve": "eevee", "booho": "boohoo", "jigglupuff": "jigglypuff", "elective": "electivire", "infernare": "infernape",
    "missingno": None, "código 0": "type-null", "codigo 0": "type-null", "ultimate project": "mewtwo", "xd001": "lugia",
    "unown ?": "unown", "unown aúreo": "unown", "unown aureo": "unown", "rey unown": "unown",
    "esencia": None, "pokémon esencia": None, "dragón original": "kyurem", "dragon original": "kyurem",
    "dragón sagrado": "dunsparce", "dragon sagrado": "dunsparce", "dragón-o": "kyurem", "dragon-o": "kyurem",
    "en": "flareon", "rai": "jolteon", "sui": "vaporeon", "ghost": None, "ghost-p": None, "ghost primigenio": None,
    "trxatu": "xatu", "guardia": "marowak", "maroghost": "marowak", "ikary": None, "akueria": None, "akua": None, "kurusu": None,
    "madaamu": "sirfetchd", "boohoo": "noctowl", "gorochu": "raichu", "auredian": "ledian", "yanmteura": "yanmega",
    "bomushikaa": None, "blessparce": "dunsparce", "dun": "dunsparce", "wrongsparce": "dudunsparce", "purakkusu": "pinsir", "purakussu": "pinsir",
    "taaban": "slowbro", "wartillery": "octillery", "shibirefugu": "qwilfish", "shibirifegu": "qwilfish", "nidogod": "nidoking",
    "porygon3": "porygon2", "porygon 3.1": "porygon2", "porygon3.1": "porygon2",
    "colmilargo": "great-tusk", "colagrito": "scream-tail", "furioseta": "brute-bonnet", "melenaleteo": "flutter-mane",
    "reptalada": "slither-wing", "pelarena": "sandy-shocks", "ferrodada": "iron-treads", "ferrosaco": "iron-bundle",
    "ferropalmas": "iron-hands", "ferrocuello": "iron-jugulis", "ferropolilla": "iron-moth", "ferropúas": "iron-thorns", "ferropuas": "iron-thorns",
    "bramaluna": "roaring-moon", "ferropaladin": "iron-valiant", "ferropaladín": "iron-valiant", "ondulagua": "walking-wake",
    "ferroverdor": "iron-leaves", "flamariete": "gouging-fire", "electrofuria": "raging-bolt", "ferromole": "iron-boulder", "ferromoles": "iron-boulder",
    "ferrotesta": "iron-crown", "vigorish": "vigoroth",
    "ivisaur": "ivysaur", "bellosom": "bellossom", "sandshlash": "sandslash", "farfecth'd": "farfetchd",
    "chinchar": "chimchar", "deoxys-v": "deoxys-speed", "giratina origen": "giratina-origin",
    "lycanroc forma diurna": "lycanroc-midday", "lycanroc forma nocturna": "lycanroc-midnight",
    "lycanroc forma crepuscular": "lycanroc-dusk", "keldeo forma brío": "keldeo-resolute", "keldeo forma brio": "keldeo-resolute",
    "darmanitan-g": "darmanitan-galar-standard", "darmanitan galar": "darmanitan-galar-standard",
    "basculin-f": "basculin-white-striped", "basculin-m": "basculin-white-striped", "basculegion": "basculegion-male",
    "blessparce y dun": "dunsparce", "mega absol z": "absol-mega", "mega toxtricity": "toxtricity-amped",
    "toxtricity-m": "toxtricity-amped", "mega mewtwo-x": "mewtwo-mega-x", "mega mewtwo-y": "mewtwo-mega-y",
    "ursaluna luna carmesí": "ursaluna-bloodmoon", "wrongsparce": "dudunsparce-two-segment", "booho": "noctowl",
}

# Sufijos que PokeAPI usa para la forma por defecto de algunas especies
DEFAULT_FORM_SUFFIXES = [
    "-male", "-normal", "-altered", "-land", "-ordinary", "-aria", "-incarnate", "-standard", "-red-striped",
    "-plant", "-shield", "-average", "-midday", "-solo", "-red-meteor", "-disguised", "-amped", "-ice",
    "-full-belly", "-single-strike", "-50", "-baile", "-green-plumage", "-curly", "-family-of-four", "-two-segment",
]

# Sufijos de forma (español) -> sufijo slug PokeAPI y etiqueta de insignia
FORM_SUFFIX = [
    (r"\s+alola$|-alola$", "-alola", "Alola"),
    (r"\s+galar$|-galar$|-g$", "-galar", "Galar"),
    (r"\s+hisui$|-hisui$", "-hisui", "Hisui"),
    (r"\s+primigenio$|-p$", "-primal", "P"),
    (r"\s+armadura$|-arm$", "", "Arm"),
    (r"\s+esqueleto$|-sk$|-s$", "", "Sk"),
    (r"\s+starter$|\s+inicial$", "-starter", "★"),
    (r"-&$", "", "&"),
    (r"-x$|\s+x$", "", "X"),
    (r"-y$|\s+y$", "", "Y"),
    (r"-z$|\s+z$", "", "Z"),
    (r"-m$", "-mega", "Mega"),
    (r"^mega\s+", "", "Mega"),
    (r"-zen$", "-zen", "Zen"),
    (r"-g-zen$", "-galar-zen", "Zen"),
    (r"\s+therian$|-t$", "-therian", "T"),
    (r"-a$", "-attack", "A"),
    (r"-d$", "-defense", "D"),
    (r"-s$", "-speed", "S"),
    (r"-o$", "-origin", "O"),
    (r"-u$", "-unbound", "U"),
    (r"-r$", "-rapid-strike", "R"),
    (r"-crep$", "-dusk", "Crep"),
    (r"\s+blanco$", "-white", "B"),
    (r"\s+negro$", "-black", "N"),
    (r"\s+cielo$", "-sky", "Cielo"),
    (r"\s+espectral$", "-shadow", "Esp"),
    (r"\s+glaciar$", "-ice", "Gla"),
    (r"\s+lluva$|\s+lluvia$", "-rainy", "Lluvia"),
    (r"\s+sol$", "-sunny", "Sol"),
    (r"\s+horno$", "-heat", "Horno"),
    (r"\s+ventilador$", "-fan", "Vent"),
    (r"\s+carmes[íi]$", "-bloodmoon", "Carmesí"),
    (r"\s+h[ée]roe$|\s+hero$", "-hero", "Héroe"),
    (r"\s+zero$", "-zero", "Zero"),
    (r"\s+flor eterna$|-e$", "-eternal", "Eterna"),
    (r"-dusk$", "-dusk", "Dusk"),
    (r"\s+terastal$", "-terastal", "Tera"),
    (r"\s+stellar$", "-stellar", "Stellar"),
    (r"\s+normal$", "", ""),
    (r"-f$", "-female", "♀"),
    (r"-m$", "-male", "♂"),
]

TYPE_WORDS = {"acero": "steel", "eléctrico": "electric", "electrico": "electric", "lucha": "fighting", "psíquico": "psychic", "psiquico": "psychic"}


def build_sprite_map(pokeapi_file: Path, names: set[str]) -> dict:
    data = json.loads(pokeapi_file.read_text())
    slug2id = {r["name"]: int(r["url"].rstrip("/").split("/")[-1]) for r in data["results"]}
    out: dict[str, dict] = {}

    def slugify(s: str) -> str:
        return re.sub(r"[^a-z0-9\-]", "", s.lower().replace(" ", "-").replace("'", "").replace(".", "-").replace("_", "-"))

    def lookup(slug: str) -> int | None:
        if slug in slug2id:
            return slug2id[slug]
        for sfx in DEFAULT_FORM_SUFFIXES:
            if slug + sfx in slug2id:
                return slug2id[slug + sfx]
        return None

    def resolve(name: str) -> dict:
        raw = clean(name)
        low = raw.lower()
        badge = ""
        # "En (Flareon-&)": la forma base va entre paréntesis
        mp = re.match(r"^.*\((?P<inner>[^)]+)\)\s*$", low)
        if mp and not low.startswith("eevee"):
            r = resolve(mp.group("inner"))
            if r["id"] is not None:
                return r
        # Arceus/Silvally tipo
        m = re.match(r"^(arceus|silvally)\s+(\w+)$", low)
        if m:
            base = m.group(1)
            t = TYPE_WORDS.get(m.group(2))
            slug = f"{base}-{t}" if t else base
            if slug in slug2id:
                return {"id": slug2id[slug], "badge": m.group(2).capitalize()}
            return {"id": slug2id[base], "badge": m.group(2).capitalize()}
        if low in NAME_FIX:
            fx = NAME_FIX[low]
            if fx is None:
                return {"id": None, "badge": ""}
            if lookup(fx) is not None:
                return {"id": lookup(fx), "badge": ""}
        if low.startswith("ultra necrozma"):
            return {"id": slug2id["necrozma-ultra"], "badge": "Ultra"}
        if low.startswith("kyogre primigenio"):
            return {"id": slug2id["kyogre-primal"], "badge": "P"}
        slug = slugify(low)
        if lookup(slug) is not None:
            return {"id": lookup(slug), "badge": ""}
        # Sufijos de forma
        for pat, sfx, b in FORM_SUFFIX:
            if re.search(pat, low):
                base = clean(re.sub(pat, "", low))
                base_fixed = NAME_FIX.get(base, base)
                if base_fixed is None:
                    return {"id": None, "badge": b}
                bslug = slugify(base_fixed)
                # Alola/Galar/Hisui/Mega/Primal reales en PokeAPI
                cand = bslug + sfx
                if sfx and lookup(cand) is not None:
                    return {"id": lookup(cand), "badge": b}
                if lookup(bslug) is not None:
                    return {"id": lookup(bslug), "badge": b}
                # Mega con -X/-Y
                mm = re.match(r"^mega\s+(.*?)\s+([xy])$", low)
                if mm:
                    c = f"{mm.group(1)}-mega-{mm.group(2)}"
                    if c in slug2id:
                        return {"id": slug2id[c], "badge": "Mega"}
        # "Mega X" compuesto
        mm = re.match(r"^mega\s+(.*?)(?:\s+([xy]))?$", low)
        if mm:
            c = mm.group(1).replace(" ", "-") + "-mega" + (f"-{mm.group(2)}" if mm.group(2) else "")
            if c in slug2id:
                return {"id": slug2id[c], "badge": "Mega"}
            if mm.group(1).replace(" ", "-") in slug2id:
                return {"id": slug2id[mm.group(1).replace(" ", "-")], "badge": "Mega"}
        # Primer token
        first = slug.split("-")[0]
        if lookup(first) is not None:
            return {"id": lookup(first), "badge": badge}
        return {"id": None, "badge": ""}

    for n in sorted(names):
        out[n] = resolve(n)
        if out[n]["id"] is None:
            warn(f"[sprite] sin sprite: {n}")
    return out


# ---------------------------------------------------------------------------
def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    src = Path(sys.argv[1])
    if not src.exists():
        # tolerar nombres NFD/NFC distintos en disco
        src = find_dir(src.parent, "INFORMACI")
    print(f"Fuente: {src}")

    battles = load_battles(src)
    pk_dir = find_dir(src, "POK")
    dex = parse_dex(read(find_file(pk_dir, "OBTENCI")))
    evolutions = parse_evolutions(read(find_file(pk_dir, "EVOLUCI")))
    stat_changes = parse_stat_blocks(read(find_file(pk_dir, "CAMBIOS en STATS")), "stats")
    nuevos_dir = find_dir(pk_dir, "NUEVOS")
    new_pokemon = {
        "experimentos": parse_new_pokemon_file(read(find_file(nuevos_dir, "Experimentos")), "experimentos"),
        "vinculo": parse_new_pokemon_file(read(find_file(nuevos_dir, "Fuertes")), "vinculo"),
        "megas": parse_new_pokemon_file(read(find_file(nuevos_dir, "Megaevoluciones")), "megas"),
        "antiguos": parse_new_pokemon_file(read(find_file(nuevos_dir, "Primigenios")), "antiguos"),
    }
    moves = parse_moves(read(find_file(src, "CAMBIOS en MOVIMIENTOS")))
    obj_dir = find_dir(src, "OBJETOS")
    items_changes = parse_item_sections(read(find_file(obj_dir, "CAMBIOS en OBJETOS")), "items-cambios")
    items_where = parse_item_sections(read(find_file(obj_dir, "OBTENCI")), "items-obtencion")
    faq = parse_faq(read(find_file(src, "Preguntas Frecuentes")))
    qol = parse_qol(read(find_file(src, "QOLS")))
    sidequests = parse_sidequests_pdf(find_file(src, "SECUNDARIAS TRE"))

    # Sprites: todos los nombres que aparecen en combates, dex y bloques de stats
    names: set[str] = set()
    for s in battles:
        for kind in ("main", "side"):
            for sec in s[kind]:
                for t in sec["trainers"]:
                    for team in t["teams"].values():
                        for p in team:
                            names.add(p["name"])
    for e in dex:
        names.add(e["name"].title() if e["name"].isupper() else e["name"])
    for b in stat_changes:
        names.add(b["title"].title())
    for grp in new_pokemon.values():
        for g in grp:
            for b in g["blocks"]:
                names.add(b["title"].title())
                for ln in b["lines"]:
                    lab = ln["label"].replace(" Oficial", "").replace(" Hackrom", "").strip()
                    if lab.lower() not in ("oficial", "hackrom") and not re.search(r"\d", lab):
                        names.add(lab)
    for ev in evolutions["changed"] + evolutions["new"]:
        names.add(ev["from"])
        names.add(ev["to"])
    sprites = build_sprite_map(HERE / "pokeapi_pokemon.json", names)

    # Normalizar nombres de dex a Title Case para mostrar
    for e in dex:
        e["display"] = e["name"].title().replace("_F", " ♀").replace("_M", " ♂").replace("_", " ")
        e["sprite"] = sprites.get(e["name"].title(), {"id": None, "badge": ""})

    data = {
        "meta": {"title": "Pokémon Team Rocket Edition", "subtitle": "Guía TRE 2026 · Dragonsden", "generated": True},
        "seasons": battles,
        "dex": dex,
        "evolutions": evolutions,
        "statChanges": stat_changes,
        "newPokemon": new_pokemon,
        "moves": moves,
        "itemChanges": items_changes,
        "itemLocations": items_where,
        "faq": faq,
        "qol": qol,
        "sidequests": sidequests,
        "sprites": sprites,
    }

    out = OUT_FILE
    out.parent.mkdir(parents=True, exist_ok=True)
    js = "window.GUIDE_DATA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n"
    out.write_text(js, encoding="utf-8")

    # Informe
    n_tr = sum(len(sec["trainers"]) for s in battles for k in ("main", "side") for sec in s[k])
    n_pk = sum(len(team) for s in battles for k in ("main", "side") for sec in s[k] for t in sec["trainers"] for team in t["teams"].values())
    print(f"Temporadas: {len(battles)} | Entrenadores: {n_tr} | Pokémon en equipos: {n_pk}")
    print(f"Dex: {len(dex)} | Evoluciones: {len(evolutions['changed'])}+{len(evolutions['new'])} | Stats: {len(stat_changes)} | Movs: {len(moves)}")
    print(f"Objetos: {sum(len(s['items']) for s in items_where)} ubicaciones, {sum(len(s['items']) for s in items_changes)} cambios | FAQ: {len(faq['items'])} | QoL: {len(qol['sections'])} | Secundarias PDF: {sum(len(r['quests']) for r in sidequests)} en {len(sidequests)} regiones")
    print(f"Sprites: {sum(1 for v in sprites.values() if v['id'])}/{len(sprites)} resueltos")
    print(f"Salida: {out} ({out.stat().st_size // 1024} KB)")
    if WARNINGS:
        print(f"\nAvisos ({len(WARNINGS)}):")
        for w in WARNINGS:
            print("  -", w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
