#!/usr/bin/env bash
# Phase 0 acceptance driver v2 — everything bounded, results to /tmp/phase0_result.log
set -u
RES=/tmp/phase0_result.log
echo "=== driver start $(date +%T) ===" >> "$RES"

export GZ_SIM_RESOURCE_PATH="$HOME/PX4-Autopilot/Tools/simulation/gz/models"
export PX4_SIM_MODEL=gz_x500
LOG=/tmp/px4gz2.log

# force Garden gz CLI (PX4 links libgz-transport13) via ~/bin/gz shim
mkdir -p "$HOME/bin"
install -m 755 /mnt/d/Things/indoor_uav_sim/phase0/bin/gz "$HOME/bin/gz"
export PATH="$HOME/bin:$PATH"

pkill -f 'gz sim' 2>/dev/null; pkill -f 'bin/px4' 2>/dev/null; sleep 2

cd "$HOME/PX4-Autopilot" || exit 1
echo "launching PX4 SITL + Gazebo" >> "$RES"
make px4_sitl gz_x500 > "$LOG" 2>&1 &
MAKE_PID=$!

# bounded boot wait: check px4 + gz sim processes alive
up=0
for i in $(seq 1 60); do
  sleep 3
  if pgrep -f 'bin/px4' >/dev/null 2>&1 && pgrep -f 'gz sim' >/dev/null 2>&1; then
    up=1
    break
  fi
done
echo "boot wait done up=$up after $((i*3))s" >> "$RES"

if [ "$up" != 1 ]; then
  echo "FAIL: px4/gz did not come up"; echo "log tail:" >> "$RES"
  timeout 3 tail -c 2000 "$LOG" >> "$RES" 2>&1
  kill $MAKE_PID 2>/dev/null
  echo "RC=1" >> "$RES"; exit 1
fi

echo "sim up, sleeping 60s more for ekf2/GPS converge" >> "$RES"
sleep 60
echo "ekf2 lines in px4 log (first 6):" >> "$RES"
timeout 3 grep -aE '\[ekf2\]' "$LOG" 2>/dev/null | grep -va pxh | head -6 >> "$RES" 2>&1

echo "gz sim sensor topic rates (imu/baro/navsat):" >> "$RES"
for t in imu_sensor/imu air_pressure_sensor/air_pressure navsat_sensor/navsat; do
  timeout 8 gz topic -i -t "/world/default/model/x500_0/link/base_link/sensor/$t" 2>&1 \
    | grep -aE 'Data rate|count|n_msgs|lcm|valid' | head -3 >> "$RES"
done

echo "gz server binary:" >> "$RES"
for p in $(pgrep -f 'gz sim'); do
  echo "  pid=$p exe=$(readlink /proc/$p/exe 2>/dev/null)" >> "$RES"
done

echo "running MAVSDK test" >> "$RES"
timeout 170 python3 -u /mnt/d/Things/indoor_uav_sim/phase0/takeoff_hover_test.py >> "$RES" 2>&1
RC=$?
echo "test exit RC=$RC" >> "$RES"

echo "cleanup" >> "$RES"
kill $MAKE_PID 2>/dev/null
pkill -f 'gz sim' 2>/dev/null
pkill -f 'bin/px4' 2>/dev/null
echo "=== driver end RC=$RC $(date +%T) ===" >> "$RES"
exit $RC