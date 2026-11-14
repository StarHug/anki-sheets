"""Demo driver: runs inside real Anki, clicks through the IchiSheet add-on with the
real mouse pointer, checks what is on screen at each step, then quits.
Not part of the add-on."""

import json
import os

from aqt import gui_hooks, mw
from aqt.qt import QCursor, QPoint, QPointF, Qt, QTimer, QEvent, QMouseEvent, QApplication
from PyQt6.QtTest import QTest

OUT = os.environ.get("SHEETS_DEMO_OUT", "/tmp/sheets-demo")
LOG = []
GRAMMAR = "Spanish::📘 Grammar::Ser and Estar"
# For the listing GIF the same walk-through can run on another sample deck, e.g.
# SHEETS_DEMO_DECK="Japanese::📗 Grammar::Particles" with SEED_EXTRAS=1 (the checks then describe the Spanish deck and are ignored).
GRAMMAR = os.environ.get("SHEETS_DEMO_DECK", GRAMMAR)
TOP, MID = GRAMMAR.split("::")[0], "::".join(GRAMMAR.split("::")[:2])


def log(name, ok, detail=None):
    LOG.append({"check": name, "ok": bool(ok), "detail": detail})
    with open(os.path.join(OUT, "checks.json"), "w") as f:
        json.dump(LOG, f, indent=1, ensure_ascii=False)


def mark(name):
    with open(os.path.join(OUT, "marks.txt"), "a") as f:
        import time
        f.write("%.2f\t%s\n" % (time.time(), name))


class Driver:
    def __init__(self):
        self.box = {}
        self.gen = self.script()
        self.step()

    def step(self):
        try:
            delay = next(self.gen)
        except StopIteration:
            return
        except Exception as e:  # keep the evidence honest: record crashes
            import traceback
            log("driver crashed", False, traceback.format_exc())
            QTimer.singleShot(500, mw.unloadProfileAndExit)
            return
        QTimer.singleShot(int(delay), self.step)

    # -------------------------------------------------------- helpers

    @property
    def dlg(self):
        from anki_sheets import dialog
        return dialog._dialog

    def js(self, code):
        """Evaluate JS in the sheet; result lands in self.box['v']."""
        self.box.pop("v", None)
        self.dlg.web.evalWithCallback(code, lambda v: self.box.__setitem__("v", v))
        for _ in range(100):
            if "v" in self.box:
                break
            yield 30
        return self.box.get("v")

    def glide(self, widget, pos):
        target = widget.mapToGlobal(pos)
        start = QCursor.pos()
        for i in range(1, 13):
            t = i / 12
            QCursor.setPos(int(start.x() + (target.x() - start.x()) * t),
                           int(start.y() + (target.y() - start.y()) * t))
            yield 22
        QTest.mouseMove(widget, pos)
        yield 180

    def click_widget(self, widget, pos):
        yield from self.glide(widget, pos)
        QTest.mouseClick(widget, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
        yield 250

    def click(self, selector, pause=900):
        web = self.dlg.web
        pt = yield from self.js(
            "(function(){var e=document.querySelector(%s); if(!e) return null;"
            "e.scrollIntoView({block:'nearest'}); var r=e.getBoundingClientRect();"
            "return [r.x+Math.min(r.width/2,140), r.y+r.height/2];})()" % json.dumps(selector))
        if not pt:
            log("element exists: " + selector, False)
            return
        z = web.zoomFactor()
        target = web.focusProxy() or web
        yield from self.click_widget(target, QPoint(int(pt[0] * z), int(pt[1] * z)))
        yield pause

    def scroll(self, to, ms=1400):
        yield from self.js(
            "document.querySelector('.scroll').scrollTo({top:%s, behavior:'smooth'}); 1" % to)
        yield ms

    def snapshot(self):
        v = yield from self.js(
            "JSON.stringify({title:(document.querySelector('.head h1')||{}).textContent,"
            "meta:(document.querySelector('.head .meta')||{}).textContent,"
            "decks:[].map.call(document.querySelectorAll('.deck h2'),function(e){return e.textContent}),"
            "groups:[].map.call(document.querySelectorAll('.group:not([hidden]) h3'),function(e){return e.textContent}),"
            "rows:document.querySelectorAll('.row:not([hidden])').length,"
            "mode:document.querySelector('.main').className,"
            "blurred:[].filter.call(document.querySelectorAll('.row .ans'),function(e){return getComputedStyle(e).filter!=='none'}).length,"
            "first:(document.querySelector('.row:not([hidden]) .q')||{}).textContent})")
        return json.loads(v)

    # -------------------------------------------------------- the demo

    def script(self):
        mw.setGeometry(0, 0, 1280, 800)
        QCursor.setPos(640, 500)
        yield 2500
        mark("start")

        # 1. open from the Tools menu, like a user would
        menu = mw.form.menuTools
        action = next(a for a in menu.actions() if a.text() == "IchiSheet")
        log("Tools menu has a IchiSheet entry", True, action.shortcut().toString())
        bar = mw.form.menubar
        rect = bar.actionGeometry(menu.menuAction())
        yield from self.glide(bar, rect.center())
        menu.popup(bar.mapToGlobal(rect.bottomLeft()))
        yield 900
        arect = menu.actionGeometry(action)
        yield from self.glide(menu, arect.center())
        yield 400
        menu.hide()
        action.trigger()
        yield 600
        self.dlg.setGeometry(0, 0, 1280, 800)
        yield 2600
        mark("opened")
        s = yield from self.snapshot()
        log("sheet window opens on a start page, not a heavy All decks load", s["title"] == "IchiSheet" and s["rows"] == 0, s)
        yield from self.click('.dk[data-deck=""]', 1500)
        s = yield from self.snapshot()
        log("All decks shows every note", s["title"] == "All decks" and s["rows"] == 19, s)

        # 2. pick a deck from the tree
        yield from self.click('.dk[data-deck="%s"]' % TOP, 900)
        yield from self.click('.dk[data-deck="%s"]' % MID, 900)
        yield from self.click('.dk[data-deck="%s"]' % GRAMMAR, 1800)
        mark("deck")
        s = yield from self.snapshot()
        log("Ser and Estar sheet: 10 notes in Verbs + Articles sections",
            s["title"] == "Ser and Estar" and s["rows"] == 10 and s["groups"] == ["Verbs", "Articles"], s)

        # 3. skim it
        yield from self.scroll(500)
        yield 700
        yield from self.scroll(0, 1100)

        # 4. expand a collapsed note + image
        yield from self.click(".row:nth-child(2) .chip", 1600)
        v = yield from self.js("!document.querySelector('.row:nth-child(2) .extra').hidden"
                               " && document.querySelector('.row:nth-child(2) .extra img').naturalWidth")
        log("note chip expands and the image loads from the media folder", v == 320, v)
        yield from self.click(".row:nth-child(2) .chip", 500)

        # 5. cover answers, reveal two rows
        yield from self.click('button[data-mode="cover"]', 1500)
        mark("cover")
        s = yield from self.snapshot()
        log("cover mode hides all 10 answers", s["blurred"] == 10, s["blurred"])
        yield from self.click(".row:nth-child(1) .q", 1100)
        yield from self.click(".row:nth-child(3) .q", 1100)
        s = yield from self.snapshot()
        log("clicking a row reveals just that answer", s["blurred"] == 8, s["blurred"])

        # 6. weak spots
        yield from self.click('button[data-mode="read"]', 600)
        yield from self.click('button[data-scope="weak"]', 2000)
        mark("weak")
        s = yield from self.snapshot()
        badges = yield from self.js("[].map.call(document.querySelectorAll('.badge'),function(e){return e.textContent}).join('|')")
        log("weak spots lists the 2 lapsing cards, worst first",
            s["rows"] == 2 and badges == "4 lapses|3 lapses", [s["rows"], badges, s["first"]])
        yield from self.click('button[data-scope="all"]', 1200)

        # 7. filter
        yield from self.click(".filter", 300)
        target = self.dlg.web.focusProxy() or self.dlg.web
        for ch in "location":
            QTest.keyClick(target, ch)
            yield 110
        yield 1300
        mark("filter")
        s = yield from self.snapshot()
        log("filter 'location' leaves the 2 rows that mention it", s["rows"] == 2, s["rows"])
        for _ in "location":
            QTest.keyClick(target, Qt.Key.Key_Backspace)
            yield 40
        yield 500

        # 8. whole parent deck: sub-decks stacked, multi-field + cloze cards
        yield from self.click('.dk[data-deck="Spanish"]', 2000)
        mark("parent")
        s = yield from self.snapshot()
        log("parent deck stacks its 3 sub-decks (17 notes)", s["rows"] == 17 and len(s["decks"]) == 3, s)
        cz = yield from self.js("document.querySelectorAll('.cz').length + '/' + document.querySelectorAll('.det').length")
        log("cloze answers highlighted and extra fields shown", cz == "6/13", cz)
        yield from self.scroll(520, 1500)
        yield 900
        yield from self.scroll(0, 900)

        # 9. compact cheat-sheet + PDF
        yield from self.click('button[data-mode="compact"]', 1800)
        mark("compact")
        cols = yield from self.js("getComputedStyle(document.querySelector('.rows')).gridTemplateColumns.split(' ').length")
        log("compact mode lays rows out in 2 columns", cols == 2, cols)
        yield from self.click("#pdf", 0) if False else iter(())
        pdf = os.path.join(OUT, "Spanish sheet.pdf")
        self.dlg.export_pdf(pdf)  # same code path as the Export PDF button, minus the save dialog
        yield 2500
        ok = os.path.exists(pdf) and os.path.getsize(pdf) > 5000
        log("PDF export writes a file", ok, os.path.getsize(pdf) if os.path.exists(pdf) else None)

        # 10. hand off to normal study
        yield from self.click('button[data-mode="read"]', 500)
        yield from self.click('.dk[data-deck="%s"]' % GRAMMAR, 1500)
        before = mw.col.db.all("select id, mod, due, ivl, reps, lapses from cards")
        yield from self.click("#study", 600)
        self.dlg.lower()
        mw.raise_()
        yield 2600
        mark("study")
        log("Study this deck opens that deck's study screen in Anki",
            mw.state == "overview" and mw.col.decks.name(mw.col.decks.get_current_id()) == GRAMMAR,
            [mw.state, mw.col.decks.name(mw.col.decks.get_current_id())])
        log("no card was rescheduled by any of this",
            before == mw.col.db.all("select id, mod, due, ivl, reps, lapses from cards"))
        saved = mw.pm.profile.get("ankiSheets")
        log("last deck/mode is remembered for next time", bool(saved) and saved.get("deck") == GRAMMAR, saved)
        mark("end")
        yield 800
        mw.unloadProfileAndExit()


def start():
    os.makedirs(OUT, exist_ok=True)
    mw._sheets_driver = Driver()


gui_hooks.main_window_did_init.append(lambda: QTimer.singleShot(1500, start))
