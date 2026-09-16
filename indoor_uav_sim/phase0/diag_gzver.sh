#!/usr/bin/env bash
# Check which gz-sim version the PX4 launch actually runs
set -u
RES=/tmp/phase0_gzver.log
echo "=== start $(date +%T) ===" > "$RES"
export GZ_SIM_RESOURCE_PATH="$HOME/PX4-Autopilot/Tools/simulation/gz/models"
export PX4_SIM_MODEL=gz_x500
LOG=/tmp/px4gzver.log
pkill -f 'gz sim' 2>/dev/null; pkill -f 'bin/px4' 2>/dev/null; sleep 2
cd "$HOME/PX4-Autopilot"
make px4_sitl gz_x500 > "$LOG" 2>&1 &
MAKE_PID=$!
sleep 30
echo "--- gz sim procs ---" >> "$RES"
for pid in $(pgrep -f 'gz sim'); do
  echo "pid=$pid $(readlink /proc/$pid/exe 2>/dev/null)" >> "$RES"
done
echo "--- gz CLI versions ---" >> "$RES"
timeout 5 gz sim --versions >> "$RES" 2>&1
echo "--- px4 gz_bridge msgs ---" >> "$RES"
timeout 5 grep -aE -- 'gz_bridge|ERROR|sensor|imu|baro' "$LOG" | grep -va pxh | head -20 >> "$RES"
kill $MAKE_PID 2>/dev/null; pkill -f 'gz sim' 2>/dev/null; pkill -f 'bin/px4' 2>/dev/null
echo "--- end $(date +%T) ---" >> "$RES"