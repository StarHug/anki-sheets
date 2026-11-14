"""Screenshot of the View panel in Anki's dark mode. Not part of the add-on."""
import json, os
from aqt import gui_hooks, mw
from aqt.qt import QTimer
OUT = os.path.join(os.environ.get("SHEETS_DEMO_OUT", "/tmp/sheets-shots"), "shots")
def start():
    os.makedirs(OUT, exist_ok=True)
    from aqt.theme import Theme, theme_manager
    mw.pm.set_theme(Theme.DARK); theme_manager.apply_style()
    next(a for a in mw.form.menuTools.actions() if a.text() == "IchiSheet").trigger()
    from anki_sheets import dialog
    d = dialog._dialog
    d.setGeometry(0, 0, 1280, 800)
    def view():
        d.web.eval("[].filter.call(document.querySelectorAll('.bar button'), function(b){return b.textContent.trim()==='View'})[0].click()")
        def about():
            d.web.grab().save(os.path.join(OUT, "dark-view.png"))
            d.web.eval("document.getElementById('view').click(); document.getElementById('about').click()")
            QTimer.singleShot(1000, lambda: (d.web.grab().save(os.path.join(OUT, "dark-about.png")), QTimer.singleShot(300, mw.unloadProfileAndExit)))
        QTimer.singleShot(1200, about)
    QTimer.singleShot(2500, lambda: (d.web.eval("Sheets.selectDeck(%s)" % json.dumps("Spanish")), QTimer.singleShot(2000, view)))
gui_hooks.main_window_did_init.append(lambda: QTimer.singleShot(1500, start))
