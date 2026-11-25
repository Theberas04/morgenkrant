"""Opschonen van opgehaalde artikelen: geen dubbele koppen, geen voetregels, geen ruis."""
import re

import lxml.html
from lxml.html import tostring

JUNK = re.compile(
    r"^(lees ook|lees meer|meer over|gerelateerd|volg ons|deel dit|adverteren|abonneer|"
    r"nu abonneren|dit artikel delen|beeld:|foto:|copyright|©|alle rechten|"
    r"geschreven door|geschreven door:|bron:|mark nrc|telegraaf journ|"
    r"bent u al abonnee|word nu lid|probeer.*gratis|log in om|"
    r"nieuwsbrief|schrijf je in|ontvang.*nieuwsbrief|tekst\s*[–—:-])",
    re.I)
BLOCK_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "div", "span", "section"}
# korte blokken met deze woorden zijn bijna altijd promotie of navigatie
JUNK_CONTAINS = ("nieuwsbrief", "op google", "journ", "lees ook", "deel dit artikel",
                 "volg ons", "abonnee worden", "word abonnee", "meld je aan",
                 "bekijk ook", "meer over dit onderwerp", "voorkeursbron",
                 "zoekresultaten", "kies nrc", "meer informatie over",
                 "dit artikel is onderdeel", "advertentie")
DROP_TAGS = {"script", "style", "figure", "iframe", "form", "aside", "noscript",
             "table", "button", "video", "audio", "figcaption"}


def _words(text):
    return re.findall(r"[a-zà-ÿ0-9]+", (text or "").lower())


def _same_heading(a, b):
    wa = {w for w in _words(a) if len(w) > 3}
    wb = {w for w in _words(b) if len(w) > 3}
    if not wa or not wb:
        return False
    return len(wa & wb) / min(len(wa), len(wb)) >= 0.6


def clean_article_html(html, title):
    """Haal kopieer-rommel weg en verwijder de kop die het artikel zelf herhaalt."""
    if not html:
        return html, 0
    try:
        root = lxml.html.fromstring(f"<div>{html}</div>")
    except Exception:
        return html, len(re.sub(r"<[^>]+>", " ", html).split())

    for tag in DROP_TAGS:
        for el in root.iter(tag):
            el.drop_tree()

    # kop-herhaling bovenaan weghalen (het artikel begint vaak met zijn eigen titel)
    for el in list(root.iter("h1", "h2", "h3")):
        if _same_heading(el.text_content(), title):
            el.drop_tree()
            break

    # ruis-blokken: voetregels, abonneeoproepen, deel-knoppen
    for el in list(root.iter(*BLOCK_TAGS)):
        text = " ".join(el.text_content().split())
        if not text:
            if el.getparent() is not None and el.tag in {"p", "div", "span", "section", "li"}:
                el.drop_tree()
            continue
        if el.tag in {"p", "li", "div", "span", "section"} and JUNK.match(text):
            el.drop_tree()
            continue
        low = text.lower()
        if el.tag in BLOCK_TAGS and len(text) < 240 and any(w in low for w in JUNK_CONTAINS):
            el.drop_tree()

    # losse attribuut-rommel en lege elementen
    for el in root.iter():
        for attr in ("class", "id", "style", "data-*"):
            if attr in el.attrib:
                del el.attrib[attr]
    for el in list(root.iter("p", "div", "span", "section", "strong", "em", "b", "i")):
        if not el.text_content().strip() and len(el) == 0:
            el.drop_tree()

    cleaned = "".join(tostring(child, encoding="unicode")
                      for child in root.iterchildren() if child.getparent() is not None)
    cleaned = re.sub(r"\s+([.,;:!?])", r"\1", cleaned)
    cleaned = re.sub(r"\.(\s*)\.", ".", cleaned)
    words = len(re.sub(r"<[^>]+>", " ", cleaned).split())
    return cleaned, words


def clean_summary(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = " ".join(text.split())
    if JUNK.match(text):
        return ""
    return text