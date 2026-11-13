import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.dirname(__file__))

import fake_ai  # noqa: E402
from anki_sheets import ai, sheet  # noqa: E402
from seed import PHRASES, CLOZES, GRAMMAR, seed  # noqa: E402


@pytest.fixture(scope="module")
def col():
    c = seed(os.path.join(tempfile.mkdtemp(), "collection.anki2"))
    yield c
    c.close()


@pytest.fixture(scope="module")
def server():
    srv, url = fake_ai.start()
    yield url
    srv.shutdown()


def nids(col, deck, tag=None):
    q = '"deck:%s"' % deck + (" tag:%s" % tag if tag else "")
    return sorted(int(n) for n in col.find_notes(q))


def compat(url):
    return {"enabled": True, "provider": "openai_compatible", "base_url": url + "/v1", "model": "stand-in"}


def claude(url, key="test-key"):
    return {"enabled": True, "provider": "anthropic", "api_key": key, "base_url": url + "/v1/messages"}


# ------------------------------------------------------------ what gets sent


def test_cards_are_sent_as_plain_text_without_pictures(col):
    out = sheet.ai_cards(col, nids(col, GRAMMAR, "topic::verbs"))
    texts = [t for _, t in out["cards"]]
    assert len(texts) == 9 and out["excluded"] == 0 and not out["capped"]
    assert texts[1] == ("Q: Conjugate ser in the present tense. | A: soy → eres → es → "
                        "somos → sois → son | Note: [image]")
    assert not any("<" in t or "verb-table" in t for t in texts)  # no markup, no file names
    phrases = sheet.ai_cards(col, nids(col, PHRASES))["cards"][0][1]
    assert phrases.startswith("Q: [Restaurant, paying]") and "| A: La cuenta, por favor. | Literally: The bill, please." in phrases
    cloze = sheet.ai_cards(col, nids(col, CLOZES))["cards"][0][1]
    assert cloze == "Statement: Ayer comí paella con mis amigos."


def test_never_send_decks_are_dropped_even_if_asked_for(col):
    cfg = {"ai": {"never_send_decks": ["Spanish::Phrasebook"]}}
    everything = nids(col, "Spanish")
    out = sheet.ai_cards(col, everything, cfg)
    assert out["excluded"] == 4 and len(out["cards"]) == 13
    assert not any("Restaurant" in t for _, t in out["cards"])
    # sub-decks are covered, look-alike names are not
    assert sheet.is_private("Spanish::Phrasebook::Unit 1-2", ["Spanish::Phrasebook"])
    assert not sheet.is_private("Spanish::Phrasebook 2", ["Spanish::Phrasebook"])
    data = sheet.build_sheet(col, "Spanish", cfg=cfg)
    assert [d["private"] for d in data["decks"]] == [True, False, False]


def test_cap_on_cards_per_request(col):
    out = sheet.ai_cards(col, nids(col, "Spanish"), {"ai": {"max_cards": 5}})
    assert len(out["cards"]) == 5 and out["capped"]


def test_ready_requires_opt_in():
    assert not ai.ready({})  # off by default
    assert not ai.ready({"enabled": True})  # on but no key
    assert not ai.ready({"enabled": False, "api_key": "k"})
    assert ai.ready({"enabled": True, "api_key": "k"})
    assert ai.ready({"enabled": True, "provider": "openai_compatible", "base_url": "http://x/v1", "model": "m"})


# ------------------------------------------------------------ condense


def test_condense_over_both_wire_formats(col, server):
    cards = sheet.ai_cards(col, nids(col, GRAMMAR, "topic::verbs"))["cards"]
    for cfg in (compat(server), claude(server)):
        fake_ai.requests.clear()
        s = ai.condense(cfg, "Verbs (Ser and Estar)", cards)
        assert s["condensable"] and s["count"] == 9 and s["intro"].startswith("Ser says what")
        table, steps = s["blocks"]
        assert table["columns"] == ["Use", "Verb", "Example"]
        assert [r["cells"][0] for r in table["rows"]] == ["Identity and lasting traits", "States and feelings", "Location", "Time and date"]
        valid = {n for n, _ in cards}
        assert all(r["sources"] and set(r["sources"]) <= valid for r in table["rows"])  # real note ids
        assert steps["type"] == "steps" and s["gaps"] == ["Estar in the present tense", "Past tenses"]
        (req,) = fake_ai.requests
        sent = json.dumps(req["body"], ensure_ascii=False)
        assert "Conjugate ser in the present tense" in sent and "definite article" not in sent  # only that section's cards
    assert fake_ai.requests[0]["headers"]["x-api-key"] == "test-key"
    assert fake_ai.requests[0]["body"]["model"] == "claude-sonnet-5-5"


def test_condense_picks_a_list_or_declines(col, server):
    phrases = sheet.ai_cards(col, nids(col, PHRASES, "subtopic::eating-out"))["cards"]
    s = ai.condense(compat(server), "Eating out", phrases)
    assert [b["type"] for b in s["blocks"]] == ["list"] and len(s["blocks"][0]["items"]) == 3
    assert s["blocks"][0]["items"][0]["sources"] == [phrases[0][0]]
    none = ai.condense(compat(server), "Preterite", sheet.ai_cards(col, nids(col, CLOZES))["cards"])
    assert none == {"condensable": False, "reason": "These cards are separate facts without a shared structure.", "count": 3}


def test_newer_openai_models_get_the_renamed_token_limit(server):
    cfg = dict(compat(server), model="newer")
    assert ai.call_model(cfg, "ser vs estar", [{"role": "user", "content": "hi"}])
    sent = fake_ai.requests[-1]["body"]
    assert "max_tokens" not in sent and sent["max_completion_tokens"] == 2000


def test_bad_model_output_is_rejected_not_rendered():
    cards = [(11, "a"), (22, "b")]
    with pytest.raises(ai.AIError):
        ai.parse_json("sorry, I can't do that")
    with pytest.raises(ai.AIError):
        ai.normalize_summary({"condensable": True, "blocks": [{"type": "iframe", "src": "x"}]}, cards)
    s = ai.normalize_summary({"intro": 5, "gaps": "nope", "blocks": [
        {"type": "table", "columns": ["A", "B"], "rows": [{"cells": ["x"], "sources": [2, 99, "1", True, 2]}, "junk"]},
        {"type": "list", "items": [{"text": ""}, {"text": "ok", "sources": [1]}]}]}, cards)
    assert s["blocks"][0]["rows"] == [{"cells": ["x", ""], "sources": [22]}]  # padded; bad sources dropped
    assert s["blocks"][1]["items"] == [{"text": "ok", "sources": [11]}] and s["gaps"] == [] and s["intro"] == "5"


# ------------------------------------------------------------ ask


def test_ask_cites_cards_and_labels_outside_knowledge(col, server):
    cards = sheet.ai_cards(col, nids(col, GRAMMAR))["cards"]
    by_id = dict(cards)
    a = ai.ask(compat(server), "Ser and Estar", cards, [], "What's the difference between ser and estar?", False)
    assert a["basis"] == "cards" and len(a["sources"]) == 3
    assert all("ser" in by_id[n].lower() and "estar" in by_id[n].lower() for n in a["sources"])
    g = ai.ask(compat(server), "Ser and Estar", cards, [], "When do you use the subjunctive?", False)
    assert g["basis"] == "general" and g["sources"] == []
    strict = ai.ask(compat(server), "Ser and Estar", cards, [], "When do you use the subjunctive?", True)
    assert strict["basis"] == "none" and "don't cover" in strict["answer"]


def test_ask_sends_history_and_only_the_given_cards(col, server):
    fake_ai.requests.clear()
    cards = sheet.ai_cards(col, nids(col, GRAMMAR, "topic::articles"))["cards"]
    hist = [{"role": "user", "text": "first q"}, {"role": "assistant", "text": "first a"}]
    ai.ask(claude(server), "Ser and Estar", cards, hist, "follow up", False)
    body = fake_ai.requests[0]["body"]
    assert [m["content"] for m in body["messages"]] == ["first q", "first a", "follow up"]
    assert "[1] Q: What is a definite article?" in body["system"] and "Ser vs estar" not in body["system"].split("Cards:")[1]


def test_errors_are_readable(col, server):
    cards = [(1, "Q: a | A: b")]
    with pytest.raises(ai.AIError, match="401.*invalid x-api-key.*Check the API key"):
        ai.ask(claude(server, key="wrong"), "t", cards, [], "q", False)
    with pytest.raises(ai.AIError, match="Couldn't reach"):
        ai.ask({"enabled": True, "provider": "openai_compatible", "base_url": "http://127.0.0.1:9/v1", "model": "m"},
               "t", cards, [], "q", False)


# ------------------------------------------------------------ saved summaries


def test_summary_store_and_staleness(col):
    path = os.path.join(tempfile.mkdtemp(), "user_files", "summaries.json")
    st = ai.SummaryStore(path)
    ids = nids(col, GRAMMAR, "topic::verbs")
    fp = lambda: ai.fingerprint([tuple(r) for r in col.db.all(  # noqa: E731
        "select id, mod from notes where id in (%s)" % ",".join(map(str, ids)))])
    before = fp()
    st.set("1|topic|verbs", {"condensable": True, "intro": "x", "blocks": []}, before)
    assert ai.SummaryStore(path).get("1|topic|verbs")["fp"] == before  # survives reopening
    note = col.get_note(ids[0])
    note.fields[1] += " edited"
    col.db.execute("update notes set mod = mod + 5 where id = ?", ids[0])
    assert fp() != before  # an edited card marks the summary stale
    st.delete("1|topic|verbs")
    assert ai.SummaryStore(path).get("1|topic|verbs") is None
    assert not os.path.exists(os.path.join(os.path.dirname(col.path), "summaries.json"))  # never in the collection folder
