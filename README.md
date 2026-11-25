# De Morgenkrant

Elke ochtend om 05:30 een verse Nederlandstalige krant uit NOS, NU.nl, RTL Nieuws, de
Volkskrant, NRC, het AD, L1, Tweakers, Bright, Techzine en Computable — met een weerblok, als
webpagina en als PDF (A4 voor de laptop, telefoonformaat voor onderweg).

## Op een Proxmox-host

Eén regel, als root op de host:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/Theberas04/morgenkrant/main/deploy/proxmox/install.sh)"
```

Het script zoekt een Debian-template en een beschrijfbare opslag, maakt een container
(2 cores, 1 GB, 4 GB schijf, DHCP), installeert de app, zet twee systemd-diensten op en bouwt
meteen de eerste editie. Aan het eind print het het adres en de commando's.

Opties: `CTID=120`, `CORES=2`, `MEM=1024`, `SCHIJF=4`, `POORT=8420`, `STORAGE=local-lvm`,
`KIT_DIR=/opt/morgenkrant-kit`. Proefdraaien zonder iets aan te maken:
`FETCH_ONLY=1 bash -c "$(curl -fsSL .../install.sh)"`.

Controle later:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/Theberas04/morgenkrant/main/deploy/proxmox/check-morgenkrant.sh)"
```

## Zelf draaien (zonder container)

```bash
python3 -m venv .venv
env -u PYTHONPATH .venv/bin/pip install -r requirements.txt   # WeasyPrint heeft Pango + Cairo nodig
.venv/bin/python build.py            # feeds lezen + editie + PDF's
.venv/bin/python build.py --no-fetch # alleen opnieuw opmaken
.venv/bin/python reclean.py          # opgeslagen artikelen opschonen en taalfilteren
.venv/bin/python app.py              # webpagina op poort 8420
```

## Hoe het werkt

1. `krant/fetch.py` leest de feeds, haalt per bron maximaal 8 nieuwe artikelen volledig op met
   trafilatura en slaat ze op in `data/krant.db`.
2. `krant/clean.py` haalt ruis weg (cookie- en abonneeteksten, "Lees ook", de kop die het
   artikel zelf herhaalt) en `krant/taal.py` gooit weg wat niet Nederlands is.
3. `krant/weer.py` haalt het weer en de verwachting op bij Open-Meteo (geen sleutel nodig).
4. `krant/select.py` kiest de editie: versheid weegt het zwaarst, een maximum per bron, vaste
   aantallen per rubriek (Nieuws, Binnenland, Regio, Techniek) en zeven korte berichten voor
   "In het kort". Geen LLM nodig.
5. `krant/render.py` maakt uit één HTML-bron de webpagina en twee PDF's met WeasyPrint.
6. `app.py` serveert de pagina; `edities/` bewaart de PDF's per dag.

## Instellingen

Alles staat in `krant/config.py`: krantennaam, ondertitel, feeds met rubriek en maximum per bron,
titelfilters per bron, hoeveel artikelen per rubriek, hoe oud nieuws mag zijn, het aantal korte
berichten en de weerplaats (`WEER_PLAATS`).

## Schermafbeeldingen

`python scripts/shoot.py` start zelf een headless Chromium en legt de pagina vast op 1440 px
(laptop) en 390 px (telefoon).

## Licentie

Alle rechten voorbehouden. Gebruikte onderdelen van derden houden hun eigen licentie:
trafilatura, WeasyPrint, Flask, feedparser, Open-Meteo en de lettertypen PT Serif, PT Sans,
Playfair Display en Roboto Condensed (SIL Open Font License).