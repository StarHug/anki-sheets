"""Turns a set of Anki cards into a readable "sheet".

No GUI imports here: everything works on a plain anki Collection so it can be
tested without starting Anki.
"""

from __future__ import annotations

import re
from typing import Any

DEFAULT_CONFIG: dict[str, Any] = {
    "max_rows": 500,
    "max_chars": 1500000,
    "weak_lapses": 2,
    "group_tag_prefixes": ["topic", "subtopic", "chapter", "section", "person"],
    "ignore_tag_prefixes": ["src", "source", "use", "kind", "level", "type"],
    "note_types": {},
    "ai": {},
}

SCOPES = ("all", "due", "new", "weak")

_SOUND = re.compile(r"\[sound:([^\]]*)\]")
# the editor stores formulas as <anki-mathjax>; MathJax wants \\( \\) and \\[ \\]
_MATHJAX = re.compile(r"<anki-mathjax(\s[^>]*\bblock\b[^>]*)?[^>]*>(.*?)</anki-mathjax>", re.I | re.S)
_SCRIPT = re.compile(r"<script\b.*?</script>", re.I | re.S)
_IMG = re.compile(r"<img\b", re.I)
_EDGE = r"(?:<br\s*/?>|</?div[^>]*>|</?p[^>]*>)"
_LINE = r"(?:^|" + _EDGE + r")(?:\s|&nbsp;)*"
_INLINE = r"(?:</?(?:b|strong|i|em|u|span)\b[^>]*>\s*)*"
# Where the main answer ends and secondary material starts: a rule line
# (--- / ___ / a lone dash / <hr>), a line starting "note:", or the first picture.
_DIVIDER = re.compile(
    r"<hr\b[^>]*>|" + _LINE + r"(?:-{3,}|_{3,}|[—–―]+)(?:\s|&nbsp;)*(?=" + _EDGE + r"|$)", re.I)
_NOTE_LINE = re.compile(_LINE + _INLINE + r"notes?\s*:", re.I)
_LEAD = re.compile(
    r"^(?:\s|&nbsp;|" + _EDGE + r"|<hr\b[^>]*>|-{3,}|_{3,}|[—–―]+|"
    + _INLINE + r"notes?\s*:" + _INLINE + r")+", re.I)
_TRAIL = re.compile(r"(?:\s|&nbsp;|" + _EDGE + r")+$", re.I)
_CLOZE = re.compile(
    r"\{\{c(\d+)::((?:(?!\{\{c\d+::).)*?)(?:::((?:(?!\}\}).)*?))?\}\}", re.S
)
_TAGS = re.compile(r"<[^>]+>")


def _sound_button(m: "re.Match") -> str:
    import html as htmllib

    # the field stores the name HTML-escaped (& as &amp;); normalise, then escape once
    name = htmllib.escape(htmllib.unescape(m.group(1)).strip(), quote=True)
    return '<button class="snd" type="button" data-snd="%s" aria-label="Play sound" title="Play sound"></button>' % name


def clean(html: str) -> str:
    """Field HTML for the sheet: scripts removed, [sound:x] turned into a play button."""
    html = _SCRIPT.sub("", html or "")
    html = _MATHJAX.sub(lambda m: ("\\[%s\\]" if m.group(1) else "\\(%s\\)") % m.group(2), html)
    html = _SOUND.sub(_sound_button, html)
    # pictures load only as they scroll into view, so a deck with hundreds of them opens quickly
    html = _IMG.sub('<img loading="lazy" decoding="async"', html)
    return html.strip()


def is_blank(html: str) -> bool:
    if _IMG.search(html or "") or 'class="snd"' in (html or ""):
        return False
    return not _TAGS.sub("", html or "").replace("&nbsp;", " ").strip()


def split_extra(answer: str) -> tuple[str, dict | None]:
    """Split an answer into (main, extra). The extra part is what the sheet
    collapses behind the "Note" button. An answer that is only a picture is
    left whole: there the picture is the answer."""
    cuts = sorted({m.start() for m in (_DIVIDER.search(answer), _NOTE_LINE.search(answer), _IMG.search(answer)) if m})
    for cut in cuts:
        main = _TRAIL.sub("", answer[:cut])
        rest = _LEAD.sub("", answer[cut:]).strip()
        if not is_blank(main) and not is_blank(rest):
            return main, {"html": rest, "images": len(_IMG.findall(rest))}
    return answer, None


def render_cloze(text: str) -> str:
    """{{c1::answer::hint}} -> highlighted span, innermost first."""

    def repl(m: re.Match) -> str:
        hint = m.group(3) or ""
        hint_attr = ' data-hint="%s"' % hint.replace('"', "&quot;") if hint else ""
        return '<span class="cz"%s>%s</span>' % (hint_attr, m.group(2))

    for _ in range(10):
        text, n = _CLOZE.subn(repl, text)
        if not n:
            break
    return text


def pretty(value: str) -> str:
    parts = [p.replace("-", " ").replace("_", " ").strip() for p in value.split("::")]
    parts = [p[:1].upper() + p[1:] for p in parts if p]
    return " › ".join(parts)


_BLOCK = re.compile(r"<(?:br|/div|/p|/li|/tr|hr)\b[^>]*>", re.I)
_IMGTAG = re.compile(r"<img\b[^>]*>", re.I)


def text_of(html: str) -> str:
    """Plain text for the AI: no markup, pictures become the word [image]."""
    import html as htmllib

    t = _IMGTAG.sub(" [image] ", html or "")
    t = _BLOCK.sub(" ", t)
    t = htmllib.unescape(_TAGS.sub("", t))
    return re.sub(r"\s+", " ", t).strip()


def row_text(row: dict) -> str:
    if row["kind"] == "cloze":
        parts = ["Statement: " + text_of(row["text"])]
    else:
        parts = ["Q: " + text_of(row["prompt"]), "A: " + text_of(row["answer"])]
        if row.get("extra"):
            parts.append("Note: " + text_of(row["extra"]["html"]))
    parts += ["%s: %s" % (d["label"], text_of(d["html"])) for d in row["details"]]
    return " | ".join(p for p in parts if p.split(": ", 1)[-1])


def is_private(deck_name: str, never: list[str]) -> bool:
    return any(deck_name == d or deck_name.startswith(d + "::") for d in never)


def ai_cards(col, nids: list[int], cfg: dict | None = None) -> dict:
    """The exact text that would be sent for these notes. Notes in a never-send
    deck are dropped here, whatever the page asked for."""
    cfg = {**DEFAULT_CONFIG, **(cfg or {})}
    ai = cfg.get("ai") or {}
    never = ai.get("never_send_decks") or []
    cap = int(ai.get("max_cards") or 200)
    nids = [int(n) for n in nids]
    home: dict[int, int] = {}
    for i in range(0, len(nids), 5000):
        chunk = ",".join(str(n) for n in nids[i : i + 5000])
        for nid, did, odid in col.db.all(
            "select nid, did, odid from cards where nid in (%s) order by ord desc" % chunk
        ):
            home[nid] = odid or did
    names: dict[int, str] = {}
    cards, excluded, models = [], 0, {}
    capped = False
    for nid in nids:
        did = home.get(nid)
        if did is None:
            continue
        name = names.get(did) or names.setdefault(did, col.decks.name(did))
        if is_private(name, never):
            excluded += 1
            continue
        if len(cards) >= cap:
            capped = True
            continue
        note = col.get_note(nid)
        model = models.get(note.mid) or models.setdefault(note.mid, note.note_type())
        cards.append((nid, row_text(note_row(note, model, cfg))))
    return {"cards": cards, "excluded": excluded, "capped": capped}


# ---------------------------------------------------------------- grouping


def tag_map(tags: list[str]) -> dict[str, str]:
    """{'topic': 'verbs', 'chapter': '3'} from hierarchical tags."""
    out: dict[str, str] = {}
    for t in tags:
        if "::" in t:
            prefix, value = t.split("::", 1)
            out.setdefault(prefix.lower(), value)
        else:
            out.setdefault("@tag", t)  # first plain tag: the fallback way to make sections
    return out


def pick_prefix(tagmaps: list[dict[str, str]], cfg: dict) -> str | None:
    """Choose the tag prefix that best splits these notes into sections."""
    if not tagmaps:
        return None
    stats: dict[str, set] = {}
    counts: dict[str, int] = {}
    for tm in tagmaps:
        for p, v in tm.items():
            stats.setdefault(p, set()).add(v)
            counts[p] = counts.get(p, 0) + 1
    plain, plain_count = stats.pop("@tag", set()), counts.pop("@tag", 0)
    stats.pop("@type", None)
    ignore = {p.lower() for p in cfg["ignore_tag_prefixes"]}
    prefs = [p.lower() for p in cfg["group_tag_prefixes"]]
    ordered = [p for p in prefs if p in stats] + sorted(
        p for p in stats if p not in prefs and p not in ignore
    )
    for p in ordered:
        if len(stats[p]) >= 2 and counts[p] >= len(tagmaps) / 2:
            return p
    # no tag family like topic::… fits: fall back to plain tags, if they split the notes into real groups
    if 2 <= len(plain) <= max(2, len(tagmaps) // 2) and plain_count >= len(tagmaps) / 2:
        return "@tag"
    return None


# ---------------------------------------------------------------- rows

_IO_MASK = re.compile(r"\{\{c(\d+)::image-occlusion:")
_IO_ENHANCED = ("ID (hidden)", "Question Mask", "Answer Mask", "Original Mask")


def occlusion_fields(names: list[str], values: dict[str, str]) -> dict | None:
    """Recognise Anki's built-in Image Occlusion notes and the older
    Image Occlusion Enhanced add-on's notes."""
    mask_field = next((n for n in names if "image-occlusion:" in values[n]), None)
    if mask_field:
        image = next((n for n in names if n != mask_field and _IMG.search(values[n])), None)
        return {"image": image, "skip": [mask_field], "one_note_per_mask": False,
                "masks": len(set(_IO_MASK.findall(values[mask_field])))}
    if "Image" in names and "Question Mask" in names:
        return {"image": "Image", "skip": [n for n in _IO_ENHANCED if n in names], "one_note_per_mask": True, "masks": 0}
    return None


def note_type_info(model: dict, cfg: dict) -> dict:
    names = [f["name"] for f in model["flds"]]
    override = cfg["note_types"].get(model["name"]) or {}
    return {"name": model["name"], "fields": names, "cloze": model.get("type") == 1,
            "prompt": override.get("prompt"), "answer": override.get("answer"),
            "hide": list(override.get("hide", [])), "custom": bool(override)}



def note_row(note, model: dict, cfg: dict) -> dict:
    names = [f["name"] for f in model["flds"]]
    values = {n: clean(v) for n, v in zip(names, note.fields)}
    override = cfg["note_types"].get(model["name"], {})
    hidden = set(override.get("hide", []))
    row: dict[str, Any] = {"nid": note.id, "details": [], "extra": None}

    io = occlusion_fields(names, values)
    if io and not override:
        # image occlusion: show the picture once, not the mask data
        row["kind"] = "qa"
        row["prompt"] = values.get("Header") or "Image occlusion"
        row["answer"] = values.get(io["image"], "") if io["image"] else ""
        row["badge"] = "%d mask%s" % (io["masks"], "" if io["masks"] == 1 else "s") if io["masks"] else "image occlusion"
        row["io_key"] = row["answer"] if io["one_note_per_mask"] else None
        used = set(io["skip"]) | {"Header", io["image"]}
    elif model.get("type") == 1 and not override:
        text_name = next((n for n in names if "{{c" in values[n]), names[0])
        row["kind"] = "cloze"
        row["text"] = render_cloze(values[text_name])
        used = {text_name}
    else:
        prompt_name = override.get("prompt", names[0])
        rest = [n for n in names if n != prompt_name]
        answer_name = override.get("answer")
        if answer_name is None:
            answer_name = next(
                (n for n in rest if not is_blank(values[n])), rest[0] if rest else None
            )
        row["kind"] = "qa"
        row["prompt"] = values.get(prompt_name, "")
        answer, extra = split_extra(values.get(answer_name, "") if answer_name else "")
        row["answer"] = answer
        row["extra"] = extra
        used = {prompt_name, answer_name}

    for n in names:
        if n in used or n in hidden or is_blank(values[n]):
            continue
        row["details"].append({"label": n, "html": values[n]})
    return row


# ---------------------------------------------------------------- queries


def build_query(col, deck_name: str | None, scope: str, cfg: dict) -> tuple[str, str]:
    """Returns (search string, sql order)."""
    parts = []
    if deck_name:
        from anki.collection import SearchNode

        parts.append(col.build_search_string(SearchNode(deck=deck_name)))
    order = "n.id asc"
    if scope == "due":
        parts.append("is:due -is:suspended")
    elif scope == "new":
        parts.append("is:new -is:suspended")
        order = "c.due asc, n.id asc"
    elif scope == "weak":
        parts.append("prop:lapses>=%d" % int(cfg["weak_lapses"]))
        order = "c.lapses desc, n.id asc"
    return " ".join(parts), order


def build_sheet(
    col,
    deck_name: str | None = None,
    scope: str = "all",
    group: str = "auto",
    limit: int | None = None,
    cfg: dict | None = None,
    max_chars: int | None = None,
) -> dict:
    cfg = {**DEFAULT_CONFIG, **(cfg or {})}
    if scope not in SCOPES:
        scope = "all"
    limit = int(limit or cfg["max_rows"])
    query, order = build_query(col, deck_name, scope, cfg)
    cids = list(col.find_cards(query, order=order))

    # one row per note: keep the first card of each note, in search order
    info: dict[int, tuple] = {}
    for i in range(0, len(cids), 5000):
        chunk = ",".join(str(c) for c in cids[i : i + 5000])
        for cid, nid, did, odid, lapses, ctype in col.db.all(
            "select id, nid, did, odid, lapses, type from cards where id in (%s)" % chunk
        ):
            info[cid] = (nid, odid or did, lapses, ctype)
    picked: dict[int, dict] = {}
    for cid in cids:
        nid, did, lapses, ctype = info[cid]
        cur = picked.get(nid)
        if cur is None:
            picked[nid] = {"did": did, "lapses": lapses, "new": ctype == 0}
        else:
            cur["lapses"] = max(cur["lapses"], lapses)
            cur["new"] = cur["new"] and ctype == 0
    total = len(picked)
    nids = list(picked)[:limit]
    budget = int(max_chars or cfg["max_chars"])  # cap on how much card text one page carries

    models: dict[int, dict] = {}
    by_deck: dict[int, list] = {}
    seen_io: dict[str, dict] = {}
    shown = 0
    for nid in nids:
        note = col.get_note(nid)
        size = sum(len(f) for f in note.fields)
        if shown and size > budget:
            break
        budget -= size
        shown += 1
        model = models.get(note.mid) or models.setdefault(note.mid, note.note_type())
        row = note_row(note, model, cfg)
        key = row.pop("io_key", None)
        if key:
            # the older add-on makes one note per mask, all with the same picture: show it once
            first = seen_io.get(key)
            if first:
                first["io_count"] += 1
                first["badge"] = "%d masks" % first["io_count"]
                first["lapses"] = max(first["lapses"], picked[nid]["lapses"])
                continue
            seen_io[key] = row
            row["io_count"] = 1
        row["lapses"] = picked[nid]["lapses"]
        row["new"] = picked[nid]["new"]
        tm = tag_map(note.tags)
        tm["@type"] = model["name"]
        by_deck.setdefault(picked[nid]["did"], []).append((row, tm))

    decks = []
    prefixes: set[str] = set()
    for did, items in by_deck.items():
        tagmaps = [tm for _, tm in items]
        for tm in tagmaps:
            prefixes.update(tm)
        if group == "auto":
            prefix = pick_prefix(tagmaps, cfg)
        elif group == "none":
            prefix = None
        else:
            prefix = group if group.startswith("@") else group.lower()
        groups: dict[str, list] = {}
        for row, tm in items:
            key = tm.get(prefix, "") if prefix else ""
            groups.setdefault(key, []).append(row)
        ordered = [k for k in groups if k] + ([""] if "" in groups else [])
        name = col.decks.name(did)
        decks.append(
            {
                "id": did,
                "name": name,
                "private": is_private(name, (cfg.get("ai") or {}).get("never_send_decks") or []),
                "short": name.split("::")[-1],
                "parents": name.split("::")[:-1],
                "count": len(items),
                "grouped_by": prefix,
                "groups": [
                    {
                        "key": k,
                        "name": (k if prefix == "@type" else pretty(k)) if k else ("Other" if prefix else ""),
                        "rows": groups[k],
                    }
                    for k in ordered
                ],
            }
        )
    decks.sort(key=lambda d: d["name"].lower())
    ignore = {p.lower() for p in cfg["ignore_tag_prefixes"]}
    return {
        "deck": deck_name,
        "scope": scope,
        "group": group,
        "query": query,
        "total": total,
        "shown": shown,
        "limit": limit,
        "group_options": sorted(p for p in prefixes if p not in ignore and not p.startswith("@")),
        "group_extra": (["@tag"] if "@tag" in prefixes else []) + (["@type"] if len(models) > 1 else []),
        "note_types": sorted((note_type_info(m, cfg) for m in models.values()), key=lambda t: t["name"].lower()),
        "decks": decks,
    }


def deck_tree(col) -> list[dict]:
    def walk(node) -> dict:
        return {
            "id": node.deck_id,
            "name": node.name,
            "full": col.decks.name(node.deck_id),
            "cards": node.total_including_children,
            "due": node.review_count + node.learn_count,
            "new": node.new_count,
            "children": [walk(c) for c in node.children],
        }

    return [walk(c) for c in col.sched.deck_due_tree().children]
