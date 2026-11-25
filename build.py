#!/usr/bin/env python3
"""Bouwt de editie van vandaag.

  python build.py              # feeds lezen, artikelen ophalen, editie + 2 PDF's maken
  python build.py --no-fetch   # alleen opnieuw opmaken uit wat al in de database staat
"""
import argparse
import sys
from datetime import date

from krant import db, fetch, render, select, weer

SNAPSHOT = ("url", "title", "source", "section", "summary", "html",
            "published", "words", "status")


def snapshot(art):
    if not art:
        return None
    return {k: art.get(k) for k in SNAPSHOT}


def build(no_fetch=False):
    db.init()
    if not no_fetch:
        fetch.refresh()

    pool = select.build_pool()
    if not pool:
        print("[build] geen verse artikelen in de database; niets gebouwd")
        return 1

    keuze = select.choose(pool)
    if not keuze["lead"] and not keuze["tech"]:
        print("[build] geen artikelen gekozen; niets gebouwd")
        return 1

    day = date.today().isoformat()
    bestaand = db.get_edition(day)
    nummer = (bestaand["payload"].get("nummer") if bestaand else None) or len(db.all_editions(1000)) + 1
    weerdata = weer.haal_alles() or weer.laatste_weer()
    payload = {
        "nummer": nummer,
        "weer": weerdata,
        "lead": snapshot(keuze["lead"]),
        "news": [snapshot(a) for a in keuze["news"]],
        "tech": [snapshot(a) for a in keuze["tech"]],
        "shorts": [snapshot(a) for a in keuze["shorts"]],
    }
    db.save_edition(day, payload)
    edition = db.get_edition(day)

    for variant in ("a4", "mobiel"):
        path = render.render_pdf(edition, variant)
        size = path.stat().st_size // 1024
        print(f"[build] {path.name} ({size} kB)")

    alles = [keuze["lead"]] + keuze["news"] + keuze["tech"]
    print(f"[build] editie {day}: {len(alles)} artikelen van "
          f"{len({a['source'] for a in alles if a})} bronnen, "
          f"{len(keuze['shorts'])} korte berichten")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-fetch", action="store_true")
    args = ap.parse_args()
    sys.exit(build(no_fetch=args.no_fetch))