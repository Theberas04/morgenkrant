"""Weerblok: Open-Meteo, geen API-sleutel nodig."""
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


def _plaats_gps(plaats):
    """Coördinaten bij de plaatsnaam, één keer opzoeken en bewaren."""
    try:
        data = json.loads(CACHE.read_text())
        if data.get("plaats") == plaats and data.get("lat"):
            return data["lat"], data["lon"]
    except (OSError, ValueError):
        data = {}
    try:
        antwoord = requests.get(GEO, params={"name": plaats, "count": 1, "language": "nl",
                                             "format": "json"}, timeout=15).json()
        hit = (antwoord.get("results") or [None])[0]
        if not hit:
            return None, None
        return hit["latitude"], hit["longitude"]
    except (requests.RequestException, ValueError, KeyError):
        return None, None


def haal_weer(plaats=None, dagen=5):
    """Actueel weer plus verwachting. Geeft None als er niets op te halen valt."""
    plaats = plaats or config.WEER_PLAATS
    lat, lon = _plaats_gps(plaats)
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
    except (requests.RequestException, ValueError):
        return None

    try:
        daily = antwoord["daily"]
        nu = antwoord["current"]
    except KeyError:
        return None

    dagen_lijst = []
    for i, dag in enumerate(daily["time"]):
        d = date.fromisoformat(dag)
        code = daily["weather_code"][i]
        dagen_lijst.append({
            "dag": "vandaag" if i == 0 else ("morgen" if i == 1 else DAG_KORT[d.weekday()]),
            "datum": f"{d.day}/{d.month}",
            "max": round(daily["temperature_2m_max"][i]),
            "min": round(daily["temperature_2m_min"][i]),
            "tekst": CODES.get(code, "wisselvallig"),
            "neerslag": daily["precipitation_probability_max"][i] or 0,
            "wind": round(daily["wind_speed_10m_max"][i] / 3.6),
            "zonsopkomst": daily["sunrise"][i][11:16],
            "zonsondergang": daily["sunset"][i][11:16],
        })

    resultaat = {
        "plaats": plaats,
        "opgehaald": datetime.now().isoformat(timespec="minutes"),
        "nu": {"temperatuur": round(nu["temperature_2m"]),
               "tekst": CODES.get(nu["weather_code"], "wisselvallig"),
               "wind": round(nu["wind_speed_10m"] / 3.6)},
        "dagen": dagen_lijst,
    }
    try:
        CACHE.write_text(json.dumps(resultaat, ensure_ascii=False))
    except OSError:
        pass
    return resultaat


def laatste_weer():
    """Terugvaloptie: het laatst bewaarde weer (als de API niet antwoordt)."""
    try:
        data = json.loads(CACHE.read_text())
        opgehaald = datetime.fromisoformat(data["opgehaald"])
        if opgehaald.date() >= date.today() - timedelta(days=1):
            return data
    except (OSError, ValueError, KeyError):
        pass
    return None