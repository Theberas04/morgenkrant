#!/usr/bin/env python3
"""Webpagina van de Morgenkrant (Flask + waitress)."""
import os

from flask import Flask, abort, send_file, send_from_directory

from krant import config, db, render

app = Flask(__name__)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 300


def _edities():
    return db.all_editions(14)


def _web_context(edition):
    """Voor de webpagina verwijzen prenten naar een URL in plaats van een bestandspad."""
    ctx = render.context(edition)
    ctx["rubrieken"] = [
        {**b, "beeld": f"/beeld/{str(b['beeld']).rsplit('/', 1)[-1]}"} if b.get("beeld") else b
        for b in ctx["rubrieken"]
    ]
    return ctx


@app.route("/")
def voorpagina():
    edition = db.get_edition()
    if not edition:
        return ("<h1>Nog geen editie</h1><p>Draai <code>python build.py</code> "
                "om de eerste krant te maken.</p>"), 503
    ctx = _web_context(edition)
    html = render.env.get_template("web.html").render(**ctx, edities=_edities())
    return html


@app.route("/editie/<day>")
def editie(day):
    edition = db.get_edition(day)
    if not edition:
        abort(404)
    ctx = _web_context(edition)
    return render.env.get_template("web.html").render(**ctx, edities=_edities())


@app.route("/pdf/<day>/<variant>.pdf")
def pdf(day, variant):
    if variant not in ("a4", "mobiel"):
        abort(404)
    path = config.EDITION_DIR / f"krant-{day}-{variant}.pdf"
    if not path.exists():
        if not db.get_edition(day):
            abort(404)
        render.render_pdf(db.get_edition(day), variant)
    return send_file(path, mimetype="application/pdf",
                     download_name=f"{config.PAPER_TITLE}-{day}-{variant}.pdf")


@app.route("/beeld/<path:naam>")
def beeld(naam):
    if not naam.lower().endswith((".jpg", ".jpeg", ".png")):
        abort(404)
    return send_from_directory(config.DATA_DIR / "rubrieken", naam)


@app.route("/fonts/<path:name>")
def fonts(name):
    return send_from_directory(config.FONTS_DIR, name)


@app.route("/gezondheid")
def gezondheid():
    ed = db.get_edition()
    return {"status": "ok", "laatste_editie": ed["day"] if ed else None,
            "artikelen_in_db": db.count_articles()}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8420))
    from waitress import serve
    serve(app, host="0.0.0.0", port=port, threads=8)