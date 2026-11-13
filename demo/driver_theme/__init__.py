"""Checks the sidebar survives a theme add-on that restyles every button. Not part of the add-on."""
import json, os
from aqt import gui_hooks, mw
from aqt.qt import QTimer
OUT = os.path.join(os.environ.get("SHEETS_DEMO_OUT", "/tmp/sheets-shots"), "shots")
THEME = ("<style>button{background:#f3eee2!important;border:1px solid #e2dccd!important;border-radius:999px!important;"
         "box-shadow:0 2px 6px rgba(0,0,0,.14)!important;padding:8px 14px!important;margin:3px 4px!important;"
         "min-width:44px!important;min-height:40px!important;font-size:17px!important}</style>")
def theme(web_content, context):
    web_content.head += THEME
gui_hooks.webview_will_set_content.append(theme)
def start():
    os.makedirs(OUT, exist_ok=True)
    next(a for a in mw.form.menuTools.actions() if a.text() == "Sheets").trigger()
    from anki_sheets import dialog
    d = dialog._dialog
    d.setGeometry(0, 0, 1280, 800)
    def shot():
        d.web.grab().save(os.path.join(OUT, "theme.png"))
        js = ("(function(){var b=document.querySelector('.node .dk'),t=document.querySelector('.node .tw'),"
              "c=getComputedStyle(b),s=getComputedStyle(t);return JSON.stringify({dk:[c.borderRadius,c.boxShadow,c.backgroundColor,c.margin,c.padding],"
              "tw:[s.width,s.padding,s.boxShadow,s.margin]})})()")
        d.web.evalWithCallback(js, lambda r: (open(os.path.join(OUT, "theme.json"), "w").write(r or ""), QTimer.singleShot(300, mw.unloadProfileAndExit)))
    QTimer.singleShot(2500, lambda: (d.web.eval("Sheets.selectDeck(%s)" % json.dumps("Spanish")), QTimer.singleShot(2000, shot)))
gui_hooks.main_window_did_init.append(lambda: QTimer.singleShot(1500, start))
