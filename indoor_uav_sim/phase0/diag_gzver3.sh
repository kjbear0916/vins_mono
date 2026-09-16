#!/usr/bin/env bash
# Which gz server version runs when PX4 launches it?
set -u
RES=/tmp/gzver3.log
> "$RES"
export GZ_SIM_RESOURCE_PATH="$HOME/PX4-Autopilot/Tools/simulation/gz/models"
export PX4_SIM_MODEL=gz_x500
LOG=/tmp/px4gzv.log
pkill -f 'gz sim' 2>/dev/null; pkill -f 'bin/px4' 2>/dev/null; sleep 2
cd "$HOME/PX4-Autopilot"
make px4_sitl gz_x500 > "$LOG" 2>&1 &
MAKE_PID=$!
sleep 40
echo "--- full gz-related process table ---" >> "$RES"
ps -ef | grep -i gz | grep -v grep >> "$RES"
echo "--- server exe resolves ---" >> "$RES"
for p in $(pgrep -f 'gz-server|gz-sim'); do
  echo "pid=$p exe=$(readlink /proc/$p/exe 2>/dev/null)" >> "$RES"
  echo "  cmd=$(tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null)" >> "$RES"
done
echo "--- gz topics visible to PX4 simulator=bridge's view ---" >> "$RES"
timeout 8 gz topic -l 2>/dev/null | head -25 >> "$RES"
kill $MAKE_PID 2>/dev/null; pkill -f 'gz sim' 2>/dev/null; pkill -f 'bin/px4' 2>/dev/null
echo "=== end $(date +%T) ===" >> "$RES"