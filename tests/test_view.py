import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.dirname(__file__))

import fake_ai  # noqa: E402
from anki_sheets import ai, sheet  # noqa: E402
from seed import SPELLING, seed  # noqa: E402


@pytest.fixture(scope="module")
def col():
    c = seed(os.path.join(tempfile.mkdtemp(), "collection.anki2"), extras=True)
    yield c
    c.close()


def rows(col, deck):
    return [r for g in sheet.build_sheet(col, deck)["decks"][0]["groups"] for r in g["rows"]]


# ------------------------------------------------------------ where notes collapse


def test_real_card_shapes_collapse_at_the_note(col):
    by = {sheet.text_of(r["prompt"])[:5]: r for r in rows(col, SPELLING)}
    accents, letters, pic = by["Accen"], by["Lette"], by["[Samp"]
    # "note:" on its own line, no divider, two pictures
    assert accents["answer"].endswith("and all others on the last.") and "note" not in accents["answer"].lower()
    assert accents["extra"]["images"] == 2 and accents["extra"]["html"].startswith("<img")
    # a lone long dash as the divider
    assert letters["answer"] == "Like the <b>ny</b> in canyon."
    assert letters["extra"] == {"html": '<img loading="lazy" decoding="async" src="note-shot.png">', "images": 1}
    # an answer that is only a picture stays whole
    assert pic["extra"] is None and pic["answer"] == '<img loading="lazy" decoding="async" src="note-shot.png">'


@pytest.mark.parametrize("answer,main,extra", [
    ("Text first<br><img src='a.png'>", "Text first", "<img src='a.png'>"),                # picture with no label at all
    ("Answer<br>---<br>more", "Answer", "more"),
    ("Answer<hr>more", "Answer", "more"),
    ("Answer<br>___<br>more", "Answer", "more"),
    ("<div>Answer</div><div><b>Notes:</b> more</div>", "<div>Answer", "more</div>"),
    ("Answer<br>NOTE: more<br><img src=x>", "Answer", "more<br><img src=x>"),              # label wins over the later picture
])
def test_split_points(answer, main, extra):
    got_main, got = sheet.split_extra(answer)
    assert got_main == main and got["html"] == extra


@pytest.mark.parametrize("answer", [
    "Not for events — those take ser.",   # a dash inside a sentence is not a divider
    "A<br>— B as a bullet",
    "<img src='only.png'>",
    "---<br>only below a rule",
    "Take note: this is inline",
    "plain",
])
def test_things_that_do_not_split(answer):
    assert sheet.split_extra(answer) == (answer, None)


# ------------------------------------------------------------ review ticks


def test_ticks_are_kept_outside_the_collection(col):
    path = os.path.join(tempfile.mkdtemp(), "user_files", "ticks.json")
    before = col.db.scalar("select mod from col"), col.db.all("select id, mod, due, ivl, reps from cards")
    t = ai.TickStore(path)
    assert t.ids == set()
    t.set(11, True); t.set(22, True); t.set(22, True); t.set(33, True); t.set(33, False)
    assert ai.TickStore(path).ids == {11, 22}                 # survives reopening
    assert json.load(open(path)) == [11, 22]
    assert t.reset([22, 99]) == 1 and ai.TickStore(path).ids == {11}   # reset only clears the given sheet
    assert t.reset([11]) == 1 and ai.TickStore(path).ids == set()
    assert before == (col.db.scalar("select mod from col"), col.db.all("select id, mod, due, ivl, reps from cards"))


def test_corrupt_tick_file_is_ignored():
    path = os.path.join(tempfile.mkdtemp(), "ticks.json")
    open(path, "w").write("{not json")
    assert ai.TickStore(path).ids == set()


# ------------------------------------------------------------ test connection


def test_connection_check_sends_no_cards():
    srv, url = fake_ai.start()
    try:
        fake_ai.requests.clear()
        assert ai.test_connection({"provider": "anthropic", "api_key": "test-key", "base_url": url + "/v1/messages"})
        body = json.dumps(fake_ai.requests[0]["body"])
        assert "Cards:" not in body and "Q:" not in body and fake_ai.requests[0]["body"]["max_tokens"] == 16
        with pytest.raises(ai.AIError, match="Check the API key"):
            ai.test_connection({"provider": "anthropic", "api_key": "wrong", "base_url": url + "/v1/messages"})
    finally:
        srv.shutdown()
    with pytest.raises(ai.AIError, match="Paste an API key first"):
        ai.test_connection({"provider": "anthropic"})
    with pytest.raises(ai.AIError, match="server address and model"):
        ai.test_connection({"provider": "openai_compatible", "base_url": "http://x/v1"})


# ------------------------------------------------------------ sound


def test_sound_tags_become_play_buttons_and_stay_out_of_ai_text(col):
    from seed import LISTENING
    r = rows(col, LISTENING)
    assert r[0]["prompt"] == 'hola <button class="snd" type="button" data-snd="hola.mp3" aria-label="Play sound" title="Play sound"></button>'
    assert 'data-snd="hello &amp; hi.mp3"' in r[0]["answer"] and "[sound" not in r[0]["answer"]
    assert r[1]["prompt"].startswith("<button") and not sheet.is_blank(r[1]["prompt"])   # a sound-only question is not empty
    sent = [t for _, t in sheet.ai_cards(col, [x["nid"] for x in r])["cards"]]
    assert sent[0] == "Q: hola | A: hello" and ".mp3" not in " ".join(sent)
    assert sheet.clean('x<script>alert(1)</script>[sound:a"b.mp3]').count("<script") == 0
    assert 'data-snd="a&quot;b.mp3"' in sheet.clean('[sound:a"b.mp3]')


# ------------------------------------------------------------ large decks


def test_page_size_cap_and_lazy_pictures(col):
    full = sheet.build_sheet(col, "Spanish")
    assert full["shown"] == full["total"] == 20
    small = sheet.build_sheet(col, "Spanish", max_chars=600)
    assert 1 <= small["shown"] < 20 and small["total"] == 20          # stops early, still reports the real total
    assert sum(len(g["rows"]) for d in small["decks"] for g in d["groups"]) == small["shown"]
    assert sheet.build_sheet(col, "Spanish", max_chars=1)["shown"] == 1   # always at least one row
    html = sheet.clean('a <img src="x.png"> b <IMG src="y.png">')
    assert html.count('loading="lazy"') == 2 and 'src="x.png"' in html


# ------------------------------------------------------------ general-use: grouping, formulas, occlusion, fields


def test_plain_tags_are_the_fallback_for_sections(col):
    from seed import MATHS_DECK
    deck = sheet.build_sheet(col, MATHS_DECK)["decks"][0]
    assert deck["grouped_by"] == "@tag"
    assert [(g["name"], len(g["rows"])) for g in deck["groups"]] == [("Algebra", 2), ("Calculus", 2)]
    # hierarchical tag families still win when they fit
    assert sheet.build_sheet(col, "Spanish::📘 Grammar::Ser and Estar")["decks"][0]["grouped_by"] == "topic"
    # every note has a different tag: that is not a grouping
    assert sheet.pick_prefix([{"@tag": str(i)} for i in range(6)], sheet.DEFAULT_CONFIG) is None
    by_type = sheet.build_sheet(col, "General", group="@type")
    assert by_type["group_extra"] == ["@tag", "@type"]
    names = {g["name"] for d in by_type["decks"] for g in d["groups"]}
    assert {"Basic", "Image Occlusion", "Image Occlusion Enhanced"} <= names


def test_editor_formulas_become_mathjax_delimiters(col):
    from seed import MATHS_DECK
    r = rows(col, MATHS_DECK)
    assert r[1]["answer"] == "\\(a^2 - b^2 = (a-b)(a+b)\\)"
    assert r[2]["answer"] == "\\[\\frac{d}{dx}x^n = nx^{n-1}\\]"
    assert r[0]["answer"].startswith("\\(x = ")


def test_image_occlusion_notes_show_the_picture_once(col):
    from seed import ANATOMY
    data = sheet.build_sheet(col, ANATOMY)
    r = [x for g in data["decks"][0]["groups"] for x in g["rows"]]
    assert data["total"] == 4 and data["shown"] == 4 and len(r) == 2      # 3 one-per-mask notes merge into one row
    builtin, enhanced = r
    assert builtin["prompt"] == "Bones of the hand" and builtin["badge"] == "2 masks"
    assert "image-occlusion" not in builtin["answer"] and "verb-table.png" in builtin["answer"]
    assert [d["label"] for d in builtin["details"]] == ["Back Extra"]
    assert enhanced["prompt"] == "Layers of the skin" and enhanced["badge"] == "3 masks"
    assert "mask-" not in enhanced["answer"] and enhanced["details"] == []
    sent = sheet.ai_cards(col, [x["nid"] for x in r])["cards"]
    assert sent[0][1] == "Q: Bones of the hand | A: [image] | Back Extra: Count from the thumb side."


def test_note_types_are_reported_for_the_fields_screen(col):
    cfg = {"note_types": {"Basic+": {"prompt": "Back", "answer": "Front"}}}
    types = {t["name"]: t for t in sheet.build_sheet(col, "Spanish", cfg=cfg)["note_types"]}
    assert types["Basic+"] == {"name": "Basic+", "fields": ["Front", "Back"], "cloze": False,
                               "prompt": "Back", "answer": "Front", "hide": [], "custom": True}
    assert types["Cloze"]["cloze"] and not types["Cloze"]["custom"]
    swapped = [r for d in sheet.build_sheet(col, "Spanish::📘 Grammar::Spelling", cfg=cfg)["decks"] for g in d["groups"] for r in g["rows"]]
    assert swapped[0]["answer"] == "Accents — when does a Spanish word need a written accent?"
