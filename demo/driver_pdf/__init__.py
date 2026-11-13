"""Exports the stress deck to PDF in Read and Compact and checks the pages. Not part of the add-on.
Run with SEED_STRESS=1. Needs pdftoppm and pdfinfo (poppler) for the page checks."""
import json, os, shutil, subprocess
from aqt import mw, gui_hooks
from aqt.qt import QTimer
OUT = os.environ.get("SHEETS_DEMO_OUT", "/tmp/sheets-pdf")
DECK = "Stress::Long cards"
LOG = []
def log(name, ok, detail=None):
    LOG.append({"check": name, "ok": bool(ok), "detail": detail})
    with open(os.path.join(OUT, "checks.json"), "w") as f:
        json.dump(LOG, f, indent=1, ensure_ascii=False)

def pages(pdf, tag):
    """Per page: share of non-background pixels, and whether ink touches the right edge (cut-off content)."""
    d = os.path.join(OUT, "pages-" + tag); os.makedirs(d, exist_ok=True)
    subprocess.run(["pdftoppm", "-r", "40", "-gray", pdf, os.path.join(d, "p")], check=True)
    out = []
    for name in sorted(os.listdir(d)):
        raw = open(os.path.join(d, name), "rb").read()
        parts = raw.split(b"\n", 3); w, h = map(int, parts[1].split()); px = parts[3]
        bg = max(set(px[:w * 3]), key=px[:w * 3].count)
        ink = sum(1 for b in px if abs(b - bg) > 40)
        edge = sum(1 for y in range(h) if abs(px[y * w + w - 2] - bg) > 40)
        out.append({"page": name, "ink": round(ink / len(px), 4), "edge": edge})
    return out

def check(pdf, tag):
    if not (os.path.exists(pdf) and shutil.which("pdftoppm")):
        log(tag + ": PDF written and poppler present", False, pdf); return
    ps = pages(pdf, tag)
    thin = [p for p in ps[:-1] if p["ink"] < 0.02]
    log(tag + ": no nearly empty page before the last", not thin, {"pages": len(ps), "thin": thin, "ink": [p["ink"] for p in ps]})
    cut = [p for p in ps if p["edge"] > 0]
    log(tag + ": nothing runs into the right page edge", not cut, cut)

def start():
    os.makedirs(OUT, exist_ok=True)
    next(a for a in mw.form.menuTools.actions() if a.text() == "Sheets").trigger()
    from anki_sheets import dialog
    d = dialog._dialog
    d.setGeometry(0, 0, 1280, 800)
    read, compact = os.path.join(OUT, "stress-read.pdf"), os.path.join(OUT, "stress-compact.pdf")
    steps = [
        (2500, lambda: d.web.eval("Sheets.state.view.theme='paper'; Sheets.state.view.emphasis='tint'; Sheets.reload().then(function(){Sheets.selectDeck(%s)})" % json.dumps(DECK))),
        (3000, lambda: d.web.evalWithCallback(
            "document.getElementById('evil') && document.getElementById('evil').click();"
            "JSON.stringify({pwned: window.pwned || 0, handlers: document.querySelectorAll('.row [onerror], .row [onload], .row iframe').length,"
            " js: [].filter.call(document.querySelectorAll('.row a'), function(a){ return /script:/i.test(a.getAttribute('href') || a.getAttribute('xlink:href') || ''); }).length,"
            " shown: document.body.textContent.indexOf('gracias') >= 0})",
            lambda r: log("a hostile card's scripts never run and its text still shows",
                          bool(r) and json.loads(r) == {"pwned": 0, "handlers": 0, "js": 0, "shown": True}, r))),
        (1000, lambda: d.export_pdf(read)),
        (6000, lambda: d.web.eval("document.querySelector('button[data-mode=compact]').click()")),
        (2500, lambda: d.export_pdf(compact)),
        (6000, lambda: (check(read, "read"), check(compact, "compact"))),
        (500, mw.unloadProfileAndExit),
    ]
    def run(i=0):
        if i < len(steps):
            QTimer.singleShot(steps[i][0], lambda: (steps[i][1](), run(i + 1)))
    run()
gui_hooks.main_window_did_init.append(lambda: QTimer.singleShot(1500, start))
