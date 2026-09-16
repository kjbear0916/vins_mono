#!/usr/bin/env bash
# probe_uorb.sh — definitive uORB inspection with px4-listener client
set -u
export GZ_SIM_RESOURCE_PATH="$HOME/PX4-Autopilot/Tools/simulation/gz/models"
export PX4_SIM_MODEL=gz_x500
export PX4_INSTANCE=0
LOG=/tmp/px4gz_uorb.log
BIN=/home/bear/PX4-Autopilot/build/px4_sitl_default/bin

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
echo "sleeping 60s for settle"; sleep 60

echo "=== px4 instances ==="
pgrep -af 'bin/px4' | head

for t in sensor_accel sensor_gyro sensor_imu sensor_baro sensor_mag \
         vehicle_global_position_groundtruth vehicle_local_position_groundtruth \
         sensor_gps vehicle_attitude_groundtruth; do
  echo "=== listener $t ==="
  timeout 8 "$BIN/px4-listener" "$t" -n 3 -i 1 2>&1 | head -12
  echo "rc=$?"
done

echo "=== ekf2 status ==="
timeout 8 "$BIN/px4-listener" vehicle_status -n 1 -i 1 2>&1 | head -6

kill $MAKE_PID 2>/dev/null
pkill -f 'gz sim' 2>/dev/null; pkill -f 'bin/px4' 2>/dev/null
echo cleaned