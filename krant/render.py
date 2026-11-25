"""Van editie naar HTML en PDF."""
from datetime import date, datetime

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

from . import config

DAGEN = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
MAANDEN = ["januari", "februari", "maart", "april", "mei", "juni", "juli",
           "augustus", "september", "oktober", "november", "december"]
KORTE_MAANDEN = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]

env = Environment(
    loader=FileSystemLoader(str(config.TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)


def lange_datum(day):
    d = date.fromisoformat(day)
    return f"{DAGEN[d.weekday()]} {d.day} {MAANDEN[d.month - 1]} {d.year}"


def korte_datum(iso):
    try:
        d = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return ""
    return f"{d.day} {KORTE_MAANDEN[d.month - 1]} · {d:%H:%M}"


def leesmin(words):
    return max(1, round((words or 0) / 200))


env.filters["lange_datum"] = lange_datum
env.filters["korte_datum"] = korte_datum
env.filters["leesmin"] = leesmin


def _kaal(art):
    return {
        "url": art["url"],
        "title": art["title"],
        "source": art["source"],
        "section": art["section"],
        "summary": art.get("summary") or "",
        "html": art.get("html") or "",
        "published": art.get("published"),
        "words": art.get("words") or 0,
        "status": art.get("status") or "summary",
    }


def context(edition):
    payload = edition["payload"]
    lead = _kaal(payload["lead"]) if payload.get("lead") else None
    news = [_kaal(a) for a in payload.get("news", [])]
    tech = [_kaal(a) for a in payload.get("tech", [])]
    shorts = [_kaal(a) for a in payload.get("shorts", [])]
    alles = ([lead] if lead else []) + news + tech
    minuten = sum(leesmin(a["words"]) for a in alles)
    return {
        "day": edition["day"],
        "nummer": payload.get("nummer", 1),
        "weer": payload.get("weer"),
        "lange_datum": lange_datum(edition["day"]),
        "krant": config.PAPER_TITLE,
        "ondertitel": config.PAPER_SUBTITLE,
        "tagline": config.PAPER_TAGLINE,
        "lead": lead,
        "news": news,
        "tech": tech,
        "shorts": shorts,
        "aantal": len(alles),
        "minuten": minuten,
        "bronnen": sorted({a["source"] for a in alles}),
    }


def render_html(edition, template="web.html"):
    return env.get_template(template).render(**context(edition))


def render_pdf(edition, variant="a4", out_dir=None):
    """variant: 'a4' (laptop/print) of 'mobiel' (telefoonformaat, één kolom)."""
    out_dir = out_dir or config.EDITION_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    html = env.get_template("print.html").render(
        **context(edition), variant_mobiel=(variant == "mobiel"))
    path = out_dir / f"krant-{edition['day']}-{variant}.pdf"
    HTML(string=html, base_url=str(config.BASE_DIR)).write_pdf(str(path))
    return path