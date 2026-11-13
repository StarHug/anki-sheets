from __future__ import annotations

import json
import os
from typing import Any

import aqt
from aqt import mw
from aqt.qt import QDialog, QMarginsF, QPageLayout, QPageSize, Qt, QVBoxLayout
from aqt.utils import getSaveFile, restoreGeom, saveGeom, tooltip
from aqt.webview import AnkiWebView

from . import ai, sheet

ADDON = __name__.split(".")[0]
HERE = os.path.dirname(__file__)
_dialog: "SheetDialog | None" = None


def _read(name: str) -> str:
    with open(os.path.join(HERE, "web", name), encoding="utf-8") as f:
        return f.read()


def config() -> dict:
    user = mw.addonManager.getConfig(ADDON) or {}
    cfg = {**sheet.DEFAULT_CONFIG, **user}
    cfg["ai"] = ai.merged(user.get("ai"))
    return cfg


def mathjax_scripts() -> list[str]:
    """Anki's own copy of MathJax, so formulas on cards render as they do in review."""
    try:
        from aqt.utils import aqt_data_path

        base = str(aqt_data_path())
    except Exception:
        try:
            from aqt.utils import aqt_data_folder

            base = aqt_data_folder()
        except Exception:
            return []
    for name in ("tex-chtml-full.js", "tex-chtml.js"):
        if os.path.exists(os.path.join(base, "web", "js", "vendor", "mathjax", name)):
            return ["js/mathjax.js", "js/vendor/mathjax/" + name]
    return []


def save_ai(ai_cfg: dict) -> None:
    user = mw.addonManager.getConfig(ADDON) or {}
    user["ai"] = ai_cfg
    mw.addonManager.writeConfig(ADDON, user)


def store() -> ai.SummaryStore:
    return ai.SummaryStore(os.path.join(HERE, "user_files", "summaries.json"))


def ticks() -> ai.TickStore:
    return ai.TickStore(os.path.join(HERE, "user_files", "ticks.json"))


def summary_key(deck_id: int, prefix: str | None, key: str) -> str:
    return "%s|%s|%s" % (deck_id, prefix or "", key)


def group_fingerprint(nids: list[int]) -> str:
    ids = ",".join(str(int(n)) for n in nids)
    return ai.fingerprint([tuple(r) for r in mw.col.db.all("select id, mod from notes where id in (%s)" % ids)])


def _where(c: dict) -> tuple:
    """Which server a saved key belongs to."""
    return (c.get("provider"), (c.get("base_url") or "").strip().rstrip("/"))


class SheetDialog(QDialog):
    def __init__(self, deck_id: int | None = None) -> None:
        super().__init__(None, Qt.WindowType.Window)
        self.setWindowTitle("Sheets")
        self.resize(1180, 800)
        restoreGeom(self, "ankiSheets")
        self.initial_deck = mw.col.decks.name(deck_id) if deck_id else None
        self.web = AnkiWebView(parent=self, title="sheets")
        self.web.set_bridge_command(self.on_cmd, self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.web)
        self.web.stdHtml(
            '<div id="app"></div><script>%s</script>' % _read("sheet.js"),
            head="<style>%s</style>" % _read("sheet.css"),
            js=mathjax_scripts(),
            context=self,
        )

    # ------------------------------------------------------------ bridge

    def on_cmd(self, cmd: str) -> Any:
        if not cmd.startswith("sheets:"):
            return None
        _, name, *rest = cmd.split(":", 2)
        try:
            arg = json.loads(rest[0]) if rest and rest[0] else {}
            return getattr(self, "cmd_" + name)(arg)
        except Exception as e:
            # never leave the page waiting on a reply: hand the problem back so it can be shown
            import traceback

            traceback.print_exc()
            return {"__error": "%s: %s" % (type(e).__name__, e)}

    def ai_public(self) -> dict:
        """AI settings for the page. The API key itself never goes to the page."""
        c = config()["ai"]
        return {
            "enabled": bool(c["enabled"]),
            "ready": ai.ready(c),
            "provider": c["provider"],
            "model": c["model"],
            "default_model": ai.DEFAULT_MODELS.get(c["provider"], ""),
            "base_url": c["base_url"],
            "has_key": bool(c["api_key"]),
            "max_cards": int(c["max_cards"]),
            "never_send_decks": list(c["never_send_decks"]),
        }

    def cmd_init(self, arg: dict) -> dict:
        state = dict(mw.pm.profile.get("ankiSheets", {}))
        if self.initial_deck:
            state["deck"] = self.initial_deck
        return {"tree": sheet.deck_tree(mw.col), "state": state, "ai": self.ai_public()}

    def cmd_load(self, arg: dict) -> dict:
        import time

        started = time.time()
        data = sheet.build_sheet(
            mw.col,
            deck_name=arg.get("deck") or None,
            scope=arg.get("scope", "all"),
            group=arg.get("group", "auto"),
            limit=arg.get("limit"),
            cfg=config(),
            max_chars=arg.get("max_chars"),
        )
        data["max_chars"] = int(arg.get("max_chars") or config()["max_chars"])
        data["ms"] = int((time.time() - started) * 1000)
        done = ticks().ids
        if done:
            for deck in data["decks"]:
                for g in deck["groups"]:
                    for r in g["rows"]:
                        if r["nid"] in done:
                            r["ticked"] = True
        saved = store()
        if data["scope"] == "all" and saved.data:
            for deck in data["decks"]:
                for g in deck["groups"]:
                    hit = saved.get(summary_key(deck["id"], deck["grouped_by"], g["key"]))
                    if hit:
                        nids = [r["nid"] for r in g["rows"]]
                        g["summary"] = hit["summary"]
                        g["stale"] = hit["fp"] != group_fingerprint(nids)
        return data

    def cmd_state(self, arg: dict) -> None:
        mw.pm.profile["ankiSheets"] = arg

    def cmd_fields_save(self, arg: dict) -> None:
        """Per-note-type choice of which field is the question, which the answer, and which to hide."""
        user = mw.addonManager.getConfig(ADDON) or {}
        types = dict(user.get("note_types") or {})
        for name, choice in (arg.get("types") or {}).items():
            if not choice or not (choice.get("prompt") or choice.get("answer") or choice.get("hide")):
                types.pop(name, None)
                continue
            entry = {}
            if choice.get("prompt"):
                entry["prompt"] = str(choice["prompt"])
            if choice.get("answer"):
                entry["answer"] = str(choice["answer"])
            if choice.get("hide"):
                entry["hide"] = [str(h) for h in choice["hide"]]
            types[name] = entry
        user["note_types"] = types
        mw.addonManager.writeConfig(ADDON, user)

    def cmd_tick(self, arg: dict) -> None:
        ticks().set(int(arg["nid"]), bool(arg.get("on")))

    def cmd_ticks_reset(self, arg: dict) -> int:
        return ticks().reset(arg.get("nids") or [])

    def cmd_play(self, arg: dict) -> bool:
        """Play a card's sound through Anki's own audio player."""
        name = os.path.basename(str(arg.get("file") or ""))
        if not name or not os.path.exists(os.path.join(mw.col.media.dir(), name)):
            tooltip("That sound file is missing from your media folder.", parent=self)
            return False
        from anki.sound import SoundOrVideoTag
        from aqt.sound import av_player

        av_player.play_tags([SoundOrVideoTag(filename=name)])
        return True

    def cmd_edit(self, arg: dict) -> None:
        aqt.dialogs.open("Browser", mw, search=("nid:%d" % int(arg["nid"]),))

    def cmd_study(self, arg: dict) -> None:
        deck = arg.get("deck")
        did = mw.col.decks.id_for_name(deck) if deck else None
        if did:
            mw.col.decks.select(did)
            mw.moveToState("overview")
        else:
            mw.moveToState("deckBrowser")
        mw.activateWindow()
        mw.raise_()

    def cmd_copy(self, arg: dict) -> None:
        mw.app.clipboard().setText(str(arg.get("text") or ""))

    def cmd_pdf(self, arg: dict) -> None:
        name = (arg.get("title") or "sheet").replace("::", " - ").replace("/", "-")
        path = getSaveFile(self, "Export PDF", "ankiSheets", "PDF", ".pdf", fname=name)
        if path:
            self.export_pdf(path)

    def export_pdf(self, path: str) -> None:
        page = self.web.page()

        def done(file: str, ok: bool) -> None:
            page.pdfPrintingFinished.disconnect(done)
            tooltip("Saved %s" % file if ok else "PDF export failed", parent=self)

        page.pdfPrintingFinished.connect(done)
        layout = QPageLayout(
            QPageSize(QPageSize.PageSizeId.Letter),
            QPageLayout.Orientation.Portrait,
            QMarginsF(12, 12, 12, 12),
            QPageLayout.Unit.Millimeter,
        )
        page.printToPdf(path, layout)

    # ------------------------------------------------------------ AI

    def cmd_ai_save(self, arg: dict) -> dict:
        c = config()["ai"]
        before = _where(c)
        for k in ("enabled", "provider", "model", "base_url"):
            if k in arg:
                c[k] = arg[k].strip() if isinstance(arg[k], str) else bool(arg[k])
        if arg.get("api_key"):
            c["api_key"] = arg["api_key"].strip()
        elif _where(c) != before:
            c["api_key"] = ""  # a saved key only ever goes to the server it was typed in for
        if arg.get("clear_key"):
            c["api_key"] = ""
        if "never_send_decks" in arg:
            c["never_send_decks"] = sorted({str(d) for d in arg["never_send_decks"] if d})
        save_ai(c)
        return self.ai_public()

    def cmd_ai_test(self, arg: dict) -> dict:
        """Check the settings as typed in the window, before they are saved."""
        c = dict(config()["ai"])
        for k in ("provider", "model", "base_url"):
            if isinstance(arg.get(k), str):
                c[k] = arg[k].strip()
        if arg.get("api_key"):
            c["api_key"] = arg["api_key"].strip()
        elif _where(c) != _where(config()["ai"]):
            c["api_key"] = ""  # never send the saved key to a server it wasn't typed in for
        self._run_ai(int(arg["req"]), lambda: ai.test_connection(c))
        return {"started": True}

    def _run_ai(self, req: int, work, on_ok=None) -> None:
        """Run a network call off the main thread, then hand the result to the page."""

        def done(fut) -> None:
            try:
                result = fut.result()
                if on_ok:
                    result = on_ok(result) or result
                payload = {"ok": True, "result": result}
            except ai.AIError as e:
                payload = {"ok": False, "error": str(e)}
            except Exception as e:  # never leave the page waiting
                payload = {"ok": False, "error": "Something went wrong: %s" % e}
            if _dialog is self:
                self.web.eval("Sheets.aiDone(%d, %s)" % (req, json.dumps(payload)))

        mw.taskman.run_in_background(work, done)

    def _cards(self, nids: list[int]) -> dict:
        return sheet.ai_cards(mw.col, nids, config())

    def cmd_ai_condense(self, arg: dict) -> dict:
        cfg = config()["ai"]
        if not ai.ready(cfg):
            return {"started": False, "error": "AI is not set up. Open AI settings."}
        picked = self._cards(arg["nids"])
        cards = picked["cards"]
        if len(cards) < 3:
            return {"started": False, "error": "There are too few cards here to condense."}
        key = summary_key(arg["deck_id"], arg.get("prefix"), arg.get("key", ""))
        fp = group_fingerprint([n for n, _ in cards])
        title = arg.get("title") or ""

        def keep(summary: dict) -> None:
            if summary.get("condensable"):
                store().set(key, summary, fp)

        self._run_ai(int(arg["req"]), lambda: ai.condense(cfg, title, cards), keep)
        return {"started": True, "sent": len(cards)}

    def cmd_ai_remove(self, arg: dict) -> None:
        store().delete(summary_key(arg["deck_id"], arg.get("prefix"), arg.get("key", "")))

    def cmd_ai_ask(self, arg: dict) -> dict:
        cfg = config()["ai"]
        if not ai.ready(cfg):
            return {"started": False, "error": "AI is not set up. Open AI settings."}
        question = (arg.get("question") or "").strip()
        if not question:
            return {"started": False, "error": "Type a question first."}
        cards = self._cards(arg.get("nids") or [])["cards"]
        title, history, strict = arg.get("title") or "", arg.get("history") or [], bool(arg.get("strict"))
        self._run_ai(int(arg["req"]), lambda: ai.ask(cfg, title, cards, history, question, strict))
        return {"started": True, "sent": len(cards)}

    def cmd_add_card(self, arg: dict) -> None:
        """Opens Anki's own Add window pre-filled. Nothing is saved until the user clicks Add."""
        col = mw.col
        model = col.models.by_name("Basic") or col.models.current()
        note = col.new_note(model)
        note.fields[0] = arg.get("front", "")
        if len(note.fields) > 1:
            note.fields[1] = arg.get("back", "")
        did = col.decks.id_for_name(arg["deck"]) if arg.get("deck") else None
        add = aqt.dialogs.open("AddCards", mw)
        add.set_note(note, did)
        add.activateWindow()
        add.raise_()

    # ------------------------------------------------------------ window

    def keyPressEvent(self, event) -> None:
        # Esc closes pictures and menus inside the sheet; it should never close the whole window
        if event.key() == Qt.Key.Key_Escape:
            event.accept()
            return
        super().keyPressEvent(event)

    def reject(self) -> None:
        global _dialog
        saveGeom(self, "ankiSheets")
        self.web.cleanup()
        _dialog = None
        super().reject()


def open_sheet(deck_id: int | None = None) -> SheetDialog | None:
    global _dialog
    if not mw.col:
        return None
    if _dialog is not None:
        if deck_id:
            name = mw.col.decks.name(deck_id)
            _dialog.web.eval("Sheets.selectDeck(%s)" % json.dumps(name))
        _dialog.activateWindow()
        _dialog.raise_()
        return _dialog
    _dialog = SheetDialog(deck_id)
    _dialog.show()
    return _dialog


def close_sheet() -> None:
    if _dialog is not None:
        _dialog.reject()
