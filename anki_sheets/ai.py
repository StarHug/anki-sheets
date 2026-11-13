"""AI features for Sheets: Condense (cheat-sheet block for a section) and Ask.

No GUI imports. Requests go straight from this computer to the provider the
user configured; nothing here runs unless the user clicks Condense or sends a
question.
"""

from __future__ import annotations

import hashlib
import json
import re
import os
import urllib.error
import urllib.request
from typing import Any

DEFAULT_AI: dict[str, Any] = {
    "enabled": False,
    "provider": "anthropic",  # or "openai_compatible" (also local models, e.g. Ollama)
    "api_key": "",
    "model": "",
    "base_url": "",
    "max_cards": 200,
    "never_send_decks": [],
}
DEFAULT_MODELS = {"anthropic": "claude-sonnet-5-5", "openai_compatible": ""}
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


class AIError(Exception):
    pass


def merged(ai_cfg: dict | None) -> dict:
    return {**DEFAULT_AI, **(ai_cfg or {})}


def ready(ai_cfg: dict) -> bool:
    c = merged(ai_cfg)
    if not c["enabled"]:
        return False
    if c["provider"] == "anthropic":
        return bool(c["api_key"])
    return bool(c["base_url"] and c["model"])  # local models need no key


# ---------------------------------------------------------------- transport


def _post(url: str, headers: dict, body: dict, timeout: int = 240) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers={"content-type": "application/json", **headers}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        try:
            err = json.loads(detail).get("error")
            detail = err.get("message", detail) if isinstance(err, dict) else (err or detail)
        except Exception:
            pass
        raise AIError(_explain(e.code, detail)) from None
    except TimeoutError:
        raise AIError("The AI service took too long to answer. Try again, or try a smaller section.") from None
    except (urllib.error.URLError, OSError) as e:
        reason = getattr(e, "reason", e)
        if isinstance(reason, TimeoutError) or "timed out" in str(reason):
            raise AIError("The AI service took too long to answer. Try again, or try a smaller section.") from None
        raise AIError("Couldn't reach the AI service (%s). Check your internet connection and the "
                      "server address in AI settings." % reason) from None


def _explain(code: int, detail: str) -> str:
    """A plain sentence for each kind of refusal, with the service's own words after it."""
    if code in (401, 403):
        lead = "The AI service didn't accept the API key. Check the key in AI settings."
    elif code == 402:
        lead = "The AI service says the account is out of credit. Add credit with your provider, then try again."
    elif code == 404:
        lead = "The AI service couldn't find that model or address. Check the model name and server address in AI settings."
    elif code == 429:
        lead = "The AI service is limiting requests, or the account is out of credit. Wait a minute and try again."
    elif code >= 500:
        lead = "The AI service is having trouble right now. Try again in a few minutes."
    else:
        lead = "The AI service turned down the request."
    return "%s (%d: %s)" % (lead, code, detail.strip()[:200]) if detail.strip() else "%s (%d)" % (lead, code)


def call_model(ai_cfg: dict, system: str, messages: list[dict], max_tokens: int = 2000) -> str:
    return _complete(ai_cfg, system, messages, max_tokens)[0]



def _complete(ai_cfg: dict, system: str, messages: list[dict], max_tokens: int) -> tuple[str, bool]:
    """The reply text, and whether the model stopped because it hit the length limit."""
    c = merged(ai_cfg)
    model = c["model"] or DEFAULT_MODELS.get(c["provider"], "")
    if c["provider"] == "anthropic":
        out = _post(
            c["base_url"] or ANTHROPIC_URL,
            {"x-api-key": c["api_key"], "anthropic-version": "2023-06-01"},
            {"model": model, "max_tokens": max_tokens, "system": system, "messages": messages},
        )
        text = "".join(b.get("text", "") for b in out.get("content", []) if b.get("type") == "text")
        return text, out.get("stop_reason") == "max_tokens"
    headers = {"authorization": "Bearer " + c["api_key"]} if c["api_key"] else {}
    url = c["base_url"].rstrip("/") + "/chat/completions"
    body = {"model": model, "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": system}] + messages}
    try:
        out = _post(url, headers, body)
    except AIError as e:
        # newer OpenAI models take the same limit under a different name
        if "max_completion_tokens" not in str(e):
            raise
        body["max_completion_tokens"] = body.pop("max_tokens")
        out = _post(url, headers, body)
    try:
        choice = out["choices"][0]
        return choice["message"].get("content") or "", choice.get("finish_reason") == "length"
    except (KeyError, IndexError, TypeError):
        raise AIError("The AI service sent a reply this add-on couldn't read.") from None


UNUSABLE = "The AI didn't return a usable answer. Try again."


def parse_json(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise AIError(UNUSABLE)
    raw = text[start : end + 1]
    try:
        out = json.loads(raw)
    except ValueError:
        # the commonest slip from smaller models: a comma before a closing bracket
        try:
            out = json.loads(re.sub(r",\s*([}\]])", r"\1", raw))
        except ValueError:
            raise AIError(UNUSABLE) from None
    if not isinstance(out, dict):
        raise AIError(UNUSABLE)
    return out


def ask_json(ai_cfg: dict, system: str, messages: list[dict], max_tokens: int, check=lambda d: d) -> dict:
    """Ask for a JSON reply. One retry when the reply is cut off, unreadable, or the wrong shape.
    `check` turns the parsed reply into the result, raising AIError if it can't be used."""
    text, cut = _complete(ai_cfg, system, messages, max_tokens)
    try:
        if not cut:
            return check(parse_json(text))
    except AIError:
        pass
    room = min(max_tokens * 2, 8000)
    if cut:  # it ran out of room: say how much it has this time
        note = ("Your reply was cut off because it hit the length limit. This time the limit is about %d words. "
                "Send the complete JSON object again so it fits, and nothing else." % (room * 3 // 4))
    else:
        note = ("That reply could not be used: it was not valid JSON in the shape asked for. "
                "Send the complete JSON object again, in exactly that shape, and nothing else.")
    retry = messages + [{"role": "assistant", "content": text[:2000] or "(empty)"}, {"role": "user", "content": note}]
    text, _ = _complete(ai_cfg, system, retry, room)
    return check(parse_json(text))


# ---------------------------------------------------------------- prompts


def cards_block(cards: list[tuple[int, str]]) -> str:
    return "\n".join("[%d] %s" % (i + 1, text) for i, (_, text) in enumerate(cards))


CONDENSE_SYSTEM = """You turn a set of flashcards about one topic into a compact cheat-sheet block, the notes someone would have written before making the cards.

Rules:
- Use ONLY facts stated in the cards. Never add outside knowledge, even if the cards are incomplete.
- Start with "intro": one plain sentence saying what the topic is, so a reader with no context knows what they are looking at.
- Then 1 or 2 "blocks". Pick the layout that fits the cards:
  - "table": parallel items that share the same properties (layers, types, options), or two things being compared. First column names the item.
  - "steps": a sequence or process, in order.
  - "list": principles, rules or standalone points. Start each with a short **bold lead phrase**.
- Keep every cell and item short (under 15 words). No filler.
- "sources": the card numbers each row or item came from. Cover every card somewhere if you can.
- "gaps": things the cards themselves name but never explain (for example a list names seven items and only four have their own card). Empty list if none.
- If the cards are unrelated facts with no shared structure, return {"condensable": false, "reason": "<one short sentence>"} and nothing else.

Return ONLY JSON in this shape:
{"condensable": true, "intro": "...", "blocks": [{"type": "table", "columns": ["...", "..."], "rows": [{"cells": ["...", "..."], "sources": [1, 2]}]}, {"type": "steps", "items": [{"text": "...", "sources": [3]}]}, {"type": "list", "items": [{"text": "**Lead.** ...", "sources": [4]}]}], "gaps": ["..."]}"""

ASK_SYSTEM = """You answer questions about the user's own flashcards, listed below with numbers.

Rules:
- Answer from the cards whenever they cover the question. Put the card numbers you used in "sources" and set "basis" to "cards".
- %s
- Keep answers short and plain: at most 90 words, no headings. **Bold** is allowed for key terms.
- Never invent what a card says.

Return ONLY JSON: {"answer": "...", "basis": "cards" | "general" | "none", "sources": [1, 2]}"""

ASK_STRICT = 'If the cards do not cover it, do NOT use outside knowledge: set "basis" to "none" and say the cards don\'t cover this, naming the closest card topic if there is one.'
ASK_OPEN = 'If the cards do not cover it, answer briefly from general knowledge and set "basis" to "general" with empty "sources". If only part of the answer is in the cards, use "general" and say which part goes beyond the cards.'


# ---------------------------------------------------------------- features


def _nids(sources: Any, cards: list[tuple[int, str]]) -> list[int]:
    out = []
    for s in sources if isinstance(sources, list) else []:
        if isinstance(s, int) and not isinstance(s, bool) and 1 <= s <= len(cards) and cards[s - 1][0] not in out:
            out.append(cards[s - 1][0])
    return out


def _s(v: Any) -> str:
    return v.strip() if isinstance(v, str) else ("" if v is None else str(v))


def normalize_summary(raw: dict, cards: list[tuple[int, str]]) -> dict:
    """Validate the model's JSON so the page only ever renders known shapes."""
    if raw.get("condensable") is False:
        return {"condensable": False, "reason": _s(raw.get("reason")) or "These cards don't share a structure to summarise."}
    blocks = []
    for b in raw.get("blocks") if isinstance(raw.get("blocks"), list) else []:
        if not isinstance(b, dict):
            continue
        kind = b.get("type")
        if kind == "table":
            cols = [_s(c) for c in b.get("columns", []) if _s(c)][:6]
            rows = []
            for r in b.get("rows", []) if isinstance(b.get("rows"), list) else []:
                if isinstance(r, dict) and isinstance(r.get("cells"), list) and cols:
                    cells = ([_s(c) for c in r["cells"]] + [""] * len(cols))[: len(cols)]
                    if any(cells):
                        rows.append({"cells": cells, "sources": _nids(r.get("sources"), cards)})
            if cols and rows:
                blocks.append({"type": "table", "columns": cols, "rows": rows})
        elif kind in ("steps", "list"):
            items = [
                {"text": _s(i.get("text")), "sources": _nids(i.get("sources"), cards)}
                for i in (b.get("items") if isinstance(b.get("items"), list) else [])
                if isinstance(i, dict) and _s(i.get("text"))
            ]
            if items:
                blocks.append({"type": kind, "items": items})
    if not blocks:
        raise AIError("The AI didn't return a usable summary. Try again.")
    gaps = [_s(g) for g in raw.get("gaps", []) if _s(g)] if isinstance(raw.get("gaps"), list) else []
    return {"condensable": True, "intro": _s(raw.get("intro")), "blocks": blocks[:2], "gaps": gaps[:8]}


def condense(ai_cfg: dict, title: str, cards: list[tuple[int, str]]) -> dict:
    user = "Topic label: %s\n\nCards:\n%s" % (title, cards_block(cards))
    out = ask_json(ai_cfg, CONDENSE_SYSTEM, [{"role": "user", "content": user}], 8000,
                   lambda raw: normalize_summary(raw, cards))
    out["count"] = len(cards)
    return out


def ask(ai_cfg: dict, title: str, cards: list[tuple[int, str]], history: list[dict],
        question: str, strict: bool) -> dict:
    system = ASK_SYSTEM % (ASK_STRICT if strict else ASK_OPEN)
    system += "\n\nSheet: %s\n\nCards:\n%s" % (title, cards_block(cards))
    messages = []
    for turn in history[-6:]:
        if turn.get("role") in ("user", "assistant") and _s(turn.get("text")):
            messages.append({"role": turn["role"], "content": _s(turn["text"])})
    messages.append({"role": "user", "content": question})
    def has_answer(raw: dict) -> dict:
        if not _s(raw.get("answer")):
            raise AIError(UNUSABLE)
        return raw

    raw = ask_json(ai_cfg, system, messages, 3000, has_answer)
    basis = raw.get("basis") if raw.get("basis") in ("cards", "general", "none") else "cards"
    if strict and basis == "general":
        basis = "none"
    answer = _s(raw.get("answer"))
    if not answer:
        raise AIError(UNUSABLE)
    return {"answer": answer, "basis": basis,
            "sources": _nids(raw.get("sources"), cards) if basis == "cards" else []}


def test_connection(ai_cfg: dict) -> str:
    """One tiny request with no card content, to check the key and address."""
    c = merged(ai_cfg)
    if c["provider"] == "anthropic" and not c["api_key"]:
        raise AIError("Paste an API key first.")
    if c["provider"] != "anthropic" and not (c["base_url"] and c["model"]):
        raise AIError("Fill in the server address and model first.")
    reply = call_model(c, "Reply with the single word OK.", [{"role": "user", "content": "ping"}], 16)
    if not reply.strip():
        raise AIError("The AI service answered, but with an empty reply.")
    return reply.strip()[:60]


# ---------------------------------------------------------------- saved summaries


def fingerprint(pairs: list[tuple[int, int]]) -> str:
    """Changes when any card in the section is added, removed or edited."""
    return hashlib.sha1(json.dumps(sorted(pairs)).encode()).hexdigest()[:16]


class SummaryStore:
    """Summaries live in the add-on's user_files folder, not in the collection,
    so they never touch cards, scheduling or sync."""

    def __init__(self, path: str) -> None:
        self.path = path
        try:
            with open(path, encoding="utf-8") as f:
                self.data = json.load(f)
        except (OSError, ValueError):
            self.data = {}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False)
        os.replace(tmp, self.path)

    def get(self, key: str) -> dict | None:
        return self.data.get(key)

    def set(self, key: str, summary: dict, fp: str) -> None:
        self.data[key] = {"summary": summary, "fp": fp}
        self._save()

    def delete(self, key: str) -> None:
        if self.data.pop(key, None) is not None:
            self._save()


class TickStore:
    """Review ticks: a personal checklist kept in the add-on's user_files.
    Never written to the collection, so scheduling and sync are untouched."""

    def __init__(self, path: str) -> None:
        self.path = path
        try:
            with open(path, encoding="utf-8") as f:
                self.ids = {int(n) for n in json.load(f)}
        except (OSError, ValueError, TypeError):
            self.ids = set()

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(sorted(self.ids), f)
        os.replace(tmp, self.path)

    def set(self, nid: int, on: bool) -> None:
        before = len(self.ids)
        (self.ids.add if on else self.ids.discard)(int(nid))
        if len(self.ids) != before:
            self._save()

    def reset(self, nids: list[int]) -> int:
        hit = self.ids & {int(n) for n in nids}
        if hit:
            self.ids -= hit
            self._save()
        return len(hit)
