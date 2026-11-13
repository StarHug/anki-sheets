"""Demo driver for the AI features: runs inside real Anki, clicks through
AI settings, Condense, Ask and the never-send list with the real mouse
pointer, and checks what is on screen and what was sent at each step.

The "AI" here is tests/fake_ai.py, a local stand-in server with canned
answers. Not part of the add-on."""

import json
import os
import time

import aqt
from aqt import gui_hooks, mw
from aqt.qt import QCursor, QPoint, Qt, QTimer
from PyQt6.QtTest import QTest

from . import fake_ai

OUT = os.environ.get("SHEETS_DEMO_OUT", "/tmp/sheets-demo-ai")
LOG = []
GRAMMAR = "Spanish::📘 Grammar::Ser and Estar"
PHRASES = "Spanish::Phrasebook"
PORT = 8765


def log(name, ok, detail=None):
    LOG.append({"check": name, "ok": bool(ok), "detail": detail})
    with open(os.path.join(OUT, "checks.json"), "w") as f:
        json.dump(LOG, f, indent=1, ensure_ascii=False)


def mark(name):
    with open(os.path.join(OUT, "marks.txt"), "a") as f:
        f.write("%.2f\t%s\n" % (time.time(), name))


def sent():
    return json.dumps([r["body"] for r in fake_ai.requests], ensure_ascii=False)


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
        except Exception:
            import traceback
            log("driver crashed", False, traceback.format_exc())
            QTimer.singleShot(500, mw.unloadProfileAndExit)
            return
        QTimer.singleShot(int(delay), self.step)

    @property
    def dlg(self):
        from anki_sheets import dialog
        return dialog._dialog

    @property
    def target(self):
        return self.dlg.web.focusProxy() or self.dlg.web

    def js(self, code):
        self.box.pop("v", None)
        self.dlg.web.evalWithCallback(code, lambda v: self.box.__setitem__("v", v))
        for _ in range(100):
            if "v" in self.box:
                break
            yield 30
        return self.box.get("v")

    def wait(self, code, tries=120):
        """Poll until a JS expression is truthy."""
        for _ in range(tries):
            v = yield from self.js(code)
            if v:
                return v
            yield 50
        return None

    def glide(self, widget, pos):
        target = widget.mapToGlobal(pos)
        start = QCursor.pos()
        for i in range(1, 11):
            t = i / 10
            QCursor.setPos(int(start.x() + (target.x() - start.x()) * t),
                           int(start.y() + (target.y() - start.y()) * t))
            yield 20
        QTest.mouseMove(widget, pos)
        yield 160

    def click(self, selector, pause=800):
        pt = yield from self.js(
            "(function(){var e=document.querySelector(%s); if(!e) return null;"
            "e.scrollIntoView({block:'nearest'}); var r=e.getBoundingClientRect();"
            "return [r.x+Math.min(r.width/2,140), r.y+r.height/2];})()" % json.dumps(selector))
        if not pt:
            log("element exists: " + selector, False)
            return
        z = self.dlg.web.zoomFactor()
        pos = QPoint(int(pt[0] * z), int(pt[1] * z))
        yield from self.glide(self.target, pos)
        QTest.mouseClick(self.target, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
        yield 220 + pause

    def type(self, text, per=45):
        for ch in text:
            QTest.keyClicks(self.target, ch)
            yield per
        yield 250

    def text(self, selector):
        v = yield from self.js("(document.querySelector(%s)||{}).textContent||''" % json.dumps(selector))
        return v

    def count(self, selector):
        v = yield from self.js("document.querySelectorAll(%s).length" % json.dumps(selector))
        return v

    def script(self):
        mw.setGeometry(0, 0, 1280, 800)
        QCursor.setPos(700, 500)
        yield 2000
        notes_before = mw.col.note_count()
        cards_before = mw.col.db.all("select id, mod, due, ivl, reps, lapses from cards")
        next(a for a in mw.form.menuTools.actions() if a.text() == "Sheets").trigger()
        yield 500
        self.dlg.setGeometry(0, 0, 1280, 800)
        yield 2200
        yield from self.js("Sheets.selectDeck(%s); 1" % json.dumps(GRAMMAR))
        yield 1800
        mark("start")

        # 1. AI is off by default: nothing AI on screen, nothing sent
        n = yield from self.count("#ask, .cond")
        log("AI off by default: no Ask or Condense buttons", n == 0, n)

        # 2. turn it on in AI settings
        yield from self.click("#aiset", 1400)
        mark("settings")
        yield from self.click("#ai-on", 500)
        yield from self.js("var s=document.getElementById('ai-provider'); s.value='custom';"
                           "s.dispatchEvent(new Event('change')); 1")
        yield 700
        yield from self.click("#ai-model", 100)
        yield from self.type("stand-in")
        yield from self.click("#ai-base", 100)
        yield from self.type("http://127.0.0.1:%d/v1" % PORT, 30)
        yield 900
        yield from self.click("#ai-save", 1500)
        n_cond = yield from self.count(".cond")
        n_ask = yield from self.count("#ask")
        log("after turning AI on: Condense on the 9-card section only, Ask in the toolbar", n_cond == 1 and n_ask == 1, [n_cond, n_ask])
        log("turning AI on sends nothing by itself", len(fake_ai.requests) == 0, len(fake_ai.requests))

        # 3. condense the Verbs section
        yield from self.click(".cond", 300)
        mark("condense")
        yield from self.wait("document.querySelector('.sum table')")
        yield 2200
        rows = yield from self.count(".sum tbody tr")
        intro = yield from self.text(".sum-intro")
        note = yield from self.text(".sum .sum-note")
        log("Condense shows an intro, a 4-row table and the gap notice",
            rows == 4 and intro.startswith("Ser says what something is") and "Estar in the present tense, Past tenses" in note, [rows, intro, note])
        body = sent()
        log("one request, with the 9 Verbs cards as plain text (no pictures, no other section)",
            len(fake_ai.requests) == 1 and "[9] " in body and "[10] " not in body and "<img" not in body
            and "verb-table" not in body and "definite article" not in body and "[image]" in body, len(fake_ai.requests))
        bold = yield from self.count(".sum td strong")
        log("AI text renders bold safely", bold == 1, bold)
        yield from self.click(".sum tbody tr:nth-child(3) .src", 1900)
        hits = yield from self.count(".row.hit")
        log("a row's source link highlights the 3 cards it came from", hits == 3, hits)
        yield from self.js("document.querySelector('.scroll').scrollTo({top:0,behavior:'smooth'}); 1")
        yield 900

        # 4. ask
        yield from self.click("#ask", 1300)
        mark("ask")
        will = yield from self.text(".ask-will")
        log("Ask panel states what will be sent", will == "Will send: Ser and Estar · 10 cards", will)
        yield from self.click(".ask-input", 100)
        yield from self.type("What's the difference between ser and estar?", 28)
        yield from self.click(".send", 200)
        yield from self.wait("document.querySelector('.srcchip')")
        yield 2600
        chips = yield from self.count(".srcchip")
        hits = yield from self.count(".row.hit")
        log("answer from the cards lists its 3 source cards and highlights them", chips == 3 and hits == 3, [chips, hits])

        yield from self.click(".ask-input", 100)
        yield from self.type("When do you use the subjunctive?", 28)
        yield from self.click(".send", 200)
        yield from self.wait("document.querySelector('.msg .tag')")
        yield 2400
        mark("general")
        tag = yield from self.text(".msg .tag")
        log("answer beyond the cards is labelled as general knowledge", tag == "Not in your cards · general knowledge", tag)

        # 5. make a card from it: Anki's own Add window, pre-filled, nothing saved
        yield from self.click(".mk", 1800)
        mark("makecard")
        add = aqt.dialogs._dialogs["AddCards"][1]
        fields = list(add.editor.note.fields) if add else None
        log("Make a card opens Anki's Add window pre-filled",
            bool(add) and fields[0] == "When do you use the subjunctive?" and fields[1].startswith("It expresses wishes"), fields)
        log("no note was added without confirmation", mw.col.note_count() == notes_before, mw.col.note_count())
        yield 2200
        if add:
            add._close()
        yield 600
        self.dlg.raise_()
        yield 900

        # 6. stick to my cards
        yield from self.click("#strict", 500)
        yield from self.click(".ask-input", 100)
        yield from self.type("When do you use the subjunctive?", 22)
        yield from self.click(".send", 200)
        yield from self.wait("document.querySelectorAll('.msg .tag').length === 2")
        yield 2400
        mark("strict")
        tags = yield from self.js("[].map.call(document.querySelectorAll('.msg .tag'),function(e){return e.textContent}).join('|')")
        log("with Stick to my cards, it says the cards don't cover it", tags.endswith("|Not in your cards"), tags)

        label = yield from self.text(".ask-foot .check span")
        yield from self.click("#newchat", 1300)
        left = yield from self.count(".msg")
        log("New chat clears the conversation; the checkbox says what it limits", left == 0 and label == "Answer only from my cards", [left, label])

        # 7. never-send list
        yield from self.click('.dk[data-deck="%s"]' % PHRASES, 1500)
        mark("private")
        yield from self.click("#aiset", 1200)
        yield from self.click("#never-search", 100)
        yield from self.type("phrase", 40)
        yield 600
        yield from self.click('.never-list input[data-deck="%s"]' % PHRASES, 1300)
        yield from self.click("#ai-save", 1700)
        conds = yield from self.count(".cond")
        will = yield from self.text(".ask-will")
        notice = yield from self.text("#private-note")
        log("a never-send deck offers no Condense and sends 0 cards",
            conds == 0 and will.endswith("· 0 cards") and "never-send list" in notice, [conds, will, notice])
        yield 600
        yield from self.click('.dk[data-deck="Spanish"]', 2000)
        will = yield from self.text(".ask-will")
        sub = yield from self.text(".ask-sub")
        lock = yield from self.text(".badge.lock")
        log("parent deck: 13 of 17 cards would be sent, 4 private ones left out, deck is labelled",
            will == "Will send: Spanish · 13 cards" and "4 cards in never-send decks left out" in sub and lock == "never sent to AI", [will, sub, lock])
        fake_ai.requests.clear()
        yield from self.click(".ask-input", 100)
        yield from self.type("Summarise these", 28)
        yield from self.click(".send", 200)
        yield from self.wait("document.querySelector('.srcchip')")
        yield 1800
        body = sent()
        log("the request really leaves the private deck out",
            len(fake_ai.requests) == 1 and "Restaurant" not in body and "[13] " in body and "[14] " not in body, len(fake_ai.requests))

        # 8. saved summary comes back without a new request; hidden in cover mode
        fake_ai.requests.clear()
        yield from self.click('.dk[data-deck="%s"]' % GRAMMAR, 1900)
        mark("saved")
        rows = yield from self.count(".sum tbody tr")
        log("the summary is saved: reopening the deck shows it with no new request", rows == 4 and len(fake_ai.requests) == 0, [rows, len(fake_ai.requests)])
        yield from self.click('button[data-mode="cover"]', 1300)
        shown = yield from self.js("getComputedStyle(document.querySelector('.sum')).display")
        log("Cover answers hides the summary so it can't give answers away", shown == "none", shown)
        yield from self.click('button[data-mode="read"]', 900)

        from anki_sheets import dialog
        path = os.path.join(os.path.dirname(dialog.__file__), "user_files", "summaries.json")
        cfg = mw.addonManager.getConfig("anki_sheets")["ai"]
        log("summary lives in the add-on's user_files, settings in add-on config",
            os.path.exists(path) and cfg["enabled"] and cfg["never_send_decks"] == [PHRASES], cfg)
        log("no card or note changed during any of this",
            cards_before == mw.col.db.all("select id, mod, due, ivl, reps, lapses from cards")
            and mw.col.note_count() == notes_before)
        mark("end")
        yield 900
        mw.unloadProfileAndExit()


def start():
    os.makedirs(OUT, exist_ok=True)
    fake_ai.start(PORT)
    mw._sheets_driver = Driver()


gui_hooks.main_window_did_init.append(lambda: QTimer.singleShot(1500, start))
