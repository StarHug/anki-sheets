"""A stand-in AI server for tests and the recorded demo.

It speaks both wire formats the add-on supports (Anthropic messages and
OpenAI-style chat completions) and returns canned answers chosen by keyword.
It is NOT a model: it proves the add-on's plumbing, not answer quality.
Every request body is kept in `requests` so tests can check exactly what the
add-on sent.
"""

from __future__ import annotations

import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

requests: list[dict] = []
_LINE = re.compile(r"^\[(\d+)\] (.*)$", re.M)


def _find(lines: list[tuple[int, str]], *words: str) -> list[int]:
    return [n for n, t in lines if all(w.lower() in t.lower() for w in words)]


def answer(system: str, messages: list[dict]) -> dict:
    text = system + "\n" + "\n".join(m["content"] for m in messages)
    lines = [(int(n), t) for n, t in _LINE.findall(text)]
    question = messages[-1]["content"].lower()
    if system.startswith("You turn a set of flashcards"):
        if _find(lines, "ser vs estar"):
            return {
                "condensable": True,
                "intro": "Ser says what something is, and estar says how or where it is right now.",
                "blocks": [
                    {"type": "table", "columns": ["Use", "Verb", "Example"], "rows": [
                        {"cells": ["Identity and lasting traits", "ser", "Soy profesora"], "sources": _find(lines, "identity")},
                        {"cells": ["States and feelings", "estar", "Estoy cansado"], "sources": _find(lines, "states and feelings")},
                        {"cells": ["Location", "estar, but **ser** for events", "Madrid está en España"], "sources": _find(lines, "location") + _find(lines, "basic difference")},
                        {"cells": ["Time and date", "ser", "Son las tres"], "sources": _find(lines, "the time")},
                    ]},
                    {"type": "steps", "items": [
                        {"text": "Present tense of ser: soy → eres → es → somos → sois → son", "sources": _find(lines, "present tense")}]},
                ],
                "gaps": ["Estar in the present tense", "Past tenses"],
            }
        if _find(lines, "は vs が"):
            return {
                "condensable": True,
                "intro": "Particles are short words placed after a noun to show its role in the sentence.",
                "blocks": [
                    {"type": "table", "columns": ["Particle", "Marks", "Example"], "rows": [
                        {"cells": ["は", "The **topic**; read wa", "私は学生です"], "sources": _find(lines, "は vs が") + _find(lines, "read wa")},
                        {"cells": ["が", "The **subject**, often new information", "猫がいます"], "sources": _find(lines, "は vs が")},
                        {"cells": ["を", "The **direct object**", "パンを食べます"], "sources": _find(lines, "direct object")},
                        {"cells": ["に", "A point in time; where something **is or arrives**", "七時に起きます"], "sources": _find(lines, "point in time") + _find(lines, "に vs で")},
                        {"cells": ["で", "Where an **action happens**; the means used", "バスで行きます"], "sources": _find(lines, "に vs で") + _find(lines, "means")},
                        {"cells": ["の", "**Possession** between two nouns", "私の本"], "sources": _find(lines, "possession")},
                        {"cells": ["か", "A **question**", "学生ですか"], "sources": _find(lines, "question")},
                    ]},
                ],
                "gaps": ["も (also)", "と (and, with)"],
            }
        if _find(lines, "[Restaurant"):
            return {
                "condensable": True,
                "intro": "Three polite restaurant phrases. Each one ends with por favor.",
                "blocks": [{"type": "list", "items": [
                    {"text": "**La cuenta, por favor.** Ask for the bill; it is not brought until you do.", "sources": _find(lines, "bill")},
                    {"text": "**Un café con leche, por favor.** A coffee with milk.", "sources": _find(lines, "coffee")},
                    {"text": "**Una mesa para dos, por favor.** A table for two.", "sources": _find(lines, "table for two")},
                ]}],
                "gaps": [],
            }
        return {"condensable": False, "reason": "These cards are separate facts without a shared structure."}
    if "subjunctive" in question:
        if "do NOT use outside knowledge" in system:
            return {"answer": "Your cards don't cover the subjunctive. The closest ones are about ser and estar.", "basis": "none", "sources": []}
        return {"answer": "It expresses wishes, doubts and things that are not certain, usually after que.", "basis": "general", "sources": []}
    if "difference" in question:
        return {"answer": "**Ser** says what something is: identity and lasting traits. **Estar** says how or where it is right now. Some adjectives change meaning: ser aburrido is boring, estar aburrido is bored.",
                "basis": "cards", "sources": _find(lines, "ser vs estar") + _find(lines, "aburrido") + _find(lines, "listo")}
    return {"answer": "Based on your cards: " + (lines[0][1][:80] if lines else "no cards were sent."), "basis": "cards", "sources": [lines[0][0]] if lines else []}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a) -> None:
        pass

    def _send(self, code: int, body: dict) -> None:
        raw = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self) -> None:
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        requests.append({"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()}, "body": body})
        if self.path.endswith("/messages"):
            if self.headers.get("x-api-key") != "test-key":
                return self._send(401, {"type": "error", "error": {"type": "authentication_error", "message": "invalid x-api-key"}})
            out = answer(body["system"], body["messages"])
            return self._send(200, {"content": [{"type": "text", "text": "Here you go:\n" + json.dumps(out)}]})
        if self.path.endswith("/chat/completions"):
            msgs = body["messages"]
            out = answer(msgs[0]["content"], msgs[1:])
            return self._send(200, {"choices": [{"message": {"role": "assistant", "content": json.dumps(out)}}]})
        self._send(404, {"error": "not found"})


def start(port: int = 0) -> tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, "http://127.0.0.1:%d" % server.server_address[1]
