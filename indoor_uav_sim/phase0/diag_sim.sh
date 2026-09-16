#!/usr/bin/env bash
# Diagnostic: which UDP ports does PX4 SITL listen on?
set -u
RES=/tmp/phase0_diag.log
echo "=== diag start $(date +%T) ===" > "$RES"
export GZ_SIM_RESOURCE_PATH="$HOME/PX4-Autopilot/Tools/simulation/gz/models"
export PX4_SIM_MODEL=gz_x500
LOG=/tmp/px4gz3.log
pkill -f 'gz sim' 2>/dev/null; pkill -f 'bin/px4' 2>/dev/null; sleep 2
cd "$HOME/PX4-Autopilot"
make px4_sitl gz_x500 > "$LOG" 2>&1 &
MAKE_PID=$!
up=0
for i in $(seq 1 50); do
  sleep 3
  if pgrep -f 'bin/px4' >/dev/null 2>&1 && pgrep -f 'gz sim' >/dev/null 2>&1; then up=1; break; fi
done
echo "up=$up after $((i*3))s px4_pid=$(pgrep -f 'bin/px4' | head -1)" >> "$RES"
if [ "$up" = 1 ]; then
  for w in 30 45 60; do
    sleep $(( w - 30 ))
    echo "--- at t=${w}s ---" >> "$RES"
    ss -ulpn 2>/dev/null | grep -E '14540|14550|14560' >> "$RES"
  done
  echo "--- mavlink log lines ---" >> "$RES"
  timeout 5 grep -aE 'mavlink|ready for takeoff|commander' "$LOG" | timeout 5 head -25 >> "$RES"
fi
kill $MAKE_PID 2>/dev/null; pkill -f 'gz sim' 2>/dev/null; pkill -f 'bin/px4' 2>/dev/null
echo "=== diag end $(date +%T) ===" >> "$RES"