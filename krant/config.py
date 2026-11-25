"""Instellingen voor de Morgenkrant. Pas hier de krant aan, niet in de code."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
EDITION_DIR = BASE_DIR / "edities"
FONTS_DIR = BASE_DIR / "fonts"
TEMPLATE_DIR = BASE_DIR / "templates"

PAPER_TITLE = "De Morgenkrant"
PAPER_SUBTITLE = "Nederlands nieuws en techniek, elke ochtend vers"
PAPER_TAGLINE = "Samengesteld uit NOS, NU.nl, RTL Nieuws, de Volkskrant, NRC, het AD, Tweakers, Bright, Techzine en Computable"

# Feeds: section bepaalt de rubriek, cap het maximum aantal artikelen per bron.
FEEDS = [
    {"url": "https://feeds.nos.nl/nosnieuwsalgemeen", "source": "NOS",         "section": "Nieuws",   "cap": 4},
    {"url": "https://www.nu.nl/rss/Algemeen",         "source": "NU.nl",       "section": "Nieuws",   "cap": 2},
    {"url": "https://www.rtlnieuws.nl/rss.xml",       "source": "RTL Nieuws",  "section": "Nieuws",   "cap": 2},
    {"url": "https://www.volkskrant.nl/nieuws/rss.xml", "source": "Volkskrant", "section": "Nieuws",  "cap": 2},
    {"url": "https://www.nrc.nl/rss/",                "source": "NRC",         "section": "Nieuws",   "cap": 2},
    {"url": "https://www.ad.nl/home/rss.xml",         "source": "AD",          "section": "Binnenland", "cap": 2},
    {"url": "https://tweakers.net/feeds/nieuws.xml",  "source": "Tweakers",    "section": "Techniek", "cap": 5},
    {"url": "https://www.bright.nl/rss",              "source": "Bright",      "section": "Techniek", "cap": 2},
    {"url": "https://www.techzine.nl/feed/",          "source": "Techzine",    "section": "Techniek", "cap": 1},
    {"url": "https://www.l1.nl/rss/nieuws",          "source": "L1",          "section": "Regio",     "cap": 2,
     "exclude": ["L1 Nieuws -", "Limburg Kiekt", "Spreekbeurt", "Limburg in de Waereld",
                 "Radio", "Podcast", "Muziek", "L1 Vandaag"]},
    {"url": "https://www.computable.nl/feed/",        "source": "Computable",  "section": "Techniek", "cap": 1},
]

# Hoeveel artikelen per rubriek in de editie.
TARGETS = {"Nieuws": 7, "Binnenland": 2, "Regio": 2, "Techniek": 5}
MAX_AGE_HOURS = 30          # ouder nieuws valt af
SHORTS = 7                  # aantal regels in "In het kort"
EXTRACT_PER_FEED = 8        # hoeveel artikelen per bron per run volledig opgehaald worden
MIN_FULL_WORDS = 220        # minder tekst = samenvatting i.p.v. volledig artikel

TIMEZONE = "Europe/Amsterdam"
MAANDEN = ["januari", "februari", "maart", "april", "mei", "juni", "juli",
           "augustus", "september", "oktober", "november", "december"]

# Weerblok (Open-Meteo, geen sleutel nodig)
WEER_PLAATSEN = ["Sittard", "Hilversum"]
WEER_DAGEN = 5

USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")