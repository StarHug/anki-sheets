"""Takes the screenshots for the store listing. Not part of the add-on."""
import json, os
from aqt import gui_hooks, mw
from aqt.qt import QTimer
from . import fake_ai
OUT = os.path.join(os.environ.get("SHEETS_DEMO_OUT", "/tmp/sheets-shots"), "shots")
JA = "Japanese::📗 Grammar::Particles"
KO = "Korean::📙 Grammar::Particles"
def start():
    os.makedirs(OUT, exist_ok=True)
    fake_ai.start(8765)
    user = mw.addonManager.getConfig("anki_sheets") or {}
    user["ai"] = dict(user.get("ai") or {}, enabled=True, provider="openai_compatible", base_url="http://127.0.0.1:8765/v1", model="stand-in")
    mw.addonManager.writeConfig("anki_sheets", user)
    next(a for a in mw.form.menuTools.actions() if a.text() == "IchiSheet").trigger()
    from anki_sheets import dialog
    d = dialog._dialog
    d.setGeometry(0, 0, 1280, 800)
    steps = [
        (2500, "Sheets.selectDeck(%s)" % json.dumps(JA), None),
        (2500, None, "1-read"),
        (300, "document.querySelector('button[data-mode=cover]').click(); setTimeout(function(){var r=document.querySelectorAll('.row'); r[0].click(); r[2].click();},300)", None),
        (1500, None, "2-cover"),
        (300, "document.querySelector('button[data-mode=read]').click(); document.querySelector('.cond').click()", None),
        (3000, None, "3-condense"),
        (300, "Sheets.selectDeck('General::Maths')", None),
        (3000, None, "4-formulas"),
        (300, "Sheets.selectDeck('Spanish'); setTimeout(function(){document.querySelector('button[data-mode=compact]').click()},1200)", None),
        (3000, None, "5-compact"),
        (300, "document.querySelector('button[data-mode=read]').click(); Sheets.state.view.ticks=true; Sheets.state.view.theme='paper'; Sheets.state.view.emphasis='tint'; Sheets.reload().then(function(){Sheets.selectDeck(%s)})" % json.dumps(KO), None),
        (3200, "document.querySelectorAll('.tick input')[0].click(); document.querySelectorAll('.tick input')[2].click(); document.getElementById('view').click()", None),
        (1500, None, "6-ticks-and-view"),
    ]
    def run(i=0):
        if i >= len(steps):
            QTimer.singleShot(300, mw.unloadProfileAndExit); return
        delay, js, shot = steps[i]
        def act():
            if js: d.web.eval(js)
            if shot: d.web.grab().save(os.path.join(OUT, shot + ".png"))
            run(i + 1)
        QTimer.singleShot(delay, act)
    run()
gui_hooks.main_window_did_init.append(lambda: QTimer.singleShot(1500, start))
