"""Weerblok: Open-Meteo, geen API-sleutel nodig. Meerdere plaatsen naast elkaar."""
import json
from datetime import date, datetime, timedelta

import requests

from . import config

CACHE = config.DATA_DIR / "weer.json"
GEO = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST = "https://api.open-meteo.com/v1/forecast"

# WMO-weercodes naar gewoon Nederlands
CODES = {
    0: "zonnig", 1: "licht bewolkt", 2: "half bewolkt", 3: "bewolkt",
    45: "mist", 48: "mist met rijp",
    51: "motregen", 53: "motregen", 55: "motregen",
    56: "motregen met vorst", 57: "motregen met vorst",
    61: "regen", 63: "regen", 65: "zware regen",
    66: "regen met vorst", 67: "regen met vorst",
    71: "sneeuw", 73: "sneeuw", 75: "zware sneeuw", 77: "sneeuwkorrels",
    80: "buien", 81: "buien", 82: "zware buien",
    85: "sneeuwbuien", 86: "sneeuwbuien",
    95: "onweer", 96: "onweer met hagel", 99: "onweer met hagel",
}
DAG_KORT = ["ma", "di", "wo", "do", "vr", "za", "zo"]


def _cache_lezen():
    try:
        data = json.loads(CACHE.read_text())
    except (OSError, ValueError):
        return {"plaatsen": {}}
    if "plaatsen" not in data:          # oude cache met één plaats
        return {"plaatsen": {}}
    return data


def _gps(plaats, cache):
    """Coördinaten bij de plaatsnaam, één keer opzoeken en bewaren."""
    bekend = cache.get("plaatsen", {}).get(plaats) or {}
    if bekend.get("lat"):
        return bekend["lat"], bekend["lon"]
    try:
        antwoord = requests.get(GEO, params={"name": plaats, "count": 1, "language": "nl",
                                             "format": "json"}, timeout=15).json()
        hit = (antwoord.get("results") or [None])[0]
        if not hit:
            return None, None
        return hit["latitude"], hit["longitude"]
    except (requests.RequestException, ValueError, KeyError):
        return None, None


def _plaats_weer(plaats, cache, dagen):
    lat, lon = _gps(plaats, cache)
    if lat is None:
        return None
    try:
        antwoord = requests.get(FORECAST, params={
            "latitude": lat, "longitude": lon,
            "current": "temperature_2m,weather_code,wind_speed_10m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                     "precipitation_probability_max,wind_speed_10m_max,sunrise,sunset",
            "timezone": config.TIMEZONE, "forecast_days": dagen,
        }, timeout=20).json()
        daily, nu = antwoord["daily"], antwoord["current"]
    except (requests.RequestException, ValueError, KeyError):
        return None

    dagen_lijst = []
    for i, dag in enumerate(daily["time"]):
        d = date.fromisoformat(dag)
        dagen_lijst.append({
            "dag": "vandaag" if i == 0 else ("morgen" if i == 1 else DAG_KORT[d.weekday()]),
            "datum": f"{d.day}/{d.month}",
            "max": round(daily["temperature_2m_max"][i]),
            "min": round(daily["temperature_2m_min"][i]),
            "tekst": CODES.get(daily["weather_code"][i], "wisselvallig"),
            "neerslag": daily["precipitation_probability_max"][i] or 0,
            "wind": round(daily["wind_speed_10m_max"][i] / 3.6),
            "zonsopkomst": daily["sunrise"][i][11:16],
            "zonsondergang": daily["sunset"][i][11:16],
        })

    return {
        "plaats": plaats,
        "lat": lat, "lon": lon,
        "nu": {"temperatuur": round(nu["temperature_2m"]),
               "tekst": CODES.get(nu["weather_code"], "wisselvallig"),
               "wind": round(nu["wind_speed_10m"] / 3.6)},
        "dagen": dagen_lijst,
    }


def haal_alles(plaatsen=None, dagen=None):
    """Weer voor alle plaatsen uit de configuratie (of de meegegeven lijst)."""
    plaatsen = plaatsen or config.WEER_PLAATSEN
    dagen = dagen or config.WEER_DAGEN
    cache = _cache_lezen()
    blokken, vers = [], False
    for plaats in plaatsen:
        blok = _plaats_weer(plaats, cache, dagen)
        if blok:
            vers = True
            cache.setdefault("plaatsen", {})[plaats] = blok
            blokken.append(blok)
        else:
            oud = (cache.get("plaatsen") or {}).get(plaats)
            if oud:
                blokken.append(oud)
    if not blokken:
        return None
    cache["opgehaald"] = datetime.now().isoformat(timespec="minutes")
    try:
        CACHE.write_text(json.dumps(cache, ensure_ascii=False))
    except OSError:
        pass
    return {"plaatsen": blokken, "opgehaald": cache["opgehaald"], "vers": vers}


def laatste_weer():
    """Terugvaloptie: het laatst bewaarde weer van vandaag of gisteren."""
    cache = _cache_lezen()
    try:
        opgehaald = datetime.fromisoformat(cache["opgehaald"])
    except (KeyError, ValueError, TypeError):
        return None
    if opgehaald.date() < date.today() - timedelta(days=1):
        return None
    blokken = [cache["plaatsen"][p] for p in config.WEER_PLAATSEN
               if p in cache.get("plaatsen", {})]
    if not blokken:
        return None
    return {"plaatsen": blokken, "opgehaald": cache["opgehaald"], "vers": False}


def haal_weer(plaats, dagen=None):
    """Eén plaats, los te gebruiken (bijv. in een test of script)."""
    return _plaats_weer(plaats, _cache_lezen(), dagen or config.WEER_DAGEN)