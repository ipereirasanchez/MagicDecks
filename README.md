# Les nostres baralles de Commander

Lloc web estàtic (GitHub Pages, carpeta `docs/`) que mostra les nostres baralles de Commander:
la llista completa de cartes amb les il·lustracions de Scryfall, estadístiques explicades en
català i la guia de joc de cada baralla. Tot el text és en català; els noms de les cartes i els
tecnicismes del joc (ramp, board wipe, sac outlet…) es mantenen en anglès. A `decks/es/` hi ha
la versió original en castellà de les guies.

Les dades es generen amb un script de Python que només fa servir la biblioteca estàndard.
No cal Node ni cap dependència externa.

## Estructura

```
decks/                 ENTRADA
  Ivan/                una carpeta per propietari: un .dek per baralla (+ .md amb la guia)
  Miquel/              el nom de la carpeta és el propietari que es mostra al web
  roles/*.json         rol de cada carta, un fitxer per baralla
  roles.json           taxonomia de rols (identificadors en anglès, definicions en català)
  es/*.md              versió en castellà de les guies
  img/                 imatges locals de les guies (no es publiquen)
  _cache/cards.json    memòria cau de Scryfall (nom -> objecte de carta), es publica al repositori
  owners.json          propietari per defecte i excepcions
tools/build_site.py    el build (Python 3.13, només stdlib)
tests/                 proves unitàries (unittest)
docs/                  SORTIDA: el lloc web (HTML, CSS, JS i JSON generats)
  data/index.json      índex de baralles (generat)
  data/decks/*.json    una baralla per fitxer (generat)
```

Les carpetes `_cache`, `roles`, `es` i `img` són reservades: mai no es llegeixen com a
propietaris. Un `.dek` deixat solt a `decks/` continua funcionant i agafa el propietari
per defecte de `owners.json`.

Les imatges no es copien mai al lloc: totes les URL apunten al CDN de Scryfall.

## Afegir una baralla

1. Exporta la baralla des de deckstats en format `.dek` (XML) i desa-la a
   `decks/<Propietari>/`. El comandant ha de ser l'entrada amb `Sideboard="true"`;
   si són partners, marca les dues entrades i totes dues sortiran com a comandants.
2. (Opcional) Escriu la guia a `decks/<Propietari>/<mateix_nom>.md`. El format esperat:
   - `# Títol (Subtítol)` com a primera línia.
   - Una cita `> Bracket N. ...` just després.
   - Seccions `##` i `###`; llistes, taules, negreta i codi inline.
   - Els noms de cartes del text es detecten automàticament i s'enllacen a la carta.
   - Les galeries d'imatges entre `<!-- cards:start -->` i `<!-- cards:end -->`
     (generades per `decks/add_images.py`) es converteixen en galeries del web.
3. (Opcional) Classifica les cartes a `decks/roles/<mateix_nom>.json` amb els
   identificadors de `decks/roles.json`. Les cartes sense rol es marquen com a `land`
   o `utility` i el build avisa amb un `WARN`.
4. Assegura't que totes les cartes són a `decks/_cache/cards.json`. Si n'hi falta alguna,
   el build s'atura amb el missatge `card 'Nom' not found in cache`.
5. El propietari surt del nom de la carpeta. Per forçar-ne un altre (o per a un `.dek`
   solt a `decks/`), afegeix-lo a `decks/owners.json`, que té prioritat sobre la carpeta:

   ```json
   { "default": "Ivan", "decks": { "Nom_del_fitxer_sense_extensio": "Anna" } }
   ```

## Generar el lloc

```bash
python3 tools/build_site.py
```

Escriu `docs/data/index.json` i `docs/data/decks/<slug>.json` (un per baralla) i esborra els
fitxers de baralles que ja no existeixen. Mostra una línia `OK <slug> 100 cards` per baralla.

Per veure-ho en local:

```bash
python3 -m http.server -d docs 8000
# obre http://localhost:8000/
```

## Proves

```bash
python3 -m unittest discover -s tests -v
```

## Publicar a GitHub Pages

1. Fes commit de tot, inclosa la carpeta `docs/` generada i `decks/_cache/cards.json`
   (els PDF i les carpetes d'imatges locals queden fora pel `.gitignore`).
2. Al repositori de GitHub: **Settings › Pages › Build and deployment**:
   *Source* = «Deploy from a branch», *Branch* = `main`, carpeta = `/docs`.
3. Al cap d'un minut el lloc estarà a `https://<usuari>.github.io/<repositori>/`.
   Totes les rutes del web són relatives, així que funciona en qualsevol subcarpeta.

Cada vegada que canviïs una baralla o una guia, torna a executar el build i fes commit de `docs/`.
