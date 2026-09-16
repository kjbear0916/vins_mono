#!/usr/bin/env bash
# run_diag.sh — launch PX4+Gazebo, wait for boot, run bridge diagnostic, cleanup
set -u
RES=/tmp/phase0_diag_result.log
export GZ_SIM_RESOURCE_PATH="$HOME/PX4-Autopilot/Tools/simulation/gz/models"
export PX4_SIM_MODEL=gz_x500
LOG=/tmp/px4gz_diag.log

mkdir -p "$HOME/bin"
install -m 755 /mnt/d/Things/indoor_uav_sim/phase0/bin/gz "$HOME/bin/gz"
export PATH="$HOME/bin:$PATH"

pkill -f 'gz sim' 2>/dev/null; pkill -f 'bin/px4' 2>/dev/null; sleep 2

cd "$HOME/PX4-Autopilot" || exit 1
make px4_sitl gz_x500 > "$LOG" 2>&1 &
MAKE_PID=$!

up=0
for i in $(seq 1 40); do
  sleep 3
  if pgrep -f 'bin/px4' >/dev/null 2>&1 && pgrep -f 'gz sim' >/dev/null 2>&1; then
    up=1
    break
  fi
done
echo "boot wait done up=$up after $((i*3))s"
if [ "$up" != 1 ]; then
  echo "FAIL: px4/gz did not come up"
  timeout 3 tail -c 2000 "$LOG"
  pkill -f 'gz sim' 2>/dev/null; pkill -f 'bin/px4' 2>/dev/null
  exit 1
fi

echo "sim up, sleeping 90s for ekf2/GPS/sensors to settle"
sleep 90

echo "==================== RUNNING DIAGNOSTIC ===================="
python3 -u /mnt/d/Things/indoor_uav_sim/phase0/diagnose_gz_bridge.py
echo "==================== DIAGNOSTIC DONE ======================="

echo "=== cleanup ==="
kill $MAKE_PID 2>/dev/null
pkill -f 'gz sim' 2>/dev/null
pkill -f 'bin/px4' 2>/dev/null
echo "=== done ==="