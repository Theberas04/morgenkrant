"""RSS in, schone artikelen uit."""
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import feedparser
import requests
import trafilatura
import lxml.html

from . import config, db
from .clean import clean_article_html, clean_summary
from .taal import is_dutch

TAG_RE = re.compile(r"<[^>]+>")


def _clean(text, limit=None):
    if not text:
        return ""
    txt = TAG_RE.sub(" ", text)
    txt = lxml.html.fromstring(f"<div>{txt}</div>").text_content()
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt[:limit].rsplit(" ", 1)[0] + "…" if limit and len(txt) > limit else txt


def _entry_date(entry):
    for key in ("published_parsed", "updated_parsed"):
        val = entry.get(key)
        if val:
            return datetime(*val[:6], tzinfo=timezone.utc)
    return None


def _entry_image(entry):
    for key in ("media_content", "media_thumbnail"):
        for m in entry.get(key) or []:
            url = m.get("url")
            if url:
                return url
    for enc in entry.get("enclosures") or []:
        if str(enc.get("type", "")).startswith("image"):
            return enc.get("href") or enc.get("url")
    return None


def _declared_date(raw_html):
    """Publicatiedatum die de pagina zelf beweert (article:published_time of JSON-LD)."""
    for pattern in (
        r'article:published_time["\'][^>]+content=["\'](\d{4}-\d{2}-\d{2}[T ][\d:]+)',
        r'content=["\'](\d{4}-\d{2}-\d{2}[T ][\d:]+)["\'][^>]+article:published_time',
        r'"datePublished"\s*:\s*["\'](\d{4}-\d{2}-\d{2}[T ][\d:]+)',
    ):
        m = re.search(pattern, raw_html or "", re.I)
        if m:
            try:
                return datetime.fromisoformat(m.group(1).replace("Z", "+00:00"))
            except ValueError:
                continue
    return None


def extract(url):
    """Haal één artikel op. Geeft (html, words, published) of (None, 0, None)."""
    try:
        resp = requests.get(url, timeout=25, headers={
            "User-Agent": config.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.5",
        })
        if resp.status_code >= 400:
            return None, 0, None
        raw = resp.text
    except requests.RequestException:
        return None, 0, None

    html = trafilatura.extract(raw, output_format="html", include_links=True,
                               include_images=False, include_formatting=True,
                               favor_recall=True)
    if not html:
        return None, 0, None
    words = len(TAG_RE.sub(" ", html).split())
    return html, words, _declared_date(raw)


def sync_bronnen():
    """Houd rubriek en titelfilter van opgeslagen artikelen gelijk aan de configuratie."""
    with db.connect() as con:
        for feed in config.FEEDS:
            con.execute("UPDATE articles SET section=? WHERE source=?",
                        (feed["section"], feed["source"]))
            pats = feed.get("exclude") or ()
            if not pats:
                continue
            for row in con.execute("SELECT url, title FROM articles WHERE source=?",
                                   (feed["source"],)).fetchall():
                if any(re.search(p, row["title"], re.I) for p in pats):
                    con.execute("DELETE FROM articles WHERE url=?", (row["url"],))


def refresh(verbose=True):
    """Lees alle feeds, sla nieuwe artikelen op, haal er een subset volledig bij."""
    db.init()
    sync_bronnen()
    known = db.known_urls()
    stats = {"feeds": 0, "new": 0, "full": 0, "summary": 0, "errors": []}

    for feed in config.FEEDS:
        parsed = feedparser.parse(feed["url"], agent=config.USER_AGENT)
        if not parsed.entries:
            stats["errors"].append(f"{feed['source']}: geen items")
            continue
        stats["feeds"] += 1
        todo = []
        for entry in parsed.entries:
            url = entry.get("link")
            title = _clean(entry.get("title"), 220)
            if not url or not title:
                continue
            if any(re.search(pat, title, re.I) for pat in feed.get("exclude", ())):
                continue
            published = _entry_date(entry) or datetime.now(timezone.utc)
            summary = clean_summary(_clean(entry.get("summary") or entry.get("description"), 600))
            art = {
                "url": url, "source": feed["source"], "section": feed["section"],
                "title": title, "summary": summary, "html": None,
                "image": _entry_image(entry),
                "published": published.astimezone(timezone.utc).isoformat(),
                "fetched": datetime.now(timezone.utc).isoformat(),
                "words": 0, "status": "summary",
            }
            if url not in known:
                todo.append(art)
                known.add(url)

        for art in todo[: config.EXTRACT_PER_FEED]:
            html, words, declared = extract(art["url"])
            if declared:
                art["published"] = declared.astimezone(timezone.utc).isoformat()
            if html:
                html, words = clean_article_html(html, art["title"])
            tekst = " ".join([art["title"], art.get("summary") or "",
                              re.sub(r"<[^>]+>", " ", html or "")])
            if not is_dutch(tekst):
                stats.setdefault("niet_nederlands", 0)
                stats["niet_nederlands"] += 1
                continue
            if html and words >= config.MIN_FULL_WORDS:
                art.update(html=html, words=words, status="full")
                stats["full"] += 1
            elif html and words > 60:
                # korte berichten (Tweakers-nieuwsflitsen) zijn als volledige tekst goed
                art.update(html=html, words=words, status="full")
                stats["full"] += 1
            else:
                stats["summary"] += 1
            db.save_article(art)
            stats["new"] += 1

    print(f"[fetch] {stats['feeds']} feeds · {stats['new']} nieuw "
          f"({stats['full']} volledig, {stats['summary']} samenvatting)")
    for err in stats["errors"]:
        print(f"[fetch] overgeslagen: {err}")
    return stats