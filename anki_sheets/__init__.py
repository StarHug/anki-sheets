"""Sheets: read any deck as one scrollable page.

Tools > Sheets, or the gear menu next to a deck > View as Sheet.
"""

from __future__ import annotations

try:
    from aqt import gui_hooks, mw
except Exception:  # imported outside Anki (tests)
    mw = None

if mw is not None:
    from aqt.qt import QAction, QKeySequence

    from .dialog import open_sheet, close_sheet

    def _menu() -> None:
        action = QAction("Sheets", mw)
        action.setShortcut(QKeySequence("Ctrl+Shift+E"))
        action.triggered.connect(lambda: open_sheet())
        mw.form.menuTools.addAction(action)

    def _deck_menu(menu, deck_id: int) -> None:
        action = menu.addAction("View as Sheet")
        action.triggered.connect(lambda _=False, did=deck_id: open_sheet(did))

    _menu()
    gui_hooks.deck_browser_will_show_options_menu.append(_deck_menu)
    gui_hooks.profile_will_close.append(close_sheet)
