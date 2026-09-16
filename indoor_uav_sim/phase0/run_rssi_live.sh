#!/usr/bin/env bash
# run_rssi_live.sh — boot gz sim, run rssi_positioning_node against real pose topic
set -u
export GZ_SIM_RESOURCE_PATH="$HOME/PX4-Autopilot/Tools/simulation/gz/models"
export PX4_SIM_MODEL=gz_x500
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
LOG=/tmp/px4gz_rssi_live.log

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
  if pgrep -f 'bin/px4' >/dev/null 2>&1 && pgrep -f 'gz sim' >/dev/null 2>&1; then up=1; break; fi
done
echo "boot up=$up after $((i*3))s"
[ "$up" != 1 ] && { echo FAIL; tail -c 2000 "$LOG"; exit 1; }
sleep 20

echo "=== running rssi_positioning_node live (30s) ==="
python3 -u /mnt/d/Things/indoor_uav_sim/phase0/rssi_positioning_node.py --duration 30 --rate 5 2>&1

kill $MAKE_PID 2>/dev/null
pkill -f 'gz sim' 2>/dev/null; pkill -f 'bin/px4' 2>/dev/null
echo cleaned