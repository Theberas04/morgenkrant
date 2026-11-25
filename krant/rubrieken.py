"""Losse rubrieken voor de achterpagina: treinverkeer, op deze dag, gedicht,
prent, tech-tip, games en film. Elke rubriek faalt zacht: lukt het ophalen niet,
dan verdwijnt hij uit de krant in plaats van de build te breken."""
import json
import re
from datetime import date
from pathlib import Path

import feedparser
import lxml.html
import requests
import time

from . import config

CACHE_DIR = config.DATA_DIR / "rubrieken"

# Tech-tips: geen bron nodig, rouleren op dagnummer.
TECH_TIPS = [
    "Maak van een oude telefoon een bewakingscamera met de app Haven of Alfred.",
    "Wachtwoorden onthoud je niet, die bewaar je: Bitwarden en KeePass zijn gratis.",
    "Tweestapsverificatie met een app is veiliger dan een sms'je, en werkt ook zonder bereik.",
    "Ruim je downloads op met een vaste map per maand; zoeken wordt dan zoeken in één map.",
    "Een lange PDF lees je prettiger in donkere modus; de meeste lezers hebben die knop.",
    "Back-ups: drie kopieën, op twee verschillende media, waarvan één buiten huis.",
    "Zet je router eens uit en aan als wifi traag is; dat lost meer op dan je denkt.",
    "Met `ipconfig /flushdns` (Windows) of `sudo resolvectl flush-caches` (Linux) ruim je een oude DNS-cache op.",
    "Een wachtwoordzin van vier willekeurige woorden is sterker dan acht tekens met een uitroepteken.",
    "Foto's van je scherm maak je op de pc met Windows+Shift+S.",
    "Verlopen certificaten zijn de meest voorkomende storing; zet een herinnering 30 dagen voor de vervaldatum.",
    "Gebruik in plaats van één groot bestand liever versies met een datum in de naam; dan kun je terug.",
    "Een verlengsnoer met schakelaar bespaart sluipverbruik van je beeldscherm en opladers.",
    "Voor je een abonnement opzegt: check of je gegevens kunt exporteren, anders ben je ze kwijt.",
    "Zet automatische updates aan voor je browser; de meeste aanvallen mikken op verouderde versies.",
    "Met een eSIM houd je je eigen nummer en heb je in het buitenland meteen data.",
    "Een tweede scherm hoeft geen geld te kosten: een oude tablet met de app Spacedesk werkt ook.",
    "Noem bestanden met een datum vooraan (2026-11-25-notulen.pdf); dan staan ze automatisch op volgorde.",
]

WIKI_UA = ("DeMorgenkrant/1.0 (zelf-gehoste dagelijkse krant; "
           "https://github.com/Theberas04/morgenkrant)")


def _get_json(url, params, pogingen=3, wacht=8):
    """GET met een nette user-agent en een herhaalpoging bij 429 of een storing."""
    for poging in range(pogingen):
        try:
            antwoord = requests.get(url, params=params, timeout=30,
                                    headers={"User-Agent": WIKI_UA})
            if antwoord.status_code == 429 or antwoord.status_code >= 500:
                raise requests.RequestException(f"HTTP {antwoord.status_code}")
            antwoord.raise_for_status()
            return antwoord.json()
        except (requests.RequestException, ValueError):
            if poging == pogingen - 1:
                raise
            time.sleep(wacht * (poging + 1))
    return None


_WIKI_LINK = re.compile(r"\[\[([^\]|]*\|)?([^\]]*)\]\]")
_WIKI_TEMPLATE = re.compile(r"\{\{[^{}]*\}\}")


def _wiki_platte_tekst(tekst):
    tekst = _WIKI_LINK.sub(lambda m: m.group(2), tekst)
    tekst = _WIKI_TEMPLATE.sub("", tekst)
    tekst = re.sub(r"<ref[^>]*?/>|<ref[^>]*?>.*?</ref>|<[^>]+>", "", tekst, flags=re.S)
    tekst = tekst.replace("'''", "").replace("''", "")
    return " ".join(tekst.split())


def _bewaar(naam, data):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / f"{naam}.json").write_text(json.dumps(data, ensure_ascii=False))


# ---------------------------------------------------------------- treinverkeer
def treinverkeer(dag=None):
    feed = feedparser.parse("https://www.rijdendetreinen.nl/rss",
                            agent=config.USER_AGENT)
    items = []
    for entry in feed.entries:
        titel = re.sub(r"<[^>]+>", "", entry.get("title", "")).strip()
        tekst = re.sub(r"<[^>]+>", " ", entry.get("summary") or entry.get("content", [{}])[0].get("value", ""))
        tekst = " ".join(tekst.split())
        if tekst.lower().startswith(titel.lower()[:40]):
            tekst = tekst[len(titel):].lstrip(" .:-")
        if not titel:
            continue
        items.append({"tekst": titel, "meta": tekst[:110]})
        if len(items) >= 4:
            break
    return {"id": "trein", "titel": "Treinverkeer", "bron": "Rijden de Treinen",
            "link": "https://www.rijdendetreinen.nl/storingen", "items": items}


# ---------------------------------------------------------------- op deze dag
def op_deze_dag(dag=None):
    dag = dag or date.today()
    pagina = f"{dag.day}_{config.MAANDEN[dag.month - 1]}"
    try:
        data = _get_json("https://nl.wikipedia.org/w/api.php", {
            "action": "parse", "page": pagina, "prop": "wikitext",
            "format": "json", "formatversion": 2,
        })
        wikitext = data["parse"]["wikitext"]
    except (requests.RequestException, KeyError, ValueError):
        return None

    blok = wikitext.split("Gebeurtenissen", 1)[-1]
    items = []
    for regel in blok.splitlines():
        m = re.match(r"\*\*\s*\[\[(\d{3,4})\]\]\s*-\s*(.+)$", regel.strip())
        if not m:
            continue
        jaar, tekst = m.group(1), _wiki_platte_tekst(m.group(2))
        if len(tekst) < 25:
            continue
        items.append({"tekst": tekst, "meta": jaar})
        if len(items) >= 8:
            break
    # spreid over de eeuwen: niet acht keer de twintigste
    gekozen, gezien = [], set()
    for item in items:
        decennium = item["meta"][:2]
        if decennium in gezien:
            continue
        gezien.add(decennium)
        gekozen.append(item)
        if len(gekozen) == 5:
            break
    return {"id": "vandaag", "titel": "Op deze dag", "bron": "Wikipedia",
            "link": f"https://nl.wikipedia.org/wiki/{pagina}", "items": gekozen}


# ---------------------------------------------------------------- gedicht
def _gedicht_uit(titel):
    """Eén wikisource-pagina omzetten naar versregels; None als het geen gedicht is."""
    try:
        data = _get_json("https://nl.wikisource.org/w/api.php", {
            "action": "parse", "page": titel, "prop": "text",
            "format": "json", "formatversion": 2,
        })
        root = lxml.html.fromstring(data["parse"]["text"])
    except (requests.RequestException, KeyError, ValueError):
        return None
    regels = [el.text_content().replace("\u2003", " ").strip()
              for el in root.iter() if "ws-poem-line" in (el.get("class") or "")]
    regels = [regel for regel in regels if regel][:22]
    return regels if len(regels) >= 6 else None


def gedicht(dag=None):
    """Een Nederlands gedicht uit het publieke domein, per dag een andere."""
    dag = dag or date.today()
    try:
        lijst = _get_json("https://nl.wikisource.org/w/api.php", {
            "action": "query", "list": "allpages", "apprefix": "Gezelle/",
            "aplimit": 80, "format": "json", "formatversion": 2,
        })
        paginas = [p["title"] for p in lijst["query"]["allpages"]
                   if not p["title"].endswith("/")]
    except (requests.RequestException, KeyError, ValueError):
        return None
    if not paginas:
        return None

    start = dag.timetuple().tm_yday % len(paginas)
    for verschuiving in range(min(6, len(paginas))):
        titel = paginas[(start + verschuiving) % len(paginas)]
        regels = _gedicht_uit(titel)
        if regels:
            naam = titel.split("/", 1)[-1].replace("_", " ")
            return {"id": "gedicht", "titel": "Gedicht", "bron": f"Guido Gezelle · {naam}",
                    "link": f"https://nl.wikisource.org/wiki/{titel.replace(' ', '_')}",
                    "items": [], "regels": regels}
    return None


# ---------------------------------------------------------------- prent
def prent(dag=None):
    dag = dag or date.today()
    url = f"https://commons.wikimedia.org/api/rest_v1/feed/featured/{dag.year}/{dag.month:02d}/{dag.day:02d}"
    try:
        data = _get_json(url, {})
        beeld = data.get("image") or {}
        bestand = (beeld.get("title") or "").replace("File:", "")
        beschrijving = ((beeld.get("description") or {}).get("text") or "")
    except (requests.RequestException, ValueError):
        return None
    if not bestand:
        return None

    try:
        info = _get_json("https://commons.wikimedia.org/w/api.php", {
            "action": "query", "titles": f"File:{bestand}", "prop": "imageinfo",
            "iiprop": "url|extmetadata", "iiurlwidth": 1400,
            "format": "json", "formatversion": 2,
        })
        pagina = info["query"]["pages"][0]
        thumb = pagina["imageinfo"][0]["thumburl"]
        licentie = (pagina["imageinfo"][0]["extmetadata"].get("LicenseShortName", {})
                    or {}).get("value", "")
    except (requests.RequestException, KeyError, ValueError, IndexError):
        return None

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    pad = CACHE_DIR / f"prent-{dag.isoformat()}.jpg"
    if not pad.exists():
        try:
            plaatje = requests.get(thumb, timeout=40,
                                   headers={"User-Agent": config.USER_AGENT})
            plaatje.raise_for_status()
            pad.write_bytes(plaatje.content)
        except requests.RequestException:
            return None

    zinnen = re.split(r"(?<=[.!?])\s+", " ".join(beschrijving.split()))
    onderschrift = " ".join(zinnen[:2])[:260]
    return {"id": "prent", "titel": "Prent van de dag", "bron": "Wikimedia Commons",
            "link": f"https://commons.wikimedia.org/wiki/File:{bestand.replace(' ', '_')}",
            "items": [], "beeld": str(pad), "onderschrift": onderschrift,
            "credit": f"{bestand.replace('_', ' ')} · {licentie}".strip(" ·")}


# ---------------------------------------------------------------- feeds
def _feed_rubriek(naam, titel, url, aantal=4, bron=""):
    feed = feedparser.parse(url, agent=config.USER_AGENT)
    items = []
    for entry in feed.entries:
        kop = re.sub(r"<[^>]+>", "", entry.get("title", "")).strip()
        samenvatting = re.sub(r"<[^>]+>", " ", entry.get("summary", "") or "")
        samenvatting = " ".join(samenvatting.split())
        if not kop:
            continue
        items.append({"tekst": kop, "meta": samenvatting[:110]})
        if len(items) >= aantal:
            break
    if not items:
        return None
    return {"id": naam, "titel": titel, "bron": bron, "link": url, "items": items}


GAME_WOORDEN = re.compile(r"\b(game|games|gaming|nintendo|playstation|xbox|steam|"
                          r"epic games|spelcomputer|console|gta|minecraft|valve|sony|"
                          r"sega|ubisoft|ea sports|blizzard|esports?)\b", re.I)


def games(dag=None):
    """Games uit de Tweakers-feed: alleen items die echt over spellen gaan."""
    feed = feedparser.parse("https://tweakers.net/feeds/nieuws.xml", agent=config.USER_AGENT)
    items = []
    for entry in feed.entries:
        kop = re.sub(r"<[^>]+>", "", entry.get("title", "")).strip()
        samenvatting = " ".join(re.sub(r"<[^>]+>", " ", entry.get("summary", "") or "").split())
        if not kop or not GAME_WOORDEN.search(f"{kop} {samenvatting}"):
            continue
        items.append({"tekst": kop, "meta": samenvatting[:110]})
        if len(items) >= 3:
            break
    if not items:
        return None
    return {"id": "games", "titel": "Games", "bron": "Tweakers",
            "link": "https://tweakers.net/", "items": items}


def film(dag=None):
    return _feed_rubriek("film", "Film & serie", "https://www.filmkrant.nl/feed", 3, "Filmkrant")


# ---------------------------------------------------------------- economie
def economie(dag=None):
    return _feed_rubriek("economie", "Economie & werk", "https://www.nu.nl/rss/Economie",
                         3, "NU.nl")


# ---------------------------------------------------------------- luchtkwaliteit
AQI_LABELS = [(20, "goed"), (40, "redelijk"), (60, "matig"), (80, "slecht"),
              (100, "zeer slecht"), (10_000, "extreem slecht")]


def _aqi_label(aqi):
    for grens, label in AQI_LABELS:
        if aqi <= grens:
            return label
    return "onbekend"


def luchtkwaliteit(dag=None):
    """Europese luchtkwaliteitsindex (EAQI) per plaats, via Open-Meteo."""
    from . import weer

    cache = weer._cache_lezen()
    items = []
    for plaats in config.WEER_PLAATSEN:
        lat, lon = weer._gps(plaats, cache)
        if lat is None:
            continue
        try:
            data = requests.get("https://air-quality-api.open-meteo.com/v1/air-quality",
                                params={"latitude": lat, "longitude": lon,
                                        "current": "european_aqi,pm2_5,pm10",
                                        "timezone": config.TIMEZONE},
                                timeout=25, headers={"User-Agent": config.USER_AGENT}).json()
            nu = data["current"]
        except (requests.RequestException, KeyError, ValueError):
            continue
        aqi = nu.get("european_aqi")
        if aqi is None:
            continue
        items.append({"tekst": f"{plaats}: {_aqi_label(aqi)} (index {round(aqi)})",
                      "meta": f"fijnstof {nu.get('pm2_5', 0):.0f} µg/m³"})
    if not items:
        return None
    return {"id": "lucht", "titel": "Luchtkwaliteit", "bron": "Open-Meteo",
            "link": "https://open-meteo.com/en/docs/air-quality-api", "items": items}


# ---------------------------------------------------------------- zon en maan
MAANFASEN = ["nieuwe maan", "wassende maan", "eerste kwartier", "wassende maan",
             "volle maan", "afnemende maan", "laatste kwartier", "afnemende maan"]
SYNODISCH = 29.530588853
NIEUWE_MAAN = date(2000, 1, 6)


def maanstand(dag=None):
    """Maanfase en het deel van de maan dat verlicht is, zonder externe dienst."""
    import math

    dag = dag or date.today()
    ouderdom = ((dag - NIEUWE_MAAN).days % SYNODISCH)
    index = int((ouderdom / SYNODISCH) * 8 + 0.5) % 8
    verlicht = (1 - math.cos(2 * math.pi * ouderdom / SYNODISCH)) / 2
    return MAANFASEN[index], ouderdom, round(verlicht * 100)


def zonmaan(dag=None):
    dag = dag or date.today()
    from . import weer

    cache = weer._cache_lezen()
    plaats = config.WEER_PLAATSEN[0]
    lat, lon = weer._gps(plaats, cache)
    if lat is None:
        return None
    try:
        data = requests.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": lat, "longitude": lon, "daily": "sunrise,sunset",
            "timezone": config.TIMEZONE, "forecast_days": 1,
        }, timeout=25, headers={"User-Agent": config.USER_AGENT}).json()["daily"]
        opkomst = data["sunrise"][0][11:16]
        ondergang = data["sunset"][0][11:16]
    except (requests.RequestException, KeyError, ValueError, IndexError):
        return None

    fasenaam, _, verlicht = maanstand(dag)
    uur, minuut = int(ondergang[:2]), int(ondergang[3:])
    daglengte = (uur * 60 + minuut) - (int(opkomst[:2]) * 60 + int(opkomst[3:]))
    items = [
        {"tekst": f"Zon op {opkomst}, onder {ondergang}", "meta": f"{plaats}"},
        {"tekst": f"Daglengte {daglengte // 60} uur {daglengte % 60} minuten", "meta": ""},
        {"tekst": f"Maan: {fasenaam}, {verlicht}% verlicht", "meta": ""},
    ]
    return {"id": "zonmaan", "titel": "Zon en maan", "bron": "Open-Meteo",
            "link": "https://open-meteo.com/", "items": items}


# ---------------------------------------------------------------- citaat
_CITAAT_VELD = re.compile(r"\|\s*(vertaling|tekst|bron)\s*=\s*(.*?)(?=\n\s*\||\Z)", re.S)


def _sjabloon_velden(blok):
    return {m.group(1): m.group(2).strip() for m in _CITAAT_VELD.finditer(blok)}


def _citaten_uit(wikitext):
    """Alle {{citaat}}/{{vertaald citaat}}-blokken als (Nederlandse tekst, bron)."""
    citaten = []
    for m in re.finditer(r"\{\{(vertaald )?citaat", wikitext):
        start = m.start()
        diepte, i = 0, start
        while i < len(wikitext) - 1:
            paar = wikitext[i:i + 2]
            if paar == "{{":
                diepte += 1
                i += 2
                continue
            if paar == "}}":
                diepte -= 1
                i += 2
                if diepte == 0:
                    break
                continue
            i += 1
        velden = _sjabloon_velden(wikitext[start:i])
        tekst = velden.get("vertaling") or velden.get("tekst") or ""
        tekst = _wiki_platte_tekst(tekst).strip(' “”"')
        if 25 <= len(tekst) <= 260:
            bron = re.sub(r"\{\{[^{}]*\}\}", "", velden.get("bron", ""))
            bron = _wiki_platte_tekst(bron).strip(" ,")
            citaten.append((tekst, bron[:80]))
    return citaten


def citaat(dag=None):
    """Een Nederlands citaat van Wikiquote; de pagina wordt per dag gekozen."""
    dag = dag or date.today()
    titels = []
    try:
        willekeurig = _get_json("https://nl.wikiquote.org/w/api.php", {
            "action": "query", "list": "random", "rnnamespace": 0, "rnlimit": 6,
            "format": "json", "formatversion": 2,
        })
        titels = [p["title"] for p in willekeurig["query"]["random"]]
    except (requests.RequestException, KeyError, ValueError, TypeError):
        titels = []

    for titel in titels:
        try:
            data = _get_json("https://nl.wikiquote.org/w/api.php", {
                "action": "parse", "page": titel, "prop": "wikitext",
                "format": "json", "formatversion": 2,
            })
            citaten = _citaten_uit(data["parse"]["wikitext"])
        except (requests.RequestException, KeyError, ValueError, TypeError):
            continue
        if not citaten:
            continue
        tekst, bron = citaten[dag.timetuple().tm_yday % len(citaten)]
        return {"id": "citaat", "titel": "Citaat", "bron": titel,
                "link": f"https://nl.wikiquote.org/wiki/{titel.replace(' ', '_')}",
                "items": [{"tekst": tekst, "meta": bron}]}
    return None


# ---------------------------------------------------------------- tech-tip
def tech_tip(dag=None):
    dag = dag or date.today()
    tip = TECH_TIPS[dag.timetuple().tm_yday % len(TECH_TIPS)]
    return {"id": "tech", "titel": "Tech-tip", "bron": "De Morgenkrant",
            "link": "", "items": [], "tekst": tip}


RUBRIEKEN = (economie, treinverkeer, op_deze_dag, citaat, gedicht, prent,
             luchtkwaliteit, zonmaan, tech_tip, games, film)


def haal_alles(dag=None, vers=True):
    """Alle rubrieken voor één editie; resultaat wordt per dag bewaard."""
    dag = dag or date.today()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    bestand = CACHE_DIR / f"{dag.isoformat()}.json"
    if bestand.exists() and not vers:
        try:
            return json.loads(bestand.read_text())
        except ValueError:
            pass

    blokken = []
    for functie in RUBRIEKEN:
        try:
            blok = functie(dag)
        except Exception as fout:                      # één rubriek mag nooit de krant stoppen
            print(f"[rubriek] {functie.__name__} overgeslagen: {type(fout).__name__}")
            blok = None
        if blok and (blok.get("items") or blok.get("regels") or blok.get("tekst")
                     or blok.get("beeld")):
            blokken.append(blok)
    try:
        bestand.write_text(json.dumps(blokken, ensure_ascii=False))
    except OSError:
        pass
    print("[rubriek] " + ", ".join(b["id"] for b in blokken))
    return blokken