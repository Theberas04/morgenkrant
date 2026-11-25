#!/usr/bin/env python3
"""Schoon alle al opgeslagen artikelen opnieuw op en gooi niet-Nederlandse eruit."""
import re
import sys

from krant import db
from krant.clean import clean_article_html, clean_summary
from krant.taal import is_dutch


def main():
    db.init()
    changed = removed = 0
    with db.connect() as con:
        rows = con.execute("SELECT url, title, html, summary FROM articles").fetchall()
        for row in rows:
            html, words = clean_article_html(row["html"], row["title"])
            summary = clean_summary(row["summary"])
            tekst = " ".join([row["title"], summary or "", re.sub(r"<[^>]+>", " ", html or "")])
            if not is_dutch(tekst):
                con.execute("DELETE FROM articles WHERE url=?", (row["url"],))
                removed += 1
                continue
            if html != row["html"] or summary != row["summary"]:
                con.execute("UPDATE articles SET html=?, words=?, summary=? WHERE url=?",
                            (html, words, summary, row["url"]))
                changed += 1
    print(f"[clean] {changed} bijgewerkt, {removed} niet-Nederlands verwijderd "
          f"({len(rows)} artikelen bekeken)")
    return 0


if __name__ == "__main__":
    sys.exit(main())