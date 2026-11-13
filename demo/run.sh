#!/bin/bash
# Launches real Anki desktop with the add-on on a virtual display and records it.
set -u
ROOT=/home/claude/anki-sheets
PY=${PY:-/home/claude/ankienv/bin/python}
OUT=${OUT:-/tmp/sheets-demo}
BASE=$OUT/base
DRIVER=${DRIVER:-driver}
rm -rf "$OUT"; mkdir -p "$BASE/addons21"

$PY - <<E
import os, sys
sys.path.insert(0, "$ROOT/tests")
from aqt.profiles import ProfileManager
pm = ProfileManager(ProfileManager.get_created_base_folder("$BASE"))
pm.setupMeta()
pm.meta["defaultLang"] = "en_US"
pm.meta["firstRun"] = False
pm.create("User 1")
pm.load("User 1")
pm.profile["autoSync"] = False
pm.profile["syncMedia"] = False
pm.save()
from seed import seed
os.makedirs(os.path.join("'$BASE'".strip("'"), "User 1"), exist_ok=True)
seed(os.path.join("$BASE", "User 1", "collection.anki2"), extras=os.environ.get("SEED_EXTRAS") == "1", stress=os.environ.get("SEED_STRESS") == "1").close()
E
echo software > "$BASE/gldriver6"
cp -r "$ROOT/anki_sheets" "$BASE/addons21/anki_sheets"
cp -r "$ROOT/demo/$DRIVER" "$BASE/addons21/zz_demo_driver"
cp "$ROOT/tests/fake_ai.py" "$BASE/addons21/zz_demo_driver/"
find "$BASE/addons21" -name __pycache__ -prune -exec rm -rf {} \;
rm -f "$BASE/addons21/anki_sheets/user_files/summaries.json" "$BASE/addons21/anki_sheets/user_files/ticks.json"

export DISPLAY=:77
Xvfb :77 -screen 0 1280x800x24 -nolisten tcp >/dev/null 2>&1 &
XPID=$!
sleep 1
export QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox --disable-gpu"
export QT_QUICK_BACKEND=software SHEETS_DEMO_OUT="$OUT" ANKI_NOHIGHDPI=1 DISABLE_QT5_COMPAT=1
ffmpeg -loglevel error -y -f x11grab -draw_mouse 1 -framerate 25 -video_size 1280x800 -i :77 \
  -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p "$OUT/raw.mp4" &
FPID=$!
date +%s.%N > "$OUT/t0"
timeout 220 $PY -c "import aqt; aqt.run()" -b "$BASE" -p "User 1" > "$OUT/anki.log" 2>&1
echo "anki exit: $?"
sleep 1
kill -INT $FPID; wait $FPID 2>/dev/null
kill $XPID
ls -la "$OUT"
