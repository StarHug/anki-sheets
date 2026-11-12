import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.dirname(__file__))

from anki_sheets import sheet  # noqa: E402
from seed import CAPITALS, PHRASES, CLOZES, GRAMMAR, seed  # noqa: E402


@pytest.fixture(scope="module")
def col():
    d = tempfile.mkdtemp()
    c = seed(os.path.join(d, "collection.anki2"))
    yield c
    c.close()


def rows(deck):
    return [r for g in deck["groups"] for r in g["rows"]]


def test_deck_sheet_groups_by_topic_tag(col):
    s = sheet.build_sheet(col, GRAMMAR)
    assert s["total"] == 10 and s["shown"] == 10
    (deck,) = s["decks"]
    assert deck["short"] == "Ser and Estar"
    assert deck["grouped_by"] == "topic"
    assert [(g["name"], len(g["rows"])) for g in deck["groups"]] == [("Verbs", 9), ("Articles", 1)]


def test_note_tail_is_split_into_collapsed_extra(col):
    deck = sheet.build_sheet(col, GRAMMAR)["decks"][0]
    first, layers = rows(deck)[0], rows(deck)[1]
    assert first["extra"] is None
    assert layers["answer"].startswith("soy → eres") and "note" not in layers["answer"]
    assert "---" not in layers["answer"] and "<img" not in layers["answer"]
    assert layers["extra"]["images"] == 1 and layers["extra"]["html"].startswith("<img")
    session = next(r for r in rows(deck) if "<strong>time</strong>" in r["prompt"])
    assert session["extra"]["images"] == 2


def test_multi_field_notes_keep_extra_fields_as_details(col):
    s = sheet.build_sheet(col, PHRASES)
    deck = s["decks"][0]
    # topic:: has a single value here, so it falls through to subtopic::
    assert deck["grouped_by"] == "subtopic"
    assert [g["name"] for g in deck["groups"]] == ["Eating out", "Getting around"]
    r = rows(deck)[0]
    assert r["answer"] == "La cuenta, por favor."
    assert [d["label"] for d in r["details"]] == ["Literally", "Example", "Tip", "Source"]
    # empty fields are dropped
    assert rows(deck)[-1]["details"] == []


def test_cloze_is_one_sentence_with_answers_marked(col):
    deck = sheet.build_sheet(col, CLOZES)["decks"][0]
    r = rows(deck)
    assert len(r) == 3 and all(x["kind"] == "cloze" for x in r)  # one row per note, not per card
    assert r[0]["text"] == 'Ayer <span class="cz">comí</span> paella con mis <span class="cz">amigos</span>.'
    assert 'data-hint="which country?"' in r[1]["text"] and "::" not in r[1]["text"]
    assert r[1]["details"] == [{"label": "Back Extra", "html": "The preterite is for a finished action in the past."}]


def test_untagged_deck_has_one_unnamed_group(col):
    deck = sheet.build_sheet(col, CAPITALS)["decks"][0]
    assert deck["grouped_by"] is None
    assert [(g["name"], len(g["rows"])) for g in deck["groups"]] == [("", 2)]


def test_parent_deck_stacks_subdecks(col):
    s = sheet.build_sheet(col, "Spanish")
    assert [d["short"] for d in s["decks"]] == [
        "Unit 1", "Ser and Estar", "Tenses & Moods"]
    assert s["total"] == 17
    assert sheet.build_sheet(col)["total"] == 19  # all decks


def test_scopes(col):
    weak = sheet.build_sheet(col, GRAMMAR, scope="weak")
    r = rows(weak["decks"][0])
    assert [x["lapses"] for x in r] == [4, 3]  # worst first
    assert "Is location always estar?" in r[0]["prompt"]
    due = sheet.build_sheet(col, GRAMMAR, scope="due")
    assert due["total"] == 4  # 2 lapsing + 2 overdue reviews
    new = sheet.build_sheet(col, GRAMMAR, scope="new")
    assert new["total"] == 4 and all(x["new"] for x in rows(new["decks"][0]))


def test_group_override_and_limit(col):
    by_situation = sheet.build_sheet(col, PHRASES, group="situation")["decks"][0]
    assert [g["name"] for g in by_situation["groups"]] == ["Restaurant", "Street"]
    flat = sheet.build_sheet(col, GRAMMAR, group="none")["decks"][0]
    assert len(flat["groups"]) == 1
    capped = sheet.build_sheet(col, limit=5)
    assert capped["shown"] == 5 and capped["total"] == 19
    assert "src" not in capped["group_options"] and "topic" in sheet.build_sheet(col)["group_options"]


def test_note_type_override(col):
    cfg = {"note_types": {"Phrase (Meaning + Example + Source)":
                          {"prompt": "Front", "answer": "Literally", "hide": ["Source", "Example"]}}}
    r = rows(sheet.build_sheet(col, PHRASES, cfg=cfg)["decks"][0])[0]
    assert r["answer"].startswith("The bill, please.")
    assert [d["label"] for d in r["details"]] == ["Answer", "Tip"]


def test_reading_does_not_modify_collection(col):
    before = col.db.scalar("select mod from col"), col.db.all("select id, mod, due, ivl, reps from cards")
    for scope in sheet.SCOPES:
        sheet.build_sheet(col, scope=scope)
    sheet.deck_tree(col)
    assert before == (col.db.scalar("select mod from col"), col.db.all("select id, mod, due, ivl, reps from cards"))


def test_deck_tree(col):
    tree = sheet.deck_tree(col)
    spanish = next(n for n in tree if n["name"] == "Spanish")
    assert spanish["cards"] == 20  # 17 notes, clozes have 2 cards each
    grammar_deck = next(n for n in spanish["children"] if "Grammar" in n["name"])
    assert {c["name"] for c in grammar_deck["children"]} == {"Ser and Estar", "Tenses & Moods"}


def test_helpers():
    assert sheet.split_extra("plain answer") == ("plain answer", None)
    assert sheet.split_extra("a<hr>b")[1] == {"html": "b", "images": 0}
    assert sheet.split_extra("---<br>only a rule")[1] is None
    assert sheet.clean('x<script>alert(1)</script>') == "x"
    assert sheet.render_cloze("{{c1::a {{c2::b}} c}}") == '<span class="cz">a <span class="cz">b</span> c</span>'
    assert sheet.pretty("eating-out") == "Eating out"
