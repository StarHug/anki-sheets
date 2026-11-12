"""Builds a small sample collection for tests and demos: a made-up language learner's decks.

It covers the shapes the add-on has to handle: plain question/answer notes with
a trailing "note + picture", a six-field note type, cloze notes, untagged notes,
hierarchical tags, sub-decks, review history, pictures and sound.
"""

from __future__ import annotations

from anki.collection import Collection

GRAMMAR = "Spanish::📘 Grammar::Ser and Estar"
PHRASES = "Spanish::Phrasebook::Unit 1"
CLOZES = "Spanish::📘 Grammar::Tenses & Moods"
CAPITALS = "General::🌍 Geography::Capitals"
SPELLING = "Spanish::📘 Grammar::Spelling"
LISTENING = "General::Listening"
MATHS_DECK = "General::Maths"
ANATOMY = "General::Anatomy"

MATHS = [
    ("Quadratic formula", "\\(x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}\\)", "algebra"),
    ("Difference of squares", '<anki-mathjax>a^2 - b^2 = (a-b)(a+b)</anki-mathjax>', "algebra"),
    ("Derivative of \\(x^n\\)", '<anki-mathjax block="true">\\frac{d}{dx}x^n = nx^{n-1}</anki-mathjax>', "calculus"),
    ("Integral of \\(1/x\\)", "\\(\\ln|x| + C\\)", "calculus"),
]

IMG = '<img src="verb-table.png">'

GRAMMAR_NOTES = [
    ("Ser vs estar — what is the basic difference?",
     "<strong>Ser</strong> says what something <strong>is</strong>. <br><strong>Estar</strong> says how or where it is right now.", "verbs", "concept"),
    ("Conjugate <em>ser</em> in the present tense.",
     "soy → eres → es → somos → sois → son<br><br>---<br>note:<br>" + IMG, "verbs", "reflex"),
    ("Ser — when do you use <strong>ser</strong> about a situation?",
     "For <strong>identity</strong>: name, job, nationality and lasting traits. <em>Soy profesora.</em><br><br>---<br>note:<br>" + IMG, "verbs", "concept"),
    ("Estar — when do you use <strong>estar</strong> about a situation?",
     "For <strong>states and feelings</strong> that can change: tired, happy, ill. <em>Estoy cansado.</em><br><br>---<br>note:<br>" + IMG, "verbs", "concept"),
    ("Ser aburrido vs estar aburrido — same adjective. What changes?",
     "<strong>Ser aburrido</strong> is to be <strong>boring</strong>. <strong>Estar aburrido</strong> is to be <strong>bored</strong>.<br>---<br>note:<br>" + IMG, "verbs", "reflex"),
    ("Estar — which verb gives the <strong>location</strong> of a situation or thing?",
     "<strong>Estar</strong>, however permanent the place: <em>Madrid está en España.</em><br>----<br>note:<br>" + IMG, "verbs", "concept"),
    ("Is location always estar?",
     "Not for events — those take ser. <br><em>La fiesta es en mi casa</em> says where the party <strong>takes place</strong>.<br><br><br>---<br>note:<br>" + IMG, "verbs", "concept"),
    ("Ser — which verb tells the <strong>time</strong> and the date?",
     "<strong>Ser</strong>: <em>Son las tres. Hoy es lunes.</em><br><br>----<br>note:<br>" + IMG + "<br>" + IMG, "verbs", "concept"),
    ("Ser listo vs estar listo — which means what?",
     "<strong>Ser listo</strong> is to be <strong>clever</strong>. <br><strong>Estar listo</strong> is to be <strong>ready</strong>.<br><br>---<br>note:<br>" + IMG, "verbs", "reflex"),
    ("What is a <strong>definite article</strong>?",
     "The word for <em>the</em>: <strong>el, la, los, las</strong>, matching the noun's gender and number.<br>---<br>note:<br>" + IMG, "articles", "concept"),
]

PHRASE_NOTES = [
    ("[Restaurant, paying] How do you ask for the bill?",
     "La cuenta, por favor.",
     "The bill, please.",
     "After the meal, catch the waiter's eye and say: La cuenta, por favor.",
     "In Spain the bill is not brought until you ask for it.",
     "Sample phrasebook, unit 1.", "restaurant", "eating-out"),
    ("[Restaurant, ordering] How do you order a coffee with milk?",
     "Un café con leche, por favor.",
     "A coffee with milk, please.",
     "At the bar in the morning: Un café con leche, por favor.",
     "Un café on its own is usually an espresso.",
     "Sample phrasebook, unit 1.", "restaurant", "eating-out"),
    ("[Restaurant] How do you ask for a table for two?",
     "Una mesa para dos, por favor.",
     "A table for two, please.",
     "At the door: Buenas tardes. Una mesa para dos, por favor.",
     "Lunch is late in Spain: restaurants fill from about two o'clock.",
     "Sample phrasebook, unit 1.", "restaurant", "eating-out"),
    # a second subtopic, with the optional fields left empty
    ("[Street] How do you ask where the bathroom is?", "¿Dónde está el baño?", "", "", "", "", "street", "getting-around"),
]

CLOZE_NOTES = [
    ("Ayer {{c1::comí}} paella con mis {{c2::amigos}}.", "", "preterite"),
    ("El año pasado {{c1::viajé}} a {{c2::México::which country?}}.", "The preterite is for a finished action in the past.", "preterite"),
    ("{{c1::Quiero}} que {{c2::vengas}} a la fiesta.", "", "subjunctive"),
]

CAPITAL_NOTES = [
    ("What is the capital of Australia?", "Canberra, not Sydney."),
    ("What is the capital of Canada?", "Ottawa."),
]


JA = "Japanese::📗 Grammar::Particles"
JA_VOCAB = "Japanese::Vocabulary::Food"
KO = "Korean::📙 Grammar::Particles"
KO_VOCAB = "Korean::Vocabulary::Food"

JA_NOTES = [
    ("は vs が — what is the basic difference?",
     "<strong>は</strong> marks the <strong>topic</strong>: what the sentence is about. <br><strong>が</strong> marks the <strong>subject</strong>, often new information.", "particles", "concept"),
    ("Count from one to five in Japanese.",
     "いち → に → さん → よん → ご<br><br>---<br>note:<br>" + IMG, "particles", "reflex"),
    ("を — what does <strong>を</strong> mark?",
     "The <strong>direct object</strong> of the verb: <em>パンを食べます</em> (I eat bread).<br><br>---<br>note:<br>" + IMG, "particles", "concept"),
    ("に — what does <strong>に</strong> mark with a time?",
     "A <strong>specific point in time</strong>: <em>七時に起きます</em> (I get up at seven).<br><br>---<br>note:<br>" + IMG, "particles", "concept"),
    ("に vs で — both can mark a place. What separates them?",
     "<strong>に</strong> marks where something <strong>exists or arrives</strong>. <strong>で</strong> marks where an <strong>action happens</strong>.<br>---<br>note:<br>" + IMG, "particles", "reflex"),
    ("で — what else can <strong>で</strong> mark besides a place?",
     "The <strong>means</strong> used: <em>バスで行きます</em> (I go by bus).<br>----<br>note:<br>" + IMG, "particles", "concept"),
    ("Is は read “ha” when it is a particle?",
     "No — as a particle it is read wa. <br>The same goes for <strong>へ</strong>, which is read <strong>e</strong>.<br><br><br>---<br>note:<br>" + IMG, "particles", "concept"),
    ("の — what does <strong>の</strong> do between two nouns?",
     "Links them, usually as <strong>possession</strong>: <em>私の本</em> (my book).<br><br>----<br>note:<br>" + IMG + "<br>" + IMG, "particles", "concept"),
    ("か — what does <strong>か</strong> do at the end of a sentence?",
     "Turns it into a <strong>question</strong>: <em>学生ですか</em> (Are you a student?).<br><br>---<br>note:<br>" + IMG, "particles", "reflex"),
    ("What is a <strong>counter</strong>?",
     "A word added to a number to count things of one kind, such as <strong>枚</strong> for flat objects.<br>---<br>note:<br>" + IMG, "counters", "concept"),
]
JA_WORDS = [("りんご", "apple"), ("水 (みず)", "water"), ("ご飯 (ごはん)", "cooked rice; a meal"), ("お茶 (おちゃ)", "tea")]

KO_NOTES = [
    ("은/는 vs 이/가 — what is the basic difference?",
     "<strong>은/는</strong> marks the <strong>topic</strong>: what the sentence is about. <br><strong>이/가</strong> marks the <strong>subject</strong>, often new information.", "particles", "concept"),
    ("Count from one to five with native Korean numbers.",
     "하나 → 둘 → 셋 → 넷 → 다섯<br><br>---<br>note:<br>" + IMG, "particles", "reflex"),
    ("을/를 — what does <strong>을/를</strong> mark?",
     "The <strong>object</strong> of the verb: <em>빵을 먹어요</em> (I eat bread).<br><br>---<br>note:<br>" + IMG, "particles", "concept"),
    ("에 — what does <strong>에</strong> mark with a time?",
     "A <strong>point in time</strong>: <em>일곱 시에 일어나요</em> (I get up at seven).<br><br>---<br>note:<br>" + IMG, "particles", "concept"),
    ("에 vs 에서 — both can mark a place. What separates them?",
     "<strong>에</strong> marks where something <strong>is or is going</strong>. <strong>에서</strong> marks where an <strong>action happens</strong>.<br>---<br>note:<br>" + IMG, "particles", "reflex"),
    ("(으)로 — what does <strong>(으)로</strong> mark?",
     "The <strong>means or direction</strong>: <em>버스로 가요</em> (I go by bus).<br>----<br>note:<br>" + IMG, "particles", "concept"),
    ("Do you choose 은 or 는 by meaning?",
     "No — by the last sound. <br><strong>은</strong> follows a consonant and <strong>는</strong> follows a vowel.<br><br><br>---<br>note:<br>" + IMG, "particles", "concept"),
    ("의 — what does <strong>의</strong> do between two nouns?",
     "Shows <strong>possession</strong>: <em>친구의 책</em> (a friend's book).<br><br>----<br>note:<br>" + IMG + "<br>" + IMG, "particles", "concept"),
    ("도 — what does <strong>도</strong> add?",
     "The meaning <strong>also</strong>: <em>저도 학생이에요</em> (I am a student too).<br><br>---<br>note:<br>" + IMG, "particles", "reflex"),
    ("What is <strong>받침</strong> (batchim)?",
     "A <strong>final consonant</strong> at the bottom of a syllable block, like the ㄴ in 한.<br>---<br>note:<br>" + IMG, "hangul", "concept"),
]
KO_WORDS = [("사과", "apple"), ("물", "water"), ("밥", "cooked rice; a meal"), ("차", "tea")]


SHOT = '<img src="note-shot.png">'
# Two note shapes that put the extra note after the answer without a "---" rule,
# and one whose answer is only a picture.
SPELLING_NOTES = [
    ("Accents — when does a Spanish word need a written accent?",
     "When the stress breaks the usual rule:<br>words ending in a vowel, n or s are stressed on the second-to-last syllable, and all others on the last.<br><br>note:<br>" + SHOT + "<br><br>" + SHOT, "accents"),
    ("Letters — what does <code>ñ</code> sound like?",
     "Like the <b>ny</b> in canyon.<br>—<br>Note:<br>" + SHOT, "letters"),
    ("[Sample] A card whose answer is only a picture", SHOT, "accents"),
]


def _png(w, h, pixel):
    import struct, zlib
    raw = b"".join(b"\x00" + b"".join(bytes(pixel(x, y)) for x in range(w)) for y in range(h))
    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def _shot_pixel(x, y):
    """A dark 'screenshot of text': rows of light bars of varying length."""
    line, inside = divmod(y, 26)
    length = 120 + (line * 97) % 520
    if 9 <= inside <= 16 and 30 <= x <= 30 + length and line % 7 != 6:
        return (214, 218, 224) if line % 5 else (122, 165, 255)
    return (24, 26, 31)


def seed(path: str, extras: bool = False) -> Collection:
    col = Collection(path)
    mm = col.models

    basic_plus = mm.copy(mm.by_name("Basic"))
    basic_plus["name"] = "Basic+"
    mm.update_dict(basic_plus)

    phrase_type = mm.new("Phrase (Meaning + Example + Source)")
    for f in ("Front", "Answer", "Literally", "Example", "Tip", "Source"):
        mm.add_field(phrase_type, mm.new_field(f))
    t = mm.new_template("Card 1")
    t["qfmt"] = "{{Front}}"
    t["afmt"] = "{{FrontSide}}<hr id=answer>{{Answer}}<br>{{Literally}}"
    mm.add_template(phrase_type, t)
    mm.add(phrase_type)

    def add(model_name, deck, fields, tags):
        note = col.new_note(mm.by_name(model_name))
        for i, v in enumerate(fields):
            note.fields[i] = v
        note.tags = tags
        col.add_note(note, col.decks.id(deck))
        return note

    for front, back, topic, use in GRAMMAR_NOTES:
        add("Basic+", GRAMMAR, [front, back],
            ["src::course::spanish-101", "topic::" + topic, "use::" + use])
    for *fields, situation, sub in PHRASE_NOTES:
        add("Phrase (Meaning + Example + Source)", PHRASES, fields,
            ["kind::phrase", "level::beginner", "situation::" + situation,
             "subtopic::" + sub, "topic::phrasebook"])
    for text, extra, topic in CLOZE_NOTES:
        add("Cloze", CLOZES, [text, extra], ["topic::" + topic])
    for front, back in CAPITAL_NOTES:
        add("Basic", CAPITALS, [front, back], [])
    if extras:
        for deck, notes, vdeck, words in ((JA, JA_NOTES, JA_VOCAB, JA_WORDS), (KO, KO_NOTES, KO_VOCAB, KO_WORDS)):
            for front, back, topic, use in notes:
                add("Basic+", deck, [front, back], ["topic::" + topic, "use::" + use])
            for front, back in words:
                add("Basic", vdeck, [front, back], [])
        for front, back, topic in SPELLING_NOTES:
            add("Basic+", SPELLING, [front, back], ["topic::" + topic])
        col.media.write_data("note-shot.png", _png(720, 940, _shot_pixel))
        # a vocabulary card with audio on both sides (the file is a placeholder, not real audio)
        add("Basic", LISTENING, ["hola [sound:hola.mp3]", "hello[sound:hello &amp; hi.mp3]"], [])
        add("Basic", LISTENING, ["[sound:only-audio.mp3]", "a card whose question is only a sound"], [])
        col.media.write_data("hola.mp3", b"placeholder")
        # formulas, plain (non-hierarchical) tags, and both kinds of image-occlusion note
        for front, back, tag in MATHS:
            add("Basic", MATHS_DECK, [front, back], [tag])
        io = mm.new("Image Occlusion")
        io["type"] = 1
        for f in ("Occlusion", "Image", "Header", "Back Extra"):
            mm.add_field(io, mm.new_field(f))
        t = mm.new_template("Card 1")
        t["qfmt"] = "{{cloze:Occlusion}}{{Image}}"
        t["afmt"] = "{{cloze:Occlusion}}{{Image}}{{Back Extra}}"
        mm.add_template(io, t)
        mm.add(io)
        add("Image Occlusion", ANATOMY, ["{{c1::image-occlusion:rect:left=.1:top=.1:width=.2:height=.2}}<br>{{c2::image-occlusion:rect:left=.5:top=.5:width=.2:height=.2}}",
                                         IMG, "Bones of the hand", "Count from the thumb side."], [])
        ioe = mm.new("Image Occlusion Enhanced")
        for f in ("ID (hidden)", "Header", "Image", "Question Mask", "Footer", "Answer Mask", "Original Mask"):
            mm.add_field(ioe, mm.new_field(f))
        t = mm.new_template("IO Card")
        t["qfmt"] = "{{Image}}{{Question Mask}}"
        t["afmt"] = "{{Image}}{{Answer Mask}}"
        mm.add_template(ioe, t)
        mm.add(ioe)
        for n in (1, 2, 3):
            add("Image Occlusion Enhanced", ANATOMY, ["abc-%d" % n, "Layers of the skin", IMG,
                '<img src="mask-q%d.svg">' % n, "", '<img src="mask-a%d.svg">' % n, '<img src="mask-o.svg">'], [])

    # review history: two cards that keep lapsing, some already reviewed
    today = col.sched.today
    for main in ((GRAMMAR, JA, KO) if extras else (GRAMMAR,)):
        cids = col.find_cards('"deck:%s"' % main, order="n.id asc")
        for i, cid in enumerate(cids):
            card = col.get_card(cid)
            if i in (4, 6):  # the two easily confused ones
                card.type, card.queue, card.ivl, card.due, card.lapses = 2, 2, 1, today, 3 + (i == 6)
            elif i < 4:
                card.type, card.queue, card.ivl, card.due = 2, 2, 5, today - 1 + i % 2 * 5
            col.update_card(card)

    # a small banded picture so "Note + 1 image" has something to expand
    import struct, zlib
    w, hgt, shades = 320, 98, [0x1F, 0x35, 0x4B, 0x61, 0x77, 0x8D, 0xA3]
    raw = b"".join(
        b"\x00" + (bytes([255, 255, 255]) if y % 14 == 13 else bytes([shades[y // 14], 0x6B, 0xD8])) * w
        for y in range(hgt))
    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, hgt, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    col.media.write_data("verb-table.png", png)
    return col
