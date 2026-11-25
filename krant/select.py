"""Kies de editie: welke artikelen, in welke volgorde, plus de korte berichten."""
import re
from datetime import datetime, timezone

from . import config

STOP = {"de", "het", "een", "van", "in", "op", "en", "voor", "met", "dat", "die", "is",
        "te", "aan", "om", "bij", "naar", "niet", "maar", "ook", "als", "door", "over",
        "uit", "dan", "wat", "hoe", "waarom", "kan", "wordt", "worden", "heeft", "zijn"}


def _tokens(title):
    words = re.findall(r"[a-zà-ÿ0-9]+", title.lower())
    return {w for w in words if len(w) > 3 and w not in STOP}


def _same_story(a, b):
    ta, tb = _tokens(a["title"]), _tokens(b["title"])
    if not ta or not tb:
        return False
    overlap = len(ta & tb) / min(len(ta), len(tb))
    return overlap >= 0.55


def _age_hours(art):
    try:
        pub = datetime.fromisoformat(art["published"])
    except (KeyError, TypeError, ValueError):
        return 999
    return (datetime.now(timezone.utc) - pub).total_seconds() / 3600


def _score(art):
    """Versheid weegt het zwaarst; volledige tekst en een kop met inhoud tellen mee."""
    score = max(0.0, 48 - _age_hours(art)) * 2
    if art.get("status") == "full":
        score += 18
    score += min(12, (art.get("words") or 0) / 120)
    if len(art["title"]) > 35:
        score += 3
    if art.get("section") == "Techniek":
        score *= 0.95          # tech mag iets ouder zijn dan het hoofdnieuws
    return score


def _dedupe(pool):
    kept = []
    for art in sorted(pool, key=_score, reverse=True):
        if not any(_same_story(art, k) for k in kept):
            kept.append(art)
    return kept


def build_pool(hours=None):
    from . import db
    pool = db.candidates(hours or config.MAX_AGE_HOURS)
    pool = [a for a in pool if a.get("title")]
    return _dedupe(pool)


def choose(pool):
    """Kies artikelen per rubriek met een maximum per bron, en de rest als korte berichten."""
    caps = {f["source"]: f["cap"] for f in config.FEEDS}
    used_per_source = {}
    picked = []

    for section, amount in config.TARGETS.items():
        cands = [a for a in pool if a["section"] == section]
        cands.sort(key=_score, reverse=True)
        taken = 0
        for art in cands:
            if taken >= amount:
                break
            if art in picked:
                continue
            if used_per_source.get(art["source"], 0) >= caps.get(art["source"], 3):
                continue
            picked.append(art)
            used_per_source[art["source"]] = used_per_source.get(art["source"], 0) + 1
            taken += 1

    # opvullen als een rubriek leeg bleef
    target_total = sum(config.TARGETS.values())
    if len(picked) < target_total:
        for art in sorted(pool, key=_score, reverse=True):
            if len(picked) >= target_total:
                break
            if art not in picked and used_per_source.get(art["source"], 0) < caps.get(art["source"], 3):
                picked.append(art)
                used_per_source[art["source"]] = used_per_source.get(art["source"], 0) + 1

    # lead = het sterkste nieuwsverhaal, daarna nieuws, dan techniek
    nieuws = [a for a in picked if a["section"] != "Techniek"]
    techniek = [a for a in picked if a["section"] == "Techniek"]
    nieuws.sort(key=_score, reverse=True)

    shorts = []
    for art in sorted(pool, key=_score, reverse=True):
        if len(shorts) >= config.SHORTS:
            break
        if art in picked or art["source"] in {s["source"] for s in shorts}:
            continue
        if not art.get("summary"):
            continue
        shorts.append(art)

    return {"lead": nieuws[0] if nieuws else None,
            "news": nieuws[1:],
            "tech": techniek,
            "shorts": shorts}