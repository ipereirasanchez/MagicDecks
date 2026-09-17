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
  _cache/sets/<codi>.json  llista completa d'una edició (per a les guies dels esdeveniments)
events/<carpeta>/      ENTRADA: un esdeveniment per carpeta (vegeu «Esdeveniments»)
tools/build_site.py    el build (Python 3.13, només stdlib)
tests/                 proves unitàries (unittest)
docs/                  SORTIDA: el lloc web (HTML, CSS, JS i JSON generats)
  js/views/life.js     comptador de vides (no depèn del build)
  data/index.json      índex de baralles (generat)
  data/decks/*.json    una baralla per fitxer (generat)
  data/events/*.json   índex i una pàgina per esdeveniment (generat)
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

## Esdeveniments

A `#/esdeveniments` hi ha la llista d'esdeveniments (drafts, tornejos, quedades). Cada
esdeveniment és una carpeta a `events/`:

```
events/draft-hobbits-2026-09-26/
  event.json     metadades: títol, data, horari (null = per confirmar), lloc (nom + enllaç),
                 edició (codi Scryfall), carta per a la il·lustració, vídeo, idiomes
  event.ca.md    la pàgina de l'esdeveniment (obligatòria per a cada idioma)
  set.ca.md      la guia de l'edició (opcional), enllaçada com a segona pàgina
  event.it.md    …el mateix en cada idioma de "languages"
  set.it.md
```

A diferència de la resta del web, les pàgines d'un esdeveniment s'escriuen en els idiomes
que indiqui `languages` i el visitant pot canviar entre ells amb un botó (l'elecció es recorda
al navegador). Els noms de les cartes sempre en anglès: el build els detecta i els enllaça a la
carta, igual que a les guies. Per poder-ho fer, cal la llista de l'edició a
`decks/_cache/sets/<codi>.json`, un document `{"set", "name", "cards": [...]}` desat de
`https://api.scryfall.com/cards/search?q=set:<codi>&unique=cards` (totes les pàgines). Les cartes
que no siguin de l'edició es poden afegir a `extra_cards` de `event.json` si són a `cards.json`.

Els fitxers `.md` segueixen el mateix format que les guies: `# Títol (Subtítol)`, seccions `##`
i `###`, i galeries entre `<!-- cards:start -->` i `<!-- cards:end -->` amb un `<img alt="Nom">`
per carta (dins d'una secció; les galeries de la introducció no es mostren).

## Comptador de vides

A `#/vides` hi ha un comptador per jugar a taula, pensat per deixar el mòbil al mig:
cada jugador té el seu panell girat cap a ell (2-6 jugadors; amb 5 i 6 els seients
laterals giren 90°). Es toca la meitat esquerra per restar i la dreta per sumar, i
mantenint premut va de pressa.

- Vides inicials per format (Commander 40, Standard 20, Dos caps 30, Brawl 25) o a mida.
- Cada jugador pot triar una de les baralles del web: el comandant li fa d'avatar i el
  color del seient surt de la identitat de color. Sense baralla, se li assigna un color.
- Comptadors de verí (a 10, fora), experiència, energia i impost del comandant.
- Dany de comandant per cada comandant rival per separat (a 21 d'un de sol, fora), i
  sumar-lo ja resta les vides. Qui juga amb partners ho marca a la configuració.
- Monarca, dau per decidir qui comença, desfés i la pantalla es manté encesa.

La partida es desa al navegador (`localStorage`), així que aguanta una recàrrega.
Tot és local: el comptador no necessita connexió un cop carregada la pàgina.

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
