var Sheets = (function () {
  var VIEW_DEFAULTS = { ticks: false, hideTicked: false, density: "comfortable", emphasis: "question",
                        theme: "anki", notesOpen: false, split: null, side: null, page: null };
  var S = { tree: [], deck: null, scope: "all", mode: "read", groups: {}, limit: null,
            filter: "", deckFilter: "", open: {}, data: null, view: Object.assign({}, VIEW_DEFAULTS), viewOpen: false,
            ai: { enabled: false, ready: false, never_send_decks: [], max_cards: 200 },
            fold: {}, askOpen: false, chat: [], strict: false, cond: {}, pending: {}, seq: 0 };
  var SCOPES = [["all", "All cards"], ["due", "Due"], ["new", "New"], ["weak", "Weak spots"]];
  var MODES = [["read", "Read"], ["cover", "Cover answers"], ["compact", "Compact"]];
  var DENSITY = [["comfortable", "Comfortable"], ["tight", "Tight"]];
  var EMPHASIS = [["question", "Bold question"], ["tint", "Tinted question"], ["answer", "Bold answer"]];
  var THEMES = [["anki", "Match Anki"], ["paper", "Paper"], ["contrast", "High contrast"]];
  // hover hints: every control explains itself
  var HINT = {
    all: "Every card in this deck", due: "Only cards Anki has due for review now", "new": "Only cards you have not studied yet, in the order Anki will show them",
    weak: "Cards you have forgotten at least twice, worst first",
    read: "Questions and answers both visible", cover: "Answers hidden until you click a row. A quick self-test that does not affect scheduling",
    compact: "Small text in two columns with notes hidden: the cheat-sheet layout, good for printing",
    comfortable: "Normal spacing between rows", tight: "Less space between rows, so more fits on screen",
    question: "Questions in bold (the default)", tint: "Questions on a shaded background, so the two columns are easy to tell apart",
    answer: "Answers in bold, questions lighter",
    anki: "Follows Anki's light or dark mode", paper: "Warm, low-glare colours", contrast: "Maximum contrast between text and background"
  };
  var SPLIT_DEFAULT = 40, SPLIT_MIN = 15, SPLIT_MAX = 70;
  var SPARK = '<svg aria-hidden="true" width="15" height="15" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M9 2.5l1.5 4 4 1.5-4 1.5-1.5 4-1.5-4-4-1.5 4-1.5z"/></svg>';
  var app = document.getElementById("app");

  function call(name, arg) {
    return new Promise(function (resolve) {
      pycmd("sheets:" + name + ":" + JSON.stringify(arg || {}), resolve);
    });
  }

  // AI calls return at once; the answer arrives later through aiDone(req, payload)
  function aiCall(name, arg, handler) {
    var req = ++S.seq;
    S.pending[req] = handler;
    arg.req = req;
    call(name, arg).then(function (r) {
      if (!r || !r.started) {
        delete S.pending[req];
        handler({ ok: false, error: (r && r.error) || "Could not start the request." });
      }
    });
  }

  function aiDone(req, payload) {
    var handler = S.pending[req];
    delete S.pending[req];
    if (handler) handler(payload);
  }

  // Card fields can come from shared decks, so their HTML is parsed without running anything,
  // then stripped of every way to run code, before it goes on the page.
  var DROP_TAGS = /^(script|iframe|frame|frameset|object|embed|applet|base|meta|link|form|portal|noscript)$/i;
  var BAD_URL = /^(javascript|vbscript|data:text\/html|data:image\/svg)/i;
  function cardHTML(src) {
    var t = document.createElement("template");
    t.innerHTML = src || "";
    var walk = document.createTreeWalker(t.content, NodeFilter.SHOW_ELEMENT), dead = [], el;
    while ((el = walk.nextNode())) {
      if (DROP_TAGS.test(el.localName)) { dead.push(el); continue; }
      for (var i = el.attributes.length - 1; i >= 0; i--) {
        var a = el.attributes[i], name = a.name.toLowerCase();
        var val = a.value.replace(/[\u0000-\u0020\u007f-\u00a0]+/g, "").toLowerCase();
        if (name.slice(0, 2) === "on" || name === "srcdoc" || name === "formaction" || BAD_URL.test(val))
          el.removeAttribute(a.name);
      }
    }
    dead.forEach(function (n) { n.remove(); });
    return t.content;
  }

  function h(tag, attrs) {
    var el = document.createElement(tag);
    for (var k in attrs || {}) {
      var v = attrs[k];
      if (v == null || v === false) continue;
      if (k === "html") el.innerHTML = v;
      else if (k === "card") el.appendChild(cardHTML(v));
      else if (k === "text") el.textContent = v;
      else if (k.slice(0, 2) === "on") el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? "" : v);
    }
    for (var i = 2; i < arguments.length; i++) {
      var c = arguments[i];
      if (c == null || c === false) continue;
      if (Array.isArray(c)) c.forEach(function (x) { if (x) el.appendChild(x); });
      else el.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    }
    return el;
  }

  function put(el, kids) { el.replaceChildren.apply(el, kids.filter(Boolean)); }
  function fmt(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ","); }
  function plural(n, word) { return fmt(n) + " " + word + (n === 1 ? "" : "s"); }
  function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
  // AI text is untrusted: escape everything, then allow **bold** and line breaks only
  function rich(s) { return esc(s).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/\n/g, "<br>"); }
  var LOGO = '<svg class="logo" viewBox="0 0 512 512" aria-hidden="true"><rect width="512" height="512" rx="112" fill="#1f3fa8"/>' +
    '<rect x="112" y="92" width="264" height="340" rx="28" fill="#fbf8f1"/>' +
    '<g fill="#1f3fa8"><rect x="144" y="150" width="78" height="18" rx="9"/><rect x="144" y="214" width="78" height="18" rx="9"/><rect x="144" y="278" width="78" height="18" rx="9"/><rect x="144" y="342" width="78" height="18" rx="9"/></g>' +
    '<g fill="#b9c3de"><rect x="244" y="150" width="100" height="18" rx="9"/><rect x="244" y="214" width="100" height="18" rx="9"/><rect x="244" y="278" width="100" height="18" rx="9"/><rect x="244" y="342" width="72" height="18" rx="9"/></g>' +
    '<path d="M384 62 C392 108 404 120 450 128 C404 136 392 148 384 194 C376 148 364 136 318 128 C364 120 376 108 384 62 Z" fill="#ffc94a" stroke="#1f3fa8" stroke-width="12" stroke-linejoin="round"/></svg>';
  function brand() { return h("h1", { class: "brand" }, h("span", { html: LOGO }), "IchiSheet"); }
  function title() { return S.home ? "IchiSheet" : S.deck ? S.deck.split("::").pop() : "All decks"; }
  function allRows() {
    var out = [];
    ((S.data && !S.data.__error && S.data.decks) || []).forEach(function (d) { d.groups.forEach(function (g) { g.rows.forEach(function (r) { out.push(r); }); }); });
    return out;
  }

  // ---------------------------------------------------------------- sidebar

  function ancestorsOpen(nodes, full) {
    nodes.forEach(function (n) {
      if (full && full.indexOf(n.full + "::") === 0) { S.open[n.id] = true; ancestorsOpen(n.children, full); }
    });
  }

  function flat(nodes, out, depth) {
    nodes.forEach(function (n) { n.depth = depth || 0; out.push(n); flat(n.children, out, (depth || 0) + 1); });
    return out;
  }

  function nodeEl(n, label) {
    var kids = n.children.length > 0, open = !!S.open[n.id];
    return h("div", { class: "node" + (S.deck === n.full ? " on" : "") },
      h("button", { class: "tw" + (kids && !label ? "" : " none"), type: "button",
        "aria-label": (open ? "Collapse " : "Expand ") + n.name, "aria-expanded": String(open),
        onclick: function () { S.open[n.id] = !open; renderSide(); } }, open ? "▾" : "▸"),
      h("button", { class: "dk", type: "button", title: n.full, "data-deck": n.full,
        onclick: function () { selectDeck(n.full); } },
        label ? h("span", {}, n.name, h("small", { class: "path", text: label })) : h("span", { text: n.name }),
        h("span", { class: "n", text: fmt(n.cards) })));
  }

  function treeEl(nodes) {
    return h("ul", {}, nodes.map(function (n) {
      return h("li", {}, nodeEl(n), n.children.length && S.open[n.id] ? treeEl(n.children) : null);
    }));
  }

  function renderSide() {
    var list = app.querySelector(".side .tree");
    var q = S.deckFilter.trim().toLowerCase();
    var body;
    if (q) {
      var hits = flat(S.tree, []).filter(function (n) { return n.full.toLowerCase().indexOf(q) >= 0; }).slice(0, 80);
      body = h("ul", {}, hits.map(function (n) { return h("li", {}, nodeEl(n, n.full.split("::").slice(0, -1).join(" › ") || " ")); }));
    } else {
      body = treeEl(S.tree);
    }
    var total = S.tree.reduce(function (a, n) { return a + n.cards; }, 0);
    var all = h("div", { class: "node" + (S.deck || S.home ? "" : " on") },
      h("button", { class: "tw none", type: "button", tabindex: "-1", "aria-hidden": "true" }),
      h("button", { class: "dk", type: "button", "data-deck": "", onclick: function () { selectDeck(null); } },
        h("span", { text: "All decks" }), h("span", { class: "n", text: fmt(total) })));
    put(list, [all, body]);
  }

  // ---------------------------------------------------------------- view options

  // The Sections choice is remembered per deck. A deck with no choice of its own uses its
  // nearest parent's, and otherwise Automatic.
  function groupFor(deck) {
    var name = deck || "";
    while (true) {
      if (S.groups[name]) return S.groups[name];
      var cut = name.lastIndexOf("::");
      if (cut < 0) return "auto";
      name = name.slice(0, cut);
    }
  }
  function setGroup(value) {
    var key = S.deck || "";
    delete S.groups[key];
    if (value !== groupFor(S.deck)) S.groups[key] = value;  // only store what differs from what it would inherit
  }

  function mainClass() {
    return "main mode-" + S.mode + " em-" + S.view.emphasis +
      (S.view.density === "tight" ? " dense" : "") + (S.view.ticks ? " ticks-on" : "");
  }

  function applyView() {
    app.className = "theme-" + S.view.theme;
    var main = app.querySelector(".main");
    if (!main) return;
    applySide();
    main.className = mainClass();
    main.style.setProperty("--qw", (S.view.split || SPLIT_DEFAULT) + "%");
    if (S.view.page) main.style.setProperty("--pw", S.view.page + "px"); else main.style.removeProperty("--pw");
  }

  function setSplit(pct, persist) {
    S.view.split = pct == null ? null : Math.max(SPLIT_MIN, Math.min(SPLIT_MAX, Math.round(pct * 10) / 10));
    applyView();
    if (persist) save();
  }

  // the edge between the deck list and the sheet is a drag handle, so long deck names can be read
  var SIDE_DEFAULT = 264, SIDE_MIN = 180, SIDE_MAX = 640, lastSideDown = 0;
  function applySide() {
    var side = app.querySelector(".side");
    if (side) side.style.flexBasis = Math.min(S.view.side || SIDE_DEFAULT, Math.max(SIDE_MIN, window.innerWidth - 360)) + "px";
  }
  function setSide(px, persist) {
    S.view.side = px == null ? null : Math.max(SIDE_MIN, Math.min(SIDE_MAX, Math.round(px)));
    applySide();
    if (persist) save();
  }
  // the sheet's right edge drags the same way, to make the page wider or narrower
  var PAGE_MIN = 520, PAGE_MAX = 4000;
  function setPage(px, persist) {
    S.view.page = px == null ? null : Math.max(PAGE_MIN, Math.min(PAGE_MAX, Math.round(px)));
    applyView();
    if (persist) save();
  }
  function sideGrip() { return grip("sidegrip", "Deck list width", "Drag to resize the deck list. Double-click to reset.",
    ".side", setSide, function () { return S.view.side || SIDE_DEFAULT; }); }
  function pageGrip() { return grip("pagegrip", "Sheet width", "Drag to make the sheet wider or narrower. Double-click to reset.",
    ".pagewrap", setPage, function () { return S.view.page || 940; }); }
  function grip(cls, label, tip, boxSel, set, get) {
    var el = h("div", { class: cls, role: "separator", "aria-orientation": "vertical", tabindex: "0", "aria-label": label, title: tip });
    function setSide(px, persist) { set(px, persist); }
    el.addEventListener("pointerdown", function (e) {
      e.preventDefault();
      el.setPointerCapture(e.pointerId);
      var now = Date.now();
      if (now - lastSideDown < 450) { lastSideDown = 0; setSide(null, true); return; }
      lastSideDown = now;
      var startX = e.clientX, moved = false, left = app.querySelector(boxSel).getBoundingClientRect().left;
      function move(ev) {
        if (!moved && Math.abs(ev.clientX - startX) < 4) return;
        moved = true;
        lastSideDown = 0;
        document.body.classList.add("dragging");
        setSide(ev.clientX - left, false);
      }
      function up() {
        el.removeEventListener("pointermove", move);
        el.removeEventListener("pointerup", up);
        el.removeEventListener("pointercancel", up);
        document.body.classList.remove("dragging");
        if (moved) save();
      }
      el.addEventListener("pointermove", move);
      el.addEventListener("pointerup", up);
      el.addEventListener("pointercancel", up);
    });
    el.addEventListener("dblclick", function () { setSide(null, true); });
    el.addEventListener("keydown", function (e) {
      var cur = get();
      if (e.key === "ArrowLeft") setSide(cur - 16, true);
      else if (e.key === "ArrowRight") setSide(cur + 16, true);
      else if (e.key === "Home" || e.key === "Enter") setSide(null, true);
    });
    return el;
  }

  // the gap between question and answer is a drag handle; any row's handle moves every row
  var lastSplitDown = 0;
  function splitEl(row) {
    var el = h("div", { class: "split", role: "separator", "aria-orientation": "vertical", tabindex: "0",
      "aria-label": "Column divider", title: "Drag to resize the columns. Double-click to reset." });
    el.addEventListener("pointerdown", function (e) {
      e.preventDefault();
      e.stopPropagation();
      el.setPointerCapture(e.pointerId);
      var main = app.querySelector(".main");
      main.classList.add("dragging");
      // two quick presses without a drag = reset (handled here so it works the same on every platform)
      var now = Date.now();
      if (now - lastSplitDown < 450) { lastSplitDown = 0; setSplit(null, true); return; }
      lastSplitDown = now;
      var startX = e.clientX, moved = false;
      function move(ev) {
        if (!moved && Math.abs(ev.clientX - startX) < 4) return;  // a click or double-click, not a drag
        moved = true;
        lastSplitDown = 0;
        // --qw is a share of the row's content box, so leave the padding out
        var rect = row.getBoundingClientRect(), cs = getComputedStyle(row);
        var padL = parseFloat(cs.paddingLeft) || 0, padR = parseFloat(cs.paddingRight) || 0;
        var x = ev.clientX - rect.left - padL - (S.view.ticks ? 30 : 0) - 12;
        setSplit(x / (rect.width - padL - padR) * 100, false);
        main.classList.add("dragging");
      }
      function up() {
        el.removeEventListener("pointermove", move);
        el.removeEventListener("pointerup", up);
        el.removeEventListener("pointercancel", up);
        app.querySelector(".main").classList.remove("dragging");
        if (moved) save();
      }
      el.addEventListener("pointermove", move);
      el.addEventListener("pointerup", up);
      el.addEventListener("pointercancel", up);
    });
    el.addEventListener("click", function (e) { e.stopPropagation(); });
    el.addEventListener("dblclick", function (e) { e.stopPropagation(); setSplit(null, true); });
    el.addEventListener("keydown", function (e) {
      var cur = S.view.split || SPLIT_DEFAULT;
      if (e.key === "ArrowLeft") setSplit(cur - 2, true);
      else if (e.key === "ArrowRight") setSplit(cur + 2, true);
      else if (e.key === "Home" || e.key === "Enter") setSplit(null, true);
    });
    return el;
  }

  function segV(items, key, label, after) {
    return h("div", { class: "seg", role: "group", "aria-label": label }, items.map(function (it) {
      var b = h("button", { type: "button", "aria-pressed": String(S.view[key] === it[0]),
        onclick: function () { S.view[key] = it[0]; applyView(); save(); renderView(); if (after) after(); } }, it[1]);
      b.setAttribute("data-" + key, it[0]);
      if (HINT[it[0]]) b.title = HINT[it[0]];
      return b;
    }));
  }

  function checkV(key, label, id, hint, after) {
    return h("label", { class: "check explained", title: hint },
      h("input", { type: "checkbox", id: id, checked: S.view[key],
        onchange: function (e) { S.view[key] = e.target.checked; applyView(); save(); if (after) after(); } }),
      h("span", {}, h("span", { text: label }), h("small", { text: hint })));
  }

  function renderView() {
    var old = app.querySelector(".viewveil");
    if (old) old.remove();
    old = app.querySelector(".viewpanel");
    if (old) old.remove();
    if (!S.viewOpen) return;
    var main = app.querySelector(".main");
    function close() { S.viewOpen = false; renderView(); renderBar(); }
    var extraNames = { "@tag": "First tag", "@type": "Note type" };
    var opts = [["auto", "Automatic"], ["none", "No sections"]].concat(
      ((S.data && S.data.group_extra) || []).map(function (p) { return [p, extraNames[p]]; }),
      ((S.data && S.data.group_options) || []).map(function (p) { return [p, "Tag: " + p + "::…"]; }));
    var current = groupFor(S.deck);
    var group = h("select", { id: "group", onchange: function (e) { setGroup(e.target.value); save(); load(); } },
      opts.map(function (o) { return h("option", { value: o[0], selected: current === o[0] }, o[1]); }));
    var panel = h("div", { class: "viewpanel", role: "dialog", "aria-label": "View options",
      onkeydown: function (e) { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); close(); } } },
      h("label", { class: "vrow", title: "How rows are split into headed sections. Automatic picks a tag family such as topic::…, or plain tags. Your choice is remembered for this deck and its sub-decks." },
        h("span", { text: "Sections" }), group),
      h("small", { class: "vnote", id: "group-note", text: "Remembered for “" + (S.deck ? S.deck.split("::").pop() : "All decks") + "” and its sub-decks." }),
      h("div", { class: "vrow", title: "How much space there is between rows" }, h("span", { text: "Spacing" }), segV(DENSITY, "density", "Row spacing")),
      h("div", { class: "vrow", title: "Which side stands out when you skim" }, h("span", { text: "Emphasis" }), segV(EMPHASIS, "emphasis", "Question and answer emphasis")),
      h("div", { class: "vrow", title: "Colours of the sheet" }, h("span", { text: "Theme" }), segV(THEMES, "theme", "Theme")),
      h("div", { class: "vrow", title: "You can drag the gap between question and answer on any row to resize the columns" }, h("span", { text: "Columns" }),
        h("button", { class: "btn small", type: "button", id: "split-reset", disabled: S.view.split == null,
          title: "Put the question and answer columns back to their default widths",
          onclick: function () { setSplit(null, true); renderView(); } }, "Reset column widths")),
      checkV("notesOpen", "Show notes expanded", "v-notes",
        "Extra notes and pictures on a card normally sit behind a “Note” button. Tick this to show them all open.",
        function () { renderSheet(true); }),
      checkV("ticks", "Review ticks", "v-ticks",
        "Adds a tick box to every row so you can check off what you have read. Does not affect Anki's scheduling.",
        function () { renderSheet(true); }),
      h("div", { class: "vrow", title: "If the wrong part of a card shows as the answer, choose here which field is the question and which is the answer" },
        h("span", { text: "Card fields" }),
        h("button", { class: "btn small", type: "button", id: "fields", disabled: !(S.data && S.data.note_types && S.data.note_types.length),
          title: "Choose which field is the question and which is the answer, for each kind of card on this sheet",
          onclick: function () { S.viewOpen = false; renderView(); renderBar(); openFields(); } }, "Choose fields…")),
      h("div", { class: "vfoot" },
        h("button", { class: "btn small", type: "button", id: "view-reset",
          title: "Puts sections (for every deck), spacing, emphasis, theme, column widths, notes and review ticks back to how IchiSheet starts out. Your ticks, card field choices and AI settings are kept.",
          onclick: function (e) {
            var b = e.currentTarget;
            if (b.getAttribute("data-armed") !== "1") {   // ask once before wiping the layout choices
              b.setAttribute("data-armed", "1");
              b.textContent = "Click again to reset";
              return;
            }
            S.view = Object.assign({}, VIEW_DEFAULTS);
            S.groups = {};
            S.mode = "read";
            applyView();
            save();
            renderBar();
            renderView();
            if (S.home) renderSheet(); else load();
          } }, "Reset view to defaults"),
        h("button", { class: "btn small", type: "button", id: "refresh",
          title: "Reload decks and cards from Anki", onclick: function () { S.viewOpen = false; init(); } }, "Refresh from Anki")),
      h("div", { class: "vsupport" },
        h("span", { text: "IchiSheet" + (S.version ? " " + S.version : "") + " by StarHug" }),
        link("rate", "Rate on AnkiWeb", "A thumbs up on AnkiWeb helps other students find IchiSheet"),
        link("issues", "Report a problem", "Opens the issue page on GitHub"),
        link("support", "Buy me a coffee", "IchiSheet is free. A coffee helps keep it maintained")));
    function link(to, label, tip) {
      return h("a", { href: "#", title: tip, onclick: function (e) { e.preventDefault(); call("link", { to: to }); } }, label);
    }
    panel.style.top = (app.querySelector(".bar").offsetHeight + 6) + "px";
    main.appendChild(h("div", { class: "viewveil", onclick: close }));
    main.appendChild(panel);
  }

  // ---------------------------------------------------------------- rows

  function rowEl(r, deck) {
    var weak = r.lapses >= 2 ? h("span", { class: "badge", text: plural(r.lapses, "lapse") }) : null;
    var kind = r.badge ? h("span", { class: "badge lock", text: r.badge }) : null;
    var fresh = r["new"] && S.scope !== "new" ? h("span", { class: "badge new", text: "new" }) : null;
    var details = r.details.map(function (d) {
      return h("div", { class: "det" }, h("span", { text: d.label + " · " }), h("div", { card: d.html }));
    });
    var row = h("div", { class: "row " + r.kind + (r.ticked ? " ticked" : ""), "data-nid": r.nid,
      "data-private": deck.private ? "1" : null });
    if (S.view.ticks) {
      row.appendChild(h("label", { class: "tick", onclick: function (e) { e.stopPropagation(); } },
        h("input", { type: "checkbox", "aria-label": "Mark as reviewed", checked: r.ticked,
          onchange: function (e) {
            r.ticked = e.target.checked;
            row.classList.toggle("ticked", r.ticked);
            call("tick", { nid: r.nid, on: r.ticked });
            renderTickBar();
            applyFilter();
          } })));
    }
    if (r.kind === "cloze") {
      var text = h("div", { class: "text", card: r.text });
      if (weak) text.appendChild(weak);
      if (fresh) text.appendChild(fresh);
      row.appendChild(h("div", { class: "full" }, text, details));
    } else {
      var q = h("div", { class: "q", card: r.prompt });
      if (kind) q.appendChild(kind);
      if (weak) q.appendChild(weak);
      if (fresh) q.appendChild(fresh);
      var a = h("div", { class: "a" }, h("div", { class: "ans", card: r.answer }), details);
      if (r.extra) {
        var open = !!S.view.notesOpen;
        var box = h("div", { class: "extra", card: r.extra.html, hidden: !open });
        var label = "Note" + (r.extra.images ? " + " + plural(r.extra.images, "image") : "");
        a.appendChild(h("button", { class: "chip", type: "button", "aria-expanded": String(open), title: "Show or hide this card's extra note and pictures",
          onclick: function (e) {
            e.stopPropagation();
            box.hidden = !box.hidden;
            e.currentTarget.setAttribute("aria-expanded", String(!box.hidden));
          } }, label));
        a.appendChild(box);
      }
      row.appendChild(q);
      if (!r.answer.replace(/<(?!img|button)[^>]*>|&nbsp;|\s/g, "") && !details.length && !r.extra) {
        row.classList.add("solo");  // nothing on the answer side: let the question use the full width
      } else {
        row.appendChild(splitEl(row));
        row.appendChild(a);
      }
    }
    row.appendChild(h("button", { class: "edit", type: "button", title: "Open this note in the browser",
      onclick: function (e) { e.stopPropagation(); call("edit", { nid: r.nid }); } }, "Edit"));
    row.addEventListener("click", function (e) {
      if (S.mode !== "cover" || e.target.closest("a, .snd") || e.target.tagName === "IMG") return;
      row.classList.toggle("shown");
    });
    return row;
  }

  function highlight(nids) {
    app.querySelectorAll(".row.hit").forEach(function (r) { r.classList.remove("hit"); });
    var first = null;
    nids.forEach(function (nid) {
      var r = app.querySelector('.row[data-nid="' + nid + '"]');
      if (r) { r.classList.add("hit"); first = first || r; }
    });
    if (first) first.scrollIntoView({ block: "center", behavior: "smooth" });
  }

  function sourceLink(nids) {
    if (!nids || !nids.length) return null;
    return h("button", { class: "src", type: "button", title: "Show the cards this came from",
      onclick: function () { highlight(nids); } }, plural(nids.length, "card"));
  }

  // click any picture to see it full size; click it again for actual pixels
  function openImage(src, alt) {
    function close() { box.remove(); }
    var img = h("img", { src: src, alt: alt || "Enlarged picture from the card" });
    img.addEventListener("click", function (e) { e.stopPropagation(); box.classList.toggle("actual"); });
    var box = h("div", { class: "lightbox", role: "dialog", "aria-modal": "true", "aria-label": "Picture", tabindex: "-1",
      onclick: close, onkeydown: function (e) { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); close(); } } },
      h("button", { class: "x lb-x", type: "button", "aria-label": "Close picture", onclick: close }, "✕"),
      h("div", { class: "lb-hint", text: "Click the picture to switch between fit and full size. Esc closes." }),
      img);
    app.appendChild(box);
    box.focus();
  }

  // ---------------------------------------------------------------- condense

  function condKey(deck, g) { return deck.id + "|" + (deck.grouped_by || "") + "|" + g.key; }

  function condense(deck, g) {
    var key = condKey(deck, g);
    S.cond[key] = { pending: true };
    renderSheet(true);
    aiCall("ai_condense", { deck_id: deck.id, prefix: deck.grouped_by, key: g.key,
      title: (g.name || deck.short) + " (" + deck.short + ")",
      nids: g.rows.map(function (r) { return r.nid; }) }, function (p) {
      if (!p.ok) S.cond[key] = { error: p.error };
      else if (!p.result.condensable) S.cond[key] = { none: p.result.reason };
      else { delete S.cond[key]; g.summary = p.result; g.stale = false; }
      renderSheet(true);
    });
  }

  function gapsText(s) {
    return s.gaps.map(function (x) { return String(x).trim().replace(/[.;,]+$/, ""); }).join("; ");
  }

  // the summary as Markdown, for pasting into notes
  function summaryText(deck, g) {
    var s = g.summary, out = ["## " + (g.name || deck.short) + " (" + deck.short + ")", ""];
    function cell(c) { return String(c == null ? "" : c).replace(/\s*\n\s*/g, " ").replace(/\|/g, "\\|"); }
    if (s.intro) out.push(s.intro, "");
    s.blocks.forEach(function (b) {
      if (b.type === "table") {
        out.push("| " + b.columns.map(cell).join(" | ") + " |", "|" + b.columns.map(function () { return " --- "; }).join("|") + "|");
        b.rows.forEach(function (r) { out.push("| " + r.cells.map(cell).join(" | ") + " |"); });
      } else {
        b.items.forEach(function (it, i) { out.push((b.type === "steps" ? (i + 1) + ". " : "- ") + it.text); });
      }
      out.push("");
    });
    if (s.gaps && s.gaps.length) out.push("Not covered by the cards: " + gapsText(s) + ".", "");
    out.push("AI summary of " + plural(s.count || g.rows.length, "card") + ", made with IchiSheet.");
    return out.join("\n");
  }

  function summaryEl(deck, g) {
    var s = g.summary, key = condKey(deck, g), st = S.cond[key] || {};
    var blocks = s.blocks.map(function (b) {
      if (b.type === "table") {
        return h("div", { class: "sum-scroll" }, h("table", {},
          h("thead", {}, h("tr", {}, b.columns.map(function (c) { return h("th", { scope: "col", text: c }); }),
            h("th", { scope: "col", class: "srcc", text: "Source" }))),
          h("tbody", {}, b.rows.map(function (r) {
            return h("tr", {}, r.cells.map(function (c, i) {
              return i === 0 ? h("th", { scope: "row", html: rich(c) }) : h("td", { html: rich(c) });
            }), h("td", { class: "srcc" }, sourceLink(r.sources)));
          }))));
      }
      return h(b.type === "steps" ? "ol" : "ul", { class: "sum-list" }, b.items.map(function (it) {
        return h("li", {}, h("span", { html: rich(it.text) }), " ", sourceLink(it.sources));
      }));
    });
    return h("div", { class: "sum" },
      h("div", { class: "sum-head" },
        h("div", { class: "sum-title" }, h("span", { class: "spark", html: SPARK }),
          h("span", { text: "AI summary of " + plural(s.count || g.rows.length, "card") })),
        h("div", { class: "sum-actions" },
          S.ai.ready ? h("button", { class: "btn small regen", type: "button", disabled: st.pending,
            onclick: function () { condense(deck, g); } }, st.pending ? "Working…" : "Regenerate") : null,
          h("button", { class: "btn small copy", type: "button", title: "Copy this summary as text you can paste into your notes",
            onclick: function (e) {
              var b = e.currentTarget;
              call("copy", { text: summaryText(deck, g) }).then(function () {
                b.textContent = "Copied";
                setTimeout(function () { b.textContent = "Copy"; }, 1600);
              });
            } }, "Copy"),
          h("button", { class: "btn small", type: "button",
            onclick: function () {
              call("ai_remove", { deck_id: deck.id, prefix: deck.grouped_by, key: g.key });
              delete g.summary; delete S.cond[key]; renderSheet(true);
            } }, "Remove"))),
      g.stale ? h("div", { class: "sum-note warn", text: "These cards changed since this summary was made. Regenerate to update it." }) : null,
      st.error ? h("div", { class: "sum-note warn", text: st.error }) : null,
      s.intro ? h("div", { class: "sum-intro", html: rich(s.intro) }) : null,
      blocks,
      s.gaps && s.gaps.length ? h("div", { class: "sum-note warn" },
        h("strong", { text: "Not covered by your cards: " }), gapsText(s) + ". The summary only uses what your cards say.") : null);
  }

  function groupEl(deck, g) {
    var key = condKey(deck, g), st = S.cond[key] || {};
    var canCondense = S.ai.ready && S.data.scope === "all" && !deck.private && g.rows.length >= 3 && !g.summary;
    var action = null;
    if (canCondense) {
      action = h("button", { class: "btn small cond", type: "button", disabled: st.pending,
        title: "Sends the text of these " + g.rows.length + " cards to your AI provider",
        onclick: function () { condense(deck, g); } },
        h("span", { class: "spark", html: SPARK }), st.pending ? "Condensing " + plural(g.rows.length, "card") + "…" : "Condense");
    } else if (S.ai.ready && S.data.scope !== "all" && !deck.private && !g.summary) {
      // summaries cover a whole section, so they are made from All cards
      action = h("button", { class: "btn small cond", type: "button", disabled: true,
        title: "Switch to All cards to condense this section" },
        h("span", { class: "spark", html: SPARK }), "Condense");
    }
    var note = !g.summary && (st.error || st.none);
    var body = h("div", { class: "gbody" },
      note ? h("div", { class: "sum-note" + (st.error ? " warn" : ""), text: st.error || ("Nothing to condense: " + st.none) }) : null,
      g.summary ? summaryEl(deck, g) : null,
      h("div", { class: "rows" }, g.rows.map(function (r) { return rowEl(r, deck); })));
    return h("div", { class: "group" },
      h("div", { class: "ghead" }, g.name ? h("h3", {}, foldBtn("g" + condKey(deck, g), g.name, body)) : h("span", {}), action),
      body);
  }

  // Section and deck titles fold their cards away. Folds last until IchiSheet is closed.
  function foldBtn(key, label, body) {
    var btn = h("button", { class: "fold", type: "button", title: "Click to fold or unfold this section" },
      h("span", { class: "caret", "aria-hidden": "true" }), h("span", { text: label }));
    function show() {
      var shut = !!S.fold[key];
      body.hidden = shut;
      btn.setAttribute("aria-expanded", String(!shut));
      btn.classList.toggle("shut", shut);
    }
    btn.addEventListener("click", function () { S.fold[key] = !S.fold[key]; show(); });
    show();
    return btn;
  }

  // ---------------------------------------------------------------- sheet

  // formulas: only run MathJax when the page actually contains some
  function typesetMath(el) {
    if (!window.MathJax || !MathJax.typesetPromise) return;
    if (!/\\\(|\\\[/.test(el.textContent)) return;
    try { MathJax.typesetPromise([el]).catch(function () {}); } catch (e) { /* MathJax still starting */ }
  }

  // which field is the question / answer, per kind of card on this sheet
  function openFields() {
    var types = (S.data.note_types || []).map(function (t) {
      return { name: t.name, fields: t.fields, cloze: t.cloze, prompt: t.prompt || "", answer: t.answer || "", hide: (t.hide || []).slice() };
    });
    function close() { overlay.remove(); }
    function pick(t, key, auto) {
      return h("select", { "aria-label": key + " field for " + t.name,
        onchange: function (e) { t[key] = e.target.value; draw(); } },
        [h("option", { value: "", selected: !t[key] }, auto)].concat(t.fields.map(function (f) {
          return h("option", { value: f, selected: t[key] === f }, f);
        })));
    }
    var body = h("div", { class: "ftypes" });
    function draw() {
      put(body, types.map(function (t) {
        var q = t.prompt || t.fields[0], others = t.fields.filter(function (f) { return f !== q && f !== t.answer; });
        var el = h("div", { class: "ftype" }, h("h3", { text: t.name }),
          t.cloze && !(t.prompt || t.answer || t.hide.length) ? h("div", { class: "muted", text: "Fill-in-the-blank cards are shown as the full sentence with the blanks highlighted. Choose fields below only if you want a question and answer layout instead." }) : null,
          h("label", { class: "vrow" }, h("span", { text: "Question" }), pick(t, "prompt", "Automatic (first field)")),
          h("label", { class: "vrow" }, h("span", { text: "Answer" }), pick(t, "answer", "Automatic (next filled field)")),
          others.length ? h("div", { class: "fhide" }, h("span", { text: "Hide these fields" }),
            h("div", { class: "fhide-list" }, others.map(function (f) {
              return h("label", { class: "check" },
                h("input", { type: "checkbox", checked: t.hide.indexOf(f) >= 0,
                  onchange: function (e) {
                    t.hide = t.hide.filter(function (x) { return x !== f; });
                    if (e.target.checked) t.hide.push(f);
                  } }), h("span", { text: f }));
            }))) : null,
          h("button", { class: "btn small", type: "button", disabled: !(t.prompt || t.answer || t.hide.length),
            onclick: function () { t.prompt = ""; t.answer = ""; t.hide = []; draw(); } }, "Back to automatic"));
        el.setAttribute("data-type", t.name);
        return el;
      }));
    }
    draw();
    var overlay = h("div", { class: "overlay", onclick: function (e) { if (e.target === overlay) close(); },
      onkeydown: function (e) { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); close(); } } },
      h("div", { class: "modal", role: "dialog", "aria-modal": "true", "aria-labelledby": "f-title" },
        h("h2", { id: "f-title", text: "Card fields" }),
        h("p", { class: "muted", text: "Each kind of card on this sheet is listed below. IchiSheet normally shows the first field as the question and the next filled field as the answer. Change that here if it guessed wrong. This only affects how IchiSheet displays cards; your cards are not changed." }),
        body,
        h("div", { class: "modal-foot" },
          h("button", { class: "btn", type: "button", onclick: close }, "Cancel"),
          h("button", { class: "btn primary", type: "button", id: "fields-save",
            onclick: function () {
              var out = {};
              types.forEach(function (t) { out[t.name] = { prompt: t.prompt, answer: t.answer, hide: t.hide }; });
              call("fields_save", { types: out }).then(function () { close(); load(); });
            } }, "Save"))));
    app.appendChild(overlay);
    overlay.querySelector("select").focus();
  }

  function renderTickBar() {
    var bar = app.querySelector(".tickbar");
    if (!bar) return;
    var rows = allRows(), done = rows.filter(function (r) { return r.ticked; }).length;
    put(bar, [
      h("span", { class: "tickcount", text: fmt(done) + " of " + fmt(rows.length) + " ticked" }),
      h("label", { class: "check", title: "Hide the rows you have ticked, so only what is left to read stays on screen" },
        h("input", { type: "checkbox", id: "hide-ticked", checked: S.view.hideTicked,
          onchange: function (e) { S.view.hideTicked = e.target.checked; save(); applyFilter(); } }),
        h("span", { text: "Hide ticked" })),
      h("button", { class: "btn small", type: "button", id: "ticks-reset", disabled: !done,
        title: "Clears the ticks on this sheet. Cards and scheduling are not touched.",
        onclick: function () {
          call("ticks_reset", { nids: rows.map(function (r) { return r.nid; }) });
          rows.forEach(function (r) { r.ticked = false; });
          renderSheet(true);
        } }, "Reset ticks")]);
  }

  function renderSheet(keepScroll) {
    var page = app.querySelector(".page"), d = S.data, scroller = app.querySelector(".scroll");
    var top = scroller.scrollTop;
    if (S.home) {
      put(page, [h("div", { class: "head" }, brand(),
        h("div", { class: "meta", text: "Pick a deck on the left to read it as one page." })),
        S.recovered ? h("div", { class: "notice", id: "recovered" }, h("span", { text: "Last time, “" + S.recovered.split("::").pop() +
          "” did not finish opening, so IchiSheet started here instead of reopening it. You can still pick it from the list." })) : null]);
      return;
    }
    if (!d) { put(page, [h("div", { class: "empty", id: "loading", text: "Loading…" })]); return; }
    if (d.__error) {
      put(page, [h("div", { class: "notice warnbox", id: "load-error" },
        h("span", { text: "This deck could not be loaded (" + d.__error + "). Nothing in your collection was changed." }),
        h("button", { class: "btn small", type: "button", onclick: function () { load(); } }, "Try again"))]);
      return;
    }
    var scopeName = SCOPES.filter(function (s) { return s[0] === d.scope; })[0][1];
    var loadedIn = d.ms != null ? "Read from Anki in " + (d.ms / 1000).toFixed(1) + "s" : null;
    var meta = plural(d.total, "note") + (d.scope === "all" ? "" : " · " + scopeName.toLowerCase()) +
      " · reading here does not change scheduling";
    var kids = [h("div", { class: "head" },
      h("h1", { text: title() }), h("div", { class: "meta", text: meta, title: loadedIn }),
      S.view.ticks && d.total ? h("div", { class: "tickbar" }) : null)];
    if (d.shown < d.total) {
      kids.push(h("div", { class: "notice" },
        h("span", { text: "Showing the first " + fmt(d.shown) + " of " + fmt(d.total) + " notes. Pick a sub-deck to narrow it down." }),
        h("button", { class: "btn", type: "button", id: "more",
          onclick: function () { S.limit = d.limit + 500; S.maxChars = d.max_chars * 2; load(); } }, "Show more")));
    }
    if (!d.total) {
      kids.push(h("div", { class: "empty", text: d.scope === "all" ? "No cards in this deck." : "Nothing here for “" + scopeName + "”. Try All cards." }));
    }
    var single = d.decks.length === 1 && d.decks[0].name === S.deck;
    if (S.ai.enabled && d.decks.length && d.decks.every(function (x) { return x.private; })) {
      kids.push(h("div", { class: "notice", id: "private-note" }, h("span", { text: "This deck is on your never-send list. Condense and Ask leave its cards out." })));
    }
    d.decks.forEach(function (deck) {
      var sec = h("section", { class: "deck" }), dbody = h("div", { class: "dbody" });
      if (!single) {
        sec.appendChild(h("header", {}, h("h2", {}, foldBtn("d" + deck.id, deck.short, dbody)),
          h("span", { text: (deck.parents.length ? deck.parents.join(" › ") + " · " : "") + plural(deck.count, "note") }),
          deck.private && S.ai.enabled ? h("span", { class: "badge lock", text: "never sent to AI" }) : null));
      }
      deck.groups.forEach(function (g) { dbody.appendChild(groupEl(deck, g)); });
      sec.appendChild(dbody);
      kids.push(sec);
    });
    kids.push(h("div", { class: "empty", id: "nomatch", hidden: true, text: "Nothing to show: every row is filtered out or ticked." }));
    put(page, kids);
    renderTickBar();
    applyFilter();
    scroller.scrollTop = keepScroll ? top : 0;
    typesetMath(page);
  }

  function applyFilter() {
    var q = S.filter.trim().toLowerCase(), any = false;
    var hideDone = S.view.ticks && S.view.hideTicked;
    app.querySelectorAll(".deck").forEach(function (deck) {
      var deckAny = false;
      deck.querySelectorAll(".group").forEach(function (g) {
        var gAny = false;
        g.querySelectorAll(".row").forEach(function (r) {
          var hit = (!q || r.textContent.toLowerCase().indexOf(q) >= 0) && !(hideDone && r.classList.contains("ticked"));
          r.hidden = !hit;
          gAny = gAny || hit;
        });
        g.hidden = !gAny;
        deckAny = deckAny || gAny;
      });
      deck.hidden = !deckAny;
      any = any || deckAny;
    });
    var none = document.getElementById("nomatch");
    if (none) none.hidden = any || !S.data || !S.data.total;
    renderAskScope();
  }

  // ---------------------------------------------------------------- ask

  // exactly which cards a question would send: the rows on screen, minus never-send decks, up to the cap
  function sendable() {
    var rows = [].slice.call(app.querySelectorAll(".row:not([hidden])"));
    var open = rows.filter(function (r) { return !r.getAttribute("data-private"); });
    var cap = S.ai.max_cards || 200;
    return { nids: open.slice(0, cap).map(function (r) { return Number(r.getAttribute("data-nid")); }),
             excluded: rows.length - open.length, capped: open.length > cap, total: open.length };
  }

  function renderAskScope() {
    var el = app.querySelector(".ask-scope");
    if (!el) return;
    var s = sendable(), extra = [];
    if (S.filter.trim()) extra.push("filtered");
    if (S.view.ticks && S.view.hideTicked) extra.push("ticked rows hidden");
    if (s.capped) extra.push("first " + fmt(s.nids.length) + " of " + fmt(s.total) + "; filter or pick a sub-deck to change which");
    if (s.excluded) extra.push(plural(s.excluded, "card") + " in never-send decks left out");
    put(el, [
      h("div", { class: "ask-will", text: "Will send: " + title() + " · " + plural(s.nids.length, "card") }),
      extra.length ? h("div", { class: "ask-sub", text: extra.join(" · ") }) : null,
      h("div", { class: "ask-sub", text: "Text only, and only when you press Send." })]);
  }

  function chipLabel(nid) {
    var r = app.querySelector('.row[data-nid="' + nid + '"] .q, .row[data-nid="' + nid + '"] .text');
    if (!r) return "Card";
    var t = r.cloneNode(true);
    t.querySelectorAll(".badge").forEach(function (b) { b.remove(); });
    var s = t.textContent.trim();
    return s.length > 38 ? s.slice(0, 36) + "…" : s;
  }

  function renderChat() {
    var log = app.querySelector(".ask-log");
    if (!log) return;
    var kids = [];
    if (!S.chat.length) {
      kids.push(h("div", { class: "ask-empty", text: "Ask anything about the cards on this sheet. Answers show which cards they came from." }));
    }
    S.chat.forEach(function (m) {
      if (m.role === "user") { kids.push(h("div", { class: "msg me", text: m.text })); return; }
      if (m.pending) { kids.push(h("div", { class: "msg ai pending", text: "Thinking…" })); return; }
      if (m.error) { kids.push(h("div", { class: "msg ai err", text: m.error })); return; }
      var general = m.basis === "general", none = m.basis === "none";
      kids.push(h("div", { class: "turn" },
        h("div", { class: "msg ai" + (general || none ? " outside" : "") },
          general ? h("div", { class: "tag", text: "Not in your cards · general knowledge" }) : null,
          none ? h("div", { class: "tag", text: "Not in your cards" }) : null,
          h("div", { html: rich(m.text) })),
        m.sources && m.sources.length ? h("div", { class: "srcs" }, h("span", { text: "From your cards:" }),
          m.sources.map(function (nid) {
            return h("button", { class: "srcchip", type: "button", onclick: function () { highlight([nid]); } }, chipLabel(nid));
          })) : null,
        general ? h("button", { class: "btn small mk", type: "button",
          title: "Opens Anki's Add window pre-filled. Nothing is added until you click Add.",
          onclick: function () { call("add_card", { front: m.question, back: m.text.replace(/\*\*/g, ""), deck: S.deck }); } },
          "Make a card from this") : null));
    });
    put(log, kids);
    log.scrollTop = log.scrollHeight;
    var fresh = app.querySelector("#newchat");
    if (fresh) fresh.hidden = !S.chat.length;
  }

  function sendQuestion() {
    var box = app.querySelector(".ask-input"), q = box.value.trim();
    if (!q || S.chat.some(function (m) { return m.pending; })) return;
    var s = sendable();
    var history = S.chat.filter(function (m) { return !m.pending && !m.error; })
      .map(function (m) { return { role: m.role === "user" ? "user" : "assistant", text: m.text }; });
    S.chat.push({ role: "user", text: q });
    var reply = { role: "ai", pending: true, question: q };
    S.chat.push(reply);
    box.value = "";
    renderChat();
    aiCall("ai_ask", { nids: s.nids, question: q, history: history, strict: S.strict, title: title() }, function (p) {
      reply.pending = false;
      if (!p.ok) reply.error = p.error;
      else { reply.text = p.result.answer; reply.basis = p.result.basis; reply.sources = p.result.sources; }
      renderChat();
      if (p.ok && reply.sources.length) highlight(reply.sources);
    });
  }

  function renderAsk() {
    var old = app.querySelector(".ask");
    if (old) old.remove();
    if (!S.askOpen || !S.ai.ready) return;
    var input = h("input", { class: "ask-input", type: "text", placeholder: "Ask about these cards", "aria-label": "Ask about these cards",
      onkeydown: function (e) { if (e.key === "Enter") sendQuestion(); } });
    app.appendChild(h("aside", { class: "ask", "aria-label": "Ask about this sheet" },
      h("div", { class: "ask-head" },
        h("div", { class: "ask-scope" }),
        h("button", { class: "btn small", type: "button", id: "newchat", title: "Clear this conversation",
          onclick: function () { S.chat = S.chat.filter(function (m) { return m.pending; }); renderChat(); } }, "New chat"),
        h("button", { class: "x", type: "button", "aria-label": "Close Ask panel",
          onclick: function () { S.askOpen = false; renderAsk(); renderBar(); } }, "✕")),
      h("div", { class: "ask-log" }),
      h("div", { class: "ask-foot" },
        h("label", { class: "check", title: "When ticked, the AI answers only from these cards and says so when they do not cover your question" },
          h("input", { type: "checkbox", id: "strict", checked: S.strict, onchange: function (e) { S.strict = e.target.checked; } }),
          h("span", { text: "Answer only from my cards" })),
        h("div", { class: "ask-sub", text: "This limits the answer, not what is sent. The same cards are sent either way." }),
        h("div", { class: "ask-row" }, input,
          h("button", { class: "btn primary send", type: "button", onclick: sendQuestion }, "Send")))));
    renderAskScope();
    renderChat();
  }

  // ---------------------------------------------------------------- AI settings

  function openSettings() {
    var a = S.ai, never = (a.never_send_decks || []).slice();
    var decks = flat(S.tree, []);
    var enabled = h("input", { type: "checkbox", id: "ai-on", checked: a.enabled });
    // Presets only fill in the server address. Everything except Anthropic speaks the OpenAI chat format.
    var PRESETS = [["anthropic", "Anthropic (Claude)", ""],
      ["openai", "OpenAI (ChatGPT)", "https://api.openai.com/v1"],
      ["gemini", "Google Gemini", "https://generativelanguage.googleapis.com/v1beta/openai"],
      ["openrouter", "OpenRouter", "https://openrouter.ai/api/v1"],
      ["ollama", "Ollama, on this computer", "http://localhost:11434/v1"],
      ["lmstudio", "LM Studio, on this computer", "http://localhost:1234/v1"],
      ["custom", "Other OpenAI-compatible server", ""]];
    var LOCAL = { ollama: 1, lmstudio: 1 };
    function trimUrl(u) { return (u || "").trim().replace(/\/+$/, ""); }
    var current = a.provider === "anthropic" ? "anthropic" : "custom";
    if (current === "custom") PRESETS.forEach(function (p) { if (p[2] && p[2] === trimUrl(a.base_url)) current = p[0]; });
    var provider = h("select", { id: "ai-provider" }, PRESETS.map(function (p) {
      return h("option", { value: p[0], selected: p[0] === current }, p[1]);
    }));
    function wire() { return provider.value === "anthropic" ? "anthropic" : "openai_compatible"; }
    var key = h("input", { type: "password", id: "ai-key", autocomplete: "off",
      placeholder: a.has_key ? "A key is saved. Type a new one to replace it." : "Paste your API key" });
    var model = h("input", { type: "text", id: "ai-model", value: a.model || "", placeholder: a.default_model || "Model name" });
    var base = h("input", { type: "text", id: "ai-base", value: a.base_url || "", placeholder: "http://localhost:11434/v1" });
    var baseNote = h("small", {});
    var baseRow = h("label", { class: "field" }, h("span", { text: "Server address" }), base, baseNote);
    var status = h("span", { class: "test-status", role: "status" });
    var testBtn = h("button", { class: "btn small", type: "button", id: "ai-test",
      title: "Sends one short test message with no card content",
      onclick: function () {
        testBtn.disabled = true;
        status.className = "test-status";
        status.textContent = "Testing…";
        aiCall("ai_test", { provider: wire(), api_key: key.value, model: model.value, base_url: base.value }, function (p) {
          testBtn.disabled = false;
          status.className = "test-status " + (p.ok ? "ok" : "bad");
          status.textContent = p.ok ? "Connected. The AI replied." : p.error;
        });
      } }, "Test connection");

    // never-send picker: search every deck, tick the private ones
    var chosen = h("div", { class: "never" });
    var list = h("div", { class: "never-list", role: "group", "aria-label": "All decks" });
    var search = h("input", { type: "search", id: "never-search", placeholder: "Find a deck to keep private", "aria-label": "Find a deck to keep private",
      oninput: function () { drawNever(); } });
    function coveredBy(full) {
      for (var i = 0; i < never.length; i++) if (full.indexOf(never[i] + "::") === 0) return never[i];
      return null;
    }
    function drawNever() {
      var picked = never.slice().sort().map(function (d) {
        return h("div", { class: "never-item" }, h("span", { text: d.split("::").join(" › ") }),
          h("button", { class: "btn small", type: "button", "aria-label": "Remove " + d.split("::").pop(),
            onclick: function () { never = never.filter(function (x) { return x !== d; }); drawNever(); } }, "Remove"));
      });
      if (!never.length) picked.push(h("div", { class: "muted", text: "No decks listed. Any deck can be sent when you ask." }));
      put(chosen, picked);
      var q = search.value.trim().toLowerCase();
      var rows = decks.filter(function (n) { return !q || n.full.toLowerCase().indexOf(q) >= 0; }).slice(0, 400).map(function (n) {
        var parent = coveredBy(n.full), on = never.indexOf(n.full) >= 0;
        var box = h("input", { type: "checkbox", checked: on || !!parent, disabled: !!parent,
          onchange: function (e) {
            if (e.target.checked) {
              never = never.filter(function (x) { return x.indexOf(n.full + "::") !== 0; });  // parent covers them
              never.push(n.full);
            } else {
              never = never.filter(function (x) { return x !== n.full; });
            }
            drawNever();
          } });
        box.setAttribute("data-deck", n.full);
        var lab = h("label", { class: "never-row" }, box,
          h("span", { class: "never-name", text: q ? n.full.split("::").join(" › ") : n.name }),
          parent ? h("span", { class: "muted", text: "covered by " + parent.split("::").pop() }) : null);
        lab.style.paddingLeft = (8 + (q ? 0 : n.depth * 16)) + "px";
        return lab;
      });
      if (!rows.length) rows.push(h("div", { class: "muted never-none", text: "No deck matches that search." }));
      put(list, rows);
    }
    function sync() {
      var v = provider.value;
      baseRow.hidden = !(v === "custom" || LOCAL[v]);
      baseNote.textContent = LOCAL[v] ? "With a model on your own computer, nothing leaves this machine. Change the address only if you moved it."
        : "The address your provider gives for its OpenAI-compatible API, usually ending in /v1.";
      model.placeholder = v === "anthropic" ? (a.default_model || "Model name") : "Model name, as your provider lists it";
    }
    provider.addEventListener("change", function () {
      var v = provider.value;
      PRESETS.forEach(function (p) { if (p[0] === v) base.value = p[2]; });
      sync();
    });
    drawNever();
    sync();
    function close() { overlay.remove(); }
    var overlay = h("div", { class: "overlay", onclick: function (e) { if (e.target === overlay) close(); },
      onkeydown: function (e) { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); close(); } } },
      h("div", { class: "modal", role: "dialog", "aria-modal": "true", "aria-labelledby": "ai-title" },
        h("h2", { id: "ai-title", text: "AI settings" }),
        h("p", { class: "muted", text: "AI is optional. With it off, IchiSheet never goes online. With it on, card text is sent only when you click Condense or send a question, straight from this computer to the provider below. Pictures and audio are never sent." }),
        h("label", { class: "check" }, enabled, h("span", { text: "Turn on Condense and Ask" })),
        h("label", { class: "field" }, h("span", { text: "Provider" }), provider),
        h("label", { class: "field" }, h("span", { text: "API key" }), key,
          h("small", { text: "Stored in Anki's add-on settings on this computer. Not needed for a local model." })),
        h("label", { class: "field" }, h("span", { text: "Model" }), model),
        baseRow,
        h("div", { class: "testrow" }, testBtn, status),
        h("div", { class: "field" }, h("span", { text: "Never send these decks" }),
          h("small", { text: "Tick a deck to keep it and its sub-decks out of Condense and Ask. This list always applies, whichever deck you have open." }),
          chosen, search, list),
        h("div", { class: "modal-foot" },
          h("button", { class: "btn", type: "button", onclick: close }, "Cancel"),
          h("button", { class: "btn primary", type: "button", id: "ai-save",
            onclick: function () {
              call("ai_save", { enabled: enabled.checked, provider: wire(), api_key: key.value,
                model: model.value, base_url: base.value, never_send_decks: never }).then(function (pub) {
                S.ai = pub;
                if (!pub.ready) S.askOpen = false;
                close();
                renderBar();
                renderAsk();
                load();
              });
            } }, "Save"))));
    app.appendChild(overlay);
    enabled.focus();
  }

  // ---------------------------------------------------------------- toolbar

  function seg(items, key, label, onpick) {
    return h("div", { class: "seg", role: "group", "aria-label": label }, items.map(function (it) {
      var b = h("button", { type: "button", "aria-pressed": String(S[key] === it[0]),
        onclick: function () { onpick(it[0]); } }, it[1]);
      b.setAttribute("data-" + key, it[0]);
      if (HINT[it[0]]) b.title = HINT[it[0]];
      return b;
    }));
  }

  function renderBar() {
    var bar = app.querySelector(".bar");
    var filter = h("input", { class: "filter", type: "search", placeholder: "Filter this sheet", "aria-label": "Filter this sheet",
      title: "Type a word to show only the rows that contain it", value: S.filter, oninput: function (e) { S.filter = e.target.value; applyFilter(); } });
    var reveal = S.mode === "cover" ? h("button", { class: "btn", type: "button", id: "reveal", title: "Show every hidden answer, or hide them all again",
      onclick: function () {
        var rows = app.querySelectorAll(".row"), on = !app.querySelector(".row.shown");
        rows.forEach(function (r) { r.classList.toggle("shown", on); });
      } }, "Reveal / hide all") : null;
    var askBtn = S.ai.ready ? h("button", { class: "btn" + (S.askOpen ? " on" : ""), type: "button", id: "ask",
      "aria-pressed": String(S.askOpen),
      title: "Ask the AI a question about the cards on this sheet",
      onclick: function () { S.askOpen = !S.askOpen; renderAsk(); renderBar(); } }, "Ask") : null;
    put(bar, [
      seg(SCOPES, "scope", "Which cards", function (v) { S.scope = v; S.limit = null; S.maxChars = null; save(); renderBar(); load(); }),
      seg(MODES, "mode", "View mode", setMode),
      reveal, filter,
      h("button", { class: "btn" + (S.viewOpen ? " on" : ""), type: "button", id: "view", "aria-expanded": String(S.viewOpen),
        title: "Layout options: sections, spacing, emphasis, theme, notes and review ticks",
        onclick: function () { S.viewOpen = !S.viewOpen; renderView(); renderBar(); } }, "View"),
      h("button", { class: "btn", type: "button", id: "pdf", title: "Save this sheet as a PDF in the mode you are in, on a white page", onclick: function () { call("pdf", { title: title() }); } }, "Export PDF"),
      h("button", { class: "btn", type: "button", id: "aiset", title: "Turn the optional AI features on or off, and choose decks that are never sent", onclick: openSettings }, "AI settings"),
      askBtn,
      h("button", { class: "btn primary", type: "button", id: "study", title: "Open this deck in Anki's normal flashcard review", onclick: function () { call("study", { deck: S.deck }); } },
        S.deck ? "Study this deck" : "Go to decks")]);
  }

  function setMode(v) {
    S.mode = v;
    applyView();
    app.querySelectorAll(".row.shown").forEach(function (r) { r.classList.remove("shown"); });
    save();
    renderBar();
  }

  // ---------------------------------------------------------------- data

  function save() {
    call("state", { deck: S.deck, scope: S.scope, mode: S.mode, groups: S.groups, view: S.view,
      home: !!S.home, pending: loading ? (S.deck || "All decks") : null });
  }

  // One load at a time. Clicking through several decks only loads the last one clicked,
  // instead of queueing a heavy page for every deck on the way.
  var loading = false, queued = false, stageTimer = null, loadStart = 0, stage = "";
  function showStage() {
    var el = document.getElementById("loading");
    if (!el) return;
    var secs = Math.round((Date.now() - loadStart) / 1000);
    if (secs < 2) { el.textContent = "Loading…"; return; }
    el.textContent = (stage === "draw" ? "Drawing the page… " : "Reading cards from Anki… ") + secs + "s" +
      (secs >= 10 ? ". If this never finishes, send a screenshot of this line: it shows which step is stuck." : "");
  }
  function load() {
    S.data = null;
    S.home = false;
    renderSheet();
    if (loading) { queued = true; return Promise.resolve(); }
    loading = true;
    loadStart = Date.now();
    stage = "anki";
    clearInterval(stageTimer);
    stageTimer = setInterval(showStage, 1000);
    save();  // records that this deck is being opened, so a page that never finishes is not reopened next time
    return call("load", { deck: S.deck, scope: S.scope, group: groupFor(S.deck), limit: S.limit, max_chars: S.maxChars }).then(function (d) {
      loading = false;
      if (queued) { queued = false; clearInterval(stageTimer); return load(); }
      stage = "draw";
      showStage();
      S.data = d || { __error: "no reply from Anki" };
      try { renderBar(); renderSheet(); renderView(); }
      catch (err) { S.data = { __error: "display problem: " + err.message }; renderSheet(); }
      clearInterval(stageTimer);
      save();
    });
  }

  function fatal(msg) {
    var main = app.querySelector(".main");
    if (!main || main.querySelector(".fatal")) return;
    main.insertBefore(h("div", { class: "fatal", role: "alert" },
      h("span", { text: "IchiSheet hit a problem (" + msg + "). Your cards are not affected." }),
      h("button", { class: "btn small", type: "button", onclick: function () { loading = false; queued = false; init(); } }, "Reload")),
      main.querySelector(".scroll"));
  }
  window.addEventListener("error", function (e) { fatal(e.message + (e.lineno ? ", line " + e.lineno : "")); });
  window.addEventListener("unhandledrejection", function (e) { fatal(String((e.reason && e.reason.message) || e.reason)); });

  function selectDeck(full) {
    S.deck = full || null;
    S.home = false;
    S.recovered = null;
    S.limit = null;
    S.maxChars = null;
    S.filter = "";
    S.deckFilter = "";
    S.chat = [];
    var box = app.querySelector(".side input");
    if (box) box.value = "";
    ancestorsOpen(S.tree, S.deck);
    flat(S.tree, []).forEach(function (n) { if (n.full === S.deck) S.open[n.id] = true; });
    save();
    renderSide();
    renderBar();
    renderChat();
    return load();
  }

  function init() {
    return call("init").then(function (r) {
      S.tree = r.tree;
      S.version = r.version || "";
      S.ai = r.ai;
      var st = r.state || {};
      var known = flat(S.tree, []).some(function (n) { return n.full === st.deck; });
      if (!S.started) {
        S.deck = known ? st.deck : null;
        S.scope = st.scope || "all";
        S.mode = st.mode || "read";
        S.groups = Object.assign({}, st.groups || {});
        S.view = Object.assign({}, VIEW_DEFAULTS, st.view || {});
        // start on a deck only if one was open last time and it finished opening
        S.recovered = st.pending || null;
        S.home = !S.deck || !!st.home || !!st.pending;
        S.started = true;
      }
      ancestorsOpen(S.tree, S.deck);
      var scroll = h("div", { class: "scroll" }, h("div", { class: "pagewrap" }, h("div", { class: "page" }), pageGrip()));
      scroll.addEventListener("click", function (e) {
        var t = e.target;
        if (t.tagName === "IMG" && t.closest(".row, .sum")) openImage(t.currentSrc || t.src, t.alt);
        var snd = t.closest(".snd");
        if (snd) call("play", { file: snd.getAttribute("data-snd") });
      });
      put(app, [
        h("nav", { class: "side", "aria-label": "Decks" },
          brand(),
          h("input", { type: "search", placeholder: "Find a deck", "aria-label": "Find a deck", title: "Type part of a deck name to find it",
            oninput: function (e) { S.deckFilter = e.target.value; renderSide(); } }),
          h("div", { class: "tree" })),
        sideGrip(),
        h("div", { class: "main" }, h("div", { class: "bar" }), scroll)]);
      applyView();
      renderSide();
      renderBar();
      renderAsk();
      if (S.home) { renderSheet(); return null; }
      return load();
    });
  }

  // Anki injects pycmd once its bridge is up, which can be after this script runs
  (function start() {
    if (typeof pycmd === "function") init();
    else setTimeout(start, 30);
  })();
  return { selectDeck: selectDeck, state: S, reload: init, aiDone: aiDone };
})();
