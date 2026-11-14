"""Demo driver for v0.3: notes and pictures, column divider, View menu,
review ticks, the never-send picker and Test connection. Runs inside real
Anki with the real mouse pointer and checks each step. Not part of the add-on."""

import json
import os
import time

from aqt import gui_hooks, mw
from aqt.qt import QCursor, QPoint, Qt, QTimer
from PyQt6.QtTest import QTest

from . import fake_ai

OUT = os.environ.get("SHEETS_DEMO_OUT", "/tmp/sheets-demo-view")
LOG = []
SPELLING = "Spanish::📘 Grammar::Spelling"
PHRASES = "Spanish::Phrasebook"
PORT = 8765


def log(name, ok, detail=None):
    LOG.append({"check": name, "ok": bool(ok), "detail": detail})
    with open(os.path.join(OUT, "checks.json"), "w") as f:
        json.dump(LOG, f, indent=1, ensure_ascii=False)


def mark(name):
    with open(os.path.join(OUT, "marks.txt"), "a") as f:
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
        for _ in range(tries):
            v = yield from self.js(code)
            if v:
                return v
            yield 50
        return None

    def point(self, selector):
        pt = yield from self.js(
            "(function(){var e=document.querySelector(%s); if(!e) return null;"
            "e.scrollIntoView({block:'nearest'}); var r=e.getBoundingClientRect();"
            "return [r.x+Math.min(r.width/2,140), r.y+Math.min(r.height/2,60)];})()" % json.dumps(selector))
        if not pt:
            log("element exists: " + selector, False)
            return None
        z = self.dlg.web.zoomFactor()
        return QPoint(int(pt[0] * z), int(pt[1] * z))

    def glide(self, pos, steps=10):
        target = self.target.mapToGlobal(pos)
        start = QCursor.pos()
        for i in range(1, steps + 1):
            t = i / steps
            QCursor.setPos(int(start.x() + (target.x() - start.x()) * t),
                           int(start.y() + (target.y() - start.y()) * t))
            yield 20
        QTest.mouseMove(self.target, pos)
        yield 150

    def click(self, selector, pause=800, double=False):
        pos = yield from self.point(selector)
        if pos is None:
            return
        yield from self.glide(pos)
        if double:
            QTest.mouseClick(self.target, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
            yield 130
            QTest.mouseClick(self.target, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
        else:
            QTest.mouseClick(self.target, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
        yield 220 + pause

    def drag(self, selector, dx, cursor=True):
        pos = yield from self.point(selector)
        if pos is None:
            return
        yield from self.glide(pos)
        QTest.mousePress(self.target, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
        yield 150
        p = pos
        for i in range(1, 15):
            p = QPoint(int(pos.x() + dx * i / 14), pos.y())
            if cursor:  # the on-screen pointer, for the recording; it reports no button held
                QCursor.setPos(self.target.mapToGlobal(p))
            QTest.mouseMove(self.target, p)
            yield 45
        QTest.mouseRelease(self.target, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, p)
        yield 700

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

    def qw(self):
        v = yield from self.js("document.querySelector('.main').style.getPropertyValue('--qw')")
        return v

    def script(self):
        from anki_sheets import dialog
        mw.setGeometry(0, 0, 1280, 800)
        QCursor.setPos(700, 500)
        yield 2000
        notes_before = mw.col.note_count()
        cards_before = mw.col.db.all("select id, mod, due, ivl, reps, lapses from cards")
        col_mod = mw.col.db.scalar("select mod from col")
        next(a for a in mw.form.menuTools.actions() if a.text() == "IchiSheet").trigger()
        yield 500
        self.dlg.setGeometry(0, 0, 1280, 800)
        yield 2200
        yield from self.js("Sheets.selectDeck(%s); 1" % json.dumps(SPELLING))
        yield 2000
        mark("start")

        # 1. notes collapse whatever the divider; a picture-only answer stays visible
        chips = yield from self.js("[].map.call(document.querySelectorAll('.chip'),function(e){return e.textContent}).join('|')")
        shown = yield from self.count(".row .ans > img")
        ticks = yield from self.count(".tick, .tickbar")
        log("notes collapse on both of card shapes; picture-only answer stays visible",
            chips == "Note + 2 images|Note + 1 image" and shown == 1, [chips, shown])
        log("default layout is clean: no tick boxes", ticks == 0, ticks)

        # 2. bigger pictures + click to enlarge
        yield from self.click(".group:nth-child(1) .row:nth-child(1) .chip", 1500)
        mark("images")
        w = yield from self.js("Math.round(document.querySelector('.group:nth-child(1) .row:nth-child(1) .extra img').getBoundingClientRect().width)")
        log("pictures inside a note fill the answer column", w and w >= 380, w)
        yield from self.click(".group:nth-child(1) .row:nth-child(1) .extra img", 1700)
        box = yield from self.js("(function(){var i=document.querySelector('.lightbox img'); return i? Math.round(i.getBoundingClientRect().height):0})()")
        log("clicking a picture opens it large over the sheet", box and box >= 600, box)
        yield from self.click(".lightbox img", 1500)
        full = yield from self.js("(function(){var i=document.querySelector('.lightbox img'); return i? Math.round(i.getBoundingClientRect().height):0})()")
        log("clicking again shows it at full size (940px tall)", full == 940, full)
        QTest.keyClick(self.target, Qt.Key.Key_Escape)
        yield 900
        gone = yield from self.count(".lightbox")
        log("Esc closes the picture", gone == 0, gone)
        yield from self.click(".group:nth-child(1) .row:nth-child(1) .chip", 500)
        yield from self.js("document.querySelector('.scroll').scrollTo({top:0}); 1")
        yield 500

        # 3. drag the column divider, then double-click to reset
        mark("divider")
        start = yield from self.qw()
        yield from self.drag(".group:nth-child(1) .row:nth-child(1) .split", -170)
        dragged = yield from self.qw()
        log("dragging the divider narrows the question column", start == "40%" and float(dragged.rstrip('%')) < 35, [start, dragged])
        yield 700
        yield from self.click(".group:nth-child(1) .row:nth-child(1) .split", 1200, double=True)
        reset = yield from self.qw()
        log("double-clicking the divider resets it", reset == "40%", reset)
        yield from self.drag(".group:nth-child(1) .row:nth-child(1) .split", -110)
        kept = yield from self.qw()

        # 3b. drag the deck list wider, double-click to reset, and search shows the deck's own name first
        W = "Math.round(document.querySelector('.side').getBoundingClientRect().width)"
        w0 = yield from self.js(W)
        yield from self.drag(".sidegrip", 150, cursor=False)
        w1 = yield from self.js(W)
        saved = yield from self.js("Sheets.state.view.side")
        log("dragging the deck list's edge widens it", w0 == 264 and 400 <= w1 <= 430 and saved == w1, [w0, w1, saved])
        yield from self.click(".sidegrip", 1200, double=True)
        w2 = yield from self.js(W)
        log("double-clicking the edge resets the deck list", w2 == 264, w2)
        F = "JSON.stringify([document.querySelectorAll('.row').length, [].filter.call(document.querySelectorAll('.row'), function(r){return r.offsetParent}).length])"
        f0 = json.loads((yield from self.js(F)))
        yield from self.click(".ghead .fold", 500)
        f1 = json.loads((yield from self.js(F)))
        yield from self.click(".ghead .fold", 500)
        f2 = json.loads((yield from self.js(F)))
        log("clicking a section title folds its cards away and back", f0[1] == f0[0] and 0 < f1[1] < f0[1] or (f1[1] == 0 and f0[1] > 0) and f2 == f0, [f0, f1, f2])
        P = "Math.round(document.querySelector('.pagewrap').getBoundingClientRect().width)"
        p0 = yield from self.js(P)
        yield from self.drag(".pagegrip", -200, cursor=False)
        p1 = yield from self.js(P)
        yield from self.click(".pagegrip", 1200, double=True)
        p2 = yield from self.js(P)
        log("dragging the sheet's right edge changes its width, double-click resets it", p1 < p0 - 150 and p2 == p0, [p0, p1, p2])
        yield from self.js("var i=document.querySelector('.side input'); i.value='partic'; i.dispatchEvent(new Event('input')); 1")
        yield 400
        hit = yield from self.js("var d=document.querySelector('.tree ul .dk span'); JSON.stringify([d.firstChild.textContent, d.querySelector('.path').textContent])")
        log("deck search shows the deck's own name first, its parents underneath", json.loads(hit)[0] == "Particles" and "Grammar" in json.loads(hit)[1], hit)
        yield from self.js("var i=document.querySelector('.side input'); i.value=''; i.dispatchEvent(new Event('input')); 1")

        yield from self.click("#about", 500)
        ab = yield from self.js("var a=document.querySelector('.about'); a ? a.textContent : ''")
        yield from self.click("#about-close", 400)
        gone = yield from self.js("!document.querySelector('.about')")
        log("clicking the logo opens an About card, and Close dismisses it",
            "Made by StarHug" in ab and "buy me a coffee" in ab and gone, ab[:120])
        yield from self.js("pycmd('sheets:not_a_real_command:{}'); 1")
        yield 400
        import aqt.utils
        tip = getattr(aqt.utils, "_tooltipLabel", None)
        alive = yield from self.js("document.querySelectorAll('.row').length > 0")
        log("a command the running code does not know asks for a restart instead of crashing",
            bool(tip) and "Restart Anki" in tip.text() and alive, tip.text() if tip else None)

        # 4. View menu: spacing, emphasis, theme
        yield from self.click("#view", 1200)
        mark("view")
        yield from self.click('.viewpanel button[data-density="tight"]', 1100)
        yield from self.click('.viewpanel button[data-emphasis="tint"]', 1300)
        yield from self.click('.viewpanel button[data-emphasis="answer"]', 1300)
        yield from self.click('.viewpanel button[data-theme="paper"]', 1500)
        yield from self.click('.viewpanel button[data-theme="contrast"]', 1500)
        cls = yield from self.js("document.getElementById('app').className + ' / ' + document.querySelector('.main').className")
        log("View menu applies spacing, emphasis and theme", cls == "theme-contrast / main mode-read em-answer dense", cls)
        yield from self.click('.viewpanel button[data-theme="paper"]', 900)
        yield from self.click('.viewpanel button[data-emphasis="tint"]', 900)
        yield from self.click("#v-notes", 1500)
        open_notes = yield from self.count(".extra:not([hidden])")
        log("Show notes expanded opens every note", open_notes == 2, open_notes)
        yield from self.click("#v-notes", 700)

        hints = yield from self.js("[].filter.call(document.querySelectorAll('.bar button, .bar input, .viewpanel button, .viewpanel .vrow, .viewpanel .check'),function(e){return !e.title}).length")
        small = yield from self.text(".viewpanel .check.explained small")
        box = yield from self.js("getComputedStyle(document.getElementById('v-notes')).backgroundColor")
        log("every toolbar and View control has a hover hint; unclear options have a written explanation",
            hints == 0 and small.startswith("Extra notes and pictures on a card normally sit behind"), [hints, small])
        log("an unticked box is drawn empty in the Paper theme", box == "rgb(250, 246, 236)", box)

        # 5. review ticks: opt-in
        yield from self.click("#v-ticks", 1200)
        mark("ticks")
        yield from self.click("#view", 900)
        bar = yield from self.text(".tickcount")
        boxes = yield from self.count(".tick input")
        log("turning Review ticks on adds tick boxes and a count", bar == "0 of 3 ticked" and boxes == 3, [bar, boxes])
        yield from self.click(".group:nth-child(1) .row:nth-child(1) .tick input", 900)
        yield from self.click(".group:nth-child(2) .row:nth-child(1) .tick input", 1100)
        bar = yield from self.text(".tickcount")
        path = os.path.join(os.path.dirname(dialog.__file__), "user_files", "ticks.json")
        saved = json.load(open(path)) if os.path.exists(path) else None
        log("ticking two rows: count updates and ticks are saved to the add-on folder",
            bar == "2 of 3 ticked" and saved and len(saved) == 2, [bar, saved])
        yield from self.click("#hide-ticked", 1500)
        visible = yield from self.count(".row:not([hidden])")
        log("Hide ticked leaves only the unticked row", visible == 1, visible)
        yield from self.click("#hide-ticked", 900)
        yield from self.js("Sheets.reload(); 1")
        yield 1800
        again = yield from self.text(".tickcount")
        log("ticks are remembered after a reload", again == "2 of 3 ticked", again)
        yield from self.click("#ticks-reset", 1400)
        bar = yield from self.text(".tickcount")
        saved = json.load(open(path))
        log("Reset ticks clears them", bar == "0 of 3 ticked" and saved == [], [bar, saved])
        yield from self.click(".group:nth-child(1) .row:nth-child(1) .tick input", 600)
        yield from self.click("#view", 900)
        yield from self.click("#v-ticks", 1300)
        boxes = yield from self.count(".tick input, .tickbar")
        still = json.load(open(path))
        log("turning ticks off hides them but keeps what was ticked", boxes == 0 and len(still) == 1, [boxes, still])
        yield from self.click("#view", 700)

        # 6. AI settings: deck picker and Test connection
        yield from self.click("#aiset", 1300)
        mark("settings")
        preset = yield from self.js("var s=document.getElementById('ai-provider'); s.value='openai'; s.dispatchEvent(new Event('change'));"
                                    "JSON.stringify([document.getElementById('ai-base').value, document.getElementById('ai-base').closest('.field').hidden, s.options.length])")
        log("choosing OpenAI fills in its address and hides the address box", json.loads(preset) == ["https://api.openai.com/v1", True, 7], preset)
        yield from self.js("var s=document.getElementById('ai-provider'); s.value='custom';"
                           "s.dispatchEvent(new Event('change')); 1")
        yield 500
        yield from self.click("#ai-model", 100)
        yield from self.type("stand-in", 30)
        yield from self.click("#ai-base", 100)
        yield from self.type("http://127.0.0.1:%d/v1" % PORT, 22)
        yield from self.click("#ai-test", 300)
        yield from self.wait("document.querySelector('.test-status.ok, .test-status.bad')")
        yield 1500
        status = yield from self.text(".test-status")
        body = json.dumps([r["body"] for r in fake_ai.requests])
        log("Test connection reports success and sends no card text",
            status == "Connected. The AI replied." and len(fake_ai.requests) == 1 and "Accents" not in body and "Cards:" not in body, [status, len(fake_ai.requests)])
        rows_all = yield from self.count(".never-row")
        yield from self.click("#never-search", 100)
        yield from self.type("phrase", 40)
        yield 700
        found = yield from self.count(".never-row")
        log("the picker lists every deck and search narrows it", rows_all == 23 and found == 2, [rows_all, found])
        yield from self.click('.never-list input[data-deck="%s"]' % PHRASES, 1500)
        item = yield from self.text(".never-item span")
        covered = yield from self.js("(function(){var b=document.querySelectorAll('.never-list input'); return b[1].checked && b[1].disabled})()")
        log("ticking a deck lists it, and its sub-deck shows as covered", item == "Spanish › Phrasebook" and covered, [item, covered])
        fits = yield from self.js("[].every.call(document.querySelectorAll('.modal .btn'),function(b){return b.scrollWidth<=b.clientWidth+1 && b.getBoundingClientRect().height<=40})")
        log("no button text overflows in AI settings", fits, fits)
        yield from self.click("#ai-save", 1600)
        cfg = mw.addonManager.getConfig("anki_sheets")["ai"]
        log("the never-send choice is saved", cfg["never_send_decks"] == [PHRASES], cfg["never_send_decks"])

        # 7. sound buttons play through Anki's own audio player
        from aqt.sound import av_player
        played = []
        av_player.play_tags = lambda tags: played.extend(t.filename for t in tags)
        yield from self.click('.dk[data-deck="General"]', 900)
        yield from self.click('.dk[data-deck="General::Listening"]', 1700)
        mark("sound")
        n = yield from self.count(".snd")
        yield from self.click(".row:nth-child(1) .q .snd", 1200)
        yield from self.click(".row:nth-child(1) .a .snd", 1200)
        log("cards with audio get play buttons that use Anki's audio player; a missing file is not played",
            n == 3 and played == ["hola.mp3"], [n, played])

        # general-use checks: formulas, plain-tag sections, image occlusion, the fields screen
        yield from self.click('.dk[data-deck="General::Maths"]', 2600)
        mark("maths")
        heads = yield from self.js("[].map.call(document.querySelectorAll('.group h3'),function(e){return e.textContent}).join('|')")
        maths = yield from self.wait("document.querySelectorAll('.row mjx-container').length >= 6 && document.querySelectorAll('.row mjx-container').length")
        raw = yield from self.js("/\\\\\\(|\\\\frac/.test(document.querySelector('.page').innerText)")
        log("formulas are typeset, and plain tags make the sections when there is no topic:: family",
            heads == "Algebra|Calculus" and maths == 6 and not raw, [heads, maths, raw])
        yield from self.click('.dk[data-deck="General::Anatomy"]', 2200)
        badges = yield from self.js("[].map.call(document.querySelectorAll('.badge.lock'),function(e){return e.textContent}).join('|')")
        rows = yield from self.count(".row")
        pics = yield from self.js("[].filter.call(document.querySelectorAll('.row .ans img'),function(i){return i.naturalWidth>0}).length")
        log("image occlusion cards show their picture once, with a mask count", rows == 2 and badges == "2 masks|3 masks" and pics == 2, [rows, badges, pics])

        yield from self.js("Sheets.selectDeck(%s); 1" % json.dumps(SPELLING))
        yield 1600
        yield from self.click("#view", 900)
        yield from self.click("#fields", 1300)
        mark("fields")
        yield from self.js("(function(){var s=document.querySelectorAll('.ftype select'); s[0].value='Back'; s[0].dispatchEvent(new Event('change')); "
                           "s=document.querySelectorAll('.ftype select'); s[1].value='Front'; s[1].dispatchEvent(new Event('change')); return 1})()")
        yield 1200
        yield from self.click("#fields-save", 1800)
        swapped = yield from self.text(".group:nth-child(1) .row:nth-child(1) .ans")
        cfg = mw.addonManager.getConfig("anki_sheets")["note_types"]
        log("the Card fields screen swaps which field is the question, and saves the choice",
            swapped.startswith("Accents") and cfg == {"Basic+": {"prompt": "Back", "answer": "Front"}}, [swapped, cfg])
        yield from self.click("#view", 800)
        yield from self.click("#fields", 1000)
        yield from self.click(".ftype > .btn", 700)
        yield from self.click("#fields-save", 1600)
        back = yield from self.text(".group:nth-child(1) .row:nth-child(1) .q")
        log("Back to automatic restores the default", back.startswith("Accents") and mw.addonManager.getConfig("anki_sheets")["note_types"] == {}, back)

        # the Sections choice is per deck, inherited by sub-decks
        yield from self.js("Sheets.selectDeck('Spanish::📘 Grammar'); 1")
        yield 1600
        yield from self.click("#view", 800)
        yield from self.js("var g=document.getElementById('group'); g.value='none'; g.dispatchEvent(new Event('change')); 1")
        yield 1600
        mark("sections")
        grammar_groups = yield from self.count(".group h3")
        yield from self.click("#view", 500)
        yield from self.js("Sheets.selectDeck(%s); 1" % json.dumps(SPELLING))
        yield 1500
        child = yield from self.count(".group h3")
        yield from self.js("Sheets.selectDeck('General::Maths'); 1")
        yield 1800
        other = yield from self.js("[].map.call(document.querySelectorAll('.group h3'),function(e){return e.textContent}).join('|')")
        saved_groups = mw.pm.profile["ankiSheets"].get("groups")
        log("No sections chosen on one deck applies to its sub-decks and leaves other decks alone",
            grammar_groups == 0 and child == 0 and other == "Algebra|Calculus" and saved_groups == {"Spanish::📘 Grammar": "none"}, [grammar_groups, child, other, saved_groups])
        yield from self.js("Sheets.selectDeck('Spanish::📘 Grammar'); 1")
        yield 1500
        yield from self.click("#view", 700)
        yield from self.js("var g=document.getElementById('group'); g.value='auto'; g.dispatchEvent(new Event('change')); 1")
        yield 1500
        yield from self.click("#view", 500)
        log("switching back to Automatic clears the saved choice", mw.pm.profile["ankiSheets"].get("groups") == {}, mw.pm.profile["ankiSheets"].get("groups"))

        # one button puts every layout choice back to the defaults
        keep_view = dict(mw.pm.profile["ankiSheets"]["view"])
        yield from self.js("Sheets.selectDeck('Spanish::📘 Grammar'); 1")
        yield 1400
        yield from self.click("#view", 700)
        yield from self.js("var g=document.getElementById('group'); g.value='none'; g.dispatchEvent(new Event('change')); 1")
        yield 1400
        yield from self.click("#view-reset", 900)
        armed = yield from self.text("#view-reset")
        still = mw.pm.profile["ankiSheets"]["view"].get("theme")
        yield from self.click("#view-reset", 1800)
        mark("reset")
        st = mw.pm.profile["ankiSheets"]
        cls = yield from self.js("document.getElementById('app').className + ' / ' + document.querySelector('.main').className")
        log("Reset view to defaults asks once, then clears layout choices and per-deck sections",
            armed == "Click again to reset" and still == "paper" and st["groups"] == {} and st["view"]["theme"] == "anki"
            and st["view"]["split"] is None and cls == "theme-anki / main mode-read em-question", [armed, still, st["groups"], st["view"], cls])
        yield from self.click("#view", 500)
        yield from self.js("Object.assign(Sheets.state.view, %s); Sheets.reload(); 1" % json.dumps(keep_view))
        yield 1500
        mw.pm.profile["ankiSheets"] = dict(mw.pm.profile["ankiSheets"], view=keep_view)

        # 8. loading never sticks: errors are shown with a retry, and quick clicks load only the last deck
        from anki_sheets import sheet as core
        real, calls = core.build_sheet, []
        def flaky(col, *a, **k):
            calls.append(k.get("deck_name"))
            if len(calls) == 1:
                raise RuntimeError("simulated failure")
            return real(col, *a, **k)
        core.build_sheet = flaky
        yield from self.click('.dk[data-deck="General"]', 1500)
        mark("error")
        err = yield from self.text("#load-error span")
        yield from self.click("#load-error button", 1500)
        rows = yield from self.count(".row")
        log("a failed load shows a message with Try again instead of staying on Loading",
            "could not be loaded (RuntimeError: simulated failure)" in err and rows == 10, [err, rows])
        del calls[:]
        yield from self.js("Sheets.selectDeck('Spanish'); Sheets.selectDeck('General'); Sheets.selectDeck('Spanish::📘 Grammar'); Sheets.selectDeck(%s); 1" % json.dumps(SPELLING))
        yield 2500
        title = yield from self.text(".head h1")
        log("clicking through four decks quickly loads two pages, not four, and ends on the last one",
            len(calls) == 2 and calls[-1] == SPELLING and title == "Spelling", [calls, title])
        core.build_sheet = real

        # a page that never finished opening is not reopened next time
        saved = dict(mw.pm.profile["ankiSheets"])
        mw.pm.profile["ankiSheets"] = dict(saved, pending=SPELLING)
        self.dlg.reject()
        yield 500
        next(a for a in mw.form.menuTools.actions() if a.text() == "IchiSheet").trigger()
        yield 500
        self.dlg.setGeometry(0, 0, 1280, 800)
        yield 2200
        note = yield from self.text("#recovered")
        rows = yield from self.count(".row")
        log("after an unfinished load, IchiSheet starts on the start page and says why", rows == 0 and "did not finish opening" in note, [rows, note])
        yield from self.js("Sheets.selectDeck(%s); 1" % json.dumps(SPELLING))
        yield 1800
        hover = yield from self.js("document.querySelector('.head .meta').title")
        log("the sheet reports how long Anki took to read the cards", hover.startswith("Read from Anki in "), hover)
        mw.pm.profile["ankiSheets"] = dict(mw.pm.profile["ankiSheets"], view=saved["view"])

        view = mw.pm.profile.get("ankiSheets", {}).get("view", {})
        log("view choices are remembered for next time",
            view.get("theme") == "paper" and view.get("emphasis") == "tint" and view.get("density") == "tight"
            and view.get("ticks") is False and str(view.get("split")) + "%" == kept, [view, kept])
        log("no card, note or collection change during any of this",
            cards_before == mw.col.db.all("select id, mod, due, ivl, reps, lapses from cards")
            and mw.col.note_count() == notes_before and col_mod == mw.col.db.scalar("select mod from col"))
        mark("end")
        yield 1200
        mw.unloadProfileAndExit()


def start():
    os.makedirs(OUT, exist_ok=True)
    fake_ai.start(PORT)
    mw._sheets_driver = Driver()


gui_hooks.main_window_did_init.append(lambda: QTimer.singleShot(1500, start))
