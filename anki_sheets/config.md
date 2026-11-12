**Sheets settings**

- `max_rows`: how many notes a sheet loads at once (a "Show 500 more" button loads the rest).
- `max_chars`: a cap on how much card text one page loads, so decks of very long notes still open quickly. "Show more" loads the rest.
- `weak_lapses`: a card counts as a weak spot once it has lapsed this many times.
- `group_tag_prefixes`: tag prefixes tried, in order, to split a deck into sections. `topic` means tags like `topic::verbs`.
- `ignore_tag_prefixes`: tag prefixes never used for sections.
- `note_types`: per-note-type field overrides, when the default (first field = prompt, next non-empty field = answer) is wrong. Example:

      "note_types": {"Korean Vocab": {"prompt": "Korean", "answer": "English", "hide": ["Audio"]}}
- `ai`: the optional Condense and Ask features. Easier to change from the **AI settings** button inside Sheets.
  - `enabled`: off by default. While off, Sheets never goes online.
  - `provider`: `anthropic`, or `openai_compatible` for any server that speaks the OpenAI chat format, including a local model (set `base_url`, e.g. `http://localhost:11434/v1`).
  - `api_key`, `model`, `base_url`: provider details. The key stays in this file on your computer.
  - `max_cards`: the most cards a single question sends.
  - `never_send_decks`: decks (and their sub-decks) whose cards are never sent to the AI.

Review ticks, column widths, spacing, emphasis and theme are set from the **View** menu inside Sheets and remembered per profile. Ticks are stored in this add-on's `user_files` folder, never in your collection.
