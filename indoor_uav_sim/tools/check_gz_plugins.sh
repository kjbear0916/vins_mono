#!/bin/bash
set -u
for p in physics user-commands scene-broadcaster contact sensors; do
  echo "=== libgz-sim8-$p-system.so ==="
  ldd /usr/lib/x86_64-linux-gnu/gz-sim-8/plugins/libgz-sim8-$p-system.so 2>/dev/null | grep 'not found'
  echo "(missing: $(ldd /usr/lib/x86_64-linux-gnu/gz-sim-8/plugins/libgz-sim8-$p-system.so 2>/dev/null | grep -c 'not found'))"
done
echo "--- python dlopen each ---"
python3 - <<'PY'
import ctypes, importlib
mods = ["physics", "user-commands", "scene-broadcaster", "contact", "sensors"]
for m in mods:
    path = f"/usr/lib/x86_64-linux-gnu/gz-sim-8/plugins/libgz-sim8-{m}-system.so"
    try:
        ctypes.CDLL(path)
        print(f"OK   {m}")
    except Exception as e:
        print(f"FAIL {m}: {e}")
PY