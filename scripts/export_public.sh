#!/bin/bash
# Makes a clean copy of the project for publishing: current files only, no git history.
# Usage: scripts/export_public.sh /path/to/new/folder
set -euo pipefail
DEST="${1:?give a destination folder}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$DEST"
git -C "$ROOT" archive HEAD | tar -x -C "$DEST"
rm -f "$DEST/anki_sheets/user_files/"*.json "$DEST/anki_sheets/meta.json"
(cd "$DEST" && git init -q -b main && git add -A && echo "Clean copy ready in $DEST (nothing committed yet: add a LICENSE first).")
